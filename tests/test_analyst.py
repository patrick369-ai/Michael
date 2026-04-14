"""Analysis Engine 测试 — 用 MockClaudeCLI 验证端到端流程"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.config import Config, ReportType
from michael.types import (
    DataManifest, BarData, SymbolData, GateStatus, ManifestIntegrity,
)
from michael.analyst import (
    AnalystEngine, MockClaudeCLI, PromptBuilder, REPORT_SKILLS,
)
from michael.analyst.claude_cli import ClaudeCLI


# ─── 测试辅助 ───

def make_bar(ts: str, o: float, h: float, l: float, c: float) -> BarData:
    return BarData(timestamp=ts, open=o, high=h, low=l, close=c, volume=1000)


def build_full_manifest(report_type: str = "daily_bias") -> DataManifest:
    """构造完整的 manifest（NQ + 多 TF）"""
    manifest = DataManifest(report_type=report_type, integrity=ManifestIntegrity.PASS)

    daily_bars = [
        make_bar(f"2026-03-{i+1:02d}", 21000 + i * 5, 21020 + i * 5, 20990 + i * 5, 21010 + i * 5)
        for i in range(25)
    ]
    weekly_bars = [
        make_bar("2026-W14", 21300, 21600, 21250, 21480),
        make_bar("2026-W15", 21480, 21650, 21400, 21540),
    ]
    h1_bars = [
        make_bar(f"2026-04-14T{i:02d}:00", 21500 + i, 21510 + i, 21490 + i, 21505 + i)
        for i in range(20)
    ]

    manifest.symbols["NQ1!"] = {
        "D": SymbolData(symbol="NQ1!", timeframe="D", bars=daily_bars),
        "W": SymbolData(symbol="NQ1!", timeframe="W", bars=weekly_bars),
        "H1": SymbolData(symbol="NQ1!", timeframe="H1", bars=h1_bars),
    }
    return manifest


def mock_response(gate: str = "PASS", **extra) -> str:
    """生成 mock 的 JSON 响应"""
    data = {
        "gate_status": gate,
        "narrative_summary": "test summary",
        "context": {"ipda_position": "premium"},
        "narrative": {"po3_phase": "distribution"},
        "bias": {"direction": "SHORT", "confidence": "HIGH"},
        "weekly_profile": {"matched_profile": "Classic Expansion"},
        "daily_profile": {"matched_profile": "London Reversal"},
        "pda_scan": {"pda_zones": []},
        "dol_framework": {"primary_dol": {"price": 21320}},
        **extra,
    }
    return f"```json\n{json.dumps(data)}\n```"


# ─── ClaudeCLI 测试 ───

class TestClaudeCLIExtraction:

    def test_extract_json_from_fenced_block(self):
        text = '前面文本\n```json\n{"key": "value"}\n```\n后面文本'
        cfg = Config()
        cli = ClaudeCLI(cfg)
        result = cli._extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_from_bare_braces(self):
        text = '一些文本 {"key": "value", "n": 42} 后面'
        cfg = Config()
        cli = ClaudeCLI(cfg)
        result = cli._extract_json(text)
        assert result == {"key": "value", "n": 42}

    def test_extract_json_returns_empty_on_no_json(self):
        text = '没有 JSON 的纯文本'
        cfg = Config()
        cli = ClaudeCLI(cfg)
        result = cli._extract_json(text)
        assert result == {}

    def test_extract_json_handles_nested(self):
        text = '```json\n{"a": {"b": [1, 2, 3]}}\n```'
        cfg = Config()
        cli = ClaudeCLI(cfg)
        result = cli._extract_json(text)
        assert result == {"a": {"b": [1, 2, 3]}}

    def test_validate_schema_required_present(self):
        cfg = Config()
        cli = ClaudeCLI(cfg)
        schema = {"required": ["a", "b"]}
        assert cli._validate_schema({"a": 1, "b": 2}, schema) is True

    def test_validate_schema_required_missing(self):
        cfg = Config()
        cli = ClaudeCLI(cfg)
        schema = {"required": ["a", "b"]}
        assert cli._validate_schema({"a": 1}, schema) is False


# ─── PromptBuilder 测试 ───

class TestPromptBuilder:

    def test_load_skill_caches(self, tmp_path):
        config = Config(project_dir=Path("/home/patrick/Michael"))
        pb = PromptBuilder(config)
        # 加载 bias.md
        content = pb._load_skill("framing/bias")
        assert "Bias" in content
        assert "知识来源" not in content  # 应被精简掉

    def test_load_skill_missing_returns_empty(self):
        config = Config(project_dir=Path("/home/patrick/Michael"))
        pb = PromptBuilder(config)
        content = pb._load_skill("nonexistent/skill")
        assert content == ""

    def test_get_merged_schema_includes_all_skills(self):
        config = Config(project_dir=Path("/home/patrick/Michael"))
        pb = PromptBuilder(config)
        schema = pb.get_merged_schema(ReportType.DAILY_BIAS)
        # 应包含 daily_bias 的所有 skill keys
        skills = REPORT_SKILLS[ReportType.DAILY_BIAS]
        for skill in skills:
            key = skill.split("/")[-1]
            assert key in schema["properties"]
        assert "gate_status" in schema["required"]

    def test_build_merged_includes_skills_and_data(self):
        config = Config(project_dir=Path("/home/patrick/Michael"))
        pb = PromptBuilder(config)
        manifest = build_full_manifest()
        from michael.analyst.prompt_builder import make_manifest_summary

        prompt = pb.build_merged(
            report_type=ReportType.DAILY_BIAS,
            steps=[],
            manifest_summary=make_manifest_summary(manifest),
            calculated_context={"current_price": 21500, "key_levels": {"PDH": 21520}},
            previous_results={"weekly": {"bias": "SHORT"}},
            audit_feedback=["lesson 1", "lesson 2"],
        )

        assert "ICT" in prompt
        assert "已计算数据" in prompt
        assert "21500" in prompt or "21520" in prompt
        assert "市场数据文件" in prompt
        assert "前序分析引用" in prompt
        assert "近期审计教训" in prompt
        assert "lesson 1" in prompt


# ─── AnalystEngine 端到端测试 ───

class TestAnalystEngineEndToEnd:

    def test_audit_report_skips_llm(self):
        """Audit 报告不调用 Claude"""
        config = Config()
        mock_cli = MockClaudeCLI(config, mock_responses=["should not be called"])
        engine = AnalystEngine(config, claude_cli=mock_cli)

        manifest = build_full_manifest("daily_review")
        result = engine.run(ReportType.DAILY_REVIEW, manifest)

        assert result.final_gate == GateStatus.PASS
        assert mock_cli._call_count == 0

    def test_daily_bias_merged_call(self):
        """daily_bias 应该是单次调用合并模式"""
        config = Config(project_dir=Path("/home/patrick/Michael"))
        mock_cli = MockClaudeCLI(config, mock_responses=[mock_response("PASS")])
        engine = AnalystEngine(config, claude_cli=mock_cli)

        manifest = build_full_manifest("daily_bias")
        result = engine.run(ReportType.DAILY_BIAS, manifest)

        # 应该只调用一次（合并模式）
        assert mock_cli._call_count == 1
        assert result.final_gate == GateStatus.PASS
        # 应有多个 Skill 的 StepResult
        assert len(result.steps) > 0

    def test_gate_fail_propagates(self):
        """LLM 输出 FAIL 应正确传递"""
        config = Config(project_dir=Path("/home/patrick/Michael"))
        mock_cli = MockClaudeCLI(config, mock_responses=[mock_response("FAIL")])
        engine = AnalystEngine(config, claude_cli=mock_cli)

        manifest = build_full_manifest("daily_bias")
        result = engine.run(ReportType.DAILY_BIAS, manifest)

        assert result.final_gate == GateStatus.FAIL

    def test_signal_report_two_stage_pass(self):
        """nyam_pre PASS 应触发 Stage 2 调用（共 2 次）"""
        config = Config(project_dir=Path("/home/patrick/Michael"))
        responses = [
            mock_response("PASS"),  # Stage 1
            mock_response("PASS", trade_plan={"entry_zone": {}}),  # Stage 2
        ]
        mock_cli = MockClaudeCLI(config, mock_responses=responses)
        engine = AnalystEngine(config, claude_cli=mock_cli)

        manifest = build_full_manifest("nyam_pre")
        result = engine.run(ReportType.NYAM_PRE, manifest)

        assert mock_cli._call_count == 2
        assert result.final_gate == GateStatus.PASS

    def test_signal_report_stage1_fail_skips_stage2(self):
        """nyam_pre Stage 1 FAIL 应跳过 Stage 2"""
        config = Config(project_dir=Path("/home/patrick/Michael"))
        mock_cli = MockClaudeCLI(config, mock_responses=[mock_response("FAIL")])
        engine = AnalystEngine(config, claude_cli=mock_cli)

        manifest = build_full_manifest("nyam_pre")
        result = engine.run(ReportType.NYAM_PRE, manifest)

        assert mock_cli._call_count == 1  # 只调用了 Stage 1
        assert result.final_gate == GateStatus.FAIL

    def test_signal_report_no_trade_skips_stage2(self):
        """Stage 1 NO_TRADE 也应跳过 Stage 2"""
        config = Config(project_dir=Path("/home/patrick/Michael"))
        mock_cli = MockClaudeCLI(config, mock_responses=[mock_response("NO_TRADE")])
        engine = AnalystEngine(config, claude_cli=mock_cli)

        manifest = build_full_manifest("nyam_pre")
        result = engine.run(ReportType.NYAM_PRE, manifest)

        assert mock_cli._call_count == 1
        assert result.final_gate == GateStatus.NO_TRADE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
