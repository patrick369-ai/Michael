"""本地 Markdown 报告归档"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from michael.config import Config
from michael.types import AnalysisResult, SupervisionReport

logger = logging.getLogger(__name__)


class LocalMarkdownPublisher:
    """生成本地 Markdown 报告"""

    def __init__(self, config: Config):
        self._config = config
        self._reports_dir = config.project_dir / "reports"

    def publish(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
    ) -> bool:
        """生成 Markdown 文件"""
        date = metadata.get("date") or datetime.now().strftime("%Y-%m-%d")
        report_dir = self._reports_dir / date
        report_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{result.report_type}_{datetime.now().strftime('%H%M%S')}.md"
        file_path = report_dir / filename

        content = self._render_markdown(result, supervision, metadata)

        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Markdown 报告写入: {file_path}")
            return True
        except OSError as e:
            logger.error(f"Markdown 报告写入失败: {e}")
            return False

    def _render_markdown(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
    ) -> str:
        """渲染 Markdown 内容"""
        lines = []
        lines.append(f"# {result.report_type.upper()} 报告")
        lines.append(f"\n**日期：** {metadata.get('date', 'N/A')}")
        lines.append(f"**生成时间：** {datetime.now().isoformat()}")
        lines.append(f"**Gate 状态：** `{result.final_gate.value}`")
        lines.append(f"**Guardian：** `{supervision.overall.value}`")
        if supervision.is_blocked:
            lines.append("\n> 🚫 此报告被 Guardian 阻断，未推送到飞书。")

        # 各 Skill 输出
        lines.append("\n---\n")
        lines.append("## 分析步骤\n")

        for step in result.steps:
            lines.append(f"### {step.step_name}\n")
            lines.append(f"- **门控：** {step.gate_status.value}")
            lines.append(f"- **耗时：** {step.duration_seconds:.2f}s")
            if step.output:
                lines.append("\n```json")
                lines.append(json.dumps(step.output, ensure_ascii=False, indent=2))
                lines.append("```\n")
            else:
                lines.append("\n（无输出）\n")

        # Guardian 详情
        if supervision.checks:
            lines.append("\n---\n")
            lines.append("## Guardian 检查详情\n")
            for check in supervision.checks:
                emoji = "🟢" if check.severity.value == "PASS" else (
                    "🟡" if check.severity.value == "WARN" else "🔴"
                )
                lines.append(f"- {emoji} **[{check.category}]** `{check.check_name}` — {check.message}")

        return "\n".join(lines)
