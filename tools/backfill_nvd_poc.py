"""Backfill NVD exploit-reference POC records into already stored events.

This tool never creates an event and never changes source summaries.  It only
adds exact NVD `Exploit` reference records to the matching event's ``poc`` list.
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
            if not event or not event.get("poc"):
                continue
            counts["events_with_poc"] += 1
            if storage.merge_event_poc(str(event.get("id")), event["poc"]):
                counts["events_updated"] += 1
            else:
                counts["events_unchanged_or_missing"] += 1
    report = {
        "snapshot_dir": str(args.snapshot_dir),
        "snapshot_files": len(files),
        "events_with_poc": counts["events_with_poc"],
        "events_updated": counts["events_updated"],
        "events_unchanged_or_missing": counts["events_unchanged_or_missing"],
        "snapshot_errors": counts["snapshot_errors"],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
