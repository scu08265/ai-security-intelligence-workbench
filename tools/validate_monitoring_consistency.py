"""Compare page, reliability JSON, and Markdown monitoring metrics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import competition_scorecard, config, reliability, storage  # noqa: E402


def _markdown_number(text: str, label: str) -> int | None:
    match = re.search(rf"{re.escape(label)}：(\d+) 天", text)
    return int(match.group(1)) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--markdown",
        type=Path,
        default=ROOT / "reports" / "7-day-continuous-run-report.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "monitoring-metrics-consistency.json",
    )
    args = parser.parse_args()

    report = reliability.build_reliability_report(days=args.days)
    page = competition_scorecard.scorecard()["monitoring_7d"]
    markdown = args.markdown.read_text(encoding="utf-8")
    json_metrics = {
        "actual_run_days": report["continuous_runs"]["actual_run_days"],
        "scheduled_run_days": report["continuous_runs"]["scheduled_run_days"],
        "monitoring_started_at": report["timeliness"]["monitoring_started_at"],
        "baseline_excluded_samples": report["timeliness"]["baseline_excluded_samples"],
        "post_monitoring_samples": report["timeliness"]["post_monitoring_samples"],
        "effective_denominator": report["timeliness"]["effective_denominator"],
    }
    page_metrics = {
        "actual_run_days": page["actual_run_days"]["value"],
        "scheduled_run_days": page["scheduled_run_days"]["value"],
        "monitoring_started_at": page["monitoring_started_at"]["value"],
        "baseline_excluded_samples": page["baseline_excluded_samples"]["value"],
        "post_monitoring_samples": page["post_monitoring_samples"]["value"],
        "effective_denominator": page["effective_denominator"]["value"],
    }
    markdown_metrics = {
        "actual_run_days": _markdown_number(markdown, "实际采集运行天数"),
        "scheduled_run_days": _markdown_number(markdown, "计划任务运行天数"),
    }
    checks = {
        "page_matches_json": page_metrics == json_metrics,
        "markdown_actual_matches_json": (
            markdown_metrics["actual_run_days"] == json_metrics["actual_run_days"]
        ),
        "markdown_scheduled_matches_json": (
            markdown_metrics["scheduled_run_days"] == json_metrics["scheduled_run_days"]
        ),
    }
    payload: dict[str, Any] = {
        "version": config.APP_VERSION,
        "generated_at": storage.utcnow(),
        "json": json_metrics,
        "page": page_metrics,
        "markdown": markdown_metrics,
        "checks": checks,
        "consistent": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if payload["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
