"""Run the disposition closure state machine against an isolated A-task DB."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _safe_version(event: dict[str, Any]) -> str | None:
    for affected in event.get("affected") or []:
        fixed = str(affected.get("fixed_version") or "").strip()
        if fixed:
            return fixed
        range_text = str(affected.get("range") or "")
        match = re.search(r"<\s*([0-9][0-9A-Za-z.+_-]*)", range_text)
        if match:
            return match.group(1)
    return None


def _asset_payload(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": asset.get("id"),
        "name": asset.get("name"),
        "component": asset.get("component"),
        "ecosystem": asset.get("ecosystem") or "",
        "version": asset.get("version"),
        "exposure": asset.get("exposure") or "unknown",
        "business_criticality": asset.get("business_criticality") or "unknown",
        "conditions": asset.get("conditions") or {},
        "policy": asset.get("policy"),
        "is_demo": bool(asset.get("is_demo")),
        "authorized": bool(asset.get("authorized", True)),
    }


def _request(
    client: Any,
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.request(method, path, json=body)
    try:
        payload = response.json()
    except ValueError:
        payload = None
    return {
        "method": method,
        "path": path,
        "request_body": body,
        "http_status": response.status_code,
        "response": payload,
    }


def _metric_snapshot(label: str, client: Any) -> dict[str, Any]:
    response = client.get("/api/dispositions/metrics")
    return {
        "label": label,
        "captured_at": _utcnow(),
        "http_status": response.status_code,
        "metrics": response.json(),
    }


def _row_key(row: dict[str, Any]) -> str:
    return f"{row.get('event_id')}::{row.get('asset_id')}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-db", type=Path, default=ROOT / "data" / "intel.sqlite")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "a_eval" / "disposition-closure-20261004",
    )
    args = parser.parse_args()

    output = args.output_dir.resolve()
    data_dir = output / "data"
    db_path = data_dir / "intel.sqlite"
    data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.base_db, db_path)

    os.environ["INTEL_DATA_DIR"] = str(data_dir)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient

    from app import config, cyclonedx_assets, disposition, storage
    from app.api import app

    client = TestClient(app)
    synthetic = json.loads(
        (ROOT / "artifacts" / "b_eval" / "asset_dimension_synthetic_20261002.json").read_text(
            encoding="utf-8"
        )
    )
    inventory = json.loads(
        (ROOT / "artifacts" / "b_eval" / "asset_inventory_probe_20261002.json").read_text(
            encoding="utf-8"
        )
    )
    bom = json.loads(
        (ROOT / "artifacts" / "sbom" / "vllm-lab.cdx.json").read_text(encoding="utf-8")
    )

    seed_requests = []
    for raw in synthetic["synthetic_assets"]:
        asset = {
            "id": raw["asset_id"],
            "name": raw["component"],
            "component": raw["component"],
            "ecosystem": "PyPI",
            "version": raw["version"],
            "exposure": "unknown",
            "business_criticality": "unknown",
            "conditions": {},
            "is_demo": True,
            "authorized": True,
        }
        seed_requests.append(_request(
            client, "POST", "/api/assets", body=_asset_payload(asset),
        ))
    for raw in inventory["imported_assets"]:
        asset = {
            "id": raw["asset_id"],
            "name": raw["component"],
            "component": raw["component"],
            "ecosystem": "PyPI",
            "version": raw["version"],
            "exposure": "unknown",
            "business_criticality": "unknown",
            "conditions": {},
            "is_demo": False,
            "authorized": True,
        }
        seed_requests.append(_request(
            client, "POST", "/api/assets", body=_asset_payload(asset),
        ))
    sbom_import = _request(
        client,
        "POST",
        "/api/assets/cyclonedx/import",
        body={"bom": bom, "authorized": True, "is_demo": True},
    )
    assessment_run = _request(client, "POST", "/api/assessments/run")

    baseline = _metric_snapshot("baseline_after_assessment", client)
    timeline = [baseline]
    assessments = client.get("/api/assessments", params={"limit": 1000}).json()["items"]
    high_rows = [
        row for row in assessments
        if row.get("status") == "affected"
        and row.get("priority") in {"critical", "high"}
    ]
    if len(high_rows) < 4:
        raise SystemExit(
            f"Expected at least 4 high-priority affected findings, found {len(high_rows)}"
        )

    assets = {item["id"]: item for item in storage.list_assets()}
    smolagents = next(
        (row for row in high_rows if assets[row["asset_id"]].get("component") == "smolagents"),
        high_rows[0],
    )
    openwebui = [
        row for row in high_rows
        if assets[row["asset_id"]].get("component") == "open-webui"
    ]
    if len(openwebui) < 3:
        openwebui = [row for row in high_rows if _row_key(row) != _row_key(smolagents)][:3]
    selected = [smolagents, *openwebui[:3]]
    failed_row = openwebui[0]

    rule_results: list[dict[str, Any]] = []

    # Rule 1: no assignee means the state cannot move into in-flow statuses.
    missing_assignee = _request(
        client,
        "PUT",
        f"/api/dispositions/{smolagents['event_id']}/{smolagents['asset_id']}",
        body={
            "event_id": smolagents["event_id"],
            "asset_id": smolagents["asset_id"],
            "status": "in_progress",
        },
    )
    after_missing = client.get(
        f"/api/dispositions/{smolagents['event_id']}/{smolagents['asset_id']}"
    ).json()
    rule_results.append({
        "rule": "missing_assignee_rejected",
        "expected": "HTTP 400 and no disposition transition",
        "request": missing_assignee,
        "actual_status": after_missing.get("status"),
        "passed": missing_assignee["http_status"] == 400
        and after_missing.get("status") == "open",
    })
    timeline.append(_metric_snapshot("after_missing_assignee_rejected", client))

    # Rule 2: a still-vulnerable version cannot be verified closed.
    failed_verification = _request(
        client,
        "PUT",
        f"/api/dispositions/{failed_row['event_id']}/{failed_row['asset_id']}",
        body={
            "event_id": failed_row["event_id"],
            "asset_id": failed_row["asset_id"],
            "status": "verified",
            "assignee": "a-evidence-owner",
            "note": "Attempt verification before upgrading the asset.",
            "version_before": assets[failed_row["asset_id"]].get("version"),
        },
    )
    failed_record = client.get(
        f"/api/dispositions/{failed_row['event_id']}/{failed_row['asset_id']}"
    ).json()
    rule_results.append({
        "rule": "unsafe_version_verified_is_downgraded",
        "expected": "applied_status=fixed, verification.passed=false, closed_at=null",
        "request": failed_verification,
        "actual": failed_record,
        "passed": (
            failed_verification["http_status"] == 200
            and failed_verification["response"]["applied_status"] == "fixed"
            and failed_verification["response"]["verification"]["passed"] is False
            and failed_record.get("closed_at") is None
        ),
    })
    timeline.append(_metric_snapshot("after_failed_reverification", client))

    # Rule 3 and closure: upgrade selected assets, then verify.
    closure_steps = []
    smol_event = storage.get_event(smolagents["event_id"])
    smol_safe = _safe_version(smol_event)
    if not smol_safe:
        raise SystemExit("No safe version found for smolagents finding")
    smol_asset = assets[smolagents["asset_id"]]
    smol_asset["version"] = smol_safe
    closure_steps.append(_request(
        client, "POST", "/api/assets", body=_asset_payload(smol_asset),
    ))
    smol_verify = _request(
        client,
        "PUT",
        f"/api/dispositions/{smolagents['event_id']}/{smolagents['asset_id']}",
        body={
            "event_id": smolagents["event_id"],
            "asset_id": smolagents["asset_id"],
            "status": "verified",
            "assignee": "a-evidence-owner",
            "note": "Upgraded to the first version outside the affected range.",
            "version_before": "1.20.0",
            "version_after": smol_safe,
        },
    )
    smol_record = client.get(
        f"/api/dispositions/{smolagents['event_id']}/{smolagents['asset_id']}"
    ).json()
    rule_results.append({
        "rule": "safe_version_verified_closes",
        "expected": "applied_status=verified and closed_at present",
        "request": smol_verify,
        "actual": smol_record,
        "passed": (
            smol_verify["http_status"] == 200
            and smol_verify["response"]["applied_status"] == "verified"
            and bool(smol_record.get("closed_at"))
        ),
    })
    timeline.append(_metric_snapshot("after_smolagents_verified", client))

    # The original assessment remains affected even after the disposition closes.
    refreshed = client.get("/api/assessments", params={"limit": 1000}).json()["items"]
    original = next(
        row for row in refreshed
        if row.get("event_id") == smolagents["event_id"]
        and row.get("asset_id") == smolagents["asset_id"]
    )
    rule_results.append({
        "rule": "assessment_status_not_overwritten",
        "expected": "assessment.status remains affected while disposition_status=verified",
        "actual": {
            "assessment_status": original.get("status"),
            "disposition_status": original.get("disposition_status"),
        },
        "passed": (
            original.get("status") == "affected"
            and original.get("disposition_status") == "verified"
        ),
    })

    open_asset = assets[failed_row["asset_id"]]
    open_event = storage.get_event(openwebui[0]["event_id"])
    open_safe = _safe_version(open_event)
    if not open_safe:
        raise SystemExit("No safe version found for open-webui finding")
    open_asset["version"] = open_safe
    closure_steps.append(_request(
        client, "POST", "/api/assets", body=_asset_payload(open_asset),
    ))
    for row in openwebui[1:3]:
        closure_steps.append(_request(
            client,
            "PUT",
            f"/api/dispositions/{row['event_id']}/{row['asset_id']}",
            body={
                "event_id": row["event_id"],
                "asset_id": row["asset_id"],
                "status": "verified",
                "assignee": "a-evidence-owner",
                "note": "Upgraded Open WebUI to the fixed version and re-assessed.",
                "version_before": "0.10.0",
                "version_after": open_safe,
            },
        ))
    timeline.append(_metric_snapshot("after_openwebui_verified", client))

    # Accepted is a resolution decision, not a verified fix. Exercise it on a
    # non-high finding so it cannot inflate the high-priority verified rate.
    accepted_candidate = next(
        (
            row for row in refreshed
            if row.get("status") == "affected"
            and row.get("priority") not in {"critical", "high"}
        ),
        None,
    )
    accepted_result = None
    if accepted_candidate:
        accepted_result = _request(
            client,
            "PUT",
            (
                f"/api/dispositions/{accepted_candidate['event_id']}/"
                f"{accepted_candidate['asset_id']}"
            ),
            body={
                "event_id": accepted_candidate["event_id"],
                "asset_id": accepted_candidate["asset_id"],
                "status": "accepted",
                "assignee": "risk-owner",
                "note": "Risk accepted for the current review period.",
            },
        )
        timeline.append(_metric_snapshot("after_non_high_risk_accepted", client))

    final_metrics_response = client.get("/api/dispositions/metrics")
    scorecard_response = client.get("/api/competition/scorecard")
    final_metrics = final_metrics_response.json()
    scorecard_disposition = scorecard_response.json()["disposition"]
    comparison_fields = (
        "high_priority_total",
        "high_priority_closed",
        "high_priority_verified",
        "high_priority_in_progress",
        "closure_rate",
        "verified_rate",
        "status_breakdown",
        "findings_total",
    )
    page_consistency = {
        "generated_at": _utcnow(),
        "api_metrics": {key: final_metrics.get(key) for key in comparison_fields},
        "scorecard_disposition": {
            key: scorecard_disposition.get(key) for key in comparison_fields
        },
        "ui_binding": {
            "endpoint": "/api/competition/scorecard",
            "field": "disposition",
            "card": "处置闭环",
            "source": "app/static/app.js",
        },
        "field_mismatches": [
            key for key in comparison_fields
            if final_metrics.get(key) != scorecard_disposition.get(key)
        ],
    }
    page_consistency["consistent"] = not page_consistency["field_mismatches"]

    selected_assets = [assets[row["asset_id"]] for row in selected]
    synthetic_count = sum(bool(asset.get("is_demo")) for asset in selected_assets)
    before_after = {
        "closure_rate_before": baseline["metrics"]["closure_rate"],
        "closure_rate_after": final_metrics["closure_rate"],
        "verified_rate_before": baseline["metrics"]["verified_rate"],
        "verified_rate_after": final_metrics["verified_rate"],
        "selected_findings": [{
            "event_id": row["event_id"],
            "asset_id": row["asset_id"],
            "component": assets[row["asset_id"]].get("component"),
            "version_before": assets[row["asset_id"]].get("version"),
            "synthetic": bool(assets[row["asset_id"]].get("is_demo")),
            "assessment_status_before": row.get("status"),
            "assessment_priority": row.get("priority"),
        } for row in selected],
        "failed_reverification_finding": {
            "event_id": failed_row["event_id"],
            "asset_id": failed_row["asset_id"],
            "status": failed_record.get("status"),
            "verification": failed_record.get("verification"),
        },
        "original_assessment_after_close": {
            "event_id": original.get("event_id"),
            "asset_id": original.get("asset_id"),
            "assessment_status": original.get("status"),
            "disposition_status": original.get("disposition_status"),
        },
        "accepted_control": accepted_result,
    }
    evidence = {
        "schema_version": "a-disposition-evidence-20261004",
        "generated_at": _utcnow(),
        "version": config.APP_VERSION,
        "mode": "isolated_api_evidence_database",
        "source_database": str(args.base_db),
        "evidence_database": str(db_path),
        "seed": {
            "synthetic_assets": len(synthetic["synthetic_assets"]),
            "real_inventory_assets": len(inventory["imported_assets"]),
            "sbom_import": sbom_import,
            "assessment_run": assessment_run,
        },
        "high_priority_total": baseline["metrics"]["high_priority_total"],
        "selected_count": len(selected),
        "selected_synthetic_count": synthetic_count,
        "selected_real_count": len(selected) - synthetic_count,
        "baseline": baseline,
        "closure_timeline": timeline,
        "rule_results": rule_results,
        "closure_steps": closure_steps,
        "before_after": before_after,
        "final_metrics": final_metrics,
        "page_consistency": page_consistency,
        "limitations": [
            "本证据库由正式 API 流程创建；高优先级条目来自合成 asset-cdx-* 资产。",
            "B 的 D:\\ICT\\intel-data-b-poc-20261002 数据副本不在当前主机，无法声称复现其中 27 条基线。",
            "真实运行时依赖资产已导入并参与研判，但该事件/组件交集没有产生高优先级 affected 条目。",
            "verified 只表示系统按当前资产版本重新研判通过，不代表生产环境已经实际执行升级。",
            "accepted 仅用于验证口径，不计入 verified_rate。",
        ],
    }
    _write_json(output / "evidence.json", evidence)
    _write_json(output / "page-consistency.json", page_consistency)
    _write_json(output / "before-after.json", before_after)
    _write_csv(output / "state-machine-rules.csv", [
        {
            "rule": item["rule"],
            "passed": item["passed"],
            "expected": item["expected"],
            "http_status": (item.get("request") or {}).get("http_status"),
            "actual_status": (
                (item.get("actual") or {}).get("status")
                or item.get("actual_status")
                or (item.get("request") or {}).get("response", {}).get("applied_status")
            ),
        }
        for item in rule_results
    ])
    _write_csv(output / "closure-timeline.csv", [
        {
            "label": item["label"],
            "captured_at": item["captured_at"],
            "high_priority_total": item["metrics"]["high_priority_total"],
            "high_priority_closed": item["metrics"]["high_priority_closed"],
            "high_priority_verified": item["metrics"]["high_priority_verified"],
            "closure_rate": item["metrics"]["closure_rate"],
            "verified_rate": item["metrics"]["verified_rate"],
            "status_breakdown": json.dumps(item["metrics"]["status_breakdown"], ensure_ascii=False),
        }
        for item in timeline
    ])
    print(json.dumps({
        "output": str(output),
        "high_priority_total": evidence["high_priority_total"],
        "selected_count": evidence["selected_count"],
        "selected_synthetic_count": synthetic_count,
        "closure_rate": final_metrics["closure_rate"],
        "verified_rate": final_metrics["verified_rate"],
        "rule_results": {item["rule"]: item["passed"] for item in rule_results},
        "page_consistency": page_consistency["consistent"],
    }, ensure_ascii=True, indent=2))
    return 0 if all(item["passed"] for item in rule_results) and page_consistency["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
