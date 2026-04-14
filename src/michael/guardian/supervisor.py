"""Supervisor — 整合所有 Guardian 检查"""

from __future__ import annotations

import logging
from typing import Optional

from michael.types import (
    CheckResult, Severity, SupervisionReport,
)
from michael.guardian.hallucination import HallucinationDetector, HallucinationConfig
from michael.guardian.consistency import ConsistencyChecker
from michael.guardian.rules import RuleEngine

logger = logging.getLogger(__name__)


class Supervisor:
    """Guardian 监督者 — 运行所有检查并生成报告"""

    def __init__(
        self,
        hallucination_config: Optional[HallucinationConfig] = None,
        rule_engine: Optional[RuleEngine] = None,
    ):
        self._hallu = HallucinationDetector(hallucination_config)
        self._consistency = ConsistencyChecker()
        self._rules = rule_engine or RuleEngine()

    def supervise(
        self,
        llm_output: dict,
        calc_context: dict,
        previous_results: Optional[dict] = None,
        external_context: Optional[dict] = None,
    ) -> SupervisionReport:
        """运行所有 Guardian 检查

        Args:
            llm_output: LLM 完整输出
            calc_context: Calculator 输出（CalculatedContext.to_guardian_dict()）
            previous_results: 前序报告（一致性检查用）
            external_context: 外部上下文（calendar/历史 PDA 失败次数等）

        Returns:
            SupervisionReport 包含所有 CheckResult + 整体严重性
        """
        all_checks: list[CheckResult] = []

        # 1. 幻觉检测
        all_checks.extend(self._hallu.check(llm_output, calc_context))

        # 2. 一致性检查
        all_checks.extend(self._consistency.check(llm_output, previous_results))

        # 3. 规则引擎（红旗 + 硬性规则）
        all_checks.extend(self._rules.evaluate(llm_output, calc_context, external_context))

        report = SupervisionReport(checks=all_checks)
        report.compute_overall()

        logger.info(
            f"Guardian: {len(all_checks)} 个检查, "
            f"FAIL={len(report.failures)}, WARN={len(report.warnings)}, "
            f"overall={report.overall.value}"
        )

        return report
