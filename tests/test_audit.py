"""Audit 层测试"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.types import ScoreBreakdown, AuditResult, FeedbackPayload
from michael.audit import Scorer, ActualOutcome, FeedbackGenerator, FeedbackStore


class TestScorer:

    def test_direction_correct_with_confidence(self):
        scorer = Scorer()
        pred = {"bias": {"direction": "SHORT", "confidence": "HIGH"}}
        actual = ActualOutcome(
            date="2026-04-14", high=21500, low=21380,
            open_price=21490, close_price=21400, direction="DOWN",
        )
        score = scorer.score(pred, actual)
        assert score.direction == 3

    def test_direction_wrong_zeros(self):
        scorer = Scorer()
        pred = {"bias": {"direction": "LONG", "confidence": "HIGH"}}
        actual = ActualOutcome(
            date="2026-04-14", high=21500, low=21380,
            open_price=21490, close_price=21400, direction="DOWN",
        )
        score = scorer.score(pred, actual)
        assert score.direction == 0

    def test_direction_neutral_on_flat(self):
        scorer = Scorer()
        pred = {"bias": {"direction": "NEUTRAL"}}
        actual = ActualOutcome(
            date="2026-04-14", high=21500, low=21490,
            open_price=21495, close_price=21495, direction="FLAT",
        )
        score = scorer.score(pred, actual)
        assert score.direction == 1

    def test_key_level_precise(self):
        scorer = Scorer()
        pred = {"dol_framework": {"primary_dol": {"price": 21380}}}
        actual = ActualOutcome(
            date="2026-04-14", high=21500, low=21381,  # 仅差 1 点
            open_price=21490, close_price=21385, direction="DOWN",
        )
        score = scorer.score(pred, actual)
        assert score.key_levels == 3

    def test_key_level_close(self):
        scorer = Scorer()
        pred = {"dol_framework": {"primary_dol": {"price": 21380}}}
        actual = ActualOutcome(
            date="2026-04-14", high=21500, low=21360,  # 差 20 点
            open_price=21490, close_price=21385, direction="DOWN",
        )
        score = scorer.score(pred, actual)
        assert score.key_levels == 2

    def test_narrative_long_gets_2(self):
        scorer = Scorer()
        # > 100 字符触发 2 分
        long_text = "Narrative: " + ("a" * 150)
        pred = {"narrative_summary": long_text}
        actual = ActualOutcome(
            date="2026-04-14", high=0, low=0, open_price=0, close_price=0, direction="FLAT",
        )
        score = scorer.score(pred, actual)
        assert score.narrative == 2

    def test_actionability_full_plan(self):
        scorer = Scorer()
        pred = {"trade_plan": {"entry": 21500}}
        actual = ActualOutcome(date="2026-04-14", high=0, low=0, open_price=0, close_price=0, direction="FLAT")
        score = scorer.score(pred, actual)
        assert score.actionability == 2

    def test_actionability_bias_only(self):
        scorer = Scorer()
        pred = {"bias": {"direction": "LONG"}}
        actual = ActualOutcome(date="2026-04-14", high=0, low=0, open_price=0, close_price=0, direction="FLAT")
        score = scorer.score(pred, actual)
        assert score.actionability == 1


class TestFeedbackGenerator:

    def test_low_direction_generates_caution(self):
        gen = FeedbackGenerator()
        audit = AuditResult(
            report_type="daily_review",
            date="2026-04-14",
            score=ScoreBreakdown(direction=0, key_levels=2, narrative=1, actionability=1),
            lessons=["方向判断错误"],
            systematic_weaknesses=["方向判断不稳定"],
        )
        payload = gen.generate(audit)
        assert len(payload.bias_cautions) > 0
        assert len(payload.session_adjustments) > 0
        assert "CISD" in " ".join(payload.knowledge_emphasis)

    def test_good_score_minimal_feedback(self):
        gen = FeedbackGenerator()
        audit = AuditResult(
            report_type="daily_review",
            date="2026-04-14",
            score=ScoreBreakdown(direction=3, key_levels=3, narrative=2, actionability=2),
            lessons=[],
            systematic_weaknesses=[],
        )
        payload = gen.generate(audit)
        assert len(payload.bias_cautions) == 0


class TestFeedbackStore:

    def test_save_and_retrieve(self, tmp_path):
        db_path = tmp_path / "test.db"
        store = FeedbackStore(db_path)

        audit = AuditResult(
            report_type="daily_review", date="2026-04-14",
            score=ScoreBreakdown(direction=0, key_levels=2, narrative=1, actionability=1),
        )
        payload = FeedbackPayload(
            bias_cautions=["方向判断准确率低"],
            session_adjustments=["加强 CISD 确认"],
        )
        ok_id = store.save(audit, payload)
        assert ok_id > 0

        # 获取最近反馈
        recent = store.get_recent(limit=5)
        assert len(recent) >= 1
        assert any("方向判断准确率低" in r for r in recent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
