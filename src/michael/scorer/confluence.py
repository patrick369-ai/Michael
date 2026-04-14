"""Confluence Scorer — 共振区域识别与加权评分

核心算法：
1. 从 Calculator 和 LLM 两个来源收集候选位点
2. 按价格范围聚类（重叠或相近的位点合并为一个 Zone）
3. 对每个 Zone 计算 9 维度基础分
4. 根据来源应用加成系数（双重确认×1.5，代码矛盾×0.0）
5. 按总分排序输出 Top-N
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ─── 枚举与数据结构 ───


class SourceType(Enum):
    """位点来源"""
    CALCULATOR = "calculator"
    LLM = "llm"
    BOTH = "both"
    CONFLICT = "conflict"  # LLM 说存在但 Calculator 矛盾


class ConfluenceGrade(Enum):
    """共振等级"""
    S = "S"  # 12-24 分
    A = "A"  # 8-11 分
    B = "B"  # 5-7 分
    C = "C"  # < 5 分


# 9 个维度的权重（基础分最高 16）
DIMENSION_WEIGHTS = {
    "htf_pda":                  3,    # H4/D 级 PDA
    "mtf_pda":                  2,    # H1 级 PDA
    "ltf_pda":                  1,    # M15/M5 级 PDA
    "key_level":                2,    # PDH/PWH/NWOG/NMO
    "fibonacci_ote":            1,    # OTE 62-79%
    "liquidity_eqh_eql":        2,    # EQH/EQL 流动性池
    "smt_confirmation":         2,    # 多品种确认
    "time_window":              1,    # KZ/Macro
    "premium_discount_correct": 2,    # 做空在 Premium，做多在 Discount
}

# 来源加成
SOURCE_MULTIPLIERS = {
    SourceType.BOTH:       1.5,   # Calculator + LLM 双重确认
    SourceType.CALCULATOR: 1.0,   # 仅 Calculator（真实存在）
    SourceType.LLM:        0.8,   # 仅 LLM（可能是 OB/Breaker 代码算不了）
    SourceType.CONFLICT:   0.0,   # 代码矛盾，丢弃
}


@dataclass
class ConfluenceComponent:
    """共振构成元素"""
    dimension: str              # "htf_pda" / "key_level" / ...
    source: SourceType
    detail: str                 # 具体描述，如 "H4 SIBI 21495-21472"
    weight: float = 0.0         # 该维度的权重


@dataclass
class ConfluenceZone:
    """共振区域"""
    price_high: float
    price_low: float
    base_score: float = 0.0           # 基础分（权重累加）
    source_multiplier: float = 1.0    # 来源加成系数
    final_score: float = 0.0          # 最终得分
    grade: ConfluenceGrade = ConfluenceGrade.C
    components: list[ConfluenceComponent] = field(default_factory=list)
    alignment_with_bias: str = "neutral"  # "aligned" | "conflicting" | "neutral"
    distance_from_price: float = 0.0

    @property
    def ce(self) -> float:
        return (self.price_high + self.price_low) / 2

    @property
    def size(self) -> float:
        return self.price_high - self.price_low

    def to_dict(self) -> dict:
        return {
            "price_range": [self.price_low, self.price_high],
            "ce": self.ce,
            "base_score": self.base_score,
            "source_multiplier": self.source_multiplier,
            "final_score": self.final_score,
            "grade": self.grade.value,
            "alignment_with_bias": self.alignment_with_bias,
            "distance_from_price": self.distance_from_price,
            "components": [
                {"dimension": c.dimension, "source": c.source.value,
                 "detail": c.detail, "weight": c.weight}
                for c in self.components
            ],
        }


@dataclass
class CandidatePoint:
    """单个候选位点（来自 Calculator 或 LLM）"""
    dimension: str              # 对应 DIMENSION_WEIGHTS 的 key
    price_high: float
    price_low: float
    source: SourceType
    detail: str
    extra: dict = field(default_factory=dict)


# ─── 核心函数 ───


def merge_sources(
    calculator_points: list[CandidatePoint],
    llm_points: list[CandidatePoint],
    merge_tolerance: float = 2.0,
) -> list[CandidatePoint]:
    """合并 Calculator 和 LLM 的候选位点

    Calculator 和 LLM 都指向相近位点 → 升级为 BOTH
    仅 Calculator → 保持 CALCULATOR
    仅 LLM → 保持 LLM
    LLM 说存在但 Calculator 明确矛盾 → CONFLICT（此处简化，由调用方预判断）

    Args:
        calculator_points: Calculator 找到的候选
        llm_points: LLM 找到的候选
        merge_tolerance: 合并的价格容差（点数）

    Returns:
        合并后的候选列表
    """
    result: list[CandidatePoint] = []
    used_llm_indices: set[int] = set()

    # 先处理 Calculator 的位点，尝试匹配 LLM
    for calc_pt in calculator_points:
        matched_llm_idx = _find_matching_llm(
            calc_pt, llm_points, used_llm_indices, merge_tolerance
        )
        if matched_llm_idx is not None:
            used_llm_indices.add(matched_llm_idx)
            llm_pt = llm_points[matched_llm_idx]
            # 合并：取两者 price_range 的交集（或并集，这里用并集更宽松）
            merged = CandidatePoint(
                dimension=calc_pt.dimension,
                price_high=max(calc_pt.price_high, llm_pt.price_high),
                price_low=min(calc_pt.price_low, llm_pt.price_low),
                source=SourceType.BOTH,
                detail=f"{calc_pt.detail} + LLM: {llm_pt.detail}",
                extra={**calc_pt.extra, **llm_pt.extra},
            )
            result.append(merged)
        else:
            # 仅 Calculator
            result.append(CandidatePoint(
                dimension=calc_pt.dimension,
                price_high=calc_pt.price_high,
                price_low=calc_pt.price_low,
                source=SourceType.CALCULATOR,
                detail=calc_pt.detail,
                extra=calc_pt.extra,
            ))

    # 剩下未匹配的 LLM 位点
    for i, llm_pt in enumerate(llm_points):
        if i in used_llm_indices:
            continue
        result.append(CandidatePoint(
            dimension=llm_pt.dimension,
            price_high=llm_pt.price_high,
            price_low=llm_pt.price_low,
            source=SourceType.LLM,
            detail=llm_pt.detail,
            extra=llm_pt.extra,
        ))

    return result


def _find_matching_llm(
    calc_pt: CandidatePoint,
    llm_points: list[CandidatePoint],
    used: set[int],
    tolerance: float,
) -> Optional[int]:
    """找匹配的 LLM 位点（价格范围有重叠或相近）"""
    for i, llm_pt in enumerate(llm_points):
        if i in used:
            continue
        if llm_pt.dimension != calc_pt.dimension:
            continue
        # 判断是否重叠或相近
        if _ranges_overlap_or_close(
            calc_pt.price_high, calc_pt.price_low,
            llm_pt.price_high, llm_pt.price_low,
            tolerance,
        ):
            return i
    return None


def _ranges_overlap_or_close(
    h1: float, l1: float, h2: float, l2: float, tolerance: float
) -> bool:
    """判断两个价格范围是否重叠或相近"""
    # 重叠
    if max(l1, l2) <= min(h1, h2):
        return True
    # 相近（距离 <= tolerance）
    gap = max(l1, l2) - min(h1, h2)
    return gap <= tolerance


def score_confluence(
    merged_points: list[CandidatePoint],
    current_price: float,
    bias_direction: str = "NEUTRAL",  # "LONG" | "SHORT" | "NEUTRAL"
    equilibrium_ref: Optional[float] = None,   # 用于 Premium/Discount 判断
    cluster_tolerance: float = 5.0,
    top_n: int = 5,
) -> list[ConfluenceZone]:
    """计算共振区域并评分

    Args:
        merged_points: 已合并的候选位点列表
        current_price: 当前价
        bias_direction: Bias 方向（LONG/SHORT/NEUTRAL）
        equilibrium_ref: 判断 Premium/Discount 的参考 Equilibrium
        cluster_tolerance: 多个位点聚类的价格容差
        top_n: 输出前 N 个 Zone

    Returns:
        ConfluenceZone 列表，按 final_score 降序
    """
    if not merged_points:
        return []

    # Step 1: 按价格范围聚类
    zones = _cluster_points_to_zones(merged_points, cluster_tolerance)

    # Step 2: 对每个 Zone 计算评分
    for zone in zones:
        _calculate_zone_score(zone, current_price, bias_direction, equilibrium_ref)

    # Step 3: 排序并限制数量
    zones.sort(key=lambda z: -z.final_score)
    return zones[:top_n]


def _cluster_points_to_zones(
    points: list[CandidatePoint],
    tolerance: float,
) -> list[ConfluenceZone]:
    """将候选位点聚类为 Zone

    相近/重叠的位点合并到同一个 Zone。
    """
    if not points:
        return []

    # 按价格低点排序
    sorted_pts = sorted(points, key=lambda p: p.price_low)

    zones: list[ConfluenceZone] = []
    current_zone_points: list[CandidatePoint] = [sorted_pts[0]]

    for pt in sorted_pts[1:]:
        # 检查是否与当前 zone 的任何点相近
        zone_high = max(p.price_high for p in current_zone_points)
        zone_low = min(p.price_low for p in current_zone_points)

        if _ranges_overlap_or_close(
            zone_high, zone_low,
            pt.price_high, pt.price_low,
            tolerance,
        ):
            current_zone_points.append(pt)
        else:
            # 完成当前 zone，开始新的
            zones.append(_build_zone(current_zone_points))
            current_zone_points = [pt]

    # 别忘了最后一个
    if current_zone_points:
        zones.append(_build_zone(current_zone_points))

    return zones


def _build_zone(points: list[CandidatePoint]) -> ConfluenceZone:
    """从候选点列表构建 Zone"""
    zone = ConfluenceZone(
        price_high=max(p.price_high for p in points),
        price_low=min(p.price_low for p in points),
    )

    # 去重：同一维度来自不同点，保留所有 components 但基础分只算一次
    dims_counted: set[str] = set()

    for pt in points:
        weight = DIMENSION_WEIGHTS.get(pt.dimension, 0)
        component = ConfluenceComponent(
            dimension=pt.dimension,
            source=pt.source,
            detail=pt.detail,
            weight=weight,
        )
        zone.components.append(component)

        # 基础分：每个维度只计一次
        if pt.dimension not in dims_counted:
            zone.base_score += weight
            dims_counted.add(pt.dimension)

    return zone


def _calculate_zone_score(
    zone: ConfluenceZone,
    current_price: float,
    bias: str,
    equilibrium_ref: Optional[float],
) -> None:
    """计算 Zone 的最终得分和等级"""
    # 距离当前价
    zone.distance_from_price = min(
        abs(current_price - zone.price_high),
        abs(current_price - zone.price_low),
    )

    # Bias 对齐（影响 premium_discount_correct 维度，但此处简化为标注）
    if equilibrium_ref is not None:
        in_premium = zone.ce > equilibrium_ref
        if bias == "SHORT" and in_premium:
            zone.alignment_with_bias = "aligned"
        elif bias == "LONG" and not in_premium:
            zone.alignment_with_bias = "aligned"
        elif bias == "NEUTRAL":
            zone.alignment_with_bias = "neutral"
        else:
            zone.alignment_with_bias = "conflicting"
    else:
        zone.alignment_with_bias = "neutral"

    # 来源加成：以 Zone 内主导来源为准
    zone.source_multiplier = _dominant_source_multiplier(zone.components)

    # 最终得分
    zone.final_score = zone.base_score * zone.source_multiplier

    # 等级
    zone.grade = _score_to_grade(zone.final_score)


def _dominant_source_multiplier(components: list[ConfluenceComponent]) -> float:
    """基于 Zone 内构成元素的来源分布，确定主导加成系数

    策略：
    - 如果有 BOTH 来源 → 1.5（双重确认）
    - 如果有 CONFLICT → 0.0（丢弃）
    - 全部 CALCULATOR → 1.0
    - 全部 LLM → 0.8
    - 混合（CALCULATOR + LLM 但没升级为 BOTH） → 取平均
    """
    sources = [c.source for c in components]

    if SourceType.CONFLICT in sources:
        return 0.0
    if SourceType.BOTH in sources:
        return 1.5

    has_calc = SourceType.CALCULATOR in sources
    has_llm = SourceType.LLM in sources

    if has_calc and has_llm:
        return 0.9  # 混合但未合并
    if has_calc:
        return 1.0
    if has_llm:
        return 0.8
    return 1.0


def _score_to_grade(score: float) -> ConfluenceGrade:
    """得分映射到等级"""
    if score >= 12:
        return ConfluenceGrade.S
    if score >= 8:
        return ConfluenceGrade.A
    if score >= 5:
        return ConfluenceGrade.B
    return ConfluenceGrade.C
