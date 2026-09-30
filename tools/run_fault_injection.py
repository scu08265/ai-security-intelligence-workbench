"""Run a reproducible NVD failure and recovery exercise."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import agents, collectors, observability, self_healing, storage  # noqa: E402
from app.collectors import vuln  # noqa: E402


def _success_payload() -> dict:
    return {
        "vulnerabilities": [{
            "cve": {
                "id": "CVE-2099-FAULT",
                "sourceIdentifier": "synthetic@example.invalid",
                "published": "2099-05-01T00:00:00Z",
                "lastModified": "2099-05-02T00:00:00Z",
                "vulnStatus": "Analyzed",
                "descriptions": [{
                    "lang": "en",
                    "value": "Synthetic vLLM failure-injection recovery fixture.",
                }],
                "metrics": {},
                "weaknesses": [],
                "configurations": [],
                "references": [{"url": "https://example.invalid/fault-injection"}],
            },
        }],
        "totalResults": 1,
        "resultsPerPage": 200,
        "startIndex": 0,
    }


def main() -> int:
    storage.init_db()
    agents.refresh_source_event_counts()
    vuln.NVD_PAGE_DELAY_SECONDS = 0.0
    collectors.BACKOFF_SECONDS = (0.0, 0.0, 0.0)
    before = storage.source_state("nvd")
    alerts_before = observability.recent_alerts(limit=1000)["items"]

    def unavailable(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "synthetic upstream outage"})

    def recovered(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_success_payload())

    collectors.set_transport(httpx.MockTransport(unavailable))
    failed_run = agents.run_collection(
        ["nvd"], trigger="fault_injection",
        scheduler={"task_id": "fault-injection", "phase": "initial_failure"},
    )
    state_after_failure = storage.source_state("nvd")
    first_healing = self_healing.run_self_healing(
        ["nvd"], parent_run_id=failed_run["run_id"],
    )

    collectors.set_transport(httpx.MockTransport(recovered))
    second_healing = self_healing.run_self_healing(
        ["nvd"], parent_run_id=failed_run["run_id"],
    )
    state_after_recovery = storage.source_state("nvd")
    collectors.set_transport(None)

    alerts = observability.recent_alerts(limit=1000)["items"]
    new_alerts = alerts[len(alerts_before):]
    payload = {
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "status": (
            "recovered"
            if state_after_recovery.get("status") == "ok"
            else "failed"
        ),
        "scenario": "NVD mock HTTP 503 followed by successful retry",
        "before": before,
        "after_failure": state_after_failure,
        "after_recovery": state_after_recovery,
        "failed_run": {
            "run_id": failed_run.get("run_id"),
            "status": failed_run.get("status"),
            "results": failed_run.get("results"),
        },
        "first_self_healing": first_healing,
        "second_self_healing": second_healing,
        "alert_codes": [item.get("code") for item in new_alerts],
        "alerts": new_alerts,
    }
    output = ROOT / "reports" / "fault-injection.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": payload["status"],
        "output": str(output),
        "after_failure_status": state_after_failure.get("status"),
        "after_recovery_status": state_after_recovery.get("status"),
        "alert_codes": payload["alert_codes"],
    }, ensure_ascii=False))
    return 0 if payload["status"] == "recovered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
