"""Validate version, run IDs, and evidence counts across generated reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import storage  # noqa: E402


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def main() -> int:
    storage.init_db()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    reports = {
        path: _load(path)
        for path in (
            "reports/reliability-report.json",
            "reports/source-health.json",
            "reports/latency-summary.json",
            "reports/scheduler-validation.json",
            "reports/nvd-completeness.json",
            "reports/backup-restore-validation.json",
            "reports/fault-injection.json",
            "reports/local-validation.json",
            "reports/ci-validation.json",
            "reports/docker-validation.json",
            "reports/rollback-validation.json",
            "reports/observability-sample.json",
            "reports/final-evidence-summary.json",
        )
    }
    version_mismatches = [
        path for path, payload in reports.items()
        if "version" in payload and payload["version"] != version
    ]
    scheduler = reports["reports/scheduler-validation.json"]
    persisted_run_ids = {run["id"] for run in storage.list_runs(limit=1000)}
    referenced_runs = [
        run["run_id"] for run in scheduler.get("runs") or []
    ]
    missing_runs = [run_id for run_id in referenced_runs if run_id not in persisted_run_ids]
    nvd = reports["reports/nvd-completeness.json"]
    backup = reports["reports/backup-restore-validation.json"]
    fault = reports["reports/fault-injection.json"]
    docker = reports["reports/docker-validation.json"]
    payload = {
        "version": version,
        "generated_at": storage.utcnow(),
        "checks": {
            "version_consistent": not version_mismatches,
            "version_mismatches": version_mismatches,
            "scheduler_run_ids_persisted": not missing_runs,
            "missing_run_ids": missing_runs,
            "nvd_post_fix_all_ok": bool(nvd.get("post_fix_all_ok")),
            "backup_restore_counts_match": bool(backup.get("counts_match")),
            "fault_injection_recovered": fault.get("status") == "recovered",
            "local_checks_passed": bool(
                reports["reports/local-validation.json"].get("all_local_checks_passed")
            ),
            "docker_runtime_verified": bool(docker.get("verified")),
            "docker_health": docker.get("container_health"),
        },
        "all_consistent": all([
            not version_mismatches,
            not missing_runs,
            bool(nvd.get("post_fix_all_ok")),
            bool(backup.get("counts_match")),
            fault.get("status") == "recovered",
            bool(reports["reports/local-validation.json"].get("all_local_checks_passed")),
            bool(docker.get("verified")),
        ]),
    }
    output = ROOT / "reports" / "evidence-consistency.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), **payload["checks"]}, ensure_ascii=False))
    return 0 if payload["all_consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
