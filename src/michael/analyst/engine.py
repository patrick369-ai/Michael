"""分析引擎 — Playbook 驱动的约束工作流

核心设计思想：
1. Playbook 是约束，不是参考。分析必须严格按照 SOP 步骤执行。
2. 自适应调用策略：简单报告合并为 1 次调用，信号报告分 2 阶段。
3. 每次调用的 prompt 都包含明确的步骤序列和输出 Schema。
4. 门控是代码级检查，不是模型自判。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from michael.config import Config, ReportType, REPORT_STEP_MAP, StepName
from michael.types import (
    AnalysisResult, DataManifest, GateStatus, StepResult,
)
from michael.analyst.claude_cli import ClaudeCLI
from michael.analyst.prompt_builder import PromptBuilder, make_manifest_summary
from michael.calculator import process_manifest, CalculatedContext

logger = logging.getLogger(__name__)


# 信号报告（需要两阶段调用）
SIGNAL_REPORTS = {ReportType.NYAM_PRE, ReportType.NYAM_OPEN}

# 审计报告（不调用 Claude）
AUDIT_REPORTS = {ReportType.DAILY_REVIEW, ReportType.WEEKLY_REVIEW}


class AnalystEngine:
    """Playbook 驱动的分析引擎

    工作流约束：
    - 每种报告类型有固定的步骤序列（REPORT_STEP_MAP）
    - 步骤不可跳过、不可重排
    - 门控状态为 FAIL/NO_TRADE 时立即终止
    - 输出必须符合预定义的 JSON Schema

    数据流：
        DataManifest → Calculator → CalculatedContext
                                   ↓
        PromptBuilder（注入 Calc 输出 + Skills + 历史引用）
                                   ↓
        ClaudeCLI（调用 + JSON 提取 + Schema 验证）
                                   ↓
        AnalysisResult（每个 Skill 的输出 + 总门控）
    """

    def __init__(
        self,
        config: Config,
        claude_cli: Optional[ClaudeCLI] = None,
        prompt_builder: Optional[PromptBuilder] = None,
    ):
        self._config = config
        self._claude = claude_cli or ClaudeCLI(config)
        self._prompt = prompt_builder or PromptBuilder(config)

    def run(
        self,
        report_type: ReportType,
        manifest: DataManifest,
        previous_results: Optional[dict] = None,
        audit_feedback: Optional[list] = None,
    ) -> AnalysisResult:
        """执行分析工作流

        Args:
            report_type: 报告类型
            manifest: 数据采集结果
            previous_results: 前序报告结果（如 weekly 结果用于 daily）
            audit_feedback: 最近的审计教训

        Returns:
            AnalysisResult 包含 Calculator 输出、所有步骤结果、最终门控状态
        """
        # Audit 报告独立处理（不调用 Claude）
        if report_type in AUDIT_REPORTS:
            return AnalysisResult(
                report_type=report_type.value,
                final_gate=GateStatus.PASS,
            )

        # Step 1: Calculator 预处理
        logger.info(f"[Calculator] 处理 manifest")
        calc_ctx = process_manifest(
            manifest,
            primary_symbol=self._config.primary_symbol,
        )
        logger.info(f"[Calculator] 完成: PDH={calc_ctx.pdh}, PDL={calc_ctx.pdl}, "
                    f"FVGs={sum(len(v) for v in calc_ctx.fvgs_by_tf.values())}")

        # Step 2: Skill 步骤
        steps = REPORT_STEP_MAP.get(report_type, [])
        result = AnalysisResult(report_type=report_type.value)

        if report_type in SIGNAL_REPORTS:
            self._run_two_stage(
                report_type, steps, manifest, calc_ctx,
                previous_results, audit_feedback, result,
            )
        elif steps:
            self._run_merged(
                report_type, steps, manifest, calc_ctx,
                previous_results, audit_feedback, result,
            )
        else:
            logger.warning(f"报告类型 {report_type.value} 无定义步骤")
            result.final_gate = GateStatus.FAIL

        return result

    def _run_merged(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest: DataManifest,
        calc_ctx: CalculatedContext,
        previous_results: Optional[dict],
        audit_feedback: Optional[list],
        result: AnalysisResult,
    ) -> None:
        """合并模式 — 所有步骤在一次 Claude 调用中完成"""
        logger.info(f"[合并模式] {report_type.value}: {len(steps)} 步")

        prompt = self._prompt.build_merged(
            report_type=report_type,
            steps=steps,
            manifest_summary=make_manifest_summary(manifest),
            calculated_context=calc_ctx.to_prompt_dict(),
            previous_results=previous_results,
            audit_feedback=audit_feedback,
        )
        schema = self._prompt.get_merged_schema(report_type)

        start = _now_ts()
        raw_text, output = self._claude.call(
            prompt=prompt,
            schema=schema,
            timeout=self._config.claude_timeout,
            max_turns=self._config.claude_max_turns,
        )
        duration = _now_ts() - start

        gate = _parse_gate(output.get("gate_status", "PASS"))

        # 为每个 Skill 创建 StepResult
        from michael.analyst.prompt_builder import REPORT_SKILLS
        skill_keys = [s.split("/")[-1] for s in REPORT_SKILLS.get(report_type, [])]

        for skill_key in skill_keys:
            step_output = output.get(skill_key, {})
            step_result = StepResult(
                step_name=skill_key,
                report_type=report_type.value,
                gate_status=gate,
                output=step_output,
                raw_text=raw_text,
                duration_seconds=duration / max(len(skill_keys), 1),
                token_count=len(prompt) // 4,
            )
            result.steps.append(step_result)

        result.final_gate = gate
        logger.info(f"[合并模式] 完成: gate={gate.value}, 耗时={duration:.1f}s")

    def _run_two_stage(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest: DataManifest,
        calc_ctx: CalculatedContext,
        previous_results: Optional[dict],
        audit_feedback: Optional[list],
        result: AnalysisResult,
    ) -> None:
        """两阶段模式 — 信号报告

        Stage 1: 方向分析（合并 framing + profiling + targeting）
        Stage 2: 执行计划（market_state + entry_model_matching + trade_plan）
        Stage 1 门控失败 → 不进入 Stage 2
        """
        # Stage 1
        logger.info(f"[两阶段] Stage 1: {report_type.value}")

        s1_prompt = self._prompt.build_merged(
            report_type=report_type,
            steps=steps,
            manifest_summary=make_manifest_summary(manifest),
            calculated_context=calc_ctx.to_prompt_dict(),
            previous_results=previous_results,
            audit_feedback=audit_feedback,
        )
        s1_schema = self._prompt.get_merged_schema(report_type)

        start = _now_ts()
        s1_raw, s1_output = self._claude.call(
            prompt=s1_prompt,
            schema=s1_schema,
            timeout=self._config.claude_timeout,
            max_turns=self._config.claude_max_turns,
        )
        s1_duration = _now_ts() - start

        s1_gate = _parse_gate(s1_output.get("gate_status", "PASS"))

        # 为 Stage 1 的 Skill 创建结果
        from michael.analyst.prompt_builder import REPORT_SKILLS, STAGE2_SKILLS
        s1_skill_keys = [s.split("/")[-1] for s in REPORT_SKILLS.get(report_type, [])]
        for skill_key in s1_skill_keys:
            result.steps.append(StepResult(
                step_name=skill_key,
                report_type=report_type.value,
                gate_status=s1_gate,
                output=s1_output.get(skill_key, {}),
                raw_text=s1_raw,
                duration_seconds=s1_duration / max(len(s1_skill_keys), 1),
            ))

        # 门控检查：Stage 1 失败则停止
        if s1_gate in (GateStatus.FAIL, GateStatus.NO_TRADE):
            result.final_gate = s1_gate
            logger.info(f"[两阶段] Stage 1 门控: {s1_gate.value}，跳过 Stage 2")
            return

        # Stage 2
        logger.info(f"[两阶段] Stage 2: 执行计划")

        s2_prompt = self._prompt.build_execution(
            report_type=report_type,
            manifest_summary=make_manifest_summary(manifest),
            stage1_result=s1_output,
            calculated_context=calc_ctx.to_prompt_dict(),
        )
        # Stage 2 的 Schema 不同，构造一个简化的
        s2_schema = {
            "type": "object",
            "required": ["trade_plan", "gate_status"],
            "properties": {
                "market_state": {"type": "object"},
                "entry_model_matching": {"type": "object"},
                "trade_plan": {"type": "object"},
                "gate_status": {"type": "string"},
            },
        }

        start = _now_ts()
        s2_raw, s2_output = self._claude.call(
            prompt=s2_prompt,
            schema=s2_schema,
            timeout=self._config.claude_timeout,
            max_turns=self._config.claude_max_turns,
        )
        s2_duration = _now_ts() - start

        s2_gate = _parse_gate(s2_output.get("gate_status", "PASS"))

        s2_skill_keys = [s.split("/")[-1] for s in STAGE2_SKILLS] + ["trade_plan"]
        for skill_key in s2_skill_keys:
            result.steps.append(StepResult(
                step_name=skill_key,
                report_type=report_type.value,
                gate_status=s2_gate,
                output=s2_output.get(skill_key, {}),
                raw_text=s2_raw,
                duration_seconds=s2_duration / max(len(s2_skill_keys), 1),
            ))

        result.final_gate = s2_gate
        logger.info(f"[两阶段] 完成: gate={s2_gate.value}, 总耗时={s1_duration + s2_duration:.1f}s")


def _parse_gate(value: str) -> GateStatus:
    """解析门控状态字符串"""
    value = value.upper().strip()
    try:
        return GateStatus(value)
    except ValueError:
        logger.warning(f"未知门控状态: {value}，默认 PASS")
        return GateStatus.PASS


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()
