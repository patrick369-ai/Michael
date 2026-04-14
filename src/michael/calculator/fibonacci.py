"""Fibonacci 计算 — OTE 区域、标准 Fib 水平"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FibLevels:
    """标准 Fibonacci 回撤水平"""
    level_0: float      # 起点
    level_236: float
    level_382: float
    level_50: float
    level_618: float
    level_705: float    # OTE 中点
    level_786: float
    level_79: float     # OTE 下沿
    level_886: float
    level_1: float      # 终点
    level_neg_1: float  # -1 扩展
    level_neg_15: float
    level_neg_2: float
    level_neg_25: float

    def to_dict(self) -> dict:
        return {
            "0": self.level_0,
            "0.236": self.level_236,
            "0.382": self.level_382,
            "0.5": self.level_50,
            "0.618": self.level_618,
            "0.705": self.level_705,
            "0.786": self.level_786,
            "0.79": self.level_79,
            "0.886": self.level_886,
            "1": self.level_1,
            "-1": self.level_neg_1,
            "-1.5": self.level_neg_15,
            "-2": self.level_neg_2,
            "-2.5": self.level_neg_25,
        }


@dataclass(frozen=True)
class OTEZone:
    """Optimal Trade Entry Zone (62-79%)"""
    zone_high: float    # 62% 水平
    zone_low: float     # 79% 水平
    sweet_spot: float   # 70.5% 水平

    @property
    def ce(self) -> float:
        return (self.zone_high + self.zone_low) / 2

    @property
    def size(self) -> float:
        return abs(self.zone_high - self.zone_low)


def calc_fib_levels(swing_high: float, swing_low: float,
                     direction: str = "bullish") -> FibLevels:
    """计算标准 Fib 水平

    Args:
        swing_high: 摆动高点
        swing_low: 摆动低点
        direction: "bullish"（从 low 回撤到 high）或 "bearish"（从 high 回撤到 low）

    Returns:
        FibLevels with all standard retracement levels
    """
    range_ = swing_high - swing_low

    if direction == "bullish":
        # 从下往上看，low 是 0，high 是 1
        base = swing_low
        sign = 1
    else:
        # 从上往下看，high 是 0，low 是 1
        base = swing_high
        sign = -1

    return FibLevels(
        level_0=base,
        level_236=base + sign * range_ * 0.236,
        level_382=base + sign * range_ * 0.382,
        level_50=base + sign * range_ * 0.50,
        level_618=base + sign * range_ * 0.618,
        level_705=base + sign * range_ * 0.705,
        level_786=base + sign * range_ * 0.786,
        level_79=base + sign * range_ * 0.79,
        level_886=base + sign * range_ * 0.886,
        level_1=base + sign * range_ * 1.0,
        level_neg_1=base + sign * range_ * -1.0,
        level_neg_15=base + sign * range_ * -1.5,
        level_neg_2=base + sign * range_ * -2.0,
        level_neg_25=base + sign * range_ * -2.5,
    )


def calc_ote_zone(swing_high: float, swing_low: float,
                   direction: str = "bullish") -> OTEZone:
    """计算 OTE 区域（62-79% 回撤）

    Args:
        swing_high: 摆动高点
        swing_low: 摆动低点
        direction: "bullish"（做多 OTE）或 "bearish"（做空 OTE）

    Returns:
        OTEZone with 62% / 70.5% / 79% levels
    """
    fib = calc_fib_levels(swing_high, swing_low, direction)
    return OTEZone(
        zone_high=fib.level_618,
        zone_low=fib.level_79,
        sweet_spot=fib.level_705,
    )
