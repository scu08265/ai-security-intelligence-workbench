"""Bounded automatic recovery for source collection failures.

The policy is intentionally narrow: retry a failed or stale source, classify
the failure, keep the previous snapshot, and record whether automatic recovery
succeeded.  It never invents success and never treats manual re-runs as
self-healing.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from . import agents, observability, sources, storage


RETRYABLE_SOURCE_STATUSES = {"failed", "stale"}
# 决策 1（2026-10-15 定稿，选项 A2）：撞抓取预算报 partial 是采集器的设计行为，
# 不是故障，所以 partial 本身不算失败。只有"连续 partial 且零产出"才按失败累计——
# 那才是"跑得起来但什么都采不到"的半坏状态。
FAILURE_STATUSES = {"failed", "stale"}
PRODUCTION_KEYS = ("kept", "events_added", "events_updated")
MAX_RECOVERY_RETRIES = 1

# A single retry is not a recovery policy.  Once a source has missed this many
# collection attempts in a row the loop stops paying full price for it: it is
# dropped from the unattended set for a cooldown, or replaced by a substitute
# that is declared on the source itself.
CONSECUTIVE_FAILURE_THRESHOLD = 3
DEGRADE_COOLDOWN_HOURS = 6
DEGRADE_ACTIONS = ("switch_backup", "reduce_frequency")


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


def consecutive_failures(source_id: str, runs: list[dict] | None = None) -> int:
    """How many recent collection attempts in a row count as failures.

    Only persisted ``collect`` runs count, newest first, and a source that has
    never been attempted has a streak of zero rather than a streak of success.
    Self-healing retries are ordinary attempts and therefore count too.

    An attempt counts as a failure when it is ``failed``/``stale``, or when it
    is ``partial`` with no output.  ``ok`` and a *productive* ``partial`` both
    break the streak: the collector ran, returned rows and kept some, which is
    a working source even when it stopped at its fetch budget.
    """
    items = runs if runs is not None else storage.list_runs(limit=None)
    streak = 0
    for run in items:
        result = _attempt_of(source_id, run)
        if result is None:
            continue
        if counts_as_failure(result.get("status"), produced(result)):
            streak += 1
            continue
        break
    return streak


def _attempt_of(source_id: str, run: dict) -> dict[str, Any] | None:
    """The result row this run recorded for ``source_id``, if it attempted it."""
    if run.get("kind") not in {"collect", "scheduled_collect"}:
        return None
    for result in ((run.get("detail") or {}).get("results") or []):
        if result.get("source_id") == source_id:
            return result
    return None


def produced(result: dict[str, Any]) -> bool:
    """Whether an attempt put anything into the corpus.

    ``fetched`` is deliberately excluded: it counts HTTP volume, and a partial
    run that stopped at its budget can pull thousands of rows and keep none.
    A record that carries no production counters at all counts as producing —
    the policy must not degrade a source over missing metadata.
    """
    present = [key for key in PRODUCTION_KEYS
               if key in result and result.get(key) is not None]
    if not present:
        return True
    return any(int(result.get(key) or 0) > 0 for key in present)


def counts_as_failure(status: str | None, produced_anything: bool) -> bool:
    """决策 1/2 的判定：哪些取值计入降级 streak。"""
    if status in FAILURE_STATUSES:
        return True
    if status == "partial":
        return not produced_anything
    return False


def streak_detail(source_id: str, runs: list[dict] | None = None) -> dict[str, Any]:
    """Streak plus the newest attempt it was derived from, for the run record."""
    items = runs if runs is not None else storage.list_runs(limit=None)
    newest: dict[str, Any] | None = None
    for run in items:
        result = _attempt_of(source_id, run)
        if result is None:
            continue
        newest = {
            "run_id": run.get("id"),
            "started_at": run.get("started_at"),
            "status": result.get("status"),
            "produced": produced(result),
            "counts_as_failure": counts_as_failure(result.get("status"), produced(result)),
        }
        break
    return {"streak": consecutive_failures(source_id, items), "newest_attempt": newest}


def degradation_for(
    source_id: str,
    streak: int,
    state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Pick the bounded action for a source that keeps failing, if any.

    ``state`` is the live ``source_state`` row.  Its ``status``/``last_error``
    are the only real evidence about *why* the source is failing, so the
    recorded ``failure_class`` comes from them; passing a hardcoded "failed"
    made the field say ``unknown`` on every record while the answer sat right
    there (决策 4).
    """
    if streak < CONSECUTIVE_FAILURE_THRESHOLD:
        return None
    current = state or {}
    failure_class = classify_failure(current.get("status"), current.get("last_error"))
    spec = sources.get(source_id)
    backups = [item for item in (spec.backup_sources if spec else ()) if item]
    reason_tail = "failed/stale，或零产出的 partial"
    if backups:
        return {
            "source_id": source_id,
            "action": "switch_backup",
            "backup_sources": backups,
            "failure_class": failure_class,
            "consecutive_failures": streak,
            "source_status": current.get("status"),
            "last_error": current.get("last_error"),
            "reason": f"连续 {streak} 次失败（{reason_tail}），切换到已登记的备用源",
        }
    return {
        "source_id": source_id,
        "action": "reduce_frequency",
        "backup_sources": [],
        "failure_class": failure_class,
        "consecutive_failures": streak,
        "source_status": current.get("status"),
        "last_error": current.get("last_error"),
        "reason": f"连续 {streak} 次失败（{reason_tail}），冷却期内不再进入无人值守采集",
    }


def _expiry(hours: int = DEGRADE_COOLDOWN_HOURS) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def apply_degradation_policy(
    selected: Sequence[str], *, now: str | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Filter an unattended run's source list through the active degradations.

    Returns the sources to actually collect plus a note per decision, so the
    run record shows why a source is missing instead of it quietly vanishing.
    """
    # A source that answers again is no longer degraded.  Clearing only inside
    # run_self_healing was not enough: self-healing is invoked when a collection
    # comes back failed or partial, so after a transient outage the recovered
    # sources could stay out of the unattended set for the rest of the cooldown
    # while every later run reported "completed".  19 sources were sitting in
    # that state when this was found.
    states = storage.all_source_states()
    active: dict[str, dict[str, Any]] = {}
    for entry in storage.active_source_degradations(now):
        source_id = entry["source_id"]
        if (states.get(source_id) or {}).get("status") == "ok":
            storage.clear_source_degradation(source_id)
            continue
        active[source_id] = entry
    final: list[str] = []
    notes: list[dict[str, Any]] = []
    for source_id in selected:
        entry = active.get(source_id)
        if not entry:
            if source_id not in final:
                final.append(source_id)
            continue
        backups = [
            item for item in (entry.get("backup_sources") or [])
            if item and sources.get(item) is not None
        ]
        if entry.get("action") == "switch_backup" and backups:
            notes.append({
                "source_id": source_id,
                "action": "switch_backup",
                "substituted_with": [item for item in backups if item not in final],
                "reason": entry.get("reason"),
                "expires_at": entry.get("expires_at"),
            })
            for backup in backups:
                if backup not in final:
                    final.append(backup)
            continue
        notes.append({
            "source_id": source_id,
            "action": entry.get("action"),
            "substituted_with": [],
            "reason": entry.get("reason"),
            "expires_at": entry.get("expires_at"),
        })
    return final, notes


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
        state_after = storage.source_state(source_id)
        entry = {
            "source_id": source_id,
            "failure_class": decision.get("failure_class"),
            "previous_status": state.get("status"),
            "recovery_run_id": result.get("run_id"),
            "run_status": result.get("status"),
            "source_status_after": state_after.get("status"),
            "status": state_after.get("status"),
            "recovered": state_after.get("status") == "ok",
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

    # A retry that keeps failing is not a strategy, so the loop also bounds the
    # cost: sources that hit the streak threshold leave the unattended set for a
    # cooldown, and a source with a declared substitute hands over to it.
    runs = storage.list_runs(limit=None)
    fresh_states = storage.all_source_states()
    details = {
        source_id: streak_detail(source_id, runs)
        for source_id in sorted(set(fresh_states) | set(candidates))
    }
    streaks = {
        source_id: detail["streak"] for source_id, detail in details.items()
    }
    degradations: list[dict[str, Any]] = []
    cleared: list[str] = []
    for source_id, streak in streaks.items():
        # A source that answers again is no longer degraded, whether it came
        # back through this cycle's retry or recovered on its own in between.
        # Leaving the cooldown in place after a healthy response would report a
        # working source as degraded for the rest of the window.
        if (fresh_states.get(source_id) or {}).get("status") == "ok":
            if storage.clear_source_degradation(source_id):
                cleared.append(source_id)
            continue
        entry = degradation_for(source_id, streak, fresh_states.get(source_id) or {})
        if not entry:
            continue
        entry["expires_at"] = _expiry()
        storage.save_source_degradation(entry)
        degradations.append(entry)
        observability.emit_alert(
            "source_degraded",
            (
                f"{source_id} 连续 {streak} 次失败（failed/stale，或零产出的 partial），"
                + (
                    f"已切换到备用源 {', '.join(entry['backup_sources'])}"
                    if entry["action"] == "switch_backup"
                    else "冷却期内已移出无人值守采集"
                )
            ),
            severity="warning",
            context=entry,
        )

    payload = {
        "status": "completed",
        "candidates": len(candidates),
        "decisions": decisions,
        "recovered": recovered,
        "failed_after_retry": failed_after_retry,
        "consecutive_failures": {
            source_id: streak for source_id, streak in streaks.items() if streak
        },
        "streak_detail": details,
        "degradations": degradations,
        "degradations_cleared": cleared,
        "active_degradations": storage.active_source_degradations(),
        "recovery_rate": (
            round(len(recovered) / len(decisions), 4) if decisions else None
        ),
        "policy": {
            "automatic_actions": [
                "有限重试",
                "连续失败（failed/stale，或零产出的 partial）后降频（移出无人值守采集）",
                "有备用源的来源切换到备用源",
                "历史数据降级",
                "来源跳过",
            ],
            "manual_action": "超过自动重试预算后转人工处理",
            "retry_budget_per_source": max(0, max_retries),
            "consecutive_failure_threshold": CONSECUTIVE_FAILURE_THRESHOLD,
            "cooldown_hours": DEGRADE_COOLDOWN_HOURS,
            "counted_as_failure": ["failed", "stale", "partial（零产出）"],
            "not_counted_as_failure": ["ok", "partial（有产出）"],
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
            f"恢复 {len(recovered)} 个，仍失败 {len(failed_after_retry)} 个，"
            f"降级 {len(degradations)} 个"
        ),
        "detail": payload,
    })
    return payload
