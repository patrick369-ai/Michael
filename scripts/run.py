#!/usr/bin/env python3
"""Michael CLI 入口 — 执行分析报告

用法:
    python3 scripts/run.py <report_type> [--dry-run] [--no-push] [--no-guardian] [--verbose]

报告类型:
    weekly_prep | daily_bias | asia_pre | london_pre |
    nyam_pre | nyam_open | nypm_pre | daily_review | weekly_review
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加 src 到 PYTHONPATH（支持直接运行）
project_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_dir / "src"))

from michael.config import Config, ReportType, SYMBOLS, PRIMARY_SYMBOL, TIMEFRAMES
from michael.ingestion.collector import Collector
from michael.analyst import AnalystEngine
from michael.guardian import Supervisor
from michael.dispatch import (
    FeishuPublisher, LocalMarkdownPublisher, MultiPublisher,
    persist_analysis_result,
)
from michael.calculator import process_manifest
from michael.audit import FeedbackStore


def parse_args():
    parser = argparse.ArgumentParser(description="Michael ICT 分析系统")
    parser.add_argument("report_type", help="报告类型")
    parser.add_argument("--dry-run", action="store_true", help="不采集数据，不调用 Claude")
    parser.add_argument("--no-push", action="store_true", help="不推送到飞书")
    parser.add_argument("--no-guardian", action="store_true", help="跳过 Guardian 验证")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    parser.add_argument("--system-version", default="A", help="系统版本 A/B")
    return parser.parse_args()


def setup_logging(verbose: bool, log_dir: Path, report_type: str) -> None:
    """配置日志"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)


def main():
    args = parse_args()

    # 解析报告类型
    try:
        report_type = ReportType(args.report_type)
    except ValueError:
        valid = ", ".join(r.value for r in ReportType)
        print(f"错误: 未知报告类型 '{args.report_type}'")
        print(f"有效值: {valid}")
        return 2

    # 加载配置
    _load_env(project_dir / ".env")
    config = Config.from_env(
        dry_run=args.dry_run,
        no_push=args.no_push,
        no_guardian=args.no_guardian,
        verbose=args.verbose,
        system_version=args.system_version,
    )
    config.ensure_dirs()

    setup_logging(args.verbose, config.logs_dir, report_type.value)
    logger = logging.getLogger("michael.run")

    logger.info("=" * 60)
    logger.info(f"Michael 启动 | 报告类型: {report_type.value}")
    logger.info(f"dry_run={args.dry_run}, no_push={args.no_push}, no_guardian={args.no_guardian}")
    logger.info(f"系统版本: {args.system_version}")
    logger.info("=" * 60)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ─── Step 1: Ingestion ───
    if args.dry_run:
        logger.info("[dry-run] 跳过数据采集")
        from michael.types import DataManifest, ManifestIntegrity
        manifest = DataManifest(report_type=report_type.value, integrity=ManifestIntegrity.FAIL)
    else:
        logger.info("[Ingestion] 开始采集")
        collector = Collector(config)
        data_dir = config.data_dir / today
        manifest = collector.collect_for_report(
            report_type=report_type.value,
            symbols=[PRIMARY_SYMBOL, "DXY", "ES1!"],
            timeframes=TIMEFRAMES,
            bars_per_tf=50,
            data_dir=data_dir,
        )
        logger.info(f"[Ingestion] 完成 integrity={manifest.integrity.value}, bars={manifest.bar_count}")

    # ─── Step 2-4: Analysis Engine ───
    logger.info("[Analysis] 启动分析引擎")

    # 反馈注入
    feedback_store = FeedbackStore(config.advisor_db_path)
    try:
        audit_feedback = feedback_store.get_recent(limit=3)
    except Exception as e:
        logger.warning(f"读取反馈失败: {e}")
        audit_feedback = []

    if args.dry_run:
        logger.info("[dry-run] 跳过 LLM 调用，输出模拟结果")
        from michael.types import AnalysisResult, GateStatus, StepResult
        result = AnalysisResult(report_type=report_type.value, final_gate=GateStatus.PASS)
        result.steps.append(StepResult(
            step_name="bias",
            report_type=report_type.value,
            gate_status=GateStatus.PASS,
            output={"direction": "NEUTRAL", "confidence": "LOW",
                    "narrative_summary": "[dry-run] 未调用 LLM"},
        ))
    else:
        engine = AnalystEngine(config)
        result = engine.run(
            report_type=report_type,
            manifest=manifest,
            audit_feedback=audit_feedback,
        )

    logger.info(f"[Analysis] 完成 gate={result.final_gate.value}, steps={len(result.steps)}")

    # ─── Step 5: Guardian ───
    from michael.types import SupervisionReport, Severity
    if args.no_guardian:
        logger.info("[Guardian] 已禁用，跳过")
        supervision = SupervisionReport(overall=Severity.PASS)
    else:
        logger.info("[Guardian] 启动验证")
        calc_ctx = process_manifest(manifest, primary_symbol=config.primary_symbol)

        # 合并所有 step 输出为单一 LLM output 字典
        llm_output = {}
        for step in result.steps:
            llm_output[step.step_name] = step.output
        llm_output["gate_status"] = result.final_gate.value

        supervisor = Supervisor()
        supervision = supervisor.supervise(
            llm_output=llm_output,
            calc_context=calc_ctx.to_guardian_dict(),
            previous_results=None,
            external_context={},
        )
        logger.info(f"[Guardian] 完成 overall={supervision.overall.value}, "
                    f"warnings={len(supervision.warnings)}, failures={len(supervision.failures)}")

    # ─── Step 6: Dispatch ───
    logger.info("[Dispatch] 持久化 + 推送")

    metadata = {
        "date": today,
        "report_type": report_type.value,
        "system_version": args.system_version,
    }

    try:
        persist_info = persist_analysis_result(
            result, supervision, config.advisor_db_path,
            system_version=args.system_version, date=today,
        )
        logger.info(f"[Persist] {persist_info}")
    except Exception as e:
        logger.error(f"[Persist] 失败: {e}")

    # 推送
    if supervision.is_blocked:
        logger.warning("[Dispatch] Guardian 阻断，不推送到飞书")
        publishers = [LocalMarkdownPublisher(config)]
    else:
        publishers = [
            LocalMarkdownPublisher(config),
            FeishuPublisher(config),
        ]

    multi = MultiPublisher(publishers)
    outcomes = multi.publish(result, supervision, metadata)
    logger.info(f"[Dispatch] 结果: {outcomes}")

    logger.info("=" * 60)
    logger.info(f"Michael 完成 | gate={result.final_gate.value} | guardian={supervision.overall.value}")
    logger.info("=" * 60)

    # 退出码
    if result.final_gate.value == "FAIL":
        return 1
    return 0


def _load_env(env_file: Path) -> None:
    """加载 .env 文件到环境变量"""
    import os
    if not env_file.exists():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)


if __name__ == "__main__":
    sys.exit(main())
