"""ManifestProcessor — 将 DataManifest 转换为 CalculatedContext

一步完成所有 Calculator 输出，供 PromptBuilder 注入和 Guardian 验证使用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from michael.types import DataManifest, BarData
from michael.calculator.key_levels import (
    calc_pdh_pdl, calc_pwh_pwl, calc_ipda_range,
    calc_current_position_in_range, calc_nwog, calc_ndog,
    PriceRange, OpeningGap,
)
from michael.calculator.fvg_scanner import scan_fvgs, FVG, filter_by_price_range
from michael.calculator.liquidity import find_equal_highs, find_equal_lows, EqualPoints
from michael.calculator.session_ranges import calc_session_range, SessionRange

logger = logging.getLogger(__name__)


@dataclass
class CalculatedContext:
    """所有 Calculator 输出的集合

    设计原则：
    - 一次计算，多处复用（PromptBuilder 注入 + Guardian 验证）
    - 所有字段都是 Optional，数据不足时安全为 None
    - to_prompt_dict() 生成适合注入 LLM 的精简格式
    - to_guardian_dict() 生成适合代码验证的完整格式
    """

    # Key Levels
    pdh: Optional[float] = None
    pdl: Optional[float] = None
    pwh: Optional[float] = None
    pwl: Optional[float] = None
    equilibrium_pdr: Optional[float] = None
    equilibrium_pwr: Optional[float] = None
    current_price: Optional[float] = None

    # IPDA
    ipda_20d: Optional[PriceRange] = None
    ipda_40d: Optional[PriceRange] = None
    ipda_60d: Optional[PriceRange] = None
    ipda_position: Optional[str] = None  # "premium" | "discount" | "equilibrium"

    # FVG（按时间框架组织）
    fvgs_by_tf: dict[str, list[FVG]] = field(default_factory=dict)

    # 流动性
    eqh_list: list[EqualPoints] = field(default_factory=list)
    eql_list: list[EqualPoints] = field(default_factory=list)

    # Session Ranges
    asia_range: Optional[SessionRange] = None
    london_range: Optional[SessionRange] = None
    ny_am_range: Optional[SessionRange] = None
    ny_pm_range: Optional[SessionRange] = None
    first_hour_dr: Optional[SessionRange] = None

    # Opening Gaps (需要特定数据，Phase 1 可选)
    nwog: Optional[OpeningGap] = None
    ndog: Optional[OpeningGap] = None

    # 元数据
    symbol: Optional[str] = None
    calculated_at: str = ""

    def to_prompt_dict(self) -> dict:
        """生成注入 LLM prompt 的精简格式

        只包含 LLM 需要的字段，去除调试信息。
        """
        result = {
            "current_price": self.current_price,
            "key_levels": {
                "PDH": self.pdh,
                "PDL": self.pdl,
                "PWH": self.pwh,
                "PWL": self.pwl,
                "Eq_PDR": self.equilibrium_pdr,
                "Eq_PWR": self.equilibrium_pwr,
            },
            "ipda": {
                "position": self.ipda_position,
                "20d": self._range_dict(self.ipda_20d),
                "40d": self._range_dict(self.ipda_40d),
                "60d": self._range_dict(self.ipda_60d),
            },
            "fvgs": {
                tf: [self._fvg_brief(f) for f in fvgs]
                for tf, fvgs in self.fvgs_by_tf.items()
                if fvgs
            },
            "liquidity": {
                "equal_highs": [{"price": eq.price, "count": eq.count} for eq in self.eqh_list[:5]],
                "equal_lows": [{"price": eq.price, "count": eq.count} for eq in self.eql_list[:5]],
            },
            "sessions": self._sessions_dict(),
            "opening_gaps": self._gaps_dict(),
        }
        # 移除 None 值使 prompt 更干净
        return _clean_none(result)

    def to_guardian_dict(self) -> dict:
        """生成 Guardian 代码级验证的完整格式"""
        return {
            "pdh": self.pdh, "pdl": self.pdl,
            "pwh": self.pwh, "pwl": self.pwl,
            "equilibrium_pdr": self.equilibrium_pdr,
            "equilibrium_pwr": self.equilibrium_pwr,
            "current_price": self.current_price,
            "ipda_20d": self._range_dict(self.ipda_20d),
            "ipda_40d": self._range_dict(self.ipda_40d),
            "ipda_60d": self._range_dict(self.ipda_60d),
            "ipda_position": self.ipda_position,
            "fvgs_by_tf": {
                tf: [f.to_dict() for f in fvgs]
                for tf, fvgs in self.fvgs_by_tf.items()
            },
            "eqh_list": [e.to_dict() for e in self.eqh_list],
            "eql_list": [e.to_dict() for e in self.eql_list],
            "sessions": self._sessions_dict(detailed=True),
        }

    @staticmethod
    def _range_dict(r: Optional[PriceRange]) -> Optional[dict]:
        if r is None:
            return None
        return {"high": r.high, "low": r.low, "eq": r.equilibrium}

    @staticmethod
    def _fvg_brief(f: FVG) -> dict:
        return {
            "type": f.type.value,
            "high": f.price_high,
            "low": f.price_low,
            "ce": f.ce,
            "filled": f.filled,
            "ts": f.timestamp,
        }

    def _sessions_dict(self, detailed: bool = False) -> dict:
        sessions = {}
        for name, sr in [
            ("asia", self.asia_range),
            ("london", self.london_range),
            ("ny_am", self.ny_am_range),
            ("ny_pm", self.ny_pm_range),
            ("first_hour_dr", self.first_hour_dr),
        ]:
            if sr is None:
                continue
            if detailed:
                sessions[name] = sr.to_dict()
            else:
                sessions[name] = {"high": sr.high, "low": sr.low, "eq": sr.equilibrium}
        return sessions

    def _gaps_dict(self) -> dict:
        gaps = {}
        if self.nwog:
            gaps["NWOG"] = {"high": self.nwog.high, "low": self.nwog.low, "ce": self.nwog.ce}
        if self.ndog:
            gaps["NDOG"] = {"high": self.ndog.high, "low": self.ndog.low, "ce": self.ndog.ce}
        return gaps


def process_manifest(
    manifest: DataManifest,
    primary_symbol: str = "NQ1!",
    fvg_min_size: float = 1.0,
    fvg_max_distance_pct: float = 5.0,
) -> CalculatedContext:
    """将 DataManifest 处理为 CalculatedContext

    Args:
        manifest: Ingestion 产出的 DataManifest
        primary_symbol: 主要分析品种（默认 NQ1!）
        fvg_min_size: FVG 最小尺寸过滤
        fvg_max_distance_pct: FVG 距当前价最大百分比

    Returns:
        完整的 CalculatedContext
    """
    ctx = CalculatedContext(symbol=primary_symbol)

    if primary_symbol not in manifest.symbols:
        logger.warning(f"{primary_symbol} 数据缺失，Calculator 跳过")
        return ctx

    symbol_data = manifest.symbols[primary_symbol]

    # 1. 当前价（用最小时间框架的最新 close）
    for tf in ["M1", "M5", "M15", "H1", "H4", "D"]:
        if tf in symbol_data and symbol_data[tf].bars:
            ctx.current_price = symbol_data[tf].bars[-1].close
            break

    # 2. 日线级别 Key Levels + IPDA
    if "D" in symbol_data and symbol_data["D"].bars:
        daily_bars = symbol_data["D"].bars

        pdr = calc_pdh_pdl(daily_bars)
        if pdr:
            ctx.pdh = pdr.high
            ctx.pdl = pdr.low
            ctx.equilibrium_pdr = pdr.equilibrium

        for days, attr in [(20, "ipda_20d"), (40, "ipda_40d"), (60, "ipda_60d")]:
            rng = calc_ipda_range(daily_bars, days)
            if rng:
                setattr(ctx, attr, rng)

        # IPDA 位置（用 20D 范围）
        if ctx.ipda_20d and ctx.current_price:
            ctx.ipda_position = calc_current_position_in_range(
                ctx.current_price, ctx.ipda_20d
            )

    # 3. 周线级别
    if "W" in symbol_data and symbol_data["W"].bars:
        weekly_bars = symbol_data["W"].bars
        pwr = calc_pwh_pwl(weekly_bars)
        if pwr:
            ctx.pwh = pwr.high
            ctx.pwl = pwr.low
            ctx.equilibrium_pwr = pwr.equilibrium

    # 4. FVG 扫描（每个时间框架）
    for tf in ["H4", "H1", "M15", "M5"]:
        if tf in symbol_data and symbol_data[tf].bars:
            bars = symbol_data[tf].bars
            fvgs = scan_fvgs(bars, timeframe=tf, check_fill=True, min_size_points=fvg_min_size)

            # 过滤：仅保留未填充 + 距当前价 5% 内
            if ctx.current_price:
                fvgs = filter_by_price_range(fvgs, ctx.current_price, fvg_max_distance_pct)

            fvgs = [f for f in fvgs if not f.filled]
            ctx.fvgs_by_tf[tf] = fvgs

    # 5. 流动性（EQH/EQL）— 用 H1 数据识别
    if "H1" in symbol_data and symbol_data["H1"].bars:
        h1_bars = symbol_data["H1"].bars
        ctx.eqh_list = find_equal_highs(h1_bars, tolerance_points=5.0, min_count=2)
        ctx.eql_list = find_equal_lows(h1_bars, tolerance_points=5.0, min_count=2)

    # 6. Session Ranges（用 M15 数据）
    if "M15" in symbol_data and symbol_data["M15"].bars:
        m15_bars = symbol_data["M15"].bars
        try:
            ctx.asia_range = calc_session_range(m15_bars, "asia")
            ctx.london_range = calc_session_range(m15_bars, "london_full")
            ctx.ny_am_range = calc_session_range(m15_bars, "ny_am")
            ctx.ny_pm_range = calc_session_range(m15_bars, "ny_pm")
            ctx.first_hour_dr = calc_session_range(m15_bars, "first_hour_dr")
        except Exception as e:
            logger.warning(f"Session range 计算失败: {e}")

    from datetime import datetime, timezone
    ctx.calculated_at = datetime.now(timezone.utc).isoformat()

    return ctx


def _clean_none(obj):
    """递归移除 dict 中的 None 值和空结构"""
    if isinstance(obj, dict):
        return {k: _clean_none(v) for k, v in obj.items()
                if v is not None and v != {} and v != []}
    if isinstance(obj, list):
        return [_clean_none(i) for i in obj if i is not None]
    return obj
