"""Dispatch 模块测试"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from michael.config import Config, ReportType
from michael.types import (
    AnalysisResult, StepResult, SupervisionReport, CheckResult,
    GateStatus, Severity,
)
from michael.dispatch import (
    Publisher, MultiPublisher, FeishuPublisher, CardColor,
    LocalMarkdownPublisher, persist_analysis_result,
)
from michael.dispatch.feishu import DEFAULT_COLOR_BY_REPORT


def make_result(report_type: str = "daily_bias", direction: str = "SHORT",
                gate: GateStatus = GateStatus.PASS) -> AnalysisResult:
    """构造测试用 AnalysisResult"""
    result = AnalysisResult(report_type=report_type, final_gate=gate)
    result.steps.append(StepResult(
        step_name="bias",
        report_type=report_type,
        gate_status=gate,
        output={
            "direction": direction,
            "confidence": "HIGH",
            "narrative_summary": "测试叙事内容用于验证渲染",
        },
    ))
    result.steps.append(StepResult(
        step_name="dol_framework",
        report_type=report_type,
        gate_status=gate,
        output={"primary_dol": {"price": 21320}},
    ))
    return result


def make_supervision(warnings: int = 0, failures: int = 0) -> SupervisionReport:
    checks = []
    for i in range(warnings):
        checks.append(CheckResult(
            check_name=f"warn_{i}", category="hallucination",
            severity=Severity.WARN, message=f"warning {i}",
        ))
    for i in range(failures):
        checks.append(CheckResult(
            check_name=f"fail_{i}", category="rule",
            severity=Severity.FAIL, message=f"failure {i}",
        ))
    report = SupervisionReport(checks=checks)
    report.compute_overall()
    return report


# ─── FeishuPublisher 测试 ───

class TestFeishuColorChoice:

    def test_long_bias_green(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(direction="LONG")
        sup = make_supervision()
        color = pub._choose_color(ReportType.DAILY_BIAS, result, sup)
        assert color == CardColor.GREEN

    def test_short_bias_red(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(direction="SHORT")
        sup = make_supervision()
        color = pub._choose_color(ReportType.DAILY_BIAS, result, sup)
        assert color == CardColor.RED

    def test_blocked_grey(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(direction="SHORT", gate=GateStatus.NO_TRADE)
        sup = make_supervision(failures=1)
        color = pub._choose_color(ReportType.DAILY_BIAS, result, sup)
        assert color == CardColor.GREY

    def test_weekly_prep_purple(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(report_type="weekly_prep", direction="NEUTRAL")
        sup = make_supervision()
        color = pub._choose_color(ReportType.WEEKLY_PREP, result, sup)
        assert color == CardColor.PURPLE

    def test_nyam_open_orange(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(report_type="nyam_open", direction="NEUTRAL")
        sup = make_supervision()
        color = pub._choose_color(ReportType.NYAM_OPEN, result, sup)
        assert color == CardColor.ORANGE


class TestFeishuCardBuild:

    def test_card_structure(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(direction="SHORT")
        sup = make_supervision(warnings=1)

        card = pub._build_interactive_card(result, sup, {"date": "2026-04-15"}, CardColor.RED)

        assert card["msg_type"] == "interactive"
        assert "card" in card
        header = card["card"]["header"]
        assert "DAILY_BIAS" in header["title"]["content"]
        assert header["template"] == "red"
        # 应包含元素
        assert len(card["card"]["elements"]) > 0

    def test_card_includes_warnings(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result()
        sup = make_supervision(warnings=2)

        card = pub._build_interactive_card(result, sup, {"date": "2026-04-15"}, CardColor.BLUE)
        # 应有 Guardian 提示元素
        text_elements = [e for e in card["card"]["elements"]
                          if e.get("tag") == "div" and "warning" in str(e).lower()]
        # 检查包含 warning 文字
        all_text = json.dumps(card, ensure_ascii=False)
        assert "warning 0" in all_text or "Guardian" in all_text

    def test_card_blocked_indicator(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(gate=GateStatus.NO_TRADE)
        sup = make_supervision(failures=2)

        card = pub._build_interactive_card(result, sup, {"date": "2026-04-15"}, CardColor.GREY)
        all_text = json.dumps(card, ensure_ascii=False)
        assert "阻断" in all_text


class TestFeishuTextFallback:

    def test_text_includes_essentials(self):
        config = Config()
        pub = FeishuPublisher(config)
        result = make_result(direction="SHORT")
        sup = make_supervision()

        text = pub._build_text_fallback(result, sup, {"date": "2026-04-15"})
        assert "DAILY_BIAS" in text
        assert "Gate" in text
        assert "测试叙事" in text


class TestFeishuNoPushMode:

    def test_no_push_skips(self):
        config = Config(no_push=True, feishu_app_id="x", feishu_app_secret="y",
                        feishu_chat_ids=["chat_test"])
        pub = FeishuPublisher(config)
        result = make_result()
        sup = make_supervision()

        # 即使凭证齐全，no_push=True 应直接返回 True 不发送
        ok = pub.publish(result, sup, {"date": "2026-04-15"})
        assert ok is True


# ─── LocalMarkdownPublisher 测试 ───

class TestLocalMarkdown:

    def test_markdown_file_created(self, tmp_path):
        config = Config(project_dir=tmp_path)
        pub = LocalMarkdownPublisher(config)
        result = make_result()
        sup = make_supervision(warnings=1)

        ok = pub.publish(result, sup, {"date": "2026-04-15"})
        assert ok is True

        # 文件应存在
        report_dir = tmp_path / "reports" / "2026-04-15"
        assert report_dir.exists()
        files = list(report_dir.glob("daily_bias_*.md"))
        assert len(files) == 1

        content = files[0].read_text(encoding="utf-8")
        assert "DAILY_BIAS" in content
        assert "Gate 状态" in content
        assert "warning 0" in content  # Guardian 检查输出

    def test_markdown_renders_steps(self, tmp_path):
        config = Config(project_dir=tmp_path)
        pub = LocalMarkdownPublisher(config)
        result = make_result()
        sup = make_supervision()

        pub.publish(result, sup, {"date": "2026-04-15"})

        files = list((tmp_path / "reports" / "2026-04-15").glob("*.md"))
        content = files[0].read_text(encoding="utf-8")

        assert "### bias" in content
        assert "### dol_framework" in content


# ─── MultiPublisher 测试 ───

class TestMultiPublisher:

    def test_multiple_publishers_called(self):
        pub1 = MagicMock()
        pub1.publish.return_value = True
        pub1.__class__.__name__ = "Pub1"

        pub2 = MagicMock()
        pub2.publish.return_value = True
        pub2.__class__.__name__ = "Pub2"

        multi = MultiPublisher([pub1, pub2])
        result = make_result()
        sup = make_supervision()

        outcomes = multi.publish(result, sup, {})
        assert pub1.publish.called
        assert pub2.publish.called
        assert all(outcomes.values())

    def test_one_failure_does_not_stop_others(self):
        pub1 = MagicMock()
        pub1.publish.side_effect = Exception("boom")
        pub2 = MagicMock()
        pub2.publish.return_value = True

        multi = MultiPublisher([pub1, pub2])
        outcomes = multi.publish(make_result(), make_supervision(), {})

        assert pub2.publish.called  # 即使 pub1 抛异常 pub2 也应运行


# ─── Persist 测试 ───

class TestPersist:

    def test_persist_no_exception_and_db_created(self, tmp_path):
        """持久化函数应正常运行，DB 文件应创建"""
        result = make_result()
        sup = make_supervision()
        db_path = tmp_path / "test.db"

        info = persist_analysis_result(
            result, sup, db_path,
            system_version="A", date="2026-04-15",
        )

        # DB 文件应被创建
        assert db_path.exists()
        # 返回信息应包含必要字段
        assert "saved_steps" in info
        assert "guardian_blocked" in info
        assert info["guardian_blocked"] is False

    def test_persist_with_legacy_step_names(self, tmp_path):
        """使用旧的 step_name 应能保存到对应表"""
        from michael.types import AnalysisResult, StepResult, GateStatus
        result = AnalysisResult(report_type="daily_bias", final_gate=GateStatus.PASS)
        result.steps.append(StepResult(
            step_name="daily_bias",  # 匹配 Database.save_step_result 的旧 step 名
            report_type="daily_bias",
            gate_status=GateStatus.PASS,
            output={"direction": "SHORT", "key_levels": [21520, 21380]},
        ))

        sup = make_supervision()
        db_path = tmp_path / "test2.db"

        info = persist_analysis_result(result, sup, db_path, date="2026-04-15")
        assert info["saved_steps"] >= 1
        assert db_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
