"""FeedbackGenerator + FeedbackStore — 反馈闭环

将审计结果转化为可注入下次 Prompt 的教训。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from michael.types import AuditResult, FeedbackPayload
from michael.store.database import Database

logger = logging.getLogger(__name__)


class FeedbackGenerator:
    """将 AuditResult 转为 FeedbackPayload"""

    def generate(self, audit: AuditResult, historical_accuracy: Optional[float] = None) -> FeedbackPayload:
        payload = FeedbackPayload()

        # Bias 警告
        if audit.score.direction <= 1:
            payload.bias_cautions.append(
                f"最近 Bias 准确率低（direction={audit.score.direction}/3），"
                f"本次需额外验证：HTF 订单流、DXY 确认、SMT 背离。"
            )

        # Session 调整
        for lesson in audit.lessons:
            if "方向判断错误" in lesson:
                payload.session_adjustments.append(
                    f"前次教训：{lesson}。本次分析需要更谨慎评估方向反转信号。"
                )

        # 知识强化
        for weakness in audit.systematic_weaknesses:
            if "方向" in weakness:
                payload.knowledge_emphasis.append("加强 CISD 和 DXY/SMT 确认")
            if "关键位" in weakness:
                payload.knowledge_emphasis.append("更严格使用 Calculator 输出的 PDH/PDL 数据")
            if "叙事" in weakness:
                payload.knowledge_emphasis.append("完整叙述 Context → Narrative → Bias 推导链")

        # 位点提醒
        payload.level_reminders.append("所有 PDA 位置必须与 Calculator 扫描一致")

        # 近期准确率
        payload.recent_accuracy = historical_accuracy or (audit.score.total / 10.0)

        return payload


class FeedbackStore:
    """反馈存储 — 持久化 + 读取最近教训"""

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def save(self, audit: AuditResult, payload: FeedbackPayload) -> int:
        """保存 Feedback"""
        db = Database(self._db_path)
        try:
            feedback_json = json.dumps(asdict(payload), ensure_ascii=False)
            return db.save_feedback(
                date=audit.date,
                report_type=audit.report_type,
                feedback_json=feedback_json,
            )
        finally:
            db.close()

    def get_recent(self, limit: int = 3) -> list[str]:
        """获取最近 N 条教训作为文本列表（用于注入 Prompt）"""
        db = Database(self._db_path)
        try:
            rows = db.get_recent_feedback(limit=limit)
        finally:
            db.close()

        lessons: list[str] = []
        for row in rows:
            try:
                payload = json.loads(row["feedback_json"])
                for field in ("bias_cautions", "session_adjustments", "knowledge_emphasis"):
                    for item in payload.get(field, []):
                        if isinstance(item, str) and item:
                            lessons.append(f"[{row['date']}] {item}")
            except (json.JSONDecodeError, KeyError):
                continue

        return lessons[:limit]
