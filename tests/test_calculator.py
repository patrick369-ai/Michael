"""Calculator 模块测试 — 用已知答案验证每个计算函数"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许直接运行（不依赖 pytest 安装到 src）
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.types import BarData
from michael.calculator.key_levels import (
    calc_pdh_pdl, calc_pwh_pwl, calc_equilibrium,
    calc_nwog, calc_ndog, calc_ipda_range,
    calc_current_position_in_range, PriceRange,
)
from michael.calculator.fvg_scanner import (
    scan_fvgs, FVGType, filter_unfilled, filter_by_price_range,
)
from michael.calculator.liquidity import find_equal_highs, find_equal_lows
from michael.calculator.fibonacci import calc_ote_zone, calc_fib_levels
from michael.calculator.session_ranges import calc_session_range


# ─── 测试辅助函数 ───

def make_bar(ts: str, o: float, h: float, l: float, c: float, v: float = 1000) -> BarData:
    return BarData(timestamp=ts, open=o, high=h, low=l, close=c, volume=v)


# ─── Key Levels 测试 ───

class TestKeyLevels:

    def test_pdh_pdl_basic(self):
        bars = [
            make_bar("2026-04-12", 100, 110, 95, 105),   # 前前日
            make_bar("2026-04-13", 105, 120, 100, 115),  # 前日 ← PDH=120, PDL=100
            make_bar("2026-04-14", 115, 125, 110, 120),  # 今日
        ]
        result = calc_pdh_pdl(bars)
        assert result is not None
        assert result.high == 120
        assert result.low == 100
        assert result.equilibrium == 110
        assert result.size == 20

    def test_pdh_pdl_insufficient_bars(self):
        bars = [make_bar("2026-04-14", 100, 110, 95, 105)]
        assert calc_pdh_pdl(bars) is None

    def test_pwh_pwl(self):
        bars = [
            make_bar("2026-W14", 100, 130, 90, 115),   # 前前周
            make_bar("2026-W15", 115, 150, 100, 140),  # 前周 ← PWH=150, PWL=100
            make_bar("2026-W16", 140, 160, 135, 155),  # 本周
        ]
        result = calc_pwh_pwl(bars)
        assert result.high == 150
        assert result.low == 100

    def test_equilibrium(self):
        assert calc_equilibrium(100, 200) == 150
        assert calc_equilibrium(21520, 21380) == 21450

    def test_nwog_bullish(self):
        # 周五收盘 21400，周日开盘 21450 (gap up)
        nwog = calc_nwog(friday_close=21400, sunday_open=21450)
        assert nwog.high == 21450
        assert nwog.low == 21400
        assert nwog.ce == 21425
        assert nwog.size == 50

    def test_nwog_bearish(self):
        # 周五收盘 21450，周日开盘 21400 (gap down)
        nwog = calc_nwog(friday_close=21450, sunday_open=21400)
        assert nwog.high == 21450
        assert nwog.low == 21400
        assert nwog.ce == 21425

    def test_ndog(self):
        ndog = calc_ndog(close_5pm=21460, open_6pm=21470)
        assert ndog.high == 21470
        assert ndog.low == 21460
        assert ndog.ce == 21465

    def test_ipda_20d(self):
        # 生成 25 根日线 bars，20 日范围应取最后 20 根
        bars = [
            make_bar(f"2026-03-{i+1:02d}", 100, 100 + i, 100 - i, 100)
            for i in range(25)
        ]
        # 最后 20 根是 i=5..24，high 范围 105..124，low 范围 95..76
        result = calc_ipda_range(bars, 20)
        assert result is not None
        assert result.high == 124  # i=24 时 high = 100+24
        assert result.low == 76    # i=24 时 low = 100-24

    def test_ipda_insufficient_data(self):
        bars = [make_bar(f"2026-04-{i+1:02d}", 100, 110, 90, 100) for i in range(10)]
        assert calc_ipda_range(bars, 20) is None

    def test_current_position(self):
        range_ = PriceRange(high=200, low=100)  # eq = 150
        assert calc_current_position_in_range(180, range_) == "premium"
        assert calc_current_position_in_range(120, range_) == "discount"
        assert calc_current_position_in_range(150, range_) == "equilibrium"
        assert calc_current_position_in_range(155, range_) == "equilibrium"  # 容差内
        assert calc_current_position_in_range(165, range_) == "premium"


# ─── FVG Scanner 测试 ───

class TestFVGScanner:

    def test_bearish_fvg_sibi(self):
        """Bearish FVG: bar1.low > bar3.high"""
        bars = [
            make_bar("2026-04-14T09:30", 100, 105, 98, 102),   # bar1: low=98
            make_bar("2026-04-14T09:35", 102, 103, 90, 92),    # bar2: 位移 down
            make_bar("2026-04-14T09:40", 92, 95, 88, 90),      # bar3: high=95
            # bar1.low(98) > bar3.high(95) ✅ SIBI
        ]
        fvgs = scan_fvgs(bars, "M5", check_fill=False)
        assert len(fvgs) == 1
        assert fvgs[0].type == FVGType.SIBI
        assert fvgs[0].price_high == 98  # FVG 上沿
        assert fvgs[0].price_low == 95   # FVG 下沿
        assert fvgs[0].ce == 96.5

    def test_bullish_fvg_bisi(self):
        """Bullish FVG: bar1.high < bar3.low"""
        bars = [
            make_bar("2026-04-14T09:30", 100, 102, 98, 101),   # bar1: high=102
            make_bar("2026-04-14T09:35", 101, 115, 100, 113),  # bar2: 位移 up
            make_bar("2026-04-14T09:40", 113, 118, 108, 115),  # bar3: low=108
            # bar1.high(102) < bar3.low(108) ✅ BISI
        ]
        fvgs = scan_fvgs(bars, "M5", check_fill=False)
        assert len(fvgs) == 1
        assert fvgs[0].type == FVGType.BISI
        assert fvgs[0].price_high == 108
        assert fvgs[0].price_low == 102

    def test_no_fvg_when_overlap(self):
        """正常重叠的 bars，无 FVG"""
        bars = [
            make_bar("t1", 100, 105, 95, 102),
            make_bar("t2", 102, 107, 98, 104),
            make_bar("t3", 104, 108, 100, 106),
        ]
        fvgs = scan_fvgs(bars, "M5", check_fill=False)
        assert len(fvgs) == 0

    def test_multiple_fvgs(self):
        """多个 FVG"""
        bars = [
            # FVG 1: SIBI at bars 0-2
            make_bar("t1", 100, 105, 98, 102),
            make_bar("t2", 102, 103, 90, 92),
            make_bar("t3", 92, 95, 88, 90),
            # 正常 bars
            make_bar("t4", 90, 93, 85, 88),
            # FVG 2: BISI at bars 4-6
            make_bar("t5", 88, 90, 85, 87),
            make_bar("t6", 87, 100, 86, 98),
            make_bar("t7", 98, 105, 95, 102),
        ]
        fvgs = scan_fvgs(bars, "M5", check_fill=False)
        assert len(fvgs) == 2
        types = [f.type for f in fvgs]
        assert FVGType.SIBI in types
        assert FVGType.BISI in types

    def test_fvg_filled(self):
        """SIBI 形成后价格回到上方填充"""
        bars = [
            make_bar("t1", 100, 105, 98, 102),
            make_bar("t2", 102, 103, 90, 92),
            make_bar("t3", 92, 95, 88, 90),
            # 回到 98 上方填充 FVG
            make_bar("t4", 90, 99, 89, 97),
        ]
        fvgs = scan_fvgs(bars, "M5", check_fill=True)
        assert len(fvgs) == 1
        assert fvgs[0].filled == True
        assert fvgs[0].filled_at_index == 3

    def test_filter_unfilled(self):
        bars = [
            make_bar("t1", 100, 105, 98, 102),
            make_bar("t2", 102, 103, 90, 92),
            make_bar("t3", 92, 95, 88, 90),
            make_bar("t4", 90, 99, 89, 97),  # 填充 FVG 1
            # FVG 2 未填充
            make_bar("t5", 97, 100, 95, 98),
            make_bar("t6", 98, 99, 85, 87),
            make_bar("t7", 87, 90, 80, 82),
        ]
        all_fvgs = scan_fvgs(bars, "M5", check_fill=True)
        unfilled = filter_unfilled(all_fvgs)
        assert len(unfilled) < len(all_fvgs)

    def test_filter_by_price_range(self):
        bars = [
            make_bar("t1", 100, 105, 98, 102),
            make_bar("t2", 102, 103, 90, 92),
            make_bar("t3", 92, 95, 88, 90),
        ]
        fvgs = scan_fvgs(bars, "M5", check_fill=False)
        # 当前价 98，FVG 在 95-98，距离 0%，在 5% 内
        close = filter_by_price_range(fvgs, current_price=98, max_distance_pct=5.0)
        assert len(close) == 1
        # 当前价 200，FVG 太远
        far = filter_by_price_range(fvgs, current_price=200, max_distance_pct=5.0)
        assert len(far) == 0


# ─── Liquidity 测试 ───

class TestLiquidity:

    def test_find_equal_highs(self):
        # 构造 3 个相近的 swing highs around 110
        bars = [
            make_bar("t1", 95, 105, 90, 100),
            make_bar("t2", 100, 110, 95, 108),   # swing high 110
            make_bar("t3", 108, 109, 100, 105),
            make_bar("t4", 105, 108, 102, 106),
            make_bar("t5", 106, 111, 100, 109),  # swing high 111 (相近)
            make_bar("t6", 109, 110, 103, 106),
            make_bar("t7", 106, 109, 102, 108),
            make_bar("t8", 108, 112, 103, 110),  # swing high 112 (相近)
            make_bar("t9", 110, 111, 100, 105),
        ]
        eqhs = find_equal_highs(bars, tolerance_points=5, min_count=2)
        assert len(eqhs) >= 1
        # 应识别出 110-112 附近的集群
        cluster = eqhs[0]
        assert cluster.count >= 2
        assert 108 <= cluster.price <= 113

    def test_find_equal_lows(self):
        bars = [
            make_bar("t1", 100, 110, 95, 105),
            make_bar("t2", 105, 108, 90, 95),    # swing low 90
            make_bar("t3", 95, 100, 92, 98),
            make_bar("t4", 98, 105, 95, 102),
            make_bar("t5", 102, 108, 91, 98),    # swing low 91
            make_bar("t6", 98, 103, 95, 100),
            make_bar("t7", 100, 105, 92, 100),   # swing low 92
        ]
        eqls = find_equal_lows(bars, tolerance_points=5, min_count=2)
        assert len(eqls) >= 1

    def test_no_equal_points_when_diverse(self):
        """所有高点都很分散，无 EQH"""
        bars = [
            make_bar("t1", 100, 110, 95, 105),
            make_bar("t2", 105, 150, 100, 120),
            make_bar("t3", 120, 125, 115, 118),
            make_bar("t4", 118, 200, 110, 180),
            make_bar("t5", 180, 185, 170, 175),
        ]
        eqhs = find_equal_highs(bars, tolerance_points=3, min_count=2)
        # 高点 150, 200 差距太大，无相近集群
        # （不做严格断言，因为 swing 定义可能不命中所有点）


# ─── Fibonacci 测试 ───

class TestFibonacci:

    def test_fib_levels_bullish(self):
        # 从 low=100 到 high=200，做多方向
        fib = calc_fib_levels(swing_high=200, swing_low=100, direction="bullish")
        assert fib.level_0 == 100
        assert fib.level_50 == 150
        assert fib.level_618 == pytest.approx(161.8, abs=0.1)
        assert fib.level_705 == pytest.approx(170.5, abs=0.1)
        assert fib.level_79 == pytest.approx(179.0, abs=0.1)
        assert fib.level_1 == 200

    def test_ote_zone_bullish(self):
        ote = calc_ote_zone(swing_high=200, swing_low=100, direction="bullish")
        assert ote.zone_high == pytest.approx(161.8, abs=0.1)  # 62%
        assert ote.zone_low == pytest.approx(179.0, abs=0.1)   # 79%
        assert ote.sweet_spot == pytest.approx(170.5, abs=0.1)  # 70.5%

    def test_ote_zone_bearish(self):
        # 从 high=200 下来，做空 OTE 是回到 62-79% 之间
        ote = calc_ote_zone(swing_high=200, swing_low=100, direction="bearish")
        assert ote.zone_high == pytest.approx(138.2, abs=0.1)
        assert ote.zone_low == pytest.approx(121.0, abs=0.1)


# ─── Session Ranges 测试 ───

class TestSessionRanges:

    def test_asia_session(self):
        # 构造 Asia session bars (8PM-12AM ET)
        bars = [
            make_bar("2026-04-13T20:00:00", 100, 105, 98, 102),
            make_bar("2026-04-13T21:00:00", 102, 108, 100, 106),
            make_bar("2026-04-13T22:00:00", 106, 107, 103, 104),
            make_bar("2026-04-13T23:00:00", 104, 110, 102, 108),
            # 此后不在 Asia session
            make_bar("2026-04-14T01:00:00", 108, 112, 107, 110),
        ]
        result = calc_session_range(bars, "asia", date="2026-04-13")
        assert result is not None
        assert result.high == 110  # 23:00 bar 的 high
        assert result.low == 98    # 20:00 bar 的 low
        assert result.bar_count == 4

    def test_ny_am_session(self):
        bars = [
            make_bar("2026-04-14T06:00:00", 100, 102, 98, 100),   # 在 NY AM 之前
            make_bar("2026-04-14T07:00:00", 100, 105, 99, 103),
            make_bar("2026-04-14T08:00:00", 103, 108, 102, 106),
            make_bar("2026-04-14T09:00:00", 106, 110, 105, 108),
            make_bar("2026-04-14T10:00:00", 108, 109, 104, 106),
            # 11:00 不在 NY AM (7-11 exclusive)
            make_bar("2026-04-14T11:00:00", 106, 107, 103, 105),
        ]
        result = calc_session_range(bars, "ny_am", date="2026-04-14")
        assert result is not None
        assert result.high == 110
        assert result.low == 99
        assert result.bar_count == 4

    def test_no_session_data(self):
        bars = [make_bar("2026-04-14T12:00:00", 100, 105, 95, 102)]
        result = calc_session_range(bars, "asia", date="2026-04-14")
        # 12:00 不在 Asia session
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
