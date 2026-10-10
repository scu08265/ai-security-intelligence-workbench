"""Scan local SQLite databases for a high-priority disposition cohort.

The 2026-10-08 brief states the production database already carried a
``total=34, closed=4`` high-priority cohort.  This tool looks for it.  For every
SQLite file under the given roots it reports row counts, the live affected
high-priority count, and the closure-rate cohort size using the application's
own cohort predicate, then writes ``cohort-search.json`` into the evidence
directory.  Read-only: nothing is written back to the scanned databases.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
HIGH_PRIORITIES = {"critical", "high"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cohort_predicate() -> Any:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app.disposition import _is_high_priority_cohort

    return _is_high_priority_cohort


def _inspect(path: Path, predicate: Any) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables = {
            row[0] for row in connection.execute("select name from sqlite_master where type='table'")
        }
        if "assessments" not in tables:
            return {"skipped": "no assessments table"}
        counts = {}
        for table in ("events", "assets", "assessments", "assessment_dispositions"):
            counts[table] = (
                connection.execute(f"select count(*) from {table}").fetchone()[0]
                if table in tables
                else None
            )
        assessments = []
        for event_id, asset_id, status, priority, doc in connection.execute(
            "select event_id, asset_id, status, priority, doc from assessments"
        ):
            record = json.loads(doc) if doc else {}
            record.update({"event_id": event_id, "asset_id": asset_id,
                           "status": status, "priority": priority})
            assessments.append(record)
        stored = {}
        if "assessment_dispositions" in tables:
            for event_id, asset_id, doc in connection.execute(
                "select event_id, asset_id, doc from assessment_dispositions"
            ):
                record = json.loads(doc) if doc else {}
                record.update({"event_id": event_id, "asset_id": asset_id})
                stored[f"{event_id}::{asset_id}"] = record
    finally:
        connection.close()

    cohort = []
    for assessment in assessments:
        key = f"{assessment.get('event_id')}::{assessment.get('asset_id')}"
        disposition = dict(stored.get(key) or {})
        disposition.setdefault("status", "open")
        if predicate({"assessment": assessment, "disposition": disposition}):
            cohort.append((assessment, disposition))
    closed = [item for item in cohort if item[1].get("status") in {"verified", "accepted"}]
    verified = [item for item in cohort if item[1].get("status") == "verified"]
    return {
        "row_counts": counts,
        "affected_high_priority": sum(
            1 for item in assessments
            if item.get("status") == "affected" and item.get("priority") in HIGH_PRIORITIES
        ),
        "cohort_size": len(cohort),
        "cohort_closed": len(closed),
        "cohort_verified": len(verified),
        "closure_rate": round(len(closed) / len(cohort), 4) if cohort else None,
        "disposition_status_breakdown": _breakdown(cohort),
    }


def _breakdown(cohort: list[tuple[dict, dict]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, disposition in cohort:
        status = str(disposition.get("status") or "open")
        counts[status] = counts.get(status, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path, default=[ROOT])
    parser.add_argument("--expected-cohort", type=int, default=34)
    parser.add_argument(
        "--evidence-dir", type=Path,
        default=ROOT / "artifacts" / "a_eval" / "disposition-live-closure-20261008",
    )
    args = parser.parse_args()

    roots = [path.resolve() for path in (args.roots or [ROOT])]
    predicate = _cohort_predicate()
    results = []
    seen = set()
    for root in roots:
        for candidate in sorted(root.rglob("*.sqlite")):
            if candidate in seen:
                continue
            seen.add(candidate)
            entry: dict[str, Any] = {
                "path": str(candidate),
                "size_bytes": candidate.stat().st_size,
            }
            try:
                entry.update(_inspect(candidate, predicate))
            except Exception as exc:  # pragma: no cover - unreadable/locked files
                entry["error"] = f"{type(exc).__name__}: {exc}"
            results.append(entry)

    matching = [item for item in results if item.get("cohort_size") == args.expected_cohort]
    payload = {
        "generated_at": _utcnow(),
        "expected_cohort_size": args.expected_cohort,
        "search_roots": [str(root) for root in roots],
        "databases_scanned": len(results),
        "databases": results,
        "summary": {
            "databases_with_any_disposition": [
                item["path"] for item in results if (item.get("row_counts") or {}).get(
                    "assessment_dispositions"
                )
            ],
            "largest_cohort_found": max(
                (item.get("cohort_size") or 0 for item in results), default=0
            ),
            "databases_matching_expected_cohort": [item["path"] for item in matching],
            "conclusion": (
                f"本机没有任何数据库包含 {args.expected_cohort} 条高优先级闭环队列；"
                "任务书中的 34 / 4 / 11.76% 基线无法在本机复现，本轮改为交付可复现的等价证据。"
                if not matching else
                f"找到 {len(matching)} 个数据库与 {args.expected_cohort} 条队列口径一致。"
            ),
        },
    }
    target = args.evidence_dir.resolve() / "cohort-search.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "written": str(target),
        "databases_scanned": payload["databases_scanned"],
        "largest_cohort_found": payload["summary"]["largest_cohort_found"],
        "matches": payload["summary"]["databases_matching_expected_cohort"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
