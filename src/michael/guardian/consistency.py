"""一致性检查 — 跨 Skill / 跨步骤 / 跨报告的逻辑对齐"""

from __future__ import annotations

import logging
from typing import Optional

from michael.types import CheckResult, Severity

logger = logging.getLogger(__name__)


class ConsistencyChecker:
    """一致性检查器"""

    def check(
        self,
        llm_output: dict,
        previous_results: Optional[dict] = None,
    ) -> list[CheckResult]:
        """运行所有一致性检查"""
        results: list[CheckResult] = []

        # 1. Bias / DOL 方向对齐
        results.extend(self._check_bias_dol_alignment(llm_output))

        # 2. Bias / Signal 方向对齐
        results.extend(self._check_bias_signal_alignment(llm_output))

        # 3. Session Bias vs Daily Bias 对齐
        results.extend(self._check_session_daily_bias(llm_output))

        # 4. 跨报告一致性（如本次 Daily Bias vs 昨日 Daily Bias）
        if previous_results:
            results.extend(self._check_cross_report(llm_output, previous_results))

        # 5. Key Levels 跨步骤一致性（同一分析中各 Skill 引用的 PDH 应一致）
        results.extend(self._check_key_levels_internal(llm_output))

        return results

    def _check_bias_dol_alignment(self, llm: dict) -> list[CheckResult]:
        """Bias 方向与 DOL 目标方向应一致"""
        results = []
        bias = self._extract_bias_direction(llm)
        dol_price = self._extract_dol_target(llm)
        current_price = self._extract_current_price(llm)

        if not bias or dol_price is None or current_price is None:
            return results

        if bias == "LONG" and dol_price < current_price:
            results.append(CheckResult(
                check_name="bias_dol_direction_conflict",
                category="consistency",
                severity=Severity.FAIL,
                message=f"Bias=LONG 但 DOL @ {dol_price} 在当前价 {current_price} 下方",
                details={"bias": bias, "dol": dol_price, "current": current_price},
            ))
        elif bias == "SHORT" and dol_price > current_price:
            results.append(CheckResult(
                check_name="bias_dol_direction_conflict",
                category="consistency",
                severity=Severity.FAIL,
                message=f"Bias=SHORT 但 DOL @ {dol_price} 在当前价 {current_price} 上方",
                details={"bias": bias, "dol": dol_price, "current": current_price},
            ))

        return results

    def _check_bias_signal_alignment(self, llm: dict) -> list[CheckResult]:
        """信号方向应与 Bias 一致"""
        results = []
        bias = self._extract_bias_direction(llm)
        signal_dir = self._extract_signal_direction(llm)

        if not bias or not signal_dir:
            return results

        if bias != "NEUTRAL" and signal_dir != "NEUTRAL" and bias != signal_dir:
            results.append(CheckResult(
                check_name="bias_signal_conflict",
                category="consistency",
                severity=Severity.FAIL,
                message=f"Bias={bias} 但信号方向={signal_dir}",
                details={"bias": bias, "signal": signal_dir},
            ))

        return results

    def _check_session_daily_bias(self, llm: dict) -> list[CheckResult]:
        """Session Bias 与 Daily Bias 对齐"""
        results = []
        # 在 LLM 输出中查找 session_role / session_bias
        session_bias = self._dig(llm, ["session_role", "bias_alignment"])
        if session_bias == "conflicting":
            results.append(CheckResult(
                check_name="session_daily_bias_conflict",
                category="consistency",
                severity=Severity.WARN,
                message="Session 角色与 Daily Bias 冲突且无合理理由",
                details={},
            ))
        return results

    def _check_cross_report(self, llm: dict, previous: dict) -> list[CheckResult]:
        """与前序报告一致性"""
        results = []

        current_bias = self._extract_bias_direction(llm)
        previous_bias = previous.get("bias_direction") or self._extract_bias_direction(previous)

        if current_bias and previous_bias and current_bias != previous_bias:
            # Bias 翻转 — 必须有理由
            reversal_reason = self._dig(llm, ["bias", "reversal_reason"])
            reversal_flag = self._dig(llm, ["bias", "reversal_from_previous"])

            if not reversal_flag or not reversal_reason:
                results.append(CheckResult(
                    check_name="cross_report_bias_reversal_unjustified",
                    category="consistency",
                    severity=Severity.WARN,
                    message=f"Bias 从前次的 {previous_bias} 翻转到 {current_bias}，但未提供翻转理由",
                    details={"prev": previous_bias, "current": current_bias},
                ))

        return results

    def _check_key_levels_internal(self, llm: dict) -> list[CheckResult]:
        """同一分析内 Key Levels 跨多个 Skill 应一致"""
        results = []

        # 收集所有提到的 PDH 值
        pdhs = self._collect_all_values(llm, "PDH") + self._collect_all_values(llm, "pdh")

        if len(set(pdhs)) > 1:
            # 容差 0.5%
            avg = sum(pdhs) / len(pdhs)
            for v in pdhs:
                if abs(v - avg) / avg > 0.005:
                    results.append(CheckResult(
                        check_name="internal_pdh_inconsistent",
                        category="consistency",
                        severity=Severity.WARN,
                        message=f"分析内 PDH 引用不一致: {set(pdhs)}",
                        details={"values": list(set(pdhs))},
                    ))
                    break

        return results

    # ─── 辅助方法 ───

    @staticmethod
    def _extract_bias_direction(llm: dict) -> Optional[str]:
        for path in [
            ["bias", "direction"],
            ["framing", "bias", "direction"],
            ["direction"],
        ]:
            v = ConsistencyChecker._dig(llm, path)
            if isinstance(v, str):
                return v.upper()
        return None

    @staticmethod
    def _extract_dol_target(llm: dict) -> Optional[float]:
        for path in [
            ["dol_framework", "primary_dol", "price"],
            ["dol_framework", "q3_where_to", "primary_dol", "price"],
            ["dol", "target"],
            ["targeting", "dol", "primary_dol", "price"],
        ]:
            v = ConsistencyChecker._dig(llm, path)
            if isinstance(v, (int, float)):
                return float(v)
        return None

    @staticmethod
    def _extract_current_price(llm: dict) -> Optional[float]:
        for path in [
            ["current_price"],
            ["calc", "current_price"],
        ]:
            v = ConsistencyChecker._dig(llm, path)
            if isinstance(v, (int, float)):
                return float(v)
        return None

    @staticmethod
    def _extract_signal_direction(llm: dict) -> Optional[str]:
        for path in [
            ["trade_plan", "direction"],
            ["entry_model_matching", "top_candidates", 0, "direction"],
            ["signal", "direction"],
        ]:
            v = ConsistencyChecker._dig(llm, path)
            if isinstance(v, str):
                return v.upper()
        return None

    @staticmethod
    def _dig(node, path):
        """递归取值，路径中的 int 表示数组索引"""
        cur = node
        for key in path:
            if cur is None:
                return None
            if isinstance(key, int):
                if isinstance(cur, list) and 0 <= key < len(cur):
                    cur = cur[key]
                else:
                    return None
            else:
                if isinstance(cur, dict):
                    cur = cur.get(key)
                else:
                    return None
        return cur

    @staticmethod
    def _collect_all_values(node, key_name) -> list:
        """递归收集所有匹配 key 的数值"""
        results = []
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key_name and isinstance(v, (int, float)):
                    results.append(float(v))
                elif isinstance(v, (dict, list)):
                    results.extend(ConsistencyChecker._collect_all_values(v, key_name))
        elif isinstance(node, list):
            for item in node:
                results.extend(ConsistencyChecker._collect_all_values(item, key_name))
        return results
