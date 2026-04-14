"""飞书交互卡片推送 — 5 色方案（绿/红/蓝/橙/紫） + 文本回退

继承自原版 ICT_Advisor 的 5 色设计：
  绿色 = 看多
  红色 = 看空
  蓝色 = 信息（周报、日报）
  橙色 = 修正/更新
  紫色 = 周度总结
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from michael.config import Config, ReportType
from michael.types import AnalysisResult, SupervisionReport, GateStatus, Severity

logger = logging.getLogger(__name__)


class CardColor(Enum):
    """飞书卡片颜色（5 色方案）"""
    GREEN = "green"     # 看多
    RED = "red"         # 看空
    BLUE = "blue"       # 信息
    ORANGE = "orange"   # 修正
    PURPLE = "purple"   # 周度
    GREY = "grey"       # 中性/审计


# 报告类型 → 默认颜色
DEFAULT_COLOR_BY_REPORT = {
    ReportType.WEEKLY_PREP: CardColor.PURPLE,
    ReportType.DAILY_BIAS: CardColor.BLUE,
    ReportType.ASIA_PRE: CardColor.BLUE,
    ReportType.LONDON_PRE: CardColor.BLUE,
    ReportType.NYAM_PRE: CardColor.BLUE,
    ReportType.NYAM_OPEN: CardColor.ORANGE,
    ReportType.NYPM_PRE: CardColor.BLUE,
    ReportType.DAILY_REVIEW: CardColor.GREY,
    ReportType.WEEKLY_REVIEW: CardColor.PURPLE,
}


class FeishuAPIError(Exception):
    """飞书 API 错误"""
    pass


class FeishuPublisher:
    """飞书消息推送"""

    TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    SEND_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"

    def __init__(self, config: Config):
        self._config = config
        self._app_id = config.feishu_app_id
        self._app_secret = config.feishu_app_secret
        self._chat_ids = config.feishu_chat_ids
        self._cached_token: Optional[str] = None

    def publish(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
    ) -> bool:
        """推送到所有配置的飞书群"""
        if self._config.no_push:
            logger.info("no_push 模式，跳过飞书推送")
            return True

        if not self._app_id or not self._app_secret or not self._chat_ids:
            logger.warning("飞书凭证或群 ID 未配置，跳过推送")
            return False

        # 选择颜色
        report_type = self._parse_report_type(result.report_type)
        color = self._choose_color(report_type, result, supervision)

        # 构建卡片
        card = self._build_interactive_card(result, supervision, metadata, color)

        # 推送到所有群
        success_count = 0
        for chat_id in self._chat_ids:
            try:
                self._send_card(chat_id, card)
                success_count += 1
            except FeishuAPIError as e:
                logger.error(f"卡片发送失败 chat={chat_id}: {e}，尝试文本回退")
                # 文本回退
                try:
                    self._send_text(chat_id, self._build_text_fallback(result, supervision, metadata))
                    success_count += 1
                except FeishuAPIError as e2:
                    logger.error(f"文本回退也失败 chat={chat_id}: {e2}")

        return success_count > 0

    def _choose_color(
        self,
        report_type: Optional[ReportType],
        result: AnalysisResult,
        supervision: SupervisionReport,
    ) -> CardColor:
        """根据报告内容选择颜色"""
        # 阻断状态特殊处理
        if supervision.is_blocked or result.final_gate == GateStatus.NO_TRADE:
            return CardColor.GREY

        # 提取 Bias 方向
        bias = self._extract_bias(result)
        if bias == "LONG":
            return CardColor.GREEN
        if bias == "SHORT":
            return CardColor.RED

        # 默认按报告类型
        if report_type:
            return DEFAULT_COLOR_BY_REPORT.get(report_type, CardColor.BLUE)
        return CardColor.BLUE

    def _extract_bias(self, result: AnalysisResult) -> Optional[str]:
        """从 result 的 steps 中提取 bias 方向"""
        for step in result.steps:
            if step.step_name in ("bias", "framing"):
                output = step.output
                # 直接顶层
                direction = output.get("direction")
                if direction:
                    return direction.upper()
                # 嵌套
                bias_obj = output.get("bias", {})
                if isinstance(bias_obj, dict):
                    direction = bias_obj.get("direction")
                    if direction:
                        return direction.upper()
        return None

    @staticmethod
    def _parse_report_type(value: str) -> Optional[ReportType]:
        try:
            return ReportType(value)
        except ValueError:
            return None

    def _build_interactive_card(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
        color: CardColor,
    ) -> dict:
        """构建飞书交互卡片"""
        report_type = result.report_type
        date = metadata.get("date", "")
        bias = self._extract_bias(result) or "—"

        title = f"📊 {report_type.upper()} | {date}"

        # 主要内容元素
        elements = []

        # 总结
        narrative = self._extract_narrative(result)
        if narrative:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**核心叙事：** {narrative}"},
            })
            elements.append({"tag": "hr"})

        # 关键字段
        key_fields = self._build_key_fields(result, supervision)
        if key_fields:
            elements.append({
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**{k}：** {v}"}}
                    for k, v in key_fields
                ],
            })

        # Guardian 警告
        if supervision.warnings or supervision.failures:
            warnings_text = "\n".join([
                f"• {w.message}" for w in (supervision.failures + supervision.warnings)[:5]
            ])
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⚠️ **Guardian 提示：**\n{warnings_text}",
                },
            })

        # 阻断状态
        if supervision.is_blocked:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"🚫 **报告被 Guardian 阻断**（{result.final_gate.value}）",
                },
            })

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color.value,
                },
                "elements": elements,
            },
        }

    @staticmethod
    def _extract_narrative(result: AnalysisResult) -> str:
        """提取叙事摘要"""
        for step in result.steps:
            for key in ("narrative_summary", "story", "summary", "reasoning"):
                value = step.output.get(key)
                if isinstance(value, str) and len(value) > 10:
                    return value[:200]
        return ""

    @staticmethod
    def _build_key_fields(result: AnalysisResult, supervision: SupervisionReport) -> list[tuple[str, str]]:
        """提取关键字段（直接对 Bias / DOL / Entry / SL / TP / R:R）"""
        fields: list[tuple[str, str]] = []

        for step in result.steps:
            output = step.output
            if step.step_name == "bias":
                direction = output.get("direction") or output.get("bias", {}).get("direction")
                confidence = output.get("confidence") or output.get("bias", {}).get("confidence")
                if direction:
                    fields.append(("方向", f"{direction} ({confidence or 'N/A'})"))

            elif step.step_name == "dol_framework":
                dol = output.get("primary_dol") or output.get("q3_where_to", {}).get("primary_dol", {})
                if isinstance(dol, dict) and dol.get("price"):
                    fields.append(("DOL", str(dol["price"])))

            elif step.step_name == "trade_plan":
                if output.get("entry"):
                    fields.append(("Entry", str(output["entry"])))
                if output.get("stop_loss"):
                    fields.append(("SL", str(output["stop_loss"])))
                if output.get("risk_reward"):
                    fields.append(("R:R", f"{output['risk_reward']:.2f}"))

        # Gate 状态
        fields.append(("Gate", result.final_gate.value))
        fields.append(("Guardian", supervision.overall.value))
        return fields

    def _build_text_fallback(
        self,
        result: AnalysisResult,
        supervision: SupervisionReport,
        metadata: dict,
    ) -> str:
        """构建纯文本回退"""
        lines = [
            f"📊 {result.report_type.upper()} | {metadata.get('date', '')}",
            f"Gate: {result.final_gate.value}",
            f"Guardian: {supervision.overall.value}",
        ]
        narrative = self._extract_narrative(result)
        if narrative:
            lines.append(f"\n{narrative}")
        for k, v in self._build_key_fields(result, supervision):
            lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _send_card(self, chat_id: str, card: dict) -> None:
        """发送卡片到指定群"""
        token = self._get_access_token()
        body = {
            "receive_id": chat_id,
            "msg_type": card["msg_type"],
            "content": json.dumps(card["card"], ensure_ascii=False),
        }
        self._http_post(self.SEND_MESSAGE_URL, body, token)

    def _send_text(self, chat_id: str, text: str) -> None:
        """发送纯文本"""
        token = self._get_access_token()
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }
        self._http_post(self.SEND_MESSAGE_URL, body, token)

    def _get_access_token(self) -> str:
        """获取 tenant_access_token"""
        if self._cached_token:
            return self._cached_token

        body = {"app_id": self._app_id, "app_secret": self._app_secret}
        response = self._http_post(self.TOKEN_URL, body)
        token = response.get("tenant_access_token")
        if not token:
            raise FeishuAPIError(f"无法获取 access_token: {response}")
        self._cached_token = token
        return token

    @staticmethod
    def _http_post(url: str, body: dict, token: Optional[str] = None) -> dict:
        """发送 POST 请求"""
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_text = resp.read().decode("utf-8")
                resp_data = json.loads(resp_text)
                if resp_data.get("code", 0) != 0:
                    raise FeishuAPIError(f"飞书 API 错误: {resp_data}")
                return resp_data.get("data", {})
        except urllib.error.URLError as e:
            raise FeishuAPIError(f"HTTP 错误: {e}") from e
