"""流动性点识别 — EQH/EQL (Equal Highs/Lows)"""

from __future__ import annotations

from dataclasses import dataclass

from michael.types import BarData


@dataclass(frozen=True)
class EqualPoints:
    """相近的多个高点或低点"""
    price: float              # 平均价位
    bar_indices: list[int]    # 涉及的 bar 索引
    timestamps: list[str]
    count: int                # 点数
    tolerance: float          # 使用的容差

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "count": self.count,
            "bar_indices": self.bar_indices,
            "tolerance": self.tolerance,
        }


def find_equal_highs(
    bars: list[BarData],
    tolerance_points: float = 5.0,
    min_count: int = 2,
    swing_lookback: int = 1,
) -> list[EqualPoints]:
    """识别相近的高点集群

    Args:
        bars: K 线数据
        tolerance_points: 容差（两个高点差 ≤ tolerance 算相近）
        min_count: 至少需要几个高点才算一个集群

    Returns:
        EqualPoints 列表，按价格降序
    """
    # 提取所有局部高点（相邻 bar 之间的 swing highs）
    swing_highs = _find_swing_highs(bars, lookback=swing_lookback)

    if len(swing_highs) < min_count:
        return []

    # 聚类：将相近的 swing highs 归并
    clusters = _cluster_by_tolerance(swing_highs, tolerance_points)

    # 过滤掉 count < min_count 的 cluster
    result = []
    for cluster in clusters:
        if len(cluster) >= min_count:
            avg_price = sum(p for _, p in cluster) / len(cluster)
            indices = [idx for idx, _ in cluster]
            timestamps = [bars[idx].timestamp for idx, _ in cluster]
            result.append(EqualPoints(
                price=avg_price,
                bar_indices=indices,
                timestamps=timestamps,
                count=len(cluster),
                tolerance=tolerance_points,
            ))

    return sorted(result, key=lambda x: -x.price)


def find_equal_lows(
    bars: list[BarData],
    tolerance_points: float = 5.0,
    min_count: int = 2,
    swing_lookback: int = 1,
) -> list[EqualPoints]:
    """识别相近的低点集群"""
    swing_lows = _find_swing_lows(bars, lookback=swing_lookback)

    if len(swing_lows) < min_count:
        return []

    clusters = _cluster_by_tolerance(swing_lows, tolerance_points)

    result = []
    for cluster in clusters:
        if len(cluster) >= min_count:
            avg_price = sum(p for _, p in cluster) / len(cluster)
            indices = [idx for idx, _ in cluster]
            timestamps = [bars[idx].timestamp for idx, _ in cluster]
            result.append(EqualPoints(
                price=avg_price,
                bar_indices=indices,
                timestamps=timestamps,
                count=len(cluster),
                tolerance=tolerance_points,
            ))

    return sorted(result, key=lambda x: x.price)


def _find_swing_highs(bars: list[BarData], lookback: int = 2) -> list[tuple[int, float]]:
    """找出 swing high：high > 前 N 根和后 N 根的 high"""
    result = []
    for i in range(lookback, len(bars) - lookback):
        high = bars[i].high
        is_swing = True
        for j in range(1, lookback + 1):
            if bars[i - j].high >= high or bars[i + j].high >= high:
                is_swing = False
                break
        if is_swing:
            result.append((i, high))
    return result


def _find_swing_lows(bars: list[BarData], lookback: int = 2) -> list[tuple[int, float]]:
    """找出 swing low：low < 前 N 根和后 N 根的 low"""
    result = []
    for i in range(lookback, len(bars) - lookback):
        low = bars[i].low
        is_swing = True
        for j in range(1, lookback + 1):
            if bars[i - j].low <= low or bars[i + j].low <= low:
                is_swing = False
                break
        if is_swing:
            result.append((i, low))
    return result


def _cluster_by_tolerance(
    points: list[tuple[int, float]],
    tolerance: float,
) -> list[list[tuple[int, float]]]:
    """将相近的点聚类"""
    if not points:
        return []

    # 按价格排序
    sorted_pts = sorted(points, key=lambda x: x[1])

    clusters: list[list[tuple[int, float]]] = []
    current = [sorted_pts[0]]

    for pt in sorted_pts[1:]:
        cluster_avg = sum(p for _, p in current) / len(current)
        if abs(pt[1] - cluster_avg) <= tolerance:
            current.append(pt)
        else:
            clusters.append(current)
            current = [pt]

    clusters.append(current)
    return clusters
