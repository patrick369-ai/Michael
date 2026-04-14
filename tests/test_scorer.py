"""Confluence Scorer 测试"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.scorer import (
    ConfluenceGrade, SourceType, ConfluenceZone,
    score_confluence, merge_sources,
)
from michael.scorer.confluence import CandidatePoint


def make_point(
    dim: str, high: float, low: float,
    source: SourceType = SourceType.CALCULATOR,
    detail: str = "",
) -> CandidatePoint:
    return CandidatePoint(
        dimension=dim,
        price_high=high,
        price_low=low,
        source=source,
        detail=detail or f"{dim} @ {low}-{high}",
    )


# ─── merge_sources 测试 ───

class TestMergeSources:

    def test_disjoint_sources(self):
        """Calculator 和 LLM 的位点不重叠 → 分别保留"""
        calc = [make_point("htf_pda", 100, 95)]
        llm = [make_point("mtf_pda", 200, 195)]
        merged = merge_sources(calc, llm)
        assert len(merged) == 2
        sources = {p.source for p in merged}
        assert SourceType.CALCULATOR in sources
        assert SourceType.LLM in sources

    def test_overlapping_same_dim_merges_to_both(self):
        """相同维度，重叠价格 → 合并为 BOTH"""
        calc = [make_point("htf_pda", 100, 90)]
        llm = [make_point("htf_pda", 105, 95)]
        merged = merge_sources(calc, llm)
        assert len(merged) == 1
        assert merged[0].source == SourceType.BOTH

    def test_different_dim_not_merged(self):
        """不同维度，即使价格重叠也不合并"""
        calc = [make_point("htf_pda", 100, 90)]
        llm = [make_point("mtf_pda", 100, 90)]
        merged = merge_sources(calc, llm)
        assert len(merged) == 2

    def test_close_ranges_within_tolerance(self):
        """在 tolerance 内的相近范围 → 合并"""
        calc = [make_point("htf_pda", 100, 95)]
        llm = [make_point("htf_pda", 102, 99)]  # gap=1，tolerance=2
        merged = merge_sources(calc, llm, merge_tolerance=2.0)
        assert len(merged) == 1
        assert merged[0].source == SourceType.BOTH


# ─── score_confluence 测试 ───

class TestScoreConfluence:

    def test_single_zone_calculator_only(self):
        points = [
            make_point("htf_pda", 100, 95, SourceType.CALCULATOR),
            make_point("key_level", 98, 97, SourceType.CALCULATOR),
        ]
        zones = score_confluence(points, current_price=80)
        assert len(zones) == 1
        zone = zones[0]
        # base_score = htf_pda (3) + key_level (2) = 5
        assert zone.base_score == 5
        assert zone.source_multiplier == 1.0
        assert zone.final_score == 5.0
        assert zone.grade == ConfluenceGrade.B  # 5-7

    def test_s_grade_high_score(self):
        """高分 Zone 应得 S 级"""
        points = [
            make_point("htf_pda", 100, 95, SourceType.BOTH),       # 3
            make_point("mtf_pda", 100, 95, SourceType.BOTH),       # 2
            make_point("key_level", 99, 97, SourceType.BOTH),      # 2
            make_point("liquidity_eqh_eql", 100, 98, SourceType.BOTH),  # 2
            make_point("smt_confirmation", 100, 95, SourceType.BOTH),   # 2
            make_point("premium_discount_correct", 100, 95, SourceType.BOTH),  # 2
        ]
        zones = score_confluence(points, current_price=80)
        assert len(zones) == 1
        # base = 3+2+2+2+2+2 = 13
        # multiplier = 1.5 (BOTH)
        # final = 19.5
        assert zones[0].grade == ConfluenceGrade.S
        assert zones[0].final_score >= 12

    def test_conflict_source_drops_zone(self):
        """CONFLICT 来源应使 Zone 得分为 0"""
        points = [
            make_point("htf_pda", 100, 95, SourceType.CONFLICT),
            make_point("key_level", 100, 95, SourceType.BOTH),
        ]
        zones = score_confluence(points, current_price=80)
        assert len(zones) == 1
        assert zones[0].final_score == 0.0
        assert zones[0].grade == ConfluenceGrade.C

    def test_multiple_zones_sorted(self):
        """多个 Zone 按得分降序"""
        points = [
            # Zone 1 (弱): 只有 ltf_pda
            make_point("ltf_pda", 50, 48, SourceType.CALCULATOR),
            # Zone 2 (强): 多维度 + BOTH
            make_point("htf_pda", 100, 95, SourceType.BOTH),
            make_point("mtf_pda", 100, 95, SourceType.BOTH),
            make_point("key_level", 99, 97, SourceType.BOTH),
        ]
        zones = score_confluence(points, current_price=80, cluster_tolerance=1.0)
        assert len(zones) == 2
        # Zone 2 (strong) 排第一
        assert zones[0].final_score > zones[1].final_score

    def test_top_n_limit(self):
        """top_n 参数限制返回数量"""
        # 构造 5 个不相关的 Zone
        points = []
        for i in range(5):
            price = 100 + i * 50
            points.append(make_point("htf_pda", price + 2, price, SourceType.CALCULATOR))

        zones = score_confluence(points, current_price=0, top_n=3, cluster_tolerance=1.0)
        assert len(zones) == 3

    def test_bias_alignment_short_in_premium(self):
        """Bias SHORT 且 Zone 在 Premium 区 → aligned"""
        points = [make_point("htf_pda", 100, 95, SourceType.CALCULATOR)]
        zones = score_confluence(
            points, current_price=80, bias_direction="SHORT",
            equilibrium_ref=90,  # Zone @ 95-100 都在 90 之上 = Premium
        )
        assert zones[0].alignment_with_bias == "aligned"

    def test_bias_alignment_long_in_discount(self):
        points = [make_point("htf_pda", 80, 75, SourceType.CALCULATOR)]
        zones = score_confluence(
            points, current_price=90, bias_direction="LONG",
            equilibrium_ref=90,
        )
        assert zones[0].alignment_with_bias == "aligned"

    def test_bias_alignment_conflicting(self):
        """Bias SHORT 但 Zone 在 Discount 区 → conflicting"""
        points = [make_point("htf_pda", 80, 75, SourceType.CALCULATOR)]
        zones = score_confluence(
            points, current_price=90, bias_direction="SHORT",
            equilibrium_ref=90,
        )
        assert zones[0].alignment_with_bias == "conflicting"

    def test_distance_from_price(self):
        points = [make_point("htf_pda", 100, 95, SourceType.CALCULATOR)]
        zones = score_confluence(points, current_price=80)
        assert zones[0].distance_from_price == 15  # 95 - 80

    def test_empty_input(self):
        assert score_confluence([], current_price=100) == []


# ─── ConfluenceZone to_dict ───

class TestZoneSerialization:

    def test_to_dict_structure(self):
        points = [
            make_point("htf_pda", 100, 95, SourceType.BOTH, "H4 SIBI"),
            make_point("key_level", 100, 99, SourceType.CALCULATOR, "PDH 100"),
        ]
        zones = score_confluence(points, current_price=80, cluster_tolerance=2.0)
        d = zones[0].to_dict()

        assert "price_range" in d
        assert "ce" in d
        assert "base_score" in d
        assert "final_score" in d
        assert "grade" in d
        assert "components" in d
        assert len(d["components"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
