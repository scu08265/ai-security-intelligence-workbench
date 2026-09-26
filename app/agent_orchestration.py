"""Bounded, auditable planning for the single-process Agent runtime.

The planner may choose only names from the action catalogue below.  It never
receives credentials, raw database handles, shell access, or arbitrary URLs.
The caller executes the chosen actions and records their *observable* results;
we deliberately do not persist model scratch work.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


COLLECTION_ACTIONS = {"collect_registered_source", "ingest_arxiv_fulltext"}
ANSWER_ACTIONS = {
    "load_event_evidence", "load_knowledge_evidence", "load_authorized_assets",
    "answer_from_evidence",
}


def _call_json_planner(goal: str, allowed: list[str], context: dict, model: dict) -> tuple[list[str], str | None]:
    """Ask an OpenAI-compatible model for a JSON action list, then validate it.

    Invalid output is intentionally indistinguishable from a planner outage to
    the executor: both use the deterministic safe plan.
    """
    key_name = str(model.get("api_key_env") or "")
    key = os.getenv(key_name, "").strip()
    base_url = str(model.get("base_url") or "").rstrip("/")
    if not key or not base_url or not model.get("model"):
        return [], "模型配置不完整"
    prompt = (
        "你是受限安全情报任务规划器。仅返回 JSON："
        '{"actions":["允许的动作名"]}。不得增加动作、参数、URL或解释。'
        f"目标：{goal}\n允许动作：{json.dumps(allowed, ensure_ascii=False)}\n"
        f"公开上下文：{json.dumps(context, ensure_ascii=False)}"
    )
    body = json.dumps({"model": model["model"], "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    request = urllib.request.Request(
        base_url + "/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=min(float(model.get("timeout", 8)), 10)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = str(payload["choices"][0]["message"]["content"])
        match = re.search(r"\{.*\}", content, re.S)
        values = json.loads(match.group(0) if match else "{}").get("actions", [])
        if not isinstance(values, list):
            raise ValueError("actions 不是列表")
        chosen = [value for value in values if isinstance(value, str) and value in allowed]
        if not chosen:
            raise ValueError("没有有效白名单动作")
        return list(dict.fromkeys(chosen)), None
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as exc:
        return [], f"模型规划不可用，已降级：{type(exc).__name__}"


def collection_plan(source_ids: list[str], model: dict | None) -> dict:
    """Plan one independent whitelisted collection call per registered source."""
    safe = [{"action": "collect_registered_source", "source_id": source_id} for source_id in source_ids]
    if "arxiv" in source_ids:
        # This action has no model-controlled URL or identifier.  The
        # executor accepts only IDs observed in the registered Atom feed.
        safe.append({"action": "ingest_arxiv_fulltext", "source_id": "arxiv",
                     "limit": 5})
    # Source ids are user/request scope, not model-controlled parameters.  The
    # model can decide whether collection is useful, but cannot expand scope.
    chosen, fallback = _call_json_planner(
        "采集登记来源", sorted(COLLECTION_ACTIONS), {"source_count": len(source_ids)}, model or {},
    ) if model and model.get("planner") else ([], "未配置模型，使用确定性计划")
    actions = safe
    return {"kind": "collection", "planner": "model" if chosen else "deterministic",
            "fallback_reason": fallback, "actions": actions,
            "allowed_actions": sorted(COLLECTION_ACTIONS)}


def answer_plan(question: str, *, has_assets: bool, model: dict | None) -> dict:
    """Plan evidence reads before one mandatory bounded answer action."""
    required = ["load_event_evidence", "load_knowledge_evidence"]
    if has_assets:
        required.append("load_authorized_assets")
    allowed = sorted(ANSWER_ACTIONS)
    chosen, fallback = _call_json_planner(
        "用本地证据回答安全问题", allowed,
        {"question": question[:500], "assets_available": has_assets}, model or {},
    ) if model and model.get("planner") else ([], "未配置模型，使用确定性计划")
    # Evidence reads and the evidence-bound finalizer are compulsory.  Model
    # output can only order/select the additional allowed reads, never skip
    # source grounding or trigger external execution.
    actions = [action for action in chosen if action in required]
    for action in required:
        if action not in actions:
            actions.append(action)
    actions.append("answer_from_evidence")
    return {"kind": "answer", "planner": "model" if chosen else "deterministic",
            "fallback_reason": fallback, "actions": actions,
            "allowed_actions": allowed}


def audit(action: str, *, status: str, result: str, count: int | None = None) -> dict:
    """Return an audit-safe observation of an action, never its hidden inputs."""
    item: dict[str, Any] = {"action": action, "status": status, "result": result}
    if count is not None:
        item["count"] = count
    return item
