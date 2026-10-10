"""Re-check the disposition denominator freeze and the state-machine rules.

Two independent checks, each against its own scratch copy of a checksummed
source database, so the delivered 2026-10-08 evidence is never mutated:

* ``denominator-freeze.json`` -- re-run the assessment pass on a copy of the
  delivered evidence DB and confirm the closure rate holds.  Remediated
  findings keep their place in the denominator through the ``opened_priority``
  frozen at open time, so a successful fix cannot make the denominator shrink.
* ``state-machine-recheck.json`` -- drive the four disposition rules on a copy
  of the pre-run baseline, using the same code path the HTTP routes use.

When ``fastapi`` is importable the checks go through ``TestClient`` (real HTTP
handlers).  Otherwise they call the exact handler functions the routes wrap and
say so in the output.  Either way the evidence records which mode was used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
HIGH_PRIORITIES = {"critical", "high"}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_version(event: dict[str, Any]) -> str | None:
    for affected in event.get("affected") or []:
        fixed = str(affected.get("fixed_version") or "").strip()
        if fixed:
            return fixed
        match = re.search(r"<\s*([0-9][0-9A-Za-z.+_-]*)", str(affected.get("range") or ""))
        if match:
            return match.group(1)
    return None


class _HttpError(Exception):
    """Stands in for a non-2xx response when running without the ASGI stack."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class Api:
    """The five routes this check needs, over HTTP when possible."""

    def __init__(self, client: Any, modules: dict[str, Any]) -> None:
        self._client = client
        self._m = modules

    @property
    def mode(self) -> str:
        return "http_testclient" if self._client else "direct_handler"

    def metrics(self) -> dict[str, Any]:
        if self._client:
            return self._client.get("/api/dispositions/metrics").json()
        return self._m["disposition"].metrics()

    def scorecard_disposition(self) -> dict[str, Any]:
        if self._client:
            return self._client.get("/api/competition/scorecard").json()["disposition"]
        return self._m["competition_scorecard"].scorecard()["disposition"]

    def run_assessments(self) -> dict[str, Any]:
        if self._client:
            response = self._client.post("/api/assessments/run")
            return {"http_status": response.status_code, "response": response.json()}
        return {"http_status": 200, "response": self._m["agents"].run_assessment()}

    def update_disposition(
        self,
        event_id: str,
        asset_id: str,
        *,
        status: str,
        assignee: str | None = None,
        note: str | None = None,
        version_after: str | None = None,
    ) -> dict[str, Any]:
        # The route's request model carries the identifiers in the body as well
        # as in the path, so mirror that on the wire.
        body = {
            "event_id": event_id,
            "asset_id": asset_id,
            "status": status,
            "assignee": assignee,
            "note": note,
        }
        if version_after:
            body["version_after"] = version_after
        if self._client:
            response = self._client.put(
                f"/api/dispositions/{event_id}/{asset_id}", json=body,
            )
            payload = response.json()
            if response.status_code >= 400:
                raise _HttpError(response.status_code, str(payload.get("detail") or payload))
            return {"http_status": response.status_code, "response": payload}
        module = self._m["disposition"]
        try:
            result = module.update_disposition(
                event_id, asset_id, status=status, assignee=assignee,
                note=note, version_after=version_after,
            )
        except module.DispositionError as exc:
            raise _HttpError(400, str(exc)) from exc
        return {"http_status": 200, "response": result}

    def upsert_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": asset.get("id"),
            "name": asset.get("name"),
            "component": asset.get("component"),
            "ecosystem": asset.get("ecosystem") or "",
            "version": asset.get("version"),
            "exposure": asset.get("exposure") or "unknown",
            "business_criticality": asset.get("business_criticality") or "unknown",
            "conditions": asset.get("conditions") or {},
            "is_demo": bool(asset.get("is_demo")),
            "authorized": bool(asset.get("authorized", True)),
        }
        if self._client:
            response = self._client.post("/api/assets", json=payload)
            return response.json()
        return self._m["storage"].upsert_asset(payload)


def _load_modules() -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app import agents, competition_scorecard, config, disposition, intelligence, storage
    return {
        "agents": agents,
        "competition_scorecard": competition_scorecard,
        "config": config,
        "disposition": disposition,
        "intelligence": intelligence,
        "storage": storage,
    }


def _point_at(modules: dict[str, Any], directory: Path) -> None:
    config = modules["config"]
    os.environ["INTEL_DATA_DIR"] = str(directory)
    config.DATA_DIR = directory
    config.SNAPSHOT_DIR = directory / "snapshots"
    config.DB_PATH = directory / "intel.sqlite"
    config.ensure_dirs()


def _make_client() -> tuple[Any, str | None]:
    try:
        from fastapi.testclient import TestClient

        from app.api import app as api_app
    except Exception as exc:  # pragma: no cover - depends on the host runtime
        return None, f"{type(exc).__name__}: {exc}"
    return TestClient(api_app), None


def _cohort_rows(modules: dict[str, Any]) -> list[dict[str, Any]]:
    disposition = modules["disposition"]
    storage = modules["storage"]
    stored = {
        str(item.get("event_id")) + "::" + str(item.get("asset_id")): item
        for item in storage.list_assessment_dispositions(limit=5000)
    }
    rows = []
    for assessment in storage.list_assessments(limit=2000):
        key = str(assessment.get("event_id")) + "::" + str(assessment.get("asset_id"))
        record = disposition._display(stored.get(key))
        rows.append({
            "key": key,
            "event_id": assessment.get("event_id"),
            "asset_id": assessment.get("asset_id"),
            "live_status": assessment.get("status"),
            "live_priority": assessment.get("priority"),
            "disposition_status": record.get("status"),
            "opened_at": record.get("opened_at"),
            "opened_priority": record.get("opened_priority"),
            "closed_at": record.get("closed_at"),
            "in_cohort": disposition._is_high_priority_cohort(
                {"assessment": assessment, "disposition": record}
            ),
        })
    return rows


def _freeze_check(modules: dict[str, Any], api: Api, scratch: Path, source: Path) -> dict[str, Any]:
    before_rows = _cohort_rows(modules)
    before = api.metrics()
    before_scorecard = api.scorecard_disposition()

    recalculation = api.run_assessments()

    after_rows = _cohort_rows(modules)
    after = api.metrics()
    after_scorecard = api.scorecard_disposition()

    before_index = {row["key"]: row for row in before_rows}
    flipped = []
    flipped_cohort = []
    for row in after_rows:
        previous = before_index.get(row["key"]) or {}
        if previous.get("live_status") == "affected" and row["live_status"] != "affected":
            record = {
                "key": row["key"],
                "live_status_before": previous.get("live_status"),
                "live_status_after": row["live_status"],
                "live_priority_before": previous.get("live_priority"),
                "opened_at": row["opened_at"],
                "opened_priority": row["opened_priority"],
                "disposition_status": row["disposition_status"],
                "in_cohort_before": bool(previous.get("in_cohort")),
                "still_in_cohort": row["in_cohort"],
            }
            flipped.append(record)
            if previous.get("in_cohort"):
                flipped_cohort.append(record)

    # Counterfactual, derived from the same rows: what the metric would report if
    # the denominator followed the live assessment instead of the frozen cohort.
    live_high = [row for row in after_rows
                 if row["live_status"] == "affected" and row["live_priority"] in HIGH_PRIORITIES]
    live_closed = [row for row in live_high
                   if row["disposition_status"] in {"verified", "accepted"}]
    counterfactual_rate = round(len(live_closed) / len(live_high), 4) if live_high else None

    cohort_after = [row for row in after_rows if row["in_cohort"]]
    # ``generated_at`` is stamped per call, so compare the payloads without it.
    def _stable(payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key != "generated_at"}

    passed = (
        before.get("high_priority_total") == after.get("high_priority_total")
        and before.get("high_priority_closed") == after.get("high_priority_closed")
        and before.get("closure_rate") == after.get("closure_rate")
        and len(cohort_after) > 0
        and len(flipped_cohort) > 0
        and all(row["still_in_cohort"] for row in flipped_cohort)
    )
    return {
        "generated_at": _utcnow(),
        "endpoint_under_test": "POST /api/assessments/run",
        "invocation_mode": api.mode,
        "scratch_database": {
            "path": str(scratch),
            "copied_from": str(source),
            "source_sha256": _sha256(source),
        },
        "rule": ("已登记处置的条目锁定在分母内：资产修复后研判转为不受影响，闭环率分子分母同时保持。"),
        "before": {"metrics": before, "scorecard_disposition": before_scorecard},
        "recalculation": recalculation,
        "after": {"metrics": after, "scorecard_disposition": after_scorecard},
        "cohort_before": [row for row in before_rows if row["in_cohort"]],
        "cohort_after": cohort_after,
        "live_assessment_flips": flipped,
        "counterfactual_without_freeze": {
            "live_affected_high_total": len(live_high),
            "live_affected_high_closed": len(live_closed),
            "closure_rate": counterfactual_rate,
            "note": ("仅作对照推导：假设分母跟随实时研判（不使用 opened_priority 冻结），"
                     "同一批数据会得到该值。它证明冻结项实际改变了结果，不是装饰性代码。"),
        },
        "comparison": {
            "high_priority_total": {"before": before.get("high_priority_total"),
                                    "after": after.get("high_priority_total")},
            "high_priority_closed": {"before": before.get("high_priority_closed"),
                                     "after": after.get("high_priority_closed")},
            "closure_rate": {"before": before.get("closure_rate"), "after": after.get("closure_rate")},
            "findings_that_flipped_to_not_affected": len(flipped),
            "cohort_findings_that_flipped_to_not_affected": len(flipped_cohort),
            "metrics_matches_scorecard_after": _stable(after) == _stable(after_scorecard),
        },
        "cohort_flips": flipped_cohort,
        "passed": passed,
    }


def _pick_recheck_rows(modules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    storage = modules["storage"]
    intelligence = modules["intelligence"]
    assets = {item["id"]: item for item in storage.list_assets()}
    candidates = []
    for assessment in storage.list_assessments(limit=2000):
        if assessment.get("status") != "affected":
            continue
        if assessment.get("priority") not in HIGH_PRIORITIES:
            continue
        asset = assets.get(assessment.get("asset_id"))
        event = storage.get_event(assessment.get("event_id"))
        if not asset or not event:
            continue
        if storage.get_assessment_disposition(assessment.get("event_id"), asset["id"]):
            continue
        live = intelligence.assess_asset(event, asset)
        candidates.append({
            "event_id": assessment.get("event_id"),
            "asset_id": asset["id"],
            "component": asset.get("component"),
            "version": asset.get("version"),
            "is_demo": bool(asset.get("is_demo")),
            "live_recheck_status": live.get("status"),
            "safe_version": _safe_version(event),
        })
    still_affected = [row for row in candidates if row["live_recheck_status"] == "affected"]
    upgradeable = [row for row in still_affected if row.get("safe_version")]
    if len(still_affected) < 1 or len(upgradeable) < 1:
        raise SystemExit("recheck database has no usable high-priority affected findings")
    upgrade_target = upgradeable[0]
    remaining = [row for row in still_affected if row is not upgrade_target]
    if not remaining:
        raise SystemExit(
            "recheck database needs two independent affected findings: one that fails the "
            "re-check and one whose asset can be upgraded"
        )
    # A row other than the upgrade target keeps rule 2 independent of rule 3.
    return {
        "rejection": candidates[0],
        "downgrade": remaining[0],
        "upgrade": upgrade_target,
        "candidates": candidates,
    }


def _state_machine_recheck(
    modules: dict[str, Any], api: Api, scratch: Path, source: Path,
) -> dict[str, Any]:
    storage = modules["storage"]
    disposition = modules["disposition"]
    picked = _pick_recheck_rows(modules)
    steps = []

    # Rule 1 -- a finding cannot enter the flow without an owner.
    rejection = None
    try:
        api.update_disposition(
            picked["rejection"]["event_id"], picked["rejection"]["asset_id"],
            status="in_progress", assignee=None,
        )
    except _HttpError as exc:
        rejection = exc
    stored = storage.get_assessment_disposition(
        picked["rejection"]["event_id"], picked["rejection"]["asset_id"]
    )
    steps.append({
        "rule": "missing_assignee_rejected",
        "target": picked["rejection"],
        "requested_status": "in_progress",
        "assignee": None,
        "http_status": rejection.status if rejection else 200,
        "detail": rejection.detail if rejection else None,
        "disposition_after": stored.get("status") if stored else None,
        "passed": bool(rejection and rejection.status == 400 and not stored),
    })

    # Rule 2 -- an asset still inside the affected range cannot be closed by
    # assertion; the failed re-check is kept as audit evidence.
    downgrade_target = picked["downgrade"]
    attempt = api.update_disposition(
        downgrade_target["event_id"], downgrade_target["asset_id"],
        status="verified", assignee="a-evidence-owner", note="independent recheck",
    )
    body = attempt["response"]
    persisted = storage.get_assessment_disposition(
        downgrade_target["event_id"], downgrade_target["asset_id"]
    ) or {}
    steps.append({
        "rule": "unsafe_version_verified_is_downgraded",
        "target": downgrade_target,
        "requested_status": "verified",
        "http_status": attempt["http_status"],
        "applied_status": body.get("applied_status"),
        "verification": body.get("verification"),
        "persisted_status": persisted.get("status"),
        "persisted_closed_at": persisted.get("closed_at"),
        "persisted_verification": persisted.get("verification"),
        "passed": (
            body.get("applied_status") == "fixed"
            and (body.get("verification") or {}).get("passed") is False
            and persisted.get("closed_at") is None
            and persisted.get("status") == "fixed"
        ),
    })

    # Rule 3 -- upgrade the asset to a safe version, then the closure sticks.
    upgrade_target = picked["upgrade"]
    asset = next(item for item in storage.list_assets() if item["id"] == upgrade_target["asset_id"])
    before_version = asset.get("version")
    upgraded = dict(asset)
    upgraded["version"] = upgrade_target["safe_version"]
    api.upsert_asset(upgraded)
    attempt = api.update_disposition(
        upgrade_target["event_id"], upgrade_target["asset_id"],
        status="verified", assignee="a-evidence-owner", note="independent recheck",
        version_after=upgrade_target["safe_version"],
    )
    body = attempt["response"]
    persisted = storage.get_assessment_disposition(
        upgrade_target["event_id"], upgrade_target["asset_id"]
    ) or {}
    steps.append({
        "rule": "safe_version_verified_closes",
        "target": upgrade_target,
        "version_before": before_version,
        "version_after": upgrade_target["safe_version"],
        "http_status": attempt["http_status"],
        "applied_status": body.get("applied_status"),
        "verification": body.get("verification"),
        "persisted_status": persisted.get("status"),
        "persisted_closed_at": persisted.get("closed_at"),
        "passed": (
            body.get("applied_status") == "verified"
            and (body.get("verification") or {}).get("passed") is True
            and bool(persisted.get("closed_at"))
            and persisted.get("status") == "verified"
        ),
    })

    # Rule 4 -- closing never rewrites the original assessment row.
    stored_assessment = next(
        (
            item for item in storage.list_assessments(limit=2000)
            if item.get("event_id") == upgrade_target["event_id"]
            and item.get("asset_id") == upgrade_target["asset_id"]
        ),
        {},
    )
    live = disposition.get_disposition(upgrade_target["event_id"], upgrade_target["asset_id"])
    steps.append({
        "rule": "assessment_status_not_overwritten",
        "target": upgrade_target,
        "assessment_status": stored_assessment.get("status"),
        "disposition_status": live.get("status"),
        "passed": (
            stored_assessment.get("status") == "affected" and live.get("status") == "verified"
        ),
    })

    return {
        "generated_at": _utcnow(),
        "invocation_mode": api.mode,
        "scratch_database": {
            "path": str(scratch),
            "copied_from": str(source),
            "source_sha256": _sha256(source),
        },
        "candidates": picked["candidates"],
        "steps": steps,
        "passed": all(step["passed"] for step in steps),
        "rules_passed": sum(1 for step in steps if step["passed"]),
        "rules_total": len(steps),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence-dir", type=Path,
        default=ROOT / "artifacts" / "a_eval" / "disposition-live-closure-20261008",
    )
    parser.add_argument(
        "--recheck-db", type=Path,
        default=ROOT / "work" / "disposition-trial-cdx" / "intel.sqlite",
        help="pre-run baseline copy used for the four state-machine rules",
    )
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work" / "disposition-freeze-recheck")
    args = parser.parse_args()

    evidence = args.evidence_dir.resolve()
    evidence_db = evidence / "data" / "intel.sqlite"
    if not evidence_db.is_file():
        raise SystemExit(f"evidence database not found: {evidence_db}")
    recheck_source = args.recheck_db.resolve()
    if not recheck_source.is_file():
        raise SystemExit(f"recheck database not found: {recheck_source}")

    work = args.work_dir.resolve()
    freeze_dir = work / "freeze"
    recheck_dir = work / "recheck"
    for directory in (freeze_dir, recheck_dir):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(evidence_db, freeze_dir / "intel.sqlite")
    shutil.copy2(recheck_source, recheck_dir / "intel.sqlite")

    modules = _load_modules()
    client, client_error = _make_client()
    api = Api(client, modules)

    _point_at(modules, freeze_dir)
    freeze = _freeze_check(modules, api, freeze_dir / "intel.sqlite", evidence_db)
    freeze["interpreter"] = sys.version.split()[0]
    freeze["http_stack"] = {"available": client is not None, "error": client_error}
    _write_json(evidence / "denominator-freeze.json", freeze)

    _point_at(modules, recheck_dir)
    recheck = _state_machine_recheck(modules, api, recheck_dir / "intel.sqlite", recheck_source)
    recheck["interpreter"] = sys.version.split()[0]
    _write_json(evidence / "state-machine-recheck.json", recheck)

    print(json.dumps({
        "invocation_mode": api.mode,
        "http_stack_error": client_error,
        "denominator_freeze_passed": freeze["passed"],
        "denominator_freeze_comparison": freeze["comparison"],
        "state_machine_rules_passed": f"{recheck['rules_passed']}/{recheck['rules_total']}",
    }, ensure_ascii=False, indent=2))
    return 0 if freeze["passed"] and recheck["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
