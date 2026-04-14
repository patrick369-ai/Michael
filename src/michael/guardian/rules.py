"""规则引擎 — 9 红旗 + 硬性规则的代码级检查"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from michael.types import CheckResult, Severity

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    """单条规则"""
    id: str                              # e.g. "RF-001"
    category: str                        # red_flag | hard_rule | sd
    description: str                     # 人类可读
    severity: Severity = Severity.WARN
    check_fn: Optional[Callable] = None  # 检查函数 (llm_output, calc, context) -> bool


@dataclass
class RuleResult:
    """规则检查结果"""
    rule_id: str
    triggered: bool
    message: str = ""


class RuleEngine:
    """规则引擎 — 注册和执行规则"""

    def __init__(self, rules: Optional[list[Rule]] = None):
        self._rules: list[Rule] = rules or _default_rules()

    def evaluate(
        self,
        llm_output: dict,
        calc_context: Optional[dict] = None,
        external_context: Optional[dict] = None,
    ) -> list[CheckResult]:
        """评估所有规则"""
        results: list[CheckResult] = []
        ctx = external_context or {}

        for rule in self._rules:
            if rule.check_fn is None:
                continue
            try:
                triggered = rule.check_fn(llm_output, calc_context or {}, ctx)
                if triggered:
                    results.append(CheckResult(
                        check_name=rule.id,
                        category=rule.category,
                        severity=rule.severity,
                        message=f"[{rule.id}] {rule.description}",
                        details={"rule_id": rule.id},
                    ))
            except Exception as e:
                logger.warning(f"规则 {rule.id} 执行异常: {e}")

        return results

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)


# ─── 默认规则集合 ───


def _default_rules() -> list[Rule]:
    """默认规则：9 红旗 + Seek & Destroy 条件 + 硬性规则"""
    return [
        # ─── 红旗（Red Flags） ───
        Rule(
            id="RF-001",
            category="red_flag",
            description="FOMC 当日（高波动）",
            severity=Severity.WARN,
            check_fn=_rf_fomc_day,
        ),
        Rule(
            id="RF-002",
            category="red_flag",
            description="NFP 当日（经济数据主导）",
            severity=Severity.WARN,
            check_fn=_rf_nfp_day,
        ),
        Rule(
            id="RF-003",
            category="red_flag",
            description="Inside Day 持续 3 天以上（无方向性）",
            severity=Severity.WARN,
            check_fn=_rf_inside_days,
        ),
        Rule(
            id="RF-004",
            category="red_flag",
            description="3 PDA 连续失败（前序判断系统性失效）",
            severity=Severity.FAIL,
            check_fn=_rf_3_pda_fail,
        ),
        Rule(
            id="RF-005",
            category="red_flag",
            description="DXY 与指数同向 3 天以上（相关性断裂）",
            severity=Severity.WARN,
            check_fn=_rf_dxy_correlation_break,
        ),
        Rule(
            id="RF-VOL-EXTREME",
            category="red_flag",
            description="极端波动（market_state.volatility=extreme）",
            severity=Severity.WARN,
            check_fn=_rf_extreme_volatility,
        ),
        Rule(
            id="RF-SEEK-DESTROY",
            category="red_flag",
            description="Seek & Destroy 周",
            severity=Severity.WARN,
            check_fn=_rf_seek_destroy,
        ),
        Rule(
            id="RF-NO-DOL",
            category="red_flag",
            description="无可识别的 DOL（价格在空白区）",
            severity=Severity.FAIL,
            check_fn=_rf_no_dol,
        ),
        Rule(
            id="RF-HRLR",
            category="red_flag",
            description="High-Resistance Liquidity Run（London 已大幅扩张 DOL 方向）",
            severity=Severity.WARN,
            check_fn=_rf_hrlr,
        ),

        # ─── 硬性规则 ───
        Rule(
            id="HR-RR-MIN",
            category="hard_rule",
            description="R:R 必须 ≥ 2",
            severity=Severity.FAIL,
            check_fn=_hr_rr_minimum,
        ),
        Rule(
            id="HR-APLUS-MIN",
            category="hard_rule",
            description="A+ 评分必须 ≥ 7（如有信号）",
            severity=Severity.FAIL,
            check_fn=_hr_aplus_minimum,
        ),
    ]


# ─── 规则检查函数 ───
# 约定：返回 True = 规则触发（应被记录为问题）


def _rf_fomc_day(llm: dict, calc: dict, ctx: dict) -> bool:
    events = ctx.get("calendar_events", [])
    return any("fomc" in str(e).lower() for e in events)


def _rf_nfp_day(llm: dict, calc: dict, ctx: dict) -> bool:
    events = ctx.get("calendar_events", [])
    return any("nfp" in str(e).lower() or "non-farm" in str(e).lower() for e in events)


def _rf_inside_days(llm: dict, calc: dict, ctx: dict) -> bool:
    return ctx.get("consecutive_inside_days", 0) >= 3


def _rf_3_pda_fail(llm: dict, calc: dict, ctx: dict) -> bool:
    fail_count = ctx.get("pda_consecutive_failures", 0)
    return fail_count >= 3


def _rf_dxy_correlation_break(llm: dict, calc: dict, ctx: dict) -> bool:
    return ctx.get("dxy_correlation_broken_days", 0) >= 3


def _rf_extreme_volatility(llm: dict, calc: dict, ctx: dict) -> bool:
    vol = _dig(llm, ["market_state", "volatility"])
    return vol == "extreme"


def _rf_seek_destroy(llm: dict, calc: dict, ctx: dict) -> bool:
    profile = _dig(llm, ["weekly_profile", "matched_profile"])
    if isinstance(profile, str) and "seek" in profile.lower():
        return True
    profile2 = _dig(llm, ["weekly_profile", "matched_profile"])
    return isinstance(profile2, str) and "destroy" in profile2.lower()


def _rf_no_dol(llm: dict, calc: dict, ctx: dict) -> bool:
    dol = _dig(llm, ["dol_framework", "primary_dol"])
    if dol is None:
        return False  # 没有 DOL 字段不算触发（可能是 audit 报告）
    if isinstance(dol, dict):
        return not dol.get("price")
    return False


def _rf_hrlr(llm: dict, calc: dict, ctx: dict) -> bool:
    daily_profile = _dig(llm, ["daily_profile", "matched_profile"])
    return isinstance(daily_profile, str) and "low probability" in daily_profile.lower()


def _hr_rr_minimum(llm: dict, calc: dict, ctx: dict) -> bool:
    """如有 Trade Plan，R:R 必须 >= 2"""
    rr = _dig(llm, ["trade_plan", "risk_reward"])
    if isinstance(rr, (int, float)) and rr < 2.0:
        return True
    return False


def _hr_aplus_minimum(llm: dict, calc: dict, ctx: dict) -> bool:
    """如有 A+ 评分，必须 >= 7"""
    aplus = _dig(llm, ["trade_plan", "aplus_score"])
    if aplus is None:
        aplus = _dig(llm, ["aplus_score"])
    if isinstance(aplus, (int, float)) and aplus < 7:
        return True
    return False


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
