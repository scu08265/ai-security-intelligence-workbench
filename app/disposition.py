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
import importlib.util
import sys
from pathlib import Path
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
        # Frozen at open time.  ``metrics()`` uses this to keep a finding in
        # the closure-rate denominator after remediation flips its live
        # assessment to ``not_affected``.
        "opened_priority": existing.get("opened_priority") or assessment.get("priority"),
        "opened_assessment_status": existing.get("opened_assessment_status") or assessment.get("status"),
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


def _is_high_priority_cohort(item: dict[str, Any]) -> bool:
    """Whether a finding belongs in the closure-rate denominator.

    A finding enters the cohort while it is a high-priority ``affected``
    assessment, and it stays there once a disposition has been opened on it.
    The priority observed at open time is frozen in the disposition record, so
    remediating the asset -- which flips the live assessment to
    ``not_affected`` -- cannot silently remove the finding from both the
    numerator and the denominator and collapse the closure rate right after a
    successful fix.
    """
    assessment = item["assessment"]
    disposition = item["disposition"]
    if (assessment.get("status") == "affected"
            and assessment.get("priority") in HIGH_PRIORITIES):
        return True
    if not disposition.get("opened_at"):
        return False
    opened_priority = disposition.get("opened_priority") or assessment.get("priority")
    return opened_priority in HIGH_PRIORITIES


def metrics() -> dict[str, Any]:
    assessments = storage.list_assessments(limit=2000)
    dispositions = {str(item.get("event_id")) + "::" + str(item.get("asset_id")): item
                    for item in storage.list_assessment_dispositions(limit=5000)}
    events = {str(event.get("id")): event for event in storage.all_events()}

    def row(assessment: dict) -> dict:
        key = str(assessment.get("event_id")) + "::" + str(assessment.get("asset_id"))
        disposition = _display(dispositions.get(key))
        return {"assessment": assessment, "disposition": disposition, "key": key}

    rows = [row(item) for item in assessments]
    findings = [item for item in rows if item["assessment"].get("status") in {"affected", "needs_confirmation"}]
    high = [item for item in rows if _is_high_priority_cohort(item)]
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
            "已登记处置的条目锁定在分母内，不因资产修复后研判转为不受影响而消失。"
        ),
        "limitations": [
            "合成演示资产上的处置记录不等于生产环境的真实修复。",
            "接受风险（accepted）只表示处置决策，不代表风险已消除。",
            "平均关闭时长只统计已有 opened_at 与 closed_at 的记录。",
        ],
    }

# --------------------------------------------------------------------------
# B-task disposal advisor bridge (single source of truth for recommendations)
# --------------------------------------------------------------------------

_ADVISOR = None


def _load_advisor():
    """Load tools/asset_disposal_advisor.py once, without duplicating its logic."""
    global _ADVISOR
    if _ADVISOR is not None:
        return _ADVISOR
    path = Path(config.BASE_DIR) / "tools" / "asset_disposal_advisor.py"
    if not path.is_file():
        _ADVISOR = False
        return _ADVISOR
    spec = importlib.util.spec_from_file_location("asset_disposal_advisor", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _ADVISOR = module
    return _ADVISOR


def advice(event_id: str, asset_id: str) -> dict[str, Any]:
    """Return the B-task policy-aware action plan for one finding.

    Recommendations are not decisions: this only reads the advisor output. The
    disposition record stays the system of record for what was actually done.
    """
    advisor = _load_advisor()
    if not advisor:
        return {"available": False, "reason": "处置建议模块不可用"}
    asset = _asset(asset_id)
    event = storage.get_event(event_id)
    if asset is None or event is None:
        return {"available": False, "reason": "事件或资产不存在"}
    try:
        policy = advisor.default_policy(str(asset_id))
        result = advisor.advise(asset, policy, {str(event_id): event})
    except Exception as exc:
        return {"available": False, "reason": "建议生成失败：" + str(exc)}
    disclaimer = result.get("disclaimer") or "本建议只读，不是执行记录；系统不执行扫描/隔离/升级/关机等任何生产动作。"
    finding = next((f for f in result.get("findings", []) if f.get("event_id") == event_id), None)
    if finding is None:
        return {
            "available": False,
            "reason": "该事件与资产组件不匹配，处置建议不适用",
            "disclaimer": disclaimer,
        }
    return {
        "available": True,
        "policy_explicit": finding.get("policy_explicit"),
        "owner": finding.get("owner"),
        "link_status": finding.get("link_status"),
        "confidence": finding.get("confidence"),
        "score": (finding.get("priority") or {}).get("score"),
        "level": (finding.get("priority") or {}).get("level"),
        "recommended_actions": finding.get("recommended_actions") or [],
        "blocked_actions": finding.get("blocked_actions") or [],
        "scheduling": finding.get("scheduling") or {},
        "conflicts": finding.get("conflicts") or [],
        "needs_human_review": finding.get("needs_human_review"),
        "enrichment_gaps": finding.get("enrichment_gaps") or [],
        "evidence_ids": finding.get("evidence_ids") or [],
        "limitations": finding.get("limitations") or [],
        "disclaimer": disclaimer,
    }
