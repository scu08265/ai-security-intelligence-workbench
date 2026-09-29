"""Bounded automatic recovery for source collection failures.

The policy is intentionally narrow: retry a failed or stale source, classify
the failure, keep the previous snapshot, and record whether automatic recovery
succeeded.  It never invents success and never treats manual re-runs as
self-healing.
"""

from __future__ import annotations

import os
import re
from typing import Any

from . import agents, observability, storage


RETRYABLE_SOURCE_STATUSES = {"failed", "stale"}
MAX_RECOVERY_RETRIES = 1


def classify_failure(status: str | None, error: str | None) -> str:
    text = " ".join(str(item) for item in (status, error) if item).casefold()
    if "retry-after" in text or "rate limit" in text or "429" in text:
        return "rate_limit"
    if "timeout" in text or "timed out" in text or "408" in text or "503" in text:
        return "upstream_timeout"
    if "403" in text or "401" in text or "token" in text or "auth" in text:
        return "authentication"
    if "json" in text or "xml" in text or "parse" in text or "format" in text:
        return "format_change"
    if "connection" in text or "disconnect" in text or "incomplete chunked" in text:
        return "connection_reset"
    if "406" in text:
        return "upstream_rejected"
    return "unknown"


def recovery_decision(source_id: str, state: dict[str, Any]) -> dict[str, Any]:
    failure = classify_failure(state.get("status"), state.get("last_error"))
    if source_id == "ghsa" and not os.getenv("GITHUB_TOKEN", "").strip():
        return {
            "source_id": source_id,
            "retry": False,
            "reason": "缺少只读 GITHUB_TOKEN，主动跳过，等待人工配置",
        }
    if state.get("status") not in RETRYABLE_SOURCE_STATUSES:
        return {"source_id": source_id, "retry": False, "reason": "来源不需要恢复"}
    return {
        "source_id": source_id,
        "retry": True,
        "failure_class": failure,
        "reason": f"允许一次受控恢复重试：{failure}",
    }


def run_self_healing(
    source_ids: list[str] | None = None,
    *,
    max_retries: int = MAX_RECOVERY_RETRIES,
    parent_run_id: str | None = None,
) -> dict[str, Any]:
    """Retry recoverable source failures and persist an evidence ledger."""
    states = storage.all_source_states()
    candidates = source_ids or sorted(
        source_id for source_id, state in states.items()
        if state.get("status") in RETRYABLE_SOURCE_STATUSES
    )
    decisions: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    failed_after_retry: list[dict[str, Any]] = []
    for source_id in candidates:
        state = states.get(source_id, {})
        decision = recovery_decision(source_id, state)
        decisions.append(decision)
        if not decision.get("retry"):
            continue
        result = agents.run_collection(
            [source_id],
            trigger="self_healing",
            scheduler={"task_id": "self_healing", "parent_run_id": parent_run_id},
        )
        entry = {
            "source_id": source_id,
            "failure_class": decision.get("failure_class"),
            "previous_status": state.get("status"),
            "recovery_run_id": result.get("run_id"),
            "status": result.get("status"),
            "recovered": result.get("status") == "completed",
            "attempts": max(0, max_retries) + 1,
            "retry_count": max(0, max_retries),
        }
        if entry["recovered"]:
            recovered.append(entry)
        else:
            failed_after_retry.append(entry)
        observability.emit_alert(
            "self_healing_recovered" if entry["recovered"] else "self_healing_failed",
            (
                f"{source_id} 自动恢复成功"
                if entry["recovered"]
                else f"{source_id} 自动恢复后仍不可用"
            ),
            severity="info" if entry["recovered"] else "warning",
            context=entry,
        )

    payload = {
        "status": "completed",
        "candidates": len(candidates),
        "decisions": decisions,
        "recovered": recovered,
        "failed_after_retry": failed_after_retry,
        "recovery_rate": (
            round(len(recovered) / len(decisions), 4) if decisions else None
        ),
        "policy": {
            "automatic_actions": ["有限重试", "历史数据降级", "来源跳过"],
            "manual_action": "超过自动重试预算后转人工处理",
            "retry_budget_per_source": max(0, max_retries),
        },
    }
    storage.save_run({
        "id": storage.new_id("run"),
        "kind": "self_healing",
        "status": "completed",
        "started_at": storage.utcnow(),
        "finished_at": storage.utcnow(),
        "summary": (
            f"自愈检查：{len(candidates)} 个来源，"
            f"恢复 {len(recovered)} 个，仍失败 {len(failed_after_retry)} 个"
        ),
        "detail": payload,
    })
    return payload
