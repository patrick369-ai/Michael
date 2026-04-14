"""SQLite 持久化 — 使用 store/database.py 的 Database 类"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from michael.types import AnalysisResult, SupervisionReport
from michael.store.database import Database

logger = logging.getLogger(__name__)


def persist_analysis_result(
    result: AnalysisResult,
    supervision: SupervisionReport,
    db_path: Path,
    system_version: str = "A",
    date: Optional[str] = None,
) -> dict:
    """将 AnalysisResult 持久化到 SQLite

    Args:
        result: 分析结果
        supervision: Guardian 报告
        db_path: 数据库文件路径
        system_version: 系统版本（A/B）
        date: 分析日期 YYYY-MM-DD

    Returns:
        {"saved_steps": int, "step_ids": [int], "guardian_blocked": bool}
    """
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    db = Database(db_path)
    saved_step_ids: list[int] = []

    try:
        for step in result.steps:
            try:
                step_id = db.save_step_result(step, date=date, system_version=system_version)
                if step_id > 0:
                    saved_step_ids.append(step_id)
            except Exception as e:
                logger.warning(f"保存 step {step.step_name} 失败: {e}")
    finally:
        db.close()

    return {
        "saved_steps": len(saved_step_ids),
        "step_ids": saved_step_ids,
        "guardian_blocked": supervision.is_blocked,
    }
