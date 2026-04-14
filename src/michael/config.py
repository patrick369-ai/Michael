"""配置中心 — 环境变量驱动，无硬编码路径"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ReportType(Enum):
    WEEKLY_PREP = "weekly_prep"
    DAILY_BIAS = "daily_bias"
    ASIA_PRE = "asia_pre"
    LONDON_PRE = "london_pre"
    NYAM_PRE = "nyam_pre"
    NYAM_OPEN = "nyam_open"
    NYPM_PRE = "nypm_pre"
    DAILY_REVIEW = "daily_review"
    WEEKLY_REVIEW = "weekly_review"


class StepName(Enum):
    WEEKLY_NARRATIVE = "weekly_narrative"
    DAILY_BIAS = "daily_bias"
    SESSION_ANALYSIS = "session_analysis"
    LTF_EXECUTION = "ltf_execution"
    SIGNAL_OUTPUT = "signal_output"


# 报告类型 → 需要执行的步骤
REPORT_STEP_MAP: dict[ReportType, list[StepName]] = {
    ReportType.WEEKLY_PREP: [StepName.WEEKLY_NARRATIVE],
    ReportType.DAILY_BIAS: [StepName.WEEKLY_NARRATIVE, StepName.DAILY_BIAS],
    ReportType.ASIA_PRE: [StepName.DAILY_BIAS, StepName.SESSION_ANALYSIS],
    ReportType.LONDON_PRE: [StepName.DAILY_BIAS, StepName.SESSION_ANALYSIS],
    ReportType.NYAM_PRE: [
        StepName.DAILY_BIAS,
        StepName.SESSION_ANALYSIS,
        StepName.LTF_EXECUTION,
        StepName.SIGNAL_OUTPUT,
    ],
    ReportType.NYAM_OPEN: [StepName.SESSION_ANALYSIS],
    ReportType.NYPM_PRE: [StepName.DAILY_BIAS, StepName.SESSION_ANALYSIS],
    ReportType.DAILY_REVIEW: [],   # Audit 流程，不走分析步骤
    ReportType.WEEKLY_REVIEW: [],  # Audit 流程
}

# 时间框架
TIMEFRAMES = ["W", "D", "H4", "H1", "M15", "M5", "M1"]

# 品种
SYMBOLS = ["NQ1!", "ES1!", "YM1!", "GC1!", "SI1!", "CL1!", "DXY"]
PRIMARY_SYMBOL = "NQ1!"
SCAN_SYMBOLS = ["ES1!", "YM1!", "GC1!", "SI1!", "CL1!"]


@dataclass
class Config:
    """应用配置，所有路径通过环境变量或自动检测获取"""

    # 项目路径（自动检测）
    project_dir: Path = field(default_factory=lambda: _detect_project_dir())

    # Claude CLI
    claude_bin: str = field(default_factory=lambda: _detect_claude_bin())
    claude_timeout: int = 600     # 秒
    claude_max_turns: int = 5

    # TradingView MCP
    mcp_server_dir: Path = field(default_factory=lambda: _detect_mcp_dir())

    # 飞书
    feishu_app_id: str = field(default_factory=lambda: os.environ.get("FEISHU_APP_ID", ""))
    feishu_app_secret: str = field(default_factory=lambda: os.environ.get("FEISHU_APP_SECRET", ""))
    feishu_chat_ids: list[str] = field(default_factory=lambda: _parse_chat_ids())

    # 交易参数
    primary_symbol: str = PRIMARY_SYMBOL
    max_sl_points: int = 30
    system_version: str = "A"

    # 运行时控制
    dry_run: bool = False
    no_push: bool = False
    no_guardian: bool = False
    verbose: bool = False

    @property
    def data_dir(self) -> Path:
        return self.project_dir / "data"

    @property
    def logs_dir(self) -> Path:
        return self.project_dir / "logs"

    @property
    def db_dir(self) -> Path:
        return self.project_dir / "db"

    @property
    def knowledge_dir(self) -> Path:
        return self.project_dir / "knowledge"

    @property
    def advisor_db_path(self) -> Path:
        return self.db_dir / "ict_advisor.db"

    @property
    def market_db_path(self) -> Path:
        return self.db_dir / "market_data.db"

    def ensure_dirs(self) -> None:
        """确保运行时目录存在"""
        for d in [self.data_dir, self.logs_dir, self.db_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, **overrides) -> Config:
        """从环境变量构建配置，支持覆盖"""
        return cls(**overrides)


def _detect_project_dir() -> Path:
    """从当前文件位置向上查找项目根目录（含 CLAUDE.md 的目录）"""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "CLAUDE.md").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # 回退到 CWD
    return Path.cwd()


def _detect_claude_bin() -> str:
    """检测 Claude CLI 路径"""
    env_bin = os.environ.get("CLAUDE_BIN")
    if env_bin:
        return env_bin
    found = shutil.which("claude")
    return found or "claude"


def _detect_mcp_dir() -> Path:
    """检测 TradingView MCP 目录"""
    env_dir = os.environ.get("MCP_SERVER_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / "tradingview-mcp"


def _parse_chat_ids() -> list[str]:
    """解析飞书群 ID 列表"""
    raw = os.environ.get("FEISHU_CHAT_IDS", "")
    if not raw:
        return []
    return [cid.strip() for cid in raw.split(",") if cid.strip()]
