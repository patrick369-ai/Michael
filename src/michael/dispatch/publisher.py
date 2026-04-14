"""Publisher 协议 — 消息推送的统一接口"""

from __future__ import annotations

import logging
from typing import Protocol

from michael.types import AnalysisResult, SupervisionReport

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    """所有推送渠道的统一接口"""

    def publish(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
    ) -> bool:
        """推送报告

        Args:
            result: 分析结果
            supervision: Guardian 报告
            metadata: 额外元数据（report_type、symbol、date 等）

        Returns:
            True if successful
        """
        ...


class MultiPublisher:
    """多通道推送（按顺序尝试，单个失败不影响其他）"""

    def __init__(self, publishers: list[Publisher]):
        self._publishers = publishers

    def publish(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
    ) -> dict[str, bool]:
        """推送到所有 Publishers"""
        outcomes: dict[str, bool] = {}
        for pub in self._publishers:
            name = pub.__class__.__name__
            try:
                ok = pub.publish(result, supervision, metadata)
                outcomes[name] = ok
            except Exception as e:
                logger.error(f"{name} 推送失败: {e}")
                outcomes[name] = False
        return outcomes
