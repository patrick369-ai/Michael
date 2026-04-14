"""Calculator 模块 — 代码级确定性价格计算

设计原则（见 DR-005）：
- 代码是眼睛（精确看数据），LLM 是大脑（判断意义）
- 所有确定性计算在这里完成，不调用 LLM
- 两个用途：注入 Prompt（减少幻觉源头）+ 供 Guardian 验证

覆盖范围：
- Key Levels: PDH/PDL/PWH/PWL/Equilibrium/NMO/NWOG/NDOG/ORG
- PDA 扫描: FVG (BISI/SIBI), Volume Imbalance, BPR
- 流动性: EQH/EQL 相近点识别
- Fibonacci: OTE 62-79% 区域
- Session ranges: Asia/London/NY H/L
"""

from michael.calculator.key_levels import (
    calc_pdh_pdl,
    calc_pwh_pwl,
    calc_equilibrium,
    calc_nwog,
    calc_ndog,
    calc_ipda_range,
)
from michael.calculator.fvg_scanner import (
    scan_fvgs,
    FVG,
)
from michael.calculator.liquidity import (
    find_equal_highs,
    find_equal_lows,
)
from michael.calculator.fibonacci import (
    calc_ote_zone,
    calc_fib_levels,
)
from michael.calculator.session_ranges import (
    calc_session_range,
)

__all__ = [
    "calc_pdh_pdl",
    "calc_pwh_pwl",
    "calc_equilibrium",
    "calc_nwog",
    "calc_ndog",
    "calc_ipda_range",
    "scan_fvgs",
    "FVG",
    "find_equal_highs",
    "find_equal_lows",
    "calc_ote_zone",
    "calc_fib_levels",
    "calc_session_range",
]
