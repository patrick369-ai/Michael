"""Session 范围计算 — Asia/London/NY 各 Session 的 H/L"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from michael.types import BarData
from michael.calculator.key_levels import PriceRange


# Session 时间定义（ET 小时）
SESSION_TIMES = {
    "asia":         {"start": 20, "end": 24, "name": "Asia"},          # 8PM-12AM
    "london_open":  {"start": 2,  "end": 5,  "name": "London Open KZ"},  # 2-5AM
    "london_full":  {"start": 2,  "end": 10, "name": "London Full"},      # 2-10AM
    "ny_am":        {"start": 7,  "end": 11, "name": "NY AM"},            # 7-11AM
    "ny_am_futures":{"start": 830,"end": 1100,"name": "NY AM Futures"},  # 8:30-11AM (minutes*100+hour)
    "ny_pm":        {"start": 13, "end": 16, "name": "NY PM"},            # 1-4PM
    "cbdr":         {"start": 14, "end": 20, "name": "CBDR"},             # 2-8PM
    "first_hour_dr":{"start": 930,"end": 1030,"name": "1st Hour DR"},    # 9:30-10:30
}


@dataclass(frozen=True)
class SessionRange:
    """单 Session 的价格范围"""
    session_name: str
    date: str              # YYYY-MM-DD
    high: float
    low: float
    open_price: float      # Session 开始时的价格
    close_price: float     # Session 结束时的价格
    bar_count: int

    @property
    def equilibrium(self) -> float:
        return (self.high + self.low) / 2

    @property
    def size(self) -> float:
        return self.high - self.low

    def to_dict(self) -> dict:
        return {
            "session": self.session_name,
            "date": self.date,
            "high": self.high,
            "low": self.low,
            "open": self.open_price,
            "close": self.close_price,
            "equilibrium": self.equilibrium,
            "size": self.size,
            "bar_count": self.bar_count,
        }


def calc_session_range(
    intraday_bars: list[BarData],
    session_key: str,
    date: Optional[str] = None,
) -> Optional[SessionRange]:
    """计算指定 Session 的价格范围

    Args:
        intraday_bars: 日内 bars（M15/M5/M1 都可以），按时间升序
                       时间戳需为 ISO 格式
        session_key: SESSION_TIMES 的 key
        date: 指定日期 YYYY-MM-DD（默认用 bars 中最新的日期）

    Returns:
        SessionRange 或 None（如无该 Session 数据）

    注意：时间戳假定为 ET 时区或已包含时区信息。
    如果是 UTC 时间戳，调用者需自行转换。
    """
    if session_key not in SESSION_TIMES:
        raise ValueError(f"未知 session: {session_key}")

    session_def = SESSION_TIMES[session_key]

    # 过滤出该 Session 的 bars
    session_bars = [
        bar for bar in intraday_bars
        if _is_in_session(bar.timestamp, session_def, date)
    ]

    if not session_bars:
        return None

    # 提取日期（使用第一根 bar 的日期）
    bar_date = _extract_date(session_bars[0].timestamp)

    return SessionRange(
        session_name=session_def["name"],
        date=bar_date,
        high=max(bar.high for bar in session_bars),
        low=min(bar.low for bar in session_bars),
        open_price=session_bars[0].open,
        close_price=session_bars[-1].close,
        bar_count=len(session_bars),
    )


def _is_in_session(timestamp: str, session_def: dict, target_date: Optional[str]) -> bool:
    """判断 bar 时间是否在指定 Session 内"""
    try:
        dt = _parse_timestamp(timestamp)
    except (ValueError, TypeError):
        return False

    if target_date:
        if dt.strftime("%Y-%m-%d") != target_date:
            return False

    start = session_def["start"]
    end = session_def["end"]

    # 处理精确到分钟的 session（如 8:30 = 830）
    if start >= 100:
        start_hour = start // 100
        start_min = start % 100
        end_hour = end // 100
        end_min = end % 100

        current_minutes = dt.hour * 60 + dt.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        return start_minutes <= current_minutes < end_minutes

    # 整点小时 session
    hour = dt.hour
    # 处理跨午夜（如 Asia 20-24 实际是 20:00-23:59）
    if end == 24:
        return hour >= start
    return start <= hour < end


def _parse_timestamp(ts: str) -> datetime:
    """解析时间戳为 datetime"""
    # 支持多种格式
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]:
        try:
            dt = datetime.strptime(ts, fmt)
            return dt
        except ValueError:
            continue
    raise ValueError(f"无法解析时间戳: {ts}")


def _extract_date(ts: str) -> str:
    """从时间戳提取日期 YYYY-MM-DD"""
    try:
        dt = _parse_timestamp(ts)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ts[:10] if len(ts) >= 10 else ""
