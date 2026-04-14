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
from pathlib import Path

from michael.config import Config, ReportType, REPORT_STEP_MAP, StepName
from michael.types import (
    AnalysisResult, DataManifest, GateStatus, StepResult,
)

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
    """

    def __init__(self, config: Config, claude_cli: ClaudeCLI, prompt_builder: PromptBuilder):
        self._config = config
        self._claude = claude_cli
        self._prompt = prompt_builder

    def run(
        self,
        report_type: ReportType,
        manifest: DataManifest,
        previous_results: dict[str, dict] | None = None,
    ) -> AnalysisResult:
        """执行分析工作流

        Args:
            report_type: 报告类型
            manifest: 数据采集结果
            previous_results: 前序报告结果（如 weekly 结果用于 daily）

        Returns:
            AnalysisResult 包含所有步骤结果和最终门控状态
        """
        if report_type in AUDIT_REPORTS:
            return AnalysisResult(
                report_type=report_type.value,
                final_gate=GateStatus.PASS,
            )

        steps = REPORT_STEP_MAP.get(report_type, [])
        if not steps:
            logger.warning(f"报告类型 {report_type.value} 无定义步骤")
            return AnalysisResult(
                report_type=report_type.value,
                final_gate=GateStatus.FAIL,
            )

        result = AnalysisResult(report_type=report_type.value)

        if report_type in SIGNAL_REPORTS:
            self._run_two_stage(report_type, steps, manifest, previous_results, result)
        else:
            self._run_merged(report_type, steps, manifest, previous_results, result)

        return result

    def _run_merged(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest: DataManifest,
        previous_results: dict[str, dict] | None,
        result: AnalysisResult,
    ) -> None:
        """合并模式 — 所有步骤在一次 Claude 调用中完成

        prompt 仍然有步骤结构（Step 1, Step 2, ...），
        但只产生一次调用。输出 JSON 包含各步骤的字段。
        """
        logger.info(f"[合并模式] {report_type.value}: {len(steps)} 步")

        prompt = self._prompt.build_merged(
            report_type=report_type,
            steps=steps,
            manifest=manifest,
            previous_results=previous_results,
        )
        schema = self._prompt.get_merged_schema(report_type, steps)

        start = _now_ts()
        raw_text, output = self._claude.call(
            prompt=prompt,
            schema=schema,
            timeout=self._config.claude_timeout,
            max_turns=self._config.claude_max_turns,
        )
        duration = _now_ts() - start

        # 解析门控状态
        gate = _parse_gate(output.get("gate_status", "PASS"))

        # 为每个步骤创建 StepResult（从合并输出中提取）
        for step in steps:
            step_key = step.value
            step_output = output.get(step_key, {})
            step_result = StepResult(
                step_name=step_key,
                report_type=report_type.value,
                gate_status=gate,
                output=step_output,
                raw_text=raw_text,
                duration_seconds=duration / len(steps),
                token_count=len(prompt) // 4,  # 粗估
            )
            result.steps.append(step_result)

        result.final_gate = gate
        logger.info(f"[合并模式] 完成: gate={gate.value}, 耗时={duration:.1f}s")

    def _run_two_stage(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest: DataManifest,
        previous_results: dict[str, dict] | None,
        result: AnalysisResult,
    ) -> None:
        """两阶段模式 — 先分析判断方向，再精确执行

        Stage 1: 方向分析（合并 weekly context + daily bias + session）
        Stage 2: 执行信号（LTF execution + signal output）

        Stage 1 门控失败 → 不进入 Stage 2（代码级检查）
        """
        # 分离步骤
        analysis_steps = [s for s in steps if s not in (StepName.LTF_EXECUTION, StepName.SIGNAL_OUTPUT)]
        execution_steps = [s for s in steps if s in (StepName.LTF_EXECUTION, StepName.SIGNAL_OUTPUT)]

        # Stage 1: 分析阶段
        logger.info(f"[两阶段] Stage 1: {report_type.value}, {len(analysis_steps)} 步")

        s1_prompt = self._prompt.build_merged(
            report_type=report_type,
            steps=analysis_steps,
            manifest=manifest,
            previous_results=previous_results,
        )
        s1_schema = self._prompt.get_merged_schema(report_type, analysis_steps)

        start = _now_ts()
        s1_raw, s1_output = self._claude.call(
            prompt=s1_prompt,
            schema=s1_schema,
            timeout=self._config.claude_timeout,
            max_turns=self._config.claude_max_turns,
        )
        s1_duration = _now_ts() - start

        s1_gate = _parse_gate(s1_output.get("gate_status", "PASS"))

        for step in analysis_steps:
            result.steps.append(StepResult(
                step_name=step.value,
                report_type=report_type.value,
                gate_status=s1_gate,
                output=s1_output.get(step.value, {}),
                raw_text=s1_raw,
                duration_seconds=s1_duration / len(analysis_steps),
            ))

        # 代码级门控检查
        if s1_gate in (GateStatus.FAIL, GateStatus.NO_TRADE):
            result.final_gate = s1_gate
            logger.info(f"[两阶段] Stage 1 门控: {s1_gate.value}，跳过 Stage 2")
            return

        # Stage 2: 执行阶段
        if not execution_steps:
            result.final_gate = s1_gate
            return

        logger.info(f"[两阶段] Stage 2: {len(execution_steps)} 步")

        s2_prompt = self._prompt.build_execution(
            report_type=report_type,
            steps=execution_steps,
            manifest=manifest,
            stage1_result=s1_output,
        )
        s2_schema = self._prompt.get_merged_schema(report_type, execution_steps)

        start = _now_ts()
        s2_raw, s2_output = self._claude.call(
            prompt=s2_prompt,
            schema=s2_schema,
            timeout=self._config.claude_timeout,
            max_turns=self._config.claude_max_turns,
        )
        s2_duration = _now_ts() - start

        s2_gate = _parse_gate(s2_output.get("gate_status", "PASS"))

        for step in execution_steps:
            result.steps.append(StepResult(
                step_name=step.value,
                report_type=report_type.value,
                gate_status=s2_gate,
                output=s2_output.get(step.value, {}),
                raw_text=s2_raw,
                duration_seconds=s2_duration / len(execution_steps),
            ))

        result.final_gate = s2_gate
        logger.info(f"[两阶段] 完成: gate={s2_gate.value}, 总耗时={s1_duration + s2_duration:.1f}s")


class ClaudeCLI:
    """Claude CLI 包装器 — 占位，待实现"""

    def __init__(self, config: Config):
        self._config = config

    def call(
        self,
        prompt: str,
        schema: dict | None = None,
        timeout: int = 600,
        max_turns: int = 5,
    ) -> tuple[str, dict]:
        """调用 Claude CLI，返回 (raw_text, parsed_json)

        TODO: 实现 subprocess 调用 + JSON 提取 + Schema 验证 + 失败重试
        """
        raise NotImplementedError("ClaudeCLI.call 待实现")


class PromptBuilder:
    """Prompt 构建器 — 占位，待实现

    核心职责：
    1. 根据报告类型和步骤，从 Playbook/SOP 加载约束指令
    2. 从 KnowledgeBrain 按类别过滤知识上下文
    3. 组装数据引用、历史结果、反馈教训
    4. 控制 token 预算
    5. 附加输出 JSON Schema
    """

    def __init__(self, config: Config):
        self._config = config

    def build_merged(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest: DataManifest,
        previous_results: dict[str, dict] | None = None,
    ) -> str:
        """构建合并模式的 prompt"""
        raise NotImplementedError("PromptBuilder.build_merged 待实现")

    def build_execution(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest: DataManifest,
        stage1_result: dict,
    ) -> str:
        """构建执行阶段的 prompt（Stage 2）"""
        raise NotImplementedError("PromptBuilder.build_execution 待实现")

    def get_merged_schema(
        self,
        report_type: ReportType,
        steps: list[StepName],
    ) -> dict:
        """获取合并模式的输出 JSON Schema"""
        raise NotImplementedError("PromptBuilder.get_merged_schema 待实现")


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
