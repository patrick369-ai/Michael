"""Guardian 模块测试"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.types import Severity
from michael.guardian import (
    Supervisor, HallucinationDetector, ConsistencyChecker, RuleEngine,
)
from michael.guardian.hallucination import HallucinationConfig


# ─── HallucinationDetector 测试 ───

class TestHallucination:

    def test_pdh_match(self):
        det = HallucinationDetector()
        llm = {"context": {"key_levels": {"PDH": 21520}}}
        calc = {"pdh": 21520, "pdl": 21380}
        results = det.check(llm, calc)
        # 不应触发警告
        pdh_warnings = [r for r in results if "key_level_PDH" in r.check_name]
        assert len(pdh_warnings) == 0

    def test_pdh_mismatch_warns(self):
        det = HallucinationDetector()
        llm = {"context": {"PDH": 21530}}  # 差 10 点
        calc = {"pdh": 21520}
        results = det.check(llm, calc)
        warnings = [r for r in results if "key_level_PDH" in r.check_name]
        assert len(warnings) == 1
        assert warnings[0].severity in (Severity.WARN, Severity.FAIL)

    def test_pdh_huge_diff_fails(self):
        det = HallucinationDetector()
        llm = {"PDH": 21620}  # 差 100 点
        calc = {"pdh": 21520}
        results = det.check(llm, calc)
        warnings = [r for r in results if "key_level_PDH" in r.check_name]
        assert len(warnings) == 1
        assert warnings[0].severity == Severity.FAIL

    def test_unknown_pda_name_warns(self):
        det = HallucinationDetector()
        llm = {"pda_scan": {"pda_zones": [{"type": "FantasyBlock"}]}}
        results = det.check(llm, {})
        unknown = [r for r in results if "pda_name_unknown" in r.check_name]
        assert len(unknown) == 1

    def test_known_pda_name_passes(self):
        det = HallucinationDetector()
        llm = {"pda_scan": {"pda_zones": [{"type": "FVG"}, {"type": "OB"}]}}
        results = det.check(llm, {})
        unknown = [r for r in results if "pda_name_unknown" in r.check_name]
        assert len(unknown) == 0

    def test_unknown_entry_model_warns(self):
        det = HallucinationDetector()
        llm = {"trade_plan": {"entry_model": "MysteryModel"}}
        results = det.check(llm, {})
        unknown = [r for r in results if "entry_model_unknown" in r.check_name]
        assert len(unknown) == 1

    def test_known_entry_model_passes(self):
        det = HallucinationDetector()
        llm = {"trade_plan": {"entry_model": "Silver Bullet"}}
        results = det.check(llm, {})
        unknown = [r for r in results if "entry_model_unknown" in r.check_name]
        assert len(unknown) == 0

    def test_sl_distance_exceeds_warns(self):
        det = HallucinationDetector()
        llm = {"trade_plan": {"entry": 21500, "stop_loss": 21560}}  # 60 点 > 30
        results = det.check(llm, {"current_price": 21500})
        sl_warnings = [r for r in results if "sl_distance" in r.check_name]
        assert len(sl_warnings) == 1
        assert sl_warnings[0].severity == Severity.FAIL

    def test_sl_within_limit(self):
        det = HallucinationDetector()
        llm = {"trade_plan": {"entry": 21500, "stop_loss": 21520}}  # 20 点 OK
        results = det.check(llm, {"current_price": 21500})
        sl_warnings = [r for r in results if "sl_distance" in r.check_name]
        assert len(sl_warnings) == 0

    def test_entry_too_far_warns(self):
        det = HallucinationDetector()
        # current=21500, max distance 5% = 1075 点
        # entry=21000 距离 500 点（< 5%）应通过
        # entry=20000 距离 1500 点（> 5%）触发
        llm = {"trade_plan": {"entry": 20000, "stop_loss": 20020}}
        results = det.check(llm, {"current_price": 21500})
        far_warnings = [r for r in results if "entry_far" in r.check_name or "trade_plan_entry_far" in r.check_name]
        assert len(far_warnings) == 1


# ─── ConsistencyChecker 测试 ───

class TestConsistency:

    def test_bias_dol_aligned_long(self):
        chk = ConsistencyChecker()
        llm = {
            "current_price": 100,
            "bias": {"direction": "LONG"},
            "dol_framework": {"primary_dol": {"price": 110}},
        }
        results = chk.check(llm)
        conflicts = [r for r in results if "bias_dol" in r.check_name]
        assert len(conflicts) == 0

    def test_bias_dol_conflict_long(self):
        chk = ConsistencyChecker()
        llm = {
            "current_price": 100,
            "bias": {"direction": "LONG"},
            "dol_framework": {"primary_dol": {"price": 90}},  # DOL 在下方但 Bias 看多
        }
        results = chk.check(llm)
        conflicts = [r for r in results if "bias_dol" in r.check_name]
        assert len(conflicts) == 1
        assert conflicts[0].severity == Severity.FAIL

    def test_bias_signal_aligned(self):
        chk = ConsistencyChecker()
        llm = {
            "bias": {"direction": "SHORT"},
            "trade_plan": {"direction": "SHORT"},
        }
        results = chk.check(llm)
        conflicts = [r for r in results if "bias_signal" in r.check_name]
        assert len(conflicts) == 0

    def test_bias_signal_conflict(self):
        chk = ConsistencyChecker()
        llm = {
            "bias": {"direction": "SHORT"},
            "trade_plan": {"direction": "LONG"},
        }
        results = chk.check(llm)
        conflicts = [r for r in results if "bias_signal" in r.check_name]
        assert len(conflicts) == 1

    def test_session_daily_conflict_warns(self):
        chk = ConsistencyChecker()
        llm = {"session_role": {"bias_alignment": "conflicting"}}
        results = chk.check(llm)
        conflicts = [r for r in results if "session_daily" in r.check_name]
        assert len(conflicts) == 1

    def test_cross_report_bias_reversal_no_reason(self):
        chk = ConsistencyChecker()
        llm = {"bias": {"direction": "LONG", "reversal_from_previous": False}}
        previous = {"bias_direction": "SHORT"}
        results = chk.check(llm, previous_results=previous)
        warnings = [r for r in results if "cross_report" in r.check_name]
        assert len(warnings) == 1

    def test_cross_report_bias_reversal_with_reason_passes(self):
        chk = ConsistencyChecker()
        llm = {"bias": {
            "direction": "LONG",
            "reversal_from_previous": True,
            "reversal_reason": "CISD confirmed bullish on D",
        }}
        previous = {"bias_direction": "SHORT"}
        results = chk.check(llm, previous_results=previous)
        warnings = [r for r in results if "cross_report" in r.check_name]
        assert len(warnings) == 0


# ─── RuleEngine 测试 ───

class TestRuleEngine:

    def test_default_rules_loaded(self):
        engine = RuleEngine()
        assert len(engine.rules) > 0
        rule_ids = [r.id for r in engine.rules]
        assert "RF-001" in rule_ids  # FOMC
        assert "HR-RR-MIN" in rule_ids  # R:R 最小值

    def test_fomc_rule_triggers(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={},
            external_context={"calendar_events": ["FOMC Meeting"]},
        )
        rf_001 = [r for r in results if "RF-001" in r.check_name]
        assert len(rf_001) == 1

    def test_3_pda_fail_triggers_fail(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={},
            external_context={"pda_consecutive_failures": 3},
        )
        rf_004 = [r for r in results if "RF-004" in r.check_name]
        assert len(rf_004) == 1
        assert rf_004[0].severity == Severity.FAIL

    def test_extreme_volatility_triggers(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={"market_state": {"volatility": "extreme"}},
        )
        rf_vol = [r for r in results if "RF-VOL-EXTREME" in r.check_name]
        assert len(rf_vol) == 1

    def test_seek_destroy_triggers(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={"weekly_profile": {"matched_profile": "Seek & Destroy"}},
        )
        rf_sd = [r for r in results if "RF-SEEK-DESTROY" in r.check_name]
        assert len(rf_sd) == 1

    def test_rr_below_2_fails(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={"trade_plan": {"risk_reward": 1.5}},
        )
        hr_rr = [r for r in results if "HR-RR-MIN" in r.check_name]
        assert len(hr_rr) == 1
        assert hr_rr[0].severity == Severity.FAIL

    def test_rr_above_2_passes(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={"trade_plan": {"risk_reward": 3.0}},
        )
        hr_rr = [r for r in results if "HR-RR-MIN" in r.check_name]
        assert len(hr_rr) == 0

    def test_aplus_below_7_fails(self):
        engine = RuleEngine()
        results = engine.evaluate(
            llm_output={"trade_plan": {"aplus_score": 5}},
        )
        hr_a = [r for r in results if "HR-APLUS-MIN" in r.check_name]
        assert len(hr_a) == 1


# ─── Supervisor 集成测试 ───

class TestSupervisorIntegration:

    def test_clean_input_passes(self):
        sup = Supervisor()
        llm = {
            "current_price": 21500,
            "bias": {"direction": "SHORT"},
            "dol_framework": {"primary_dol": {"price": 21320}},
            "trade_plan": {
                "direction": "SHORT",
                "entry_model": "Silver Bullet",
                "entry": 21500, "stop_loss": 21520,
                "risk_reward": 3.0, "aplus_score": 8,
            },
        }
        calc = {
            "pdh": 21520, "pdl": 21380, "current_price": 21500,
        }
        report = sup.supervise(llm, calc)
        assert report.overall == Severity.PASS or report.overall == Severity.WARN
        assert not report.is_blocked

    def test_multiple_failures_block(self):
        sup = Supervisor()
        llm = {
            "current_price": 21500,
            "bias": {"direction": "LONG"},
            "dol_framework": {"primary_dol": {"price": 21000}},  # 冲突
            "trade_plan": {
                "entry_model": "MadeUpModel",  # 未知
                "entry": 21500, "stop_loss": 21600,  # SL 100 点
                "risk_reward": 1.0,  # < 2
            },
        }
        calc = {"current_price": 21500}
        report = sup.supervise(llm, calc)
        assert report.is_blocked
        assert len(report.failures) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
