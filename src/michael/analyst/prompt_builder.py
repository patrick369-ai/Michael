"""PromptBuilder — 按报告类型组装 Prompt

核心职责：
1. 按报告类型加载对应的 Skill 组合
2. 注入 Calculator 已计算的 Key Levels / FVGs
3. 注入历史引用（如 daily_bias 引用 weekly_prep 结果）
4. 控制 token 预算（精简 Skill 内容、去除"知识来源"区块）
5. 附加输出 JSON Schema
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from michael.config import Config, ReportType, StepName

logger = logging.getLogger(__name__)


# 报告类型 → Skill 组合映射
REPORT_SKILLS: dict[ReportType, list[str]] = {
    ReportType.WEEKLY_PREP: [
        "framing/context",
        "framing/narrative",
        "framing/bias",
        "profiling/weekly_profile",
        "targeting/pda_scan",
        "targeting/dol_framework",
    ],
    ReportType.DAILY_BIAS: [
        "framing/context",
        "framing/narrative",
        "framing/bias",
        "profiling/weekly_profile",
        "profiling/daily_profile",
        "targeting/pda_scan",
        "targeting/dol_framework",
    ],
    ReportType.ASIA_PRE: [
        "framing/bias",            # ref: daily
        "profiling/session_role",
        "targeting/pda_scan",
        "targeting/dol_framework",
    ],
    ReportType.LONDON_PRE: [
        "framing/bias",
        "profiling/session_role",
        "targeting/pda_scan",
        "targeting/dol_framework",
    ],
    ReportType.NYAM_PRE: [  # Stage 1
        "framing/bias",
        "profiling/daily_profile",
        "profiling/session_role",
        "targeting/pda_scan",
        "targeting/dol_framework",
    ],
    ReportType.NYAM_OPEN: [
        "profiling/session_role",
        "targeting/pda_scan",
    ],
    ReportType.NYPM_PRE: [
        "framing/bias",
        "profiling/session_role",
        "targeting/pda_scan",
        "targeting/dol_framework",
    ],
}

# NYAM_PRE Stage 2 (执行阶段) 的 Skill
STAGE2_SKILLS = [
    "planning/market_state",
    "planning/entry_model_matching",
]


class PromptBuilder:
    """Prompt 构建器"""

    def __init__(self, config: Config):
        self._config = config
        self._skills_dir = config.project_dir / "knowledge" / "skills"
        self._skill_cache: dict[str, str] = {}

    def build_merged(
        self,
        report_type: ReportType,
        steps: list[StepName],
        manifest_summary: dict,
        calculated_context: Optional[dict] = None,
        previous_results: Optional[dict] = None,
        audit_feedback: Optional[list] = None,
    ) -> str:
        """构建合并模式的 prompt

        Args:
            report_type: 报告类型
            steps: 执行的步骤列表（用于决定加载哪些 Skill）
            manifest_summary: 数据采集摘要（文件路径、bar 数量）
            calculated_context: Calculator 输出（CalculatedContext.to_prompt_dict()）
            previous_results: 前序报告结果（从 SQLite 读取）
            audit_feedback: 最近的审计教训

        Returns:
            完整的 prompt 文本
        """
        sections: list[str] = []

        # 1. System 引导
        sections.append(self._system_intro(report_type))

        # 2. Skill 内容（按依赖顺序加载）
        skill_names = REPORT_SKILLS.get(report_type, [])
        if skill_names:
            sections.append("## 分析 Skills（严格按顺序执行）\n")
            for skill_name in skill_names:
                skill_content = self._load_skill(skill_name)
                if skill_content:
                    sections.append(f"---\n### Skill: {skill_name}\n\n{skill_content}\n")

        # 3. Calculator 输出（已计算的数据）
        if calculated_context:
            sections.append("---\n## 已计算数据（代码级，请直接引用，不要重新计算）\n")
            sections.append("```json\n" + json.dumps(calculated_context, ensure_ascii=False, indent=2) + "\n```\n")

        # 4. 数据文件引用
        if manifest_summary:
            sections.append("---\n## 市场数据文件\n")
            sections.append("```json\n" + json.dumps(manifest_summary, ensure_ascii=False, indent=2) + "\n```\n")

        # 5. 前序报告引用
        if previous_results:
            sections.append("---\n## 前序分析引用\n")
            sections.append("```json\n" + json.dumps(previous_results, ensure_ascii=False, indent=2) + "\n```\n")

        # 6. 审计反馈（最近教训）
        if audit_feedback:
            sections.append("---\n## 近期审计教训（下次要改进的）\n")
            for i, lesson in enumerate(audit_feedback[:3], 1):
                sections.append(f"{i}. {lesson}\n")

        # 7. 输出指令
        sections.append(self._output_instruction(report_type, skill_names))

        return "\n".join(sections)

    def build_execution(
        self,
        report_type: ReportType,
        manifest_summary: dict,
        stage1_result: dict,
        calculated_context: Optional[dict] = None,
    ) -> str:
        """构建 Stage 2 执行阶段的 prompt（仅信号报告）"""
        sections: list[str] = []

        sections.append("# NYAM 信号报告 Stage 2：执行计划")
        sections.append("已完成 Stage 1 分析，现需给出具体 Trade Plan。\n")

        sections.append("## 分析 Skills（Stage 2）\n")
        for skill_name in STAGE2_SKILLS:
            content = self._load_skill(skill_name)
            if content:
                sections.append(f"---\n### Skill: {skill_name}\n\n{content}\n")

        sections.append("---\n## Stage 1 分析结果\n")
        sections.append("```json\n" + json.dumps(stage1_result, ensure_ascii=False, indent=2) + "\n```\n")

        if calculated_context:
            sections.append("---\n## 已计算数据\n")
            sections.append("```json\n" + json.dumps(calculated_context, ensure_ascii=False, indent=2) + "\n```\n")

        if manifest_summary:
            sections.append("---\n## 市场数据\n")
            sections.append("```json\n" + json.dumps(manifest_summary, ensure_ascii=False, indent=2) + "\n```\n")

        sections.append(self._execution_output_instruction())
        return "\n".join(sections)

    def get_merged_schema(
        self,
        report_type: ReportType,
        skill_names: Optional[list[str]] = None,
    ) -> dict:
        """获取合并模式的输出 JSON Schema"""
        if skill_names is None:
            skill_names = REPORT_SKILLS.get(report_type, [])

        properties: dict[str, dict] = {}
        required = ["gate_status"]

        for skill_path in skill_names:
            # 从路径提取 Skill 的简短 key
            key = skill_path.split("/")[-1]
            properties[key] = {"type": "object"}
            required.append(key)

        properties["gate_status"] = {
            "type": "string",
            "enum": ["PASS", "CAUTION", "FAIL", "NO_TRADE"],
        }
        properties["narrative_summary"] = {"type": "string"}

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def _load_skill(self, skill_name: str) -> str:
        """加载并精简 Skill 内容（去除"知识来源"区块）"""
        if skill_name in self._skill_cache:
            return self._skill_cache[skill_name]

        skill_path = self._skills_dir / f"{skill_name}.md"
        if not skill_path.exists():
            logger.warning(f"Skill 文件不存在: {skill_path}")
            return ""

        content = skill_path.read_text(encoding="utf-8")

        # 精简：去除"## 8. 知识来源"及之后内容（对运行时无用）
        content = re.split(r"\n##\s*8\.\s*知识来源", content)[0]

        # 去除元信息（> Layer: / > 依赖）不必要
        # 保留前几行结构信息

        self._skill_cache[skill_name] = content
        return content

    def _system_intro(self, report_type: ReportType) -> str:
        """系统引导提示"""
        return f"""# {report_type.value} 分析任务

你是专业的 ICT（Inner Circle Trader）交易分析师。请严格按照下方提供的 Skill 模块顺序执行分析，每个 Skill 对应一个分析步骤。

**核心约束：**
- 严格按 Skill 的"执行步骤"和"判断规则"操作
- 所有价格引用必须来自"已计算数据"或"市场数据文件"，禁止凭空生成价格
- 每个 Skill 的输出必须符合其"输出 Schema"
- 遇到"门控条件"为 FAIL/NO_TRADE 时，立即终止并输出原因
- 最终输出一个完整的 JSON，包含所有 Skill 的结果

**禁止：**
- 重新计算已在"已计算数据"中提供的 PDH/PDL/PWH/PWL/FVG 等
- 跳过 Skill 步骤或改变顺序
- 引用不存在的 PDA 或 Key Level（幻觉）
"""

    def _output_instruction(self, report_type: ReportType, skill_names: list[str]) -> str:
        """输出格式指令"""
        skill_keys = [s.split("/")[-1] for s in skill_names]
        fields_hint = ",\n  ".join([f'"{k}": {{ ... }}' for k in skill_keys])

        return f"""---
## 输出要求

请以以下 JSON 结构输出完整分析结果：

```json
{{
  {fields_hint},
  "gate_status": "PASS | CAUTION | FAIL | NO_TRADE",
  "narrative_summary": "一段简短叙事，综述本次分析的核心结论"
}}
```

每个顶层字段对应一个 Skill 的输出 Schema。不要添加注释，输出纯 JSON。
"""

    def _execution_output_instruction(self) -> str:
        return """---
## 输出要求（Stage 2 执行计划）

```json
{
  "market_state": { ... },
  "entry_model_matching": { ... },
  "trade_plan": {
    "entry_zone": {"high": 0, "low": 0, "pda_reference": "..."},
    "stop_loss": 0,
    "tp1": {"price": 0, "partial": "50%", "type": "IRL"},
    "tp2": {"price": 0, "partial": "50%", "type": "ERL"},
    "entry_model_chosen": "...",
    "mss_confirmed": true,
    "liquidity_swept": "..."
  },
  "gate_status": "PASS | CAUTION | FAIL | NO_TRADE",
  "narrative_summary": "..."
}
```
"""


def make_manifest_summary(manifest) -> dict:
    """将 DataManifest 转为 prompt 注入的摘要格式"""
    summary = {
        "report_type": manifest.report_type,
        "integrity": manifest.integrity.value,
        "symbols": {},
    }
    for sym, tf_data in manifest.symbols.items():
        summary["symbols"][sym] = {
            tf: {
                "bar_count": len(sd.bars),
                "file_path": sd.file_path or None,
                "first_ts": sd.bars[0].timestamp if sd.bars else None,
                "last_ts": sd.bars[-1].timestamp if sd.bars else None,
            }
            for tf, sd in tf_data.items()
        }
    return summary
