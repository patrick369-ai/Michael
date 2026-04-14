"""DataManifest — 数据采集结果结构化描述"""

from __future__ import annotations

from michael.config import PRIMARY_SYMBOL
from michael.types import DataManifest, ManifestIntegrity, SymbolData


def evaluate_integrity(manifest: DataManifest) -> ManifestIntegrity:
    """评估数据完整性

    规则：
    - NQ1! 是关键品种，必须有数据 → 无则 FAIL
    - 任何品种的 bar 数量 < 50% 预期 → 标记为 missing
    - 有 missing 但非关键品种 → PARTIAL
    - 全部正常 → PASS
    """
    # NQ1! 必须存在
    if PRIMARY_SYMBOL not in manifest.symbols:
        return ManifestIntegrity.FAIL

    nq_data = manifest.symbols[PRIMARY_SYMBOL]
    if not nq_data:
        return ManifestIntegrity.FAIL

    # 检查 NQ 各时间框架的 bar 数量
    min_bars_threshold = 10  # 最少需要的 bar 数
    nq_missing = False
    for tf, data in nq_data.items():
        if len(data.bars) < min_bars_threshold:
            nq_missing = True
            break

    if nq_missing:
        return ManifestIntegrity.FAIL

    # 检查其他品种
    has_partial = False
    for symbol, tf_data in manifest.symbols.items():
        if symbol == PRIMARY_SYMBOL:
            continue
        for tf, data in tf_data.items():
            if len(data.bars) < min_bars_threshold:
                has_partial = True
                break

    return ManifestIntegrity.PARTIAL if has_partial else ManifestIntegrity.PASS


def create_manifest(report_type: str) -> DataManifest:
    """创建空的 DataManifest"""
    return DataManifest(report_type=report_type)
