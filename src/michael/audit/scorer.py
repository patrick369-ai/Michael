"""Scorer — 4 维评分系统

维度：
- direction (0-3): 方向准确性
- key_levels (0-3): 关键位准确性（精确/接近/部分阈值）
- narrative (0-2): 叙事质量
- actionability (0-2): 可操作性
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from michael.types import ScoreBreakdown

logger = logging.getLogger(__name__)


# NQ 点数阈值（精确/接近/部分）
KEY_LEVEL_THRESHOLDS = {
    "precise": 10,   # < 10 点 = 精确
    "close": 25,     # < 25 点 = 接近
    "partial": 50,   # < 50 点 = 部分
}


@dataclass
class ActualOutcome:
    """当日实际行情结果"""
    date: str
    high: float
    low: float
    open_price: float
    close_price: float
    direction: str              # "UP" | "DOWN" | "FLAT"（基于 close vs open）
    key_level_touches: dict = field(default_factory=dict)  # 哪些 key level 被触及


class Scorer:
    """4 维评分"""

    def score(
        self,
        prediction: dict,
        actual: ActualOutcome,
    ) -> ScoreBreakdown:
        """对一个预测打分"""
        return ScoreBreakdown(
            direction=self._score_direction(prediction, actual),
            key_levels=self._score_key_levels(prediction, actual),
            narrative=self._score_narrative(prediction, actual),
            actionability=self._score_actionability(prediction, actual),
        )

    def _score_direction(self, pred: dict, actual: ActualOutcome) -> int:
        """方向评分 0-3

        - 3: 方向完全正确 + 有明确置信度
        - 2: 方向正确
        - 1: 方向中性（NEUTRAL）且实际也是 FLAT
        - 0: 方向错误
        """
        pred_dir = self._extract_direction(pred)
        actual_dir = actual.direction

        if not pred_dir:
            return 0

        pred_dir = pred_dir.upper()

        # 映射
        mapping = {"LONG": "UP", "SHORT": "DOWN", "NEUTRAL": "FLAT"}
        expected = mapping.get(pred_dir)

        if expected == actual_dir:
            if pred_dir == "NEUTRAL":
                return 1
            # 检查置信度
            confidence = self._extract_confidence(pred)
            if confidence and confidence.upper() in ("HIGH", "MEDIUM"):
                return 3
            return 2

        # 错误方向 = 0（原版的"方向错归零"规则）
        return 0

    def _score_key_levels(self, pred: dict, actual: ActualOutcome) -> int:
        """关键位评分 0-3"""
        predicted_levels = self._extract_predicted_levels(pred)
        if not predicted_levels:
            return 0

        # 对每个预测位，看实际行情是否触及
        touch_scores = []
        for level in predicted_levels:
            distance = min(
                abs(level - actual.high),
                abs(level - actual.low),
            )
            if distance < KEY_LEVEL_THRESHOLDS["precise"]:
                touch_scores.append(3)
            elif distance < KEY_LEVEL_THRESHOLDS["close"]:
                touch_scores.append(2)
            elif distance < KEY_LEVEL_THRESHOLDS["partial"]:
                touch_scores.append(1)
            else:
                touch_scores.append(0)

        if not touch_scores:
            return 0
        # 取平均（取整）
        avg = sum(touch_scores) / len(touch_scores)
        return min(3, int(round(avg)))

    def _score_narrative(self, pred: dict, actual: ActualOutcome) -> int:
        """叙事质量评分 0-2（简化版：看是否有足够的叙事内容）"""
        narrative_len = 0
        for key in ("narrative_summary", "story", "reasoning"):
            val = pred.get(key)
            if isinstance(val, str):
                narrative_len = max(narrative_len, len(val))

        # 递归查找嵌套的叙事
        if narrative_len == 0:
            narrative_len = self._find_deepest_narrative(pred)

        if narrative_len > 100:
            return 2
        if narrative_len > 30:
            return 1
        return 0

    def _score_actionability(self, pred: dict, actual: ActualOutcome) -> int:
        """可操作性评分 0-2

        - 2: 有完整 Trade Plan（Entry/SL/TP）
        - 1: 有 Bias + DOL 但无完整 Plan
        - 0: 无具体位点
        """
        if self._dig(pred, ["trade_plan", "entry"]) is not None:
            return 2
        if self._dig(pred, ["dol_framework", "primary_dol"]) is not None:
            return 1
        if self._dig(pred, ["bias", "direction"]) and self._dig(pred, ["bias", "direction"]) != "NEUTRAL":
            return 1
        return 0

    # ─── 辅助 ───

    @staticmethod
    def _extract_direction(pred: dict) -> Optional[str]:
        for path in [["bias", "direction"], ["direction"], ["framing", "bias", "direction"]]:
            v = Scorer._dig(pred, path)
            if isinstance(v, str):
                return v
        return None

    @staticmethod
    def _extract_confidence(pred: dict) -> Optional[str]:
        for path in [["bias", "confidence"], ["confidence"]]:
            v = Scorer._dig(pred, path)
            if isinstance(v, str):
                return v
        return None

    @staticmethod
    def _extract_predicted_levels(pred: dict) -> list[float]:
        """提取所有预测的关键价位"""
        levels = []

        # 常见位置
        targets = [
            ["dol_framework", "primary_dol", "price"],
            ["trade_plan", "tp1", "price"],
            ["trade_plan", "tp2", "price"],
            ["trade_plan", "entry"],
            ["trade_plan", "stop_loss"],
        ]

        for path in targets:
            v = Scorer._dig(pred, path)
            if isinstance(v, (int, float)):
                levels.append(float(v))

        return levels

    @staticmethod
    def _find_deepest_narrative(node) -> int:
        """递归找最长的叙事文本"""
        if isinstance(node, str):
            return len(node) if len(node) > 20 else 0
        if isinstance(node, dict):
            return max([Scorer._find_deepest_narrative(v) for v in node.values()] + [0])
        if isinstance(node, list):
            return max([Scorer._find_deepest_narrative(v) for v in node] + [0])
        return 0

    @staticmethod
    def _dig(node, path):
        cur = node
        for key in path:
            if cur is None:
                return None
            if isinstance(cur, dict):
                cur = cur.get(key)
            else:
                return None
        return cur
