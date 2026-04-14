"""核心数据类型 — 跨层共享的数据结构"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Severity(Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class GateStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NO_TRADE = "NO_TRADE"
    CAUTION = "CAUTION"


class ManifestIntegrity(Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"


# ─── Layer 1: Ingestion ───


@dataclass
class BarData:
    """单根 K 线"""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class SymbolData:
    """单品种单时间框架的数据"""
    symbol: str
    timeframe: str
    bars: list[BarData]
    file_path: str = ""


@dataclass
class DataManifest:
    """数据采集结果清单"""
    report_type: str
    collected_at: str = field(default_factory=lambda: _now_iso())
    symbols: dict[str, dict[str, SymbolData]] = field(default_factory=dict)
    integrity: ManifestIntegrity = ManifestIntegrity.PASS
    errors: list[str] = field(default_factory=list)

    def get_data(self, symbol: str, timeframe: str) -> SymbolData | None:
        return self.symbols.get(symbol, {}).get(timeframe)

    @property
    def bar_count(self) -> int:
        total = 0
        for sym_data in self.symbols.values():
            for tf_data in sym_data.values():
                total += len(tf_data.bars)
        return total


# ─── Layer 2: Analyst ───


@dataclass
class StepResult:
    """单步分析结果"""
    step_name: str
    report_type: str
    gate_status: GateStatus = GateStatus.PASS
    output: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    token_count: int = 0
    duration_seconds: float = 0.0
    created_at: str = field(default_factory=lambda: _now_iso())


@dataclass
class AnalysisResult:
    """完整分析结果（所有步骤）"""
    report_type: str
    steps: list[StepResult] = field(default_factory=list)
    final_gate: GateStatus = GateStatus.PASS
    created_at: str = field(default_factory=lambda: _now_iso())

    @property
    def is_blocked(self) -> bool:
        return self.final_gate in (GateStatus.FAIL, GateStatus.NO_TRADE)

    def last_step(self) -> StepResult | None:
        return self.steps[-1] if self.steps else None


# ─── Layer 3: Guardian ───


@dataclass
class CheckResult:
    """单项检查结果"""
    check_name: str
    category: str
    severity: Severity = Severity.PASS
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SupervisionReport:
    """Guardian 检查报告"""
    checks: list[CheckResult] = field(default_factory=list)
    overall: Severity = Severity.PASS

    @property
    def is_blocked(self) -> bool:
        return self.overall == Severity.FAIL

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.severity == Severity.WARN]

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.severity == Severity.FAIL]

    def compute_overall(self) -> None:
        if any(c.severity == Severity.FAIL for c in self.checks):
            self.overall = Severity.FAIL
        elif any(c.severity == Severity.WARN for c in self.checks):
            self.overall = Severity.WARN
        else:
            self.overall = Severity.PASS


# ─── Layer 4: Audit ───


@dataclass
class ScoreBreakdown:
    """4 维评分"""
    direction: int = 0       # 0-3
    key_levels: int = 0      # 0-3
    narrative: int = 0       # 0-2
    actionability: int = 0   # 0-2

    @property
    def total(self) -> int:
        return self.direction + self.key_levels + self.narrative + self.actionability

    @property
    def max_score(self) -> int:
        return 10


@dataclass
class AuditResult:
    """审计结果"""
    report_type: str
    date: str
    score: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    lessons: list[str] = field(default_factory=list)
    systematic_weaknesses: list[str] = field(default_factory=list)


@dataclass
class FeedbackPayload:
    """反馈载荷（注入下次分析）"""
    bias_cautions: list[str] = field(default_factory=list)
    session_adjustments: list[str] = field(default_factory=list)
    knowledge_emphasis: list[str] = field(default_factory=list)
    level_reminders: list[str] = field(default_factory=list)
    recent_accuracy: float = 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
