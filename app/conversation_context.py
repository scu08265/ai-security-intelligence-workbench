"""Structured multi-turn focus and constraint resolution.

This module is deliberately independent of persistence.  It consumes and
returns the ``context_snapshot`` dictionary described in
``docs/AGENT_UPGRADE_PLAN.md`` and accepts a few nested aliases so a future task or
thread store can adopt it without changing question answering again.

Only identifiers and user-supplied constraints are carried across turns.
Free-form assistant prose is used solely as a legacy compatibility source and
is never promoted to a factual constraint.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable


EVENT_ID_RE = re.compile(r"\b(?:CVE-\d{4}-\d{4,}|GHSA-[A-Z0-9-]+|ARXIV-[A-Z0-9.\-]+)\b", re.I)
EVENT_PRONOUN_RE = re.compile(r"(?:它|该漏洞|这个漏洞|此漏洞|该事件|这个事件|前者|后者|\bit\b|\bthis vulnerability\b|\bthat issue\b)", re.I)
ASSET_PRONOUN_RE = re.compile(r"(?:该资产|这个资产|这台(?:机器|服务|主机)|我的资产|上述资产|\bthis asset\b|\bthat host\b)", re.I)
DOCUMENT_PRONOUN_RE = re.compile(r"(?:这篇(?:文档|论文)|该(?:文档|论文)|上述(?:文档|论文)|这份资料|\bthis (?:document|paper)\b|\bthat (?:document|paper)\b)", re.I)
PLURAL_RE = re.compile(r"(?:哪些|有哪些|全部|分别|对比|比较|它们|这些|all\b|compare|them\b)", re.I)
SWITCH_RE = re.compile(r"(?:换个|另一个|另外看|改看|转到|切换到|新话题|不说.+了|switch to|new topic|instead look at)", re.I)
CORRECTION_RE = re.compile(r"(?:更正|改为|改成|不是.+而是|纠正|actually|instead|correction)", re.I)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _norm(value: Any) -> str:
    return re.sub(r"[\s_.\-/]+", "", _text(value).casefold())


def _unique(values: Iterable[Any]) -> list[str]:
    return list(dict.fromkeys(_text(value) for value in values if _text(value)))


def _known_event_map(events: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for event in events:
        event_id = _text(event.get("id"))
        if not event_id:
            continue
        mapping[event_id.casefold()] = event_id
        for alias in event.get("aliases") or []:
            if _text(alias):
                mapping[_text(alias).casefold()] = event_id
    return mapping


def _snapshot_values(snapshot: dict | None) -> tuple[list[str], list[str], list[str], dict]:
    value = snapshot or {}
    focus = value.get("focus") if isinstance(value.get("focus"), dict) else {}
    event_ids = value.get("selected_event_ids", focus.get("event_ids", [])) or []
    asset_ids = value.get("selected_asset_ids", focus.get("asset_ids", [])) or []
    document_ids = value.get("selected_document_ids", focus.get("document_ids", [])) or []
    constraints = value.get("inherited_constraints", value.get("constraints", {})) or {}
    return _unique(event_ids), _unique(asset_ids), _unique(document_ids), deepcopy(constraints)


def _latest_structured_snapshot(history: list[dict]) -> dict | None:
    for message in reversed(history):
        candidate = message.get("context_snapshot")
        if isinstance(candidate, dict):
            return candidate
        # Some callers replay snapshots as typed history records.
        if message.get("type") == "context_snapshot" and isinstance(message.get("content"), dict):
            return message["content"]
    return None


def _legacy_focus(history: list[dict], events: list[dict], assets: list[dict]) -> tuple[list[str], list[str]]:
    """Recover identifiers from old text history without inheriting claims."""
    event_map = _known_event_map(events)
    asset_by_id = {_text(asset.get("id")).casefold(): _text(asset.get("id")) for asset in assets if asset.get("id")}
    asset_names = [(_norm(asset.get("name")), _text(asset.get("id"))) for asset in assets if asset.get("name") and asset.get("id")]
    for message in reversed(history):
        content = message.get("content")
        if not isinstance(content, str):
            continue
        event_ids = _unique(event_map[item.casefold()] for item in EVENT_ID_RE.findall(content) if item.casefold() in event_map)
        asset_ids = []
        for token, canonical in asset_by_id.items():
            if token and token in content.casefold():
                asset_ids.append(canonical)
        for name, canonical in asset_names:
            if name and name in _norm(content):
                asset_ids.append(canonical)
        if event_ids or asset_ids:
            return event_ids, _unique(asset_ids)
    return [], []


def _event_mentions(question: str, events: list[dict]) -> tuple[list[str], bool]:
    event_map = _known_event_map(events)
    ids = _unique(event_map[item.casefold()] for item in EVENT_ID_RE.findall(question) if item.casefold() in event_map)
    if ids:
        return ids, True

    normalized = _norm(question)
    component_matches: list[str] = []
    for event in events:
        event_id = _text(event.get("id"))
        names = [_text(event.get("component")), *(_text(alias) for alias in event.get("aliases") or [])]
        # A component name is an explicit mention; very short names would
        # otherwise match arbitrary prose.
        if any(len(_norm(name)) >= 3 and _norm(name) in normalized for name in names if name):
            component_matches.append(event_id)
    return _unique(component_matches), bool(component_matches)


def _asset_mentions(question: str, assets: list[dict]) -> tuple[list[str], bool]:
    lowered, normalized = question.casefold(), _norm(question)
    matches: list[str] = []
    for asset in assets:
        asset_id = _text(asset.get("id"))
        if not asset_id:
            continue
        if asset_id.casefold() in lowered:
            matches.append(asset_id)
            continue
        name = _norm(asset.get("name"))
        if len(name) >= 3 and name in normalized:
            matches.append(asset_id)
    return _unique(matches), bool(matches)


def _parse_constraint_changes(question: str) -> dict[str, Any]:
    """Parse explicit asset assumptions; never infer missing values."""
    changes: dict[str, Any] = {}
    version = re.search(r"(?:版本|version)\s*(?:是|为|=|改为|改成|to)?\s*([0-9][A-Za-z0-9_.+\-]*)", question, re.I)
    if version:
        changes["version"] = version.group(1)
    if re.search(r"(?:公网|互联网|public).{0,5}(?:暴露|开放|可访问)|exposure\s*=\s*public", question, re.I):
        changes["exposure"] = "public"
    if re.search(r"(?:不|未|没有)(?:向)?(?:公网|互联网).{0,5}(?:暴露|开放)|(?:仅|只)(?:在)?内网|exposure\s*=\s*internal", question, re.I):
        changes["exposure"] = "internal"
    if re.search(r"(?:高|核心|关键)(?:业务)?(?:重要性|资产)|criticality\s*=\s*high", question, re.I):
        changes["business_criticality"] = "high"
    if re.search(r"(?:低)(?:业务)?(?:重要性)|criticality\s*=\s*low", question, re.I):
        changes["business_criticality"] = "low"

    conditions: dict[str, bool] = {}
    # Machine-readable config names are safer to carry than an attempted
    # translation of arbitrary prose into configuration keys.
    condition_pattern = re.compile(
        r"\b([A-Za-z][A-Za-z0-9_.-]{1,63})\b\s*(?:=|是|为|已)?\s*(开启|启用|打开|关闭|禁用|true|false|enabled|disabled)\b",
        re.I,
    )
    for name, state in condition_pattern.findall(question):
        conditions[name] = state.casefold() in {"开启", "启用", "打开", "true", "enabled"}
    if conditions:
        changes["conditions"] = conditions

    removals = re.findall(r"(?:取消|删除|不再假设)\s*([A-Za-z][A-Za-z0-9_.-]{1,63})", question, re.I)
    if removals:
        changes["remove_conditions"] = removals
    return changes


def _merge_asset_constraints(
    inherited: dict, changes: dict, selected_asset_ids: list[str], *, reset: bool,
) -> tuple[dict, list[dict]]:
    constraints = {} if reset else deepcopy(inherited)
    overrides = constraints.setdefault("asset_overrides", {})
    target_ids = selected_asset_ids or ["*"]
    audit: list[dict] = []
    for asset_id in target_ids:
        current = deepcopy(overrides.get(asset_id) or {})
        for key in ("version", "exposure", "business_criticality"):
            if key in changes:
                previous = current.get(key)
                current[key] = changes[key]
                audit.append({"field": key, "asset_id": asset_id, "previous": previous, "current": changes[key]})
        condition_values = current.setdefault("conditions", {})
        for name, value in (changes.get("conditions") or {}).items():
            previous = condition_values.get(name)
            condition_values[name] = value
            audit.append({"field": f"conditions.{name}", "asset_id": asset_id, "previous": previous, "current": value})
        for name in changes.get("remove_conditions") or []:
            previous = condition_values.pop(name, None)
            audit.append({"field": f"conditions.{name}", "asset_id": asset_id, "previous": previous, "current": None})
        if not condition_values:
            current.pop("conditions", None)
        if current:
            overrides[asset_id] = current
        else:
            overrides.pop(asset_id, None)
    if not overrides:
        constraints.pop("asset_overrides", None)
    return constraints, audit


def resolve_conversation_context(
    question: str,
    events: list[dict],
    assets: list[dict],
    *,
    history: list[dict] | None = None,
    context_snapshot: dict | None = None,
) -> dict[str, Any]:
    """Resolve focus, references and user constraints for one turn."""
    history = history or []
    supplied_snapshot = context_snapshot is not None
    base_snapshot = context_snapshot if supplied_snapshot else _latest_structured_snapshot(history)
    previous_events, previous_assets, previous_documents, inherited = _snapshot_values(base_snapshot)
    context_source = "provided_snapshot" if supplied_snapshot else (
        "history_snapshot" if base_snapshot else "none"
    )
    if not base_snapshot:
        previous_events, previous_assets = _legacy_focus(history, events, assets)
        if previous_events or previous_assets:
            context_source = "legacy_history_identifiers"

    explicit_events, has_event_mention = _event_mentions(question, events)
    explicit_assets, has_asset_mention = _asset_mentions(question, assets)
    if CORRECTION_RE.search(question):
        # "不是 A，而是 B" and "改看 B" make the last explicit target the
        # corrected focus rather than a request to compare A with B.
        if len(explicit_events) > 1:
            explicit_events = explicit_events[-1:]
        if len(explicit_assets) > 1:
            explicit_assets = explicit_assets[-1:]
    event_pronoun = bool(EVENT_PRONOUN_RE.search(question))
    asset_pronoun = bool(ASSET_PRONOUN_RE.search(question))
    document_pronoun = bool(DOCUMENT_PRONOUN_RE.search(question))
    plural = bool(PLURAL_RE.search(question))

    topic_switched = False
    if has_event_mention and previous_events and set(explicit_events) != set(previous_events):
        topic_switched = True
    if SWITCH_RE.search(question) and (has_event_mention or has_asset_mention):
        topic_switched = True

    selected_events = explicit_events if has_event_mention else ([] if topic_switched else previous_events)
    selected_assets = explicit_assets if has_asset_mention else ([] if topic_switched else previous_assets)
    resolved_references: list[dict] = []
    if has_event_mention:
        resolved_references.append({"expression": "explicit_event", "type": "event", "ids": selected_events, "confidence": 1.0})
    elif event_pronoun and selected_events:
        resolved_references.append({"expression": "event_pronoun", "type": "event", "ids": selected_events,
                                    "confidence": 0.95 if len(selected_events) == 1 else 0.45})
    if has_asset_mention:
        resolved_references.append({"expression": "explicit_asset", "type": "asset", "ids": selected_assets, "confidence": 1.0})
    elif asset_pronoun and selected_assets:
        resolved_references.append({"expression": "asset_pronoun", "type": "asset", "ids": selected_assets,
                                    "confidence": 0.95 if len(selected_assets) == 1 else 0.45})
    if document_pronoun and previous_documents:
        resolved_references.append({"expression": "document_pronoun", "type": "document", "ids": previous_documents,
                                    "confidence": 0.95 if len(previous_documents) == 1 else 0.45})

    clarification: dict[str, Any] | None = None
    if event_pronoun and len(selected_events) > 1 and not plural:
        clarification = {
            "type": "event", "candidate_ids": selected_events,
            "question": "你说的“该漏洞”指哪一个事件？请指定事件编号。",
        }
    elif asset_pronoun and len(selected_assets) > 1 and not plural:
        clarification = {
            "type": "asset", "candidate_ids": selected_assets,
            "question": "你说的“该资产”指哪一个资产？请指定资产名称或编号。",
        }
    elif document_pronoun and len(previous_documents) > 1 and not plural:
        clarification = {
            "type": "document", "candidate_ids": previous_documents,
            "question": "当前会话引用了多篇文档。请指定要继续讨论的文档。",
        }
    elif has_asset_mention and len(selected_assets) > 1 and not plural:
        clarification = {
            "type": "asset", "candidate_ids": selected_assets,
            "question": "该名称关联多个资产。请指定资产编号，或明确要求比较全部资产。",
        }
    elif not has_event_mention and previous_events and len(selected_events) > 1 and not plural:
        clarification = {
            "type": "event", "candidate_ids": selected_events,
            "question": "当前会话同时聚焦多个事件。请指定要继续讨论的事件编号。",
        }

    changes = _parse_constraint_changes(question)
    reset_constraints = topic_switched
    inherited, applied_changes = _merge_asset_constraints(
        inherited, changes, selected_assets, reset=reset_constraints,
    )

    prior = base_snapshot or {}
    turn_value = prior.get("turn_id")
    if isinstance(turn_value, int):
        turn_value += 1
    elif turn_value:
        turn_value = f"{turn_value}:next"
    else:
        turn_value = 1
    snapshot = {
        "task_id": prior.get("task_id"),
        "turn_id": turn_value,
        "selected_event_ids": selected_events,
        "selected_asset_ids": selected_assets,
        "selected_document_ids": [] if topic_switched else previous_documents,
        "resolved_references": resolved_references,
        "inherited_constraints": inherited,
        "source_versions": deepcopy(prior.get("source_versions") or {}),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    return {
        "context_snapshot": snapshot,
        "context_source": context_source,
        "topic_switched": topic_switched,
        "corrected": bool(CORRECTION_RE.search(question) or applied_changes),
        "applied_changes": applied_changes,
        "needs_clarification": clarification is not None,
        "clarification": clarification,
    }


def apply_asset_constraints(asset: dict, constraints: dict) -> tuple[dict, list[dict]]:
    """Return a copy with explicit conversation assumptions applied."""
    result = deepcopy(asset)
    overrides = constraints.get("asset_overrides") or {}
    merged: dict[str, Any] = {}
    for key in ("*", _text(asset.get("id"))):
        value = overrides.get(key)
        if isinstance(value, dict):
            for field, field_value in value.items():
                if field == "conditions":
                    merged.setdefault("conditions", {}).update(field_value or {})
                else:
                    merged[field] = field_value
    applied: list[dict] = []
    for field, value in merged.items():
        if field == "conditions":
            conditions = deepcopy(result.get("conditions") or {})
            for name, state in value.items():
                conditions[name] = state
                applied.append({"field": f"conditions.{name}", "value": state, "source": "user_context"})
            result["conditions"] = conditions
        else:
            result[field] = value
            applied.append({"field": field, "value": value, "source": "user_context"})
    return result, applied
