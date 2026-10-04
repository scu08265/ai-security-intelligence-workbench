"""Remediation disposition closure loop for asset findings.

The assessment layer answers "is this asset affected?".  This module adds the
second half: who owns the finding, when it was opened, what was changed, and
whether a re-assessment confirms the risk is actually gone.

Design rules:

* The original assessment status is never mutated.  A finding can be
  ``verified`` closed while the evidence that it was once ``affected`` stays in
  the assessment table.
* A finding cannot be closed by assertion alone.  ``verified`` requires a
  system re-check that the asset version no longer matches the affected range.
* Unknowns and priorities are treated as data, not guesses: missing owner,
  missing re-check and missing version all stay visible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import config, intelligence, storage

DISPOSITION_STATUSES = ("open", "in_progress", "fixed", "verified", "accepted")
CLOSED_STATUSES = {"verified"}
RESOLVED_STATUSES = {"verified", "accepted"}
HIGH_PRIORITIES = {"critical", "high"}
STATUS_LABELS = {
    "open": "待处置",
    "in_progress": "处置中",
    "fixed": "已修复待复测",
    "verified": "已复测关闭",
    "accepted": "已接受风险",
}


class DispositionError(ValueError):
    """Raised when a disposition transition or input is invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(value: Any) -> datetime | None:
    text = str(value or "").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _hours_between(start: Any, end: Any) -> float | None:
    first, second = _parse(start), _parse(end)
    if first is None or second is None or second < first:
        return None
    return round((second - first).total_seconds() / 3600.0, 1)


def _assessment(event_id: str, asset_id: str) -> dict | None:
    records = storage.list_assessments(limit=2000)
    for item in records:
        if item.get("event_id") == event_id and item.get("asset_id") == asset_id:
            return item
    return None


def _asset(asset_id: str) -> dict | None:
    for item in storage.list_assets():
        if item.get("id") == asset_id:
            return item
    return None


def _display(disposition: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(disposition or {})
    status = str(item.get("status") or "open")
    item.setdefault("status", status)
    item["status_label"] = STATUS_LABELS.get(status, status)
    item["closed"] = status in CLOSED_STATUSES
    item["resolved"] = status in RESOLVED_STATUSES
    item["requires_verification"] = status in {"fixed"}
    return item


def get_disposition(event_id: str, asset_id: str) -> dict[str, Any]:
    return _display(storage.get_assessment_disposition(event_id, asset_id))


def list_dispositions(limit: int = 1000) -> dict[str, Any]:
    items = [_display(item) for item in storage.list_assessment_dispositions(limit=limit)]
    return {
        "items": items,
        "total": len(items),
        "status_labels": STATUS_LABELS,
    }


def _reverify(event_id: str, asset_id: str) -> dict[str, Any]:
    assessment = _assessment(event_id, asset_id)
    asset = _asset(asset_id)
    event = storage.get_event(event_id)
    if assessment is None or asset is None or event is None:
        raise DispositionError("找不到对应的研判结论、资产或事件，无法执行复测")
    try:
        result = intelligence.assess_asset(event, asset)
    except Exception as exc:  # pragma: no cover - defensive, surfaced to the user
        raise DispositionError(f"复测执行失败：{exc}") from exc
    previous_status = str(assessment.get("status") or "unknown")
    current_status = str(result.get("status") or "unknown")
    passed = current_status != "affected"
    return {
        "checked_at": _now(),
        "assessment_status_before": previous_status,
        "assessment_status_after": current_status,
        "priority_after": result.get("priority"),
        "reasons_after": result.get("reasons") or [],
        "passed": passed,
        "verdict": (
            "复测通过：按当前资产事实，该资产已不命中受影响区间。"
            if passed else
            "复测未通过：资产仍命中受影响区间，不能标记为已关闭。"
        ),
    }


def update_disposition(
    event_id: str,
    asset_id: str,
    *,
    status: str,
    assignee: str | None = None,
    note: str | None = None,
    evidence_ids: list[str] | None = None,
    version_before: str | None = None,
    version_after: str | None = None,
    operator: str | None = None,
    run_verification: bool = True,
) -> dict[str, Any]:
    status = str(status or "").strip()
    if status not in DISPOSITION_STATUSES:
        raise DispositionError(f"未知处置状态：{status or '空'}，允许值：{', '.join(DISPOSITION_STATUSES)}")
    assessment = _assessment(event_id, asset_id)
    if assessment is None:
        raise DispositionError("研判结论不存在，不能创建处置记录")
    asset = _asset(asset_id) or {}
    existing = storage.get_assessment_disposition(event_id, asset_id) or {}
    assignee = (assignee or existing.get("assignee") or "").strip() or None
    if status in {"in_progress", "fixed", "verified", "accepted"} and not assignee:
        raise DispositionError("进入处置流转必须填写处置人（assignee）")
    version_before = (version_before or existing.get("version_before") or asset.get("version") or "").strip() or None
    verification: dict[str, Any] | None = existing.get("verification")
    closed_at: str | None = existing.get("closed_at")
    final_status = status
    if status == "verified":
        if not run_verification:
            raise DispositionError("标记已复测关闭必须执行系统复测，不能仅靠人工声明")
        verification = _reverify(event_id, asset_id)
        if not verification.get("passed"):
            # Keep the finding open and record the failed re-check as audit evidence.
            final_status = "fixed"
            closed_at = None
        else:
            closed_at = verification["checked_at"]
            version_after = (version_after or asset.get("version") or "").strip() or None
    elif status in {"open", "in_progress", "fixed"}:
        closed_at = None
        if status != "fixed":
            verification = None
    elif status == "accepted":
        closed_at = existing.get("closed_at") or _now()
        verification = existing.get("verification")
    payload = {
        "event_id": event_id,
        "asset_id": asset_id,
        "status": final_status,
        "assignee": assignee,
        "note": (note if note is not None else existing.get("note")) or None,
        "evidence_ids": list(dict.fromkeys([*(existing.get("evidence_ids") or []), *(evidence_ids or [])])),
        "version_before": version_before,
        "version_after": version_after or existing.get("version_after"),
        "opened_at": existing.get("opened_at") or _now(),
        "updated_at": _now(),
        "closed_at": closed_at,
        "operator": operator or assignee,
        "system_version": config.APP_VERSION,
        "verification": verification,
    }
    storage.save_assessment_disposition(payload)
    return {
        "disposition": _display(storage.get_assessment_disposition(event_id, asset_id)),
        "assessment_status": assessment.get("status"),
        "assessment_priority": assessment.get("priority"),
        "verification": verification,
        "requested_status": status,
        "applied_status": final_status,
    }


def metrics() -> dict[str, Any]:
    assessments = storage.list_assessments(limit=2000)
    dispositions = {str(item.get("event_id")) + "::" + str(item.get("asset_id")): item
                    for item in storage.list_assessment_dispositions(limit=5000)}
    events = {str(event.get("id")): event for event in storage.all_events(limit=5000)}

    def row(assessment: dict) -> dict:
        key = str(assessment.get("event_id")) + "::" + str(assessment.get("asset_id"))
        disposition = _display(dispositions.get(key))
        return {"assessment": assessment, "disposition": disposition, "key": key}

    rows = [row(item) for item in assessments]
    findings = [item for item in rows if item["assessment"].get("status") in {"affected", "needs_confirmation"}]
    high = [item for item in rows if item["assessment"].get("status") == "affected"
            and item["assessment"].get("priority") in HIGH_PRIORITIES]
    closed = [item for item in high if item["disposition"]["resolved"]]
    verified = [item for item in high if item["disposition"]["status"] == "verified"]
    in_progress = [item for item in high if item["disposition"]["status"] in {"in_progress", "fixed"}]
    by_status: dict[str, int] = {name: 0 for name in DISPOSITION_STATUSES}
    for item in high:
        by_status[item["disposition"]["status"]] = by_status.get(item["disposition"]["status"], 0) + 1
    ages = [
        _hours_between(item["disposition"].get("opened_at"), item["disposition"].get("closed_at"))
        for item in closed
    ]
    ages = [age for age in ages if age is not None]
    total = len(high)
    return {
        "generated_at": _now(),
        "high_priority_total": total,
        "high_priority_closed": len(closed),
        "high_priority_verified": len(verified),
        "high_priority_in_progress": len(in_progress),
        "closure_rate": round(len(closed) / total, 4) if total else None,
        "verified_rate": round(len(verified) / total, 4) if total else None,
        "mean_time_to_close_hours": round(sum(ages) / len(ages), 1) if ages else None,
        "status_breakdown": by_status,
        "findings_total": len(findings),
        "evidence_policy": (
            "原始研判结论不会被处置覆盖；只有系统复测确认资产已不命中受影响区间，"
            "才计入已关闭。接受风险不改变原始受影响事实。"
        ),
        "limitations": [
            "合成演示资产上的处置记录不等于生产环境的真实修复。",
            "接受风险（accepted）只表示处置决策，不代表风险已消除。",
            "平均关闭时长只统计已有 opened_at 与 closed_at 的记录。",
        ],
    }
