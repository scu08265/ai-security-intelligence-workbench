"""A4 证据：逐日核对 trigger=scheduled 运行，并给出 target_met 的预计达成日期。

口径不另造：判定"当天是否有计划运行"直接复用 app.reliability 的
`kind in {collect, scheduled_collect}` + `detail.trigger == "scheduled"`，
与 /api/competition/scorecard 的 scheduled_run_days 同源。

用法：
    ./.venv/Scripts/python.exe tools/check_continuous_run.py --days 7
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config, reliability, storage  # noqa: E402


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _database_path() -> Path | None:
    value = getattr(config, "DB_PATH", None)
    if not isinstance(value, (str, Path)):
        return None
    candidate = Path(value)
    return candidate if candidate.is_absolute() else ROOT / candidate


def build_report(days: int, runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    runs = list(runs) if runs is not None else list(storage.list_runs(limit=None))
    evidence = reliability.continuous_run_evidence(days, runs)

    scheduled_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        if reliability._is_collect_run(run) and reliability._is_scheduled_run(run):
            started = str(run.get("started_at") or "")
            if started:
                scheduled_by_day[started[:10]].append(run)

    today = datetime.now(timezone.utc).date()
    window = [
        (today - timedelta(days=offset)).isoformat()
        for offset in range(days - 1, -1, -1)
    ]
    rows = []
    for day in window:
        day_runs = sorted(
            scheduled_by_day.get(day, []),
            key=lambda run: str(run.get("started_at") or ""),
        )
        rows.append({
            "date": day,
            "scheduled_run_count": len(day_runs),
            "statuses": [run.get("status") for run in day_runs],
            "run_ids": [run.get("id") for run in day_runs],
            "first_started_at": day_runs[0].get("started_at") if day_runs else None,
            "last_started_at": day_runs[-1].get("started_at") if day_runs else None,
        })

    missing = [row["date"] for row in rows if row["scheduled_run_count"] == 0]
    eta: str | None = None
    if missing:
        # 从最后一个缺口次日起，连续 days 天都有计划运行，窗口才成立。
        eta = (date.fromisoformat(max(missing)) + timedelta(days=days)).isoformat()

    database = _database_path()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "timezone_note": "日期按 UTC 切分，与 /api/competition/scorecard 的日界一致（本机为 UTC+8）。",
        "source": {
            "database": str(database) if database else None,
            "database_sha256": _sha256(database) if database else None,
            "rule": "kind in {collect, scheduled_collect} 且 detail.trigger == 'scheduled'",
        },
        "scorecard_view": {
            "target_days": evidence.get("target_days"),
            "cumulative_actual_run_days": evidence.get("actual_run_days"),
            "cumulative_scheduled_run_days": evidence.get("scheduled_run_days"),
            "consecutive_scheduled_days": evidence.get("consecutive_executed_days"),
            "scheduled_days_in_window": sum(
                1 for row in rows if row["scheduled_run_count"] > 0
            ),
            "target_met": evidence.get("target_met") and not missing,
            "note": (
                "cumulative_* 是累计不同自然日，与 /api/competition/scorecard 的 "
                "actual_run_days / scheduled_run_days 同源；scheduled_days_in_window 是 "
                f"{days} 天窗口内实际有计划运行的天数。"
            ),
        },
        "window": {
            "from": window[0],
            "to": window[-1],
            "days": rows,
            "days_missing_scheduled_run": missing,
        },
        "target_met_eta_utc": eta,
        "eta_note": (
            None if not missing else
            f"前提是自 {date.fromisoformat(max(missing)) + timedelta(days=1)} 起每天至少一次计划运行；"
            "机器休眠或关机期间计划任务不会补触发，缺口不会被回填。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "continuous-run-check.json",
    )
    args = parser.parse_args()

    report = build_report(args.days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\noutput: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
