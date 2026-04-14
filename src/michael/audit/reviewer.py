"""Reviewer — 从 SQLite 读取预测 + 获取实际行情 + 打分"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from michael.types import AuditResult, ScoreBreakdown
from michael.audit.scorer import Scorer, ActualOutcome
from michael.store.database import Database

logger = logging.getLogger(__name__)


class Reviewer:
    """审计复盘器

    工作流：
    1. 从 SQLite 读取指定日期的预测记录
    2. 获取当日实际 OHLC（从 MarketStore 或 MCP）
    3. Scorer 对每条预测打分
    4. 汇总成 AuditResult
    5. 存回 daily_review 表
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._scorer = Scorer()

    def review_daily(
        self,
        date: str,
        actual: ActualOutcome,
        system_version: str = "A",
    ) -> AuditResult:
        """复盘指定日期的所有预测

        Args:
            date: YYYY-MM-DD
            actual: 当日实际行情
            system_version: A/B 版本

        Returns:
            AuditResult
        """
        db = Database(self._db_path)

        # 收集当日所有预测
        predictions: list[dict] = []
        try:
            daily = db.get_latest_daily(system_version=system_version)
            if daily and daily.get("date") == date:
                predictions.append(("daily_bias", daily))

            # 扩展：从 session_analysis 表读取（需要新的查询方法）
            # 简化：暂时只评 daily_bias
        finally:
            db.close()

        if not predictions:
            logger.warning(f"未找到 {date} 的预测")
            return AuditResult(report_type="daily_review", date=date)

        # 综合评分（取多个预测的平均）
        all_scores: list[ScoreBreakdown] = []
        lessons: list[str] = []

        for report_type, record in predictions:
            pred_dict = self._record_to_pred_dict(record)
            score = self._scorer.score(pred_dict, actual)
            all_scores.append(score)

            # 记录教训
            if score.direction == 0:
                lessons.append(f"[{report_type}] 方向判断错误: 预测={pred_dict.get('direction')}, 实际={actual.direction}")

        # 平均分
        avg_score = ScoreBreakdown(
            direction=round(sum(s.direction for s in all_scores) / len(all_scores)),
            key_levels=round(sum(s.key_levels for s in all_scores) / len(all_scores)),
            narrative=round(sum(s.narrative for s in all_scores) / len(all_scores)),
            actionability=round(sum(s.actionability for s in all_scores) / len(all_scores)),
        )

        # 识别系统性弱点
        weaknesses = self._identify_weaknesses(avg_score, actual)

        audit = AuditResult(
            report_type="daily_review",
            date=date,
            score=avg_score,
            lessons=lessons,
            systematic_weaknesses=weaknesses,
        )

        # 保存到 DB
        self._save_audit(audit, system_version)
        return audit

    def _record_to_pred_dict(self, record: dict) -> dict:
        """将 DB 记录转为预测字典"""
        return {
            "bias": {"direction": record.get("direction"), "confidence": "MEDIUM"},
            "dol_framework": {
                "primary_dol": {"price": self._extract_first_level(record.get("key_levels"))},
            },
            "narrative_summary": record.get("raw_output", "")[:300],
        }

    @staticmethod
    def _extract_first_level(key_levels_json: Optional[str]) -> Optional[float]:
        if not key_levels_json:
            return None
        try:
            levels = json.loads(key_levels_json)
            if isinstance(levels, list) and levels:
                first = levels[0]
                if isinstance(first, (int, float)):
                    return float(first)
                if isinstance(first, dict):
                    return first.get("price")
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    @staticmethod
    def _identify_weaknesses(score: ScoreBreakdown, actual: ActualOutcome) -> list[str]:
        """识别需要改进的系统性弱点"""
        weaknesses = []
        if score.direction <= 1:
            weaknesses.append("方向判断不稳定")
        if score.key_levels <= 1:
            weaknesses.append("关键位识别精度不足")
        if score.narrative <= 0:
            weaknesses.append("缺乏完整叙事")
        if score.actionability <= 0:
            weaknesses.append("无可操作的 Trade Plan")
        return weaknesses

    def _save_audit(self, audit: AuditResult, system_version: str) -> None:
        """保存到 daily_review 表"""
        db = Database(self._db_path)
        try:
            db.save_audit(audit, system_version=system_version)
        finally:
            db.close()
