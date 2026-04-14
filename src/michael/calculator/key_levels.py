"""Key Levels 计算 — PDH/PDL/PWH/PWL/NWOG/NDOG/IPDA"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from michael.types import BarData


@dataclass(frozen=True)
class PriceRange:
    """通用价格范围"""
    high: float
    low: float

    @property
    def equilibrium(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class OpeningGap:
    """NWOG / NDOG / ORG 通用结构"""
    high: float
    low: float
    ce: float  # Consequent Encroachment (50% 中点)
    timestamp: str

    @property
    def size(self) -> float:
        return abs(self.high - self.low)


def calc_pdh_pdl(daily_bars: list[BarData]) -> Optional[PriceRange]:
    """前日高低

    Args:
        daily_bars: 日线 bars，按时间升序

    Returns:
        PriceRange(high=PDH, low=PDL) 或 None（如数据不足）
    """
    if len(daily_bars) < 2:
        return None

    # 前一日 = 倒数第二根（最后一根是今日）
    prev_day = daily_bars[-2]
    return PriceRange(high=prev_day.high, low=prev_day.low)


def calc_pwh_pwl(weekly_bars: list[BarData]) -> Optional[PriceRange]:
    """前周高低

    Args:
        weekly_bars: 周线 bars，按时间升序

    Returns:
        PriceRange(high=PWH, low=PWL) 或 None
    """
    if len(weekly_bars) < 2:
        return None

    prev_week = weekly_bars[-2]
    return PriceRange(high=prev_week.high, low=prev_week.low)


def calc_equilibrium(high: float, low: float) -> float:
    """通用 Equilibrium 计算"""
    return (high + low) / 2


def calc_nwog(friday_close: float, sunday_open: float,
              friday_ts: str = "", sunday_ts: str = "") -> OpeningGap:
    """New Week Opening Gap

    Args:
        friday_close: 周五收盘价
        sunday_open: 周日开盘价
        friday_ts: 周五收盘时间戳
        sunday_ts: 周日开盘时间戳

    Returns:
        OpeningGap with high=max, low=min, ce=midpoint
    """
    high = max(friday_close, sunday_open)
    low = min(friday_close, sunday_open)
    return OpeningGap(
        high=high,
        low=low,
        ce=(high + low) / 2,
        timestamp=f"{friday_ts}→{sunday_ts}",
    )


def calc_ndog(close_5pm: float, open_6pm: float,
              close_ts: str = "", open_ts: str = "") -> OpeningGap:
    """New Day Opening Gap (5PM close vs 6PM open ET)"""
    high = max(close_5pm, open_6pm)
    low = min(close_5pm, open_6pm)
    return OpeningGap(
        high=high,
        low=low,
        ce=(high + low) / 2,
        timestamp=f"{close_ts}→{open_ts}",
    )


def calc_ipda_range(daily_bars: list[BarData], days: int) -> Optional[PriceRange]:
    """IPDA 范围计算（20/40/60 日）

    Args:
        daily_bars: 日线 bars，按时间升序（最后一根是今日或最新）
        days: 回溯天数（20/40/60）

    Returns:
        PriceRange(high=period_high, low=period_low)
    """
    if len(daily_bars) < days:
        return None

    # 取最近 days 根 bars（不含今日如果今日未收盘，或含今日如果是 EOD 数据）
    recent = daily_bars[-days:]
    high = max(bar.high for bar in recent)
    low = min(bar.low for bar in recent)
    return PriceRange(high=high, low=low)


def calc_current_position_in_range(current_price: float, range_: PriceRange) -> str:
    """判断当前价在范围内的位置

    Returns:
        "premium" (>50%) | "discount" (<50%) | "equilibrium" (接近50%，容差1%)
    """
    if range_.size == 0:
        return "equilibrium"

    position = (current_price - range_.low) / range_.size

    if position > 0.55:
        return "premium"
    if position < 0.45:
        return "discount"
    return "equilibrium"
