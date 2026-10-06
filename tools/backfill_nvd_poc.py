"""Backfill NVD-derived enrichment into already stored events.

This tool never creates an event and never changes source summaries.  For each
NVD record it merges two fields into the matching stored event:

* exact NVD ``Exploit`` references into ``poc``
* NVD CVSS metrics (v4.0 / v3.1 / v3.0 / v2) into ``cvss``

Merging CVSS matters because an event that reached the corpus via OSV/MITRE/KEV
carries no CVSS of its own; without this backfill the ``cvss`` relation dimension
has nothing to extract for those events.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app import config, normalize, storage


ROOT = Path(__file__).resolve().parent.parent


def _snapshot_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path,
                        default=config.SNAPSHOT_DIR / "nvd")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "reports" / "nvd-poc-backfill.json")
    args = parser.parse_args()

    counts = Counter()
    files = _snapshot_files(args.snapshot_dir)
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            counts["snapshot_errors"] += 1
            continue
        for item in payload.get("vulnerabilities") or []:
            event = normalize.nvd_to_event(item)
            if not event:
                continue
            event_id = str(event.get("id"))
            if event.get("poc"):
                counts["events_with_poc"] += 1
                if storage.merge_event_poc(event_id, event["poc"]):
                    counts["poc_events_updated"] += 1
                else:
                    counts["poc_events_unchanged_or_missing"] += 1
            if event.get("cvss"):
                counts["events_with_cvss"] += 1
                if storage.merge_event_cvss(event_id, event["cvss"]):
                    counts["cvss_events_updated"] += 1
                else:
                    counts["cvss_events_unchanged_or_missing"] += 1
    report = {
        "snapshot_dir": str(args.snapshot_dir),
        "snapshot_files": len(files),
        "events_with_poc": counts["events_with_poc"],
        "poc_events_updated": counts["poc_events_updated"],
        "poc_events_unchanged_or_missing": counts["poc_events_unchanged_or_missing"],
        "events_with_cvss": counts["events_with_cvss"],
        "cvss_events_updated": counts["cvss_events_updated"],
        "cvss_events_unchanged_or_missing": counts["cvss_events_unchanged_or_missing"],
        "events_updated_any": counts["poc_events_updated"] + counts["cvss_events_updated"],
        "snapshot_errors": counts["snapshot_errors"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
