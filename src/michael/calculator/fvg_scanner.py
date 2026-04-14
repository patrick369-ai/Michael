"""FVG (Fair Value Gap) 扫描器 — 3-bar 模式识别

FVG 定义（来自 ICT 5 ENTRY MODELS + All ICT PD Arrays）：
- Bearish FVG (SIBI): bar[i].low > bar[i+2].high —— 第 1 根低点高于第 3 根高点
- Bullish FVG (BISI): bar[i].high < bar[i+2].low —— 第 1 根高点低于第 3 根低点

关键规则：
- FVG 只取位移后形成的（中间 bar 有明显力度）
- 过滤已被完全填充的 FVG（可选，保留 filled 标记供 LLM 判断）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from michael.types import BarData


class FVGType(Enum):
    BISI = "BISI"  # Buyside Imbalance Sellside Inefficiency (Bullish FVG)
    SIBI = "SIBI"  # Sellside Imbalance Buyside Inefficiency (Bearish FVG)


@dataclass(frozen=True)
class FVG:
    """Fair Value Gap"""
    type: FVGType
    price_high: float
    price_low: float
    timeframe: str            # "W" / "D" / "H4" / "H1" / "M15" / "M5" / "M1"
    bar_index: int            # 中间 bar 的索引（在原 bars 列表中）
    timestamp: str            # 中间 bar 的时间戳
    filled: bool = False      # 是否被完全填充
    filled_at_index: Optional[int] = None

    @property
    def ce(self) -> float:
        """Consequent Encroachment (50% 中点)"""
        return (self.price_high + self.price_low) / 2

    @property
    def size(self) -> float:
        return self.price_high - self.price_low

    def is_bullish(self) -> bool:
        return self.type == FVGType.BISI

    def is_bearish(self) -> bool:
        return self.type == FVGType.SIBI

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "price_high": self.price_high,
            "price_low": self.price_low,
            "timeframe": self.timeframe,
            "bar_index": self.bar_index,
            "timestamp": self.timestamp,
            "filled": self.filled,
            "ce": self.ce,
            "size": self.size,
        }


def scan_fvgs(
    bars: list[BarData],
    timeframe: str,
    check_fill: bool = True,
    min_size_points: float = 0.0,
) -> list[FVG]:
    """扫描 bars 中的所有 FVG

    Args:
        bars: K 线数据，按时间升序
        timeframe: 时间框架标识（用于输出）
        check_fill: 是否检查后续 bars 填充情况
        min_size_points: 最小 FVG 尺寸过滤（默认 0，全保留）

    Returns:
        FVG 列表，按 bar_index 升序
    """
    fvgs: list[FVG] = []

    if len(bars) < 3:
        return fvgs

    # 扫描 3-bar 模式
    for i in range(len(bars) - 2):
        bar1 = bars[i]
        bar2 = bars[i + 1]  # 中间 bar（位移 bar）
        bar3 = bars[i + 2]

        # Bearish FVG (SIBI): bar1.low > bar3.high
        if bar1.low > bar3.high:
            size = bar1.low - bar3.high
            if size >= min_size_points:
                fvg = FVG(
                    type=FVGType.SIBI,
                    price_high=bar1.low,    # FVG 上沿
                    price_low=bar3.high,    # FVG 下沿
                    timeframe=timeframe,
                    bar_index=i + 1,         # 中间 bar
                    timestamp=bar2.timestamp,
                    filled=False,
                )
                fvgs.append(fvg)

        # Bullish FVG (BISI): bar1.high < bar3.low
        elif bar1.high < bar3.low:
            size = bar3.low - bar1.high
            if size >= min_size_points:
                fvg = FVG(
                    type=FVGType.BISI,
                    price_high=bar3.low,    # FVG 上沿
                    price_low=bar1.high,    # FVG 下沿
                    timeframe=timeframe,
                    bar_index=i + 1,
                    timestamp=bar2.timestamp,
                    filled=False,
                )
                fvgs.append(fvg)

    # 检查填充情况
    if check_fill:
        fvgs = _mark_filled(fvgs, bars)

    return fvgs


def _mark_filled(fvgs: list[FVG], bars: list[BarData]) -> list[FVG]:
    """标记已被后续 bars 完全填充的 FVG"""
    result = []
    for fvg in fvgs:
        filled = False
        filled_idx = None

        # 从 FVG 形成后的下一根 bar 开始检查
        for j in range(fvg.bar_index + 2, len(bars)):
            bar = bars[j]
            if fvg.is_bearish():
                # Bearish FVG 被填充 = 价格回到 FVG 上沿之上
                if bar.high >= fvg.price_high:
                    filled = True
                    filled_idx = j
                    break
            else:
                # Bullish FVG 被填充 = 价格回到 FVG 下沿之下
                if bar.low <= fvg.price_low:
                    filled = True
                    filled_idx = j
                    break

        # 使用 dataclasses.replace 创建新实例
        result.append(FVG(
            type=fvg.type,
            price_high=fvg.price_high,
            price_low=fvg.price_low,
            timeframe=fvg.timeframe,
            bar_index=fvg.bar_index,
            timestamp=fvg.timestamp,
            filled=filled,
            filled_at_index=filled_idx,
        ))

    return result


def filter_unfilled(fvgs: list[FVG]) -> list[FVG]:
    """只保留未填充的 FVG"""
    return [f for f in fvgs if not f.filled]


def filter_by_price_range(
    fvgs: list[FVG],
    current_price: float,
    max_distance_pct: float = 5.0,
) -> list[FVG]:
    """过滤距离当前价过远的 FVG（默认 5% 内）"""
    max_distance = current_price * (max_distance_pct / 100)
    result = []
    for fvg in fvgs:
        distance = min(
            abs(current_price - fvg.price_high),
            abs(current_price - fvg.price_low),
        )
        if distance <= max_distance:
            result.append(fvg)
    return result
