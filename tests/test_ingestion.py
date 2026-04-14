"""Ingestion 模块测试 — 使用 mock subprocess 验证 MCP 交互"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.config import Config
from michael.types import DataManifest, BarData, ManifestIntegrity
from michael.ingestion.collector import Collector, MCPError, CollectorError
from michael.ingestion.manifest import evaluate_integrity, create_manifest


class TestManifestEvaluation:
    def test_empty_manifest_fails(self):
        manifest = create_manifest("daily_bias")
        assert evaluate_integrity(manifest) == ManifestIntegrity.FAIL

    def test_nq_missing_fails(self):
        from michael.types import SymbolData
        manifest = create_manifest("daily_bias")
        manifest.symbols["ES1!"] = {
            "D": SymbolData(symbol="ES1!", timeframe="D", bars=[
                BarData("2026-04-14", 100, 110, 90, 105, 1000) for _ in range(20)
            ])
        }
        assert evaluate_integrity(manifest) == ManifestIntegrity.FAIL

    def test_nq_insufficient_bars_fails(self):
        from michael.types import SymbolData
        manifest = create_manifest("daily_bias")
        manifest.symbols["NQ1!"] = {
            "D": SymbolData(symbol="NQ1!", timeframe="D", bars=[
                BarData("2026-04-14", 100, 110, 90, 105, 1000) for _ in range(5)  # 少于阈值
            ])
        }
        assert evaluate_integrity(manifest) == ManifestIntegrity.FAIL

    def test_nq_ok_others_missing_partial(self):
        from michael.types import SymbolData
        manifest = create_manifest("daily_bias")
        manifest.symbols["NQ1!"] = {
            "D": SymbolData(symbol="NQ1!", timeframe="D", bars=[
                BarData("2026-04-14", 100, 110, 90, 105, 1000) for _ in range(20)
            ])
        }
        manifest.symbols["ES1!"] = {
            "D": SymbolData(symbol="ES1!", timeframe="D", bars=[
                BarData("2026-04-14", 100, 110, 90, 105, 1000) for _ in range(5)  # 不足
            ])
        }
        assert evaluate_integrity(manifest) == ManifestIntegrity.PARTIAL

    def test_all_good_passes(self):
        from michael.types import SymbolData
        manifest = create_manifest("daily_bias")
        bars20 = [BarData(f"2026-04-{i+1:02d}", 100, 110, 90, 105, 1000) for i in range(20)]
        manifest.symbols["NQ1!"] = {"D": SymbolData(symbol="NQ1!", timeframe="D", bars=bars20)}
        manifest.symbols["ES1!"] = {"D": SymbolData(symbol="ES1!", timeframe="D", bars=bars20)}
        assert evaluate_integrity(manifest) == ManifestIntegrity.PASS


class TestCollectorRPC:
    def test_connect_missing_server_raises(self, tmp_path):
        config = Config(mcp_server_dir=tmp_path / "nonexistent")
        collector = Collector(config)
        with pytest.raises(CollectorError):
            collector.connect()

    def test_collect_ohlcv_parse_bars(self):
        """验证 bars 解析逻辑（mock 返回 JSON 字符串）"""
        config = Config()
        collector = Collector(config)

        mock_json = json.dumps({
            "bars": [
                {"time": "2026-04-14T09:00", "open": 21500, "high": 21520,
                 "low": 21490, "close": 21515, "volume": 1000},
                {"time": "2026-04-14T10:00", "open": 21515, "high": 21540,
                 "low": 21510, "close": 21530, "volume": 1200},
            ]
        })
        collector._call_tool = MagicMock(return_value=mock_json)

        bars = collector.collect_ohlcv("NQ1!", "H1", 2)
        assert len(bars) == 2
        assert bars[0].open == 21500
        assert bars[0].high == 21520
        assert bars[1].close == 21530

    def test_collect_ohlcv_handles_mcp_error(self):
        config = Config()
        collector = Collector(config)

        collector._call_tool = MagicMock(side_effect=MCPError(-1, "test error"))
        bars = collector.collect_ohlcv("NQ1!", "H1", 10)
        assert bars == []

    def test_collect_ohlcv_handles_malformed_data(self):
        config = Config()
        collector = Collector(config)

        # 返回非 JSON 字符串 — 应返回空列表
        collector._call_tool = MagicMock(return_value="not json text")
        bars = collector.collect_ohlcv("NQ1!", "H1", 10)
        assert bars == []


class TestCollectForReport:
    def test_returns_manifest_with_errors_when_server_missing(self, tmp_path):
        config = Config(mcp_server_dir=tmp_path / "nonexistent")
        collector = Collector(config)
        # 不应抛异常，而是将错误记录到 manifest.errors
        try:
            manifest = collector.collect_for_report("daily_bias", ["NQ1!"], timeframes=["D"])
            # 如果执行到这里，manifest 应该有错误
            assert manifest.integrity == ManifestIntegrity.FAIL
        except CollectorError:
            pass  # 也可接受直接抛出


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
