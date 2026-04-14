"""幻觉检测 — 用 Calculator 输出验证 LLM 声称的值

核心检查：
1. Key Levels (PDH/PDL/PWH/PWL) 是否与 Calculator 一致（容差 1-2 点）
2. FVG 位置是否与 Calculator 扫描结果匹配（如果 LLM 说 M5 有 FVG @ X，验证 Calculator 是否找到了相近的）
3. Entry/SL/TP 价格是否在合理范围（相对当前价 < 5%）
4. SL 距离是否 ≤ 30 NQ 点
5. PDA/Entry Model 名称是否在已知词典中
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from michael.types import CheckResult, Severity

logger = logging.getLogger(__name__)


# 已知的 PDA 名称（含变体）
KNOWN_PDA_NAMES = {
    "FVG", "BISI", "SIBI",
    "OB", "+OB", "-OB", "Order Block", "Bullish OB", "Bearish OB",
    "Breaker", "+BB", "-BB", "Breaker Block",
    "MB", "+MB", "-MB", "Mitigation Block",
    "RB", "+RB", "-RB", "Rejection Block",
    "PB", "Propulsion Block",
    "VI", "Volume Imbalance", "VIB",
    "BPR", "Balanced Price Range",
    "Suspension Block",
    "Immediate Rebalance",
    "IFVG", "Inversion FVG", "Inverted FVG",
    "Inversion Breaker",
    "Reaper FVG",
    "NWOG", "NDOG", "ORG",
    "EQH", "EQL", "Equal Highs", "Equal Lows",
    "BSL", "SSL", "REL", "REH",
    "Liquidity Void", "LV",
    "Implied FVG",
    "Hidden OB", "Reclaimed OB",
}

# 已知的 Entry Model 名称
KNOWN_ENTRY_MODELS = {
    "2022 Entry", "2022 Model", "ICT 2022",
    "Silver Bullet", "SB",
    "OTE", "Optimal Trade Entry",
    "Unicorn",
    "IFVG Model", "Inversion FVG Model",
    "Breaker Model",
    "1st Presented FVG", "First Presented FVG",
    "Judas Swing",
    "NY Continuation",
    "MEP", "Market Efficiency Paradigm",
    "2025 Model",
    "MMXM", "Market Maker Model", "MMBM", "MMSM",
    "Sequence 1", "Sequence 2", "The Sequence",
    "Reaper FVG", "Propulsion Block",
    "30-Second Model",
    "Turtle Soup", "Failure Swing", "Three Drives",
    "2nd Stage Distribution",
    "Venom", "Venom Model",
    "IOFED",
    "Bread & Butter", "Bread and Butter",
    "ICT ATM", "ATM Method",
    "Asia-London Entry",
}


@dataclass
class HallucinationConfig:
    """幻觉检测配置"""
    key_level_tolerance_points: float = 2.0    # PDH/PDL 容差
    fvg_tolerance_points: float = 3.0          # FVG 价格容差
    entry_max_distance_pct: float = 5.0        # Entry 距当前价最大百分比
    sl_max_points_nq: int = 30                 # NQ SL 最大点数


class HallucinationDetector:
    """幻觉检测器"""

    def __init__(self, hconfig: Optional[HallucinationConfig] = None):
        self._cfg = hconfig or HallucinationConfig()

    def check(
        self,
        llm_output: dict,
        calc_context: dict,
    ) -> list[CheckResult]:
        """运行所有幻觉检查

        Args:
            llm_output: LLM 输出的完整 JSON
            calc_context: Calculator 输出（CalculatedContext.to_guardian_dict()）

        Returns:
            CheckResult 列表
        """
        results: list[CheckResult] = []

        # 1. Key Levels 验证
        results.extend(self._check_key_levels(llm_output, calc_context))

        # 2. PDA 名称存在性
        results.extend(self._check_pda_names(llm_output))

        # 3. Entry Model 名称
        results.extend(self._check_entry_model_names(llm_output))

        # 4. Trade Plan 价格合理性
        results.extend(self._check_trade_plan_prices(llm_output, calc_context))

        # 5. SL 距离
        results.extend(self._check_sl_distance(llm_output))

        # 6. FVG 位置验证
        results.extend(self._check_fvg_positions(llm_output, calc_context))

        return results

    def _check_key_levels(self, llm: dict, calc: dict) -> list[CheckResult]:
        """检查 LLM 声称的 Key Levels 与 Calculator 一致"""
        results = []
        tolerance = self._cfg.key_level_tolerance_points

        # 在多个可能的位置查找 LLM 提到的 Key Levels
        llm_levels = self._extract_key_levels_from_llm(llm)

        for level_name, calc_value in [
            ("PDH", calc.get("pdh")),
            ("PDL", calc.get("pdl")),
            ("PWH", calc.get("pwh")),
            ("PWL", calc.get("pwl")),
        ]:
            if calc_value is None:
                continue
            llm_value = llm_levels.get(level_name)
            if llm_value is None:
                continue
            try:
                diff = abs(float(llm_value) - float(calc_value))
                if diff > tolerance:
                    results.append(CheckResult(
                        check_name=f"key_level_{level_name}",
                        category="hallucination",
                        severity=Severity.WARN if diff < 10 else Severity.FAIL,
                        message=f"{level_name}: LLM={llm_value}, Calculator={calc_value}, 差距 {diff:.1f} 点",
                        details={"llm": llm_value, "calc": calc_value, "diff": diff},
                    ))
            except (ValueError, TypeError):
                pass

        return results

    def _extract_key_levels_from_llm(self, llm: dict) -> dict:
        """从 LLM 输出中递归查找 PDH/PDL/PWH/PWL 等"""
        found = {}
        targets = {"PDH", "PDL", "PWH", "PWL", "pdh", "pdl", "pwh", "pwl"}

        def walk(node, path=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k.upper() in targets and isinstance(v, (int, float)):
                        found[k.upper()] = v
                    elif isinstance(v, (dict, list)):
                        walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    walk(item, f"{path}[{i}]")

        walk(llm)
        return found

    def _check_pda_names(self, llm: dict) -> list[CheckResult]:
        """递归查找 type 字段，验证 PDA 名称"""
        results = []
        unknown_pdas = self._find_unknown_pda_names(llm)

        for name in unknown_pdas:
            results.append(CheckResult(
                check_name="pda_name_unknown",
                category="hallucination",
                severity=Severity.WARN,
                message=f"未知 PDA 名称: '{name}'",
                details={"name": name},
            ))
        return results

    def _find_unknown_pda_names(self, llm: dict) -> set[str]:
        """递归查找 type 字段中不在已知 PDA 列表的"""
        unknown: set[str] = set()

        def walk(node):
            if isinstance(node, dict):
                # 检查 type 字段
                type_val = node.get("type")
                if isinstance(type_val, str):
                    if not self._is_known_pda(type_val):
                        unknown.add(type_val)
                # 递归
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(llm)
        return unknown

    @staticmethod
    def _is_known_pda(name: str) -> bool:
        normalized = name.strip()
        return (normalized in KNOWN_PDA_NAMES or
                normalized.replace(" ", "") in {n.replace(" ", "") for n in KNOWN_PDA_NAMES})

    def _check_entry_model_names(self, llm: dict) -> list[CheckResult]:
        """检查 entry_model 字段"""
        results = []
        models = self._find_entry_model_mentions(llm)
        for name in models:
            if not self._is_known_model(name):
                results.append(CheckResult(
                    check_name="entry_model_unknown",
                    category="hallucination",
                    severity=Severity.WARN,
                    message=f"未知 Entry Model: '{name}'",
                    details={"name": name},
                ))
        return results

    def _find_entry_model_mentions(self, llm: dict) -> set[str]:
        models: set[str] = set()

        def walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ("entry_model", "model_name", "entry_model_chosen"):
                        if isinstance(v, str):
                            models.add(v)
                    if isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(llm)
        return models

    @staticmethod
    def _is_known_model(name: str) -> bool:
        normalized = name.strip().lower()
        known_lower = {m.strip().lower() for m in KNOWN_ENTRY_MODELS}
        return normalized in known_lower

    def _check_trade_plan_prices(self, llm: dict, calc: dict) -> list[CheckResult]:
        """检查 Trade Plan 中的 Entry 价格合理性"""
        results = []
        current_price = calc.get("current_price")
        if current_price is None:
            return results

        trade_plan = self._find_trade_plan(llm)
        if not trade_plan:
            return results

        max_distance = current_price * self._cfg.entry_max_distance_pct / 100

        for field in ("entry", "stop_loss", "tp1", "tp2"):
            value = self._extract_price(trade_plan.get(field))
            if value is None:
                continue
            distance = abs(value - current_price)
            if distance > max_distance:
                pct = distance / current_price * 100
                results.append(CheckResult(
                    check_name=f"trade_plan_{field}_far",
                    category="hallucination",
                    severity=Severity.WARN,
                    message=f"{field}={value} 距当前价 {current_price} 偏离 {pct:.2f}%（>{self._cfg.entry_max_distance_pct}%）",
                    details={"value": value, "current": current_price, "distance_pct": pct},
                ))

        return results

    @staticmethod
    def _find_trade_plan(llm: dict) -> Optional[dict]:
        """递归查找 trade_plan 字段"""
        if "trade_plan" in llm and isinstance(llm["trade_plan"], dict):
            return llm["trade_plan"]
        for v in llm.values():
            if isinstance(v, dict):
                result = HallucinationDetector._find_trade_plan(v)
                if result:
                    return result
        return None

    @staticmethod
    def _extract_price(value) -> Optional[float]:
        """从可能的嵌套结构中提取价格"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for k in ("price", "value", "high", "low"):
                if k in value and isinstance(value[k], (int, float)):
                    return float(value[k])
        return None

    def _check_sl_distance(self, llm: dict) -> list[CheckResult]:
        """SL 距离不能超过 30 NQ 点"""
        results = []
        trade_plan = self._find_trade_plan(llm)
        if not trade_plan:
            return results

        entry = self._extract_price(trade_plan.get("entry") or trade_plan.get("entry_zone"))
        sl = self._extract_price(trade_plan.get("stop_loss"))

        if entry is not None and sl is not None:
            distance = abs(entry - sl)
            if distance > self._cfg.sl_max_points_nq:
                results.append(CheckResult(
                    check_name="sl_distance_exceeds_max",
                    category="hallucination",
                    severity=Severity.FAIL,
                    message=f"SL 距离 {distance:.1f} 点 > 上限 {self._cfg.sl_max_points_nq} 点",
                    details={"entry": entry, "sl": sl, "distance": distance},
                ))

        return results

    def _check_fvg_positions(self, llm: dict, calc: dict) -> list[CheckResult]:
        """检查 LLM 声称的 FVG 位置是否在 Calculator 扫描结果中"""
        results = []

        # 提取 LLM 中标记为 FVG 的位点（带价格范围）
        llm_fvgs = self._extract_llm_fvgs(llm)
        if not llm_fvgs:
            return results

        calc_fvgs_by_tf = calc.get("fvgs_by_tf", {})

        # 把所有 calculator 找到的 FVG 扁平化
        all_calc_fvgs = []
        for tf, fvgs in calc_fvgs_by_tf.items():
            for f in fvgs:
                all_calc_fvgs.append({"tf": tf, "high": f.get("price_high"), "low": f.get("price_low")})

        tolerance = self._cfg.fvg_tolerance_points

        for llm_fvg in llm_fvgs:
            llm_high = llm_fvg.get("high")
            llm_low = llm_fvg.get("low")
            if llm_high is None or llm_low is None:
                continue

            # 在 Calculator 的 FVG 中找匹配
            matched = False
            for calc_fvg in all_calc_fvgs:
                if (abs(calc_fvg["high"] - llm_high) <= tolerance and
                        abs(calc_fvg["low"] - llm_low) <= tolerance):
                    matched = True
                    break

            if not matched:
                # LLM 声称的 FVG 位置 Calculator 找不到
                results.append(CheckResult(
                    check_name="fvg_position_not_found",
                    category="hallucination",
                    severity=Severity.WARN,
                    message=f"LLM 声称的 FVG @ {llm_low}-{llm_high} 在 Calculator 扫描结果中未找到",
                    details={"llm_fvg": llm_fvg},
                ))

        return results

    @staticmethod
    def _extract_llm_fvgs(llm: dict) -> list[dict]:
        """从 LLM 输出中提取所有标记为 FVG 的项"""
        fvgs = []

        def walk(node):
            if isinstance(node, dict):
                type_val = node.get("type", "").upper() if isinstance(node.get("type"), str) else ""
                if type_val in ("FVG", "BISI", "SIBI", "BULLISH FVG", "BEARISH FVG"):
                    high = node.get("price_high") or node.get("high")
                    low = node.get("price_low") or node.get("low")
                    if isinstance(high, (int, float)) and isinstance(low, (int, float)):
                        fvgs.append({"high": high, "low": low, "type": type_val})
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(llm)
        return fvgs
