"""SQLite 数据存储 — 分析结果持久化"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from michael.types import AnalysisResult, AuditResult, StepResult


class Database:
    """分析数据库，管理所有持久化操作"""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS weekly_prep (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        system_version TEXT DEFAULT 'A',
        ipda_ranges TEXT,
        bias TEXT,
        dol TEXT,
        narrative TEXT,
        key_levels TEXT,
        weekly_profile TEXT,
        raw_output TEXT,
        review_score REAL,
        review_notes TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_bias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        system_version TEXT DEFAULT 'A',
        direction TEXT,
        dol_analysis TEXT,
        key_levels TEXT,
        dxy_smt TEXT,
        seek_destroy TEXT,
        session_plan TEXT,
        raw_output TEXT,
        review_score REAL,
        review_notes TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS session_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        session_type TEXT NOT NULL,
        system_version TEXT DEFAULT 'A',
        direction TEXT,
        entry_model TEXT,
        key_levels TEXT,
        confidence TEXT,
        signal_entry REAL,
        signal_sl REAL,
        signal_tp REAL,
        raw_output TEXT,
        review_score REAL,
        review_notes TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS trade_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        session_type TEXT NOT NULL,
        system_version TEXT DEFAULT 'A',
        direction TEXT,
        entry_model TEXT,
        aplus_score INTEGER,
        entry_price REAL,
        stop_loss REAL,
        take_profit REAL,
        risk_reward REAL,
        result TEXT,
        pnl_points REAL,
        raw_output TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS daily_review (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        system_version TEXT DEFAULT 'A',
        direction_score INTEGER,
        key_level_score INTEGER,
        narrative_score INTEGER,
        actionability_score INTEGER,
        total_score INTEGER,
        lessons TEXT,
        weaknesses TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS audit_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        report_type TEXT NOT NULL,
        feedback_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE VIEW IF NOT EXISTS v_accuracy_stats AS
    SELECT
        system_version,
        COUNT(*) as total_reviews,
        AVG(total_score) as avg_score,
        AVG(direction_score) as avg_direction,
        AVG(key_level_score) as avg_levels,
        AVG(narrative_score) as avg_narrative,
        AVG(actionability_score) as avg_actionability
    FROM daily_review
    GROUP BY system_version;
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save_step_result(self, result: StepResult, date: str, system_version: str = "A") -> int:
        """根据步骤类型保存到对应表"""
        output = result.output

        if result.step_name == "weekly_narrative":
            return self._insert("weekly_prep", {
                "date": date,
                "system_version": system_version,
                "ipda_ranges": json.dumps(output.get("ipda_ranges", {})),
                "bias": output.get("bias", ""),
                "dol": output.get("dol", ""),
                "narrative": output.get("narrative", ""),
                "key_levels": json.dumps(output.get("key_levels", [])),
                "weekly_profile": output.get("weekly_profile", ""),
                "raw_output": result.raw_text,
                "created_at": result.created_at,
            })

        if result.step_name == "daily_bias":
            return self._insert("daily_bias", {
                "date": date,
                "system_version": system_version,
                "direction": output.get("direction", ""),
                "dol_analysis": json.dumps(output.get("dol_analysis", {})),
                "key_levels": json.dumps(output.get("key_levels", [])),
                "dxy_smt": json.dumps(output.get("dxy_smt", {})),
                "seek_destroy": output.get("seek_destroy", ""),
                "session_plan": json.dumps(output.get("session_plan", {})),
                "raw_output": result.raw_text,
                "created_at": result.created_at,
            })

        if result.step_name == "session_analysis":
            return self._insert("session_analysis", {
                "date": date,
                "session_type": result.report_type,
                "system_version": system_version,
                "direction": output.get("direction", ""),
                "entry_model": output.get("entry_model", ""),
                "key_levels": json.dumps(output.get("key_levels", [])),
                "confidence": output.get("confidence", ""),
                "signal_entry": output.get("signal_entry"),
                "signal_sl": output.get("signal_sl"),
                "signal_tp": output.get("signal_tp"),
                "raw_output": result.raw_text,
                "created_at": result.created_at,
            })

        if result.step_name == "signal_output":
            return self._insert("trade_signals", {
                "date": date,
                "session_type": result.report_type,
                "system_version": system_version,
                "direction": output.get("direction", ""),
                "entry_model": output.get("entry_model", ""),
                "aplus_score": output.get("aplus_score"),
                "entry_price": output.get("entry"),
                "stop_loss": output.get("stop_loss"),
                "take_profit": output.get("take_profit"),
                "risk_reward": output.get("risk_reward"),
                "raw_output": result.raw_text,
                "created_at": result.created_at,
            })

        return -1

    def save_audit(self, result: AuditResult, system_version: str = "A") -> int:
        return self._insert("daily_review", {
            "date": result.date,
            "system_version": system_version,
            "direction_score": result.score.direction,
            "key_level_score": result.score.key_levels,
            "narrative_score": result.score.narrative,
            "actionability_score": result.score.actionability,
            "total_score": result.score.total,
            "lessons": json.dumps(result.lessons),
            "weaknesses": json.dumps(result.systematic_weaknesses),
            "created_at": result.date,
        })

    def save_feedback(self, date: str, report_type: str, feedback_json: str) -> int:
        return self._insert("audit_feedback", {
            "date": date,
            "report_type": report_type,
            "feedback_json": feedback_json,
            "created_at": date,
        })

    def get_recent_feedback(self, limit: int = 5) -> list[dict]:
        cursor = self._conn.execute(
            "SELECT * FROM audit_feedback ORDER BY date DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_weekly(self, system_version: str = "A") -> dict | None:
        cursor = self._conn.execute(
            "SELECT * FROM weekly_prep WHERE system_version = ? ORDER BY date DESC LIMIT 1",
            (system_version,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_latest_daily(self, system_version: str = "A") -> dict | None:
        cursor = self._conn.execute(
            "SELECT * FROM daily_bias WHERE system_version = ? ORDER BY date DESC LIMIT 1",
            (system_version,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_accuracy_stats(self, system_version: str = "A") -> dict | None:
        cursor = self._conn.execute(
            "SELECT * FROM v_accuracy_stats WHERE system_version = ?",
            (system_version,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _insert(self, table: str, data: dict) -> int:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        cursor = self._conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        self._conn.commit()
        return cursor.lastrowid or -1
