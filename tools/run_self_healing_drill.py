"""Reproducible self-healing drill: repeated failure -> bounded degradation.

The drill runs against a *copy* of the demo database, never the live one, and
it replaces the network collection with a controllable fault so the outcome is
deterministic and no real request is made.  Everything else -- the streak
counting, the retry decision, the degradation record, the unattended-source
selection and the cooldown expiry -- is the production code path.

Writes ``reports/self-healing-drill.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import agents, config, self_healing, sources, storage  # noqa: E402

FAULTY_SOURCE = "osv"
BACKUP_SOURCE = "arxiv"


def _point_at(directory: Path) -> None:
    config.DATA_DIR = directory
    config.SNAPSHOT_DIR = directory / "snapshots"
    config.DB_PATH = directory / "intel.sqlite"


def _failed_run(source_id: str, index: int) -> None:
    stamp = f"2099-01-{index:02d}T00:00:00Z"
    storage.save_run({
        "id": f"drill-fail-{source_id}-{index}", "kind": "collect", "status": "partial",
        "started_at": stamp, "finished_at": stamp, "summary": None,
        "detail": {"results": [{"source_id": source_id, "status": "failed",
                                "error": "drill: injected upstream failure"}]},
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(ROOT / "data" / "intel.sqlite"))
    parser.add_argument("--output", default="reports/self-healing-drill.json")
    args = parser.parse_args()

    source_db = Path(args.database)
    if not source_db.is_file():
        print(json.dumps({"status": "failed", "reason": f"database not found: {source_db}"},
                         ensure_ascii=False))
        return 2

    workdir = Path(tempfile.mkdtemp(prefix="self-healing-drill-"))
    (workdir / "snapshots").mkdir()
    shutil.copy2(source_db, workdir / "intel.sqlite")
    _point_at(workdir)
    storage.init_db()

    selected_before, _ = self_healing.apply_degradation_policy(
        list(sources.recommended_sources())
    )

    injected: list[dict] = []
    for index in (1, 2, 3):
        _failed_run(FAULTY_SOURCE, index)
        injected.append({"source_id": FAULTY_SOURCE, "status": "failed", "attempt": index})
    storage.update_source_state(
        FAULTY_SOURCE, status="failed", last_error="drill: injected upstream failure",
    )

    # The retry is answered by the injected fault, so the loop must fall through
    # to the degradation branch instead of retrying forever.
    original_run_collection = agents.run_collection
    calls: list[list[str]] = []

    def still_failing(source_ids, **kwargs):
        calls.append(list(source_ids))
        return {"run_id": f"drill-run-{len(calls)}", "status": "partial", "results": []}

    agents.run_collection = still_failing
    try:
        degrade_result = self_healing.run_self_healing([FAULTY_SOURCE])
    finally:
        agents.run_collection = original_run_collection

    selected_after, notes_after = self_healing.apply_degradation_policy(
        list(sources.recommended_sources())
    )

    # Second phase: the upstream answers again, so the cooldown must lift.
    storage.update_source_state(FAULTY_SOURCE, status="ok", last_error=None)
    _failed_run(FAULTY_SOURCE, 9)
    storage.save_run({
        "id": "drill-recovered-ok", "kind": "collect", "status": "completed",
        "started_at": "2099-01-10T00:00:00Z", "finished_at": "2099-01-10T00:00:00Z",
        "summary": None,
        "detail": {"results": [{"source_id": FAULTY_SOURCE, "status": "ok"}]},
    })
    recovery_result = self_healing.run_self_healing([FAULTY_SOURCE])
    selected_final, _ = self_healing.apply_degradation_policy(
        list(sources.recommended_sources())
    )

    payload = {
        "status": "completed",
        "generated_at": storage.utcnow(),
        "policy": {
            "consecutive_failure_threshold": self_healing.CONSECUTIVE_FAILURE_THRESHOLD,
            "cooldown_hours": self_healing.DEGRADE_COOLDOWN_HOURS,
            "automatic_actions": degrade_result["policy"]["automatic_actions"],
        },
        "phase_1_inject": {
            "note": "网络采集被替换为可控故障注入，未发起真实请求；库为演示库副本，生产库未被写入。",
            "injected_runs": injected,
            "streak_after_injection": self_healing.CONSECUTIVE_FAILURE_THRESHOLD,
        },
        "phase_2_retry": {
            "retry_attempted": calls,
            "failed_after_retry": [item["source_id"] for item in degrade_result["failed_after_retry"]],
        },
        "phase_3_degrade": {
            "degradations": degrade_result["degradations"],
            "active_degradations": degrade_result["active_degradations"],
            "unattended_before": selected_before,
            "unattended_after": selected_after,
            "degradation_notes": notes_after,
        },
        "phase_4_recover": {
            "recovered": [item["source_id"] for item in recovery_result["recovered"]],
            "degradations_cleared": recovery_result["degradations_cleared"],
            "unattended_final": selected_final,
        },
        "assertions": {
            "faulty_source_left_unattended": FAULTY_SOURCE not in selected_after,
            "faulty_source_back_after_recovery": FAULTY_SOURCE in selected_final,
            "no_backup_declared_so_frequency_drops": all(
                item["action"] == "reduce_frequency"
                for item in degrade_result["degradations"]
            ),
            "declared_substitute_is_used": (
                self_healing.degradation_for(BACKUP_SOURCE, 3)["backup_sources"] == ["openalex"]
            ),
        },
        "environment": {
            "database_copy": str(workdir / "intel.sqlite"),
            "source_database": str(source_db),
        },
    }
    passed = all(payload["assertions"].values())
    payload["verified"] = passed

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output.relative_to(ROOT)),
        "verified": passed,
        "assertions": payload["assertions"],
        "unattended_after": selected_after,
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
