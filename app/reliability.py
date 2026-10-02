"""Operational reliability, timeliness, and continuous-run evidence.

The report layer only projects persisted runs, source state, events, and raw
observations.  Missing evidence remains visible as unknown instead of being
converted to success.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Iterable

from . import config, sources, storage


TIMELINESS_TARGETS = (
    ("within_6h", 6 * 3600, "优秀目标 <= 6h"),
    ("within_12h", 12 * 3600, "良好目标 <= 12h"),
    ("within_24h", 24 * 3600, "合格目标 <= 24h"),
)

DEGRADATION_STRATEGIES: dict[str, dict[str, Any]] = {
    "arxiv": {
        "failure_reason": "当前网络出口访问 arXiv API 返回 HTTP 406。",
        "degradation": "保留真实失败记录，使用 OpenAlex 作为论文元数据与摘要备用源。",
        "data_availability": "历史快照与已入库论文仍可检索；不伪造 arXiv 新数据。",
        "manual_action": "更换可访问 arXiv API 的网络出口后重新运行。",
    },
    "openalex": {
        "failure_reason": "OpenAlex 限流、超时或响应格式变化。",
        "degradation": "保留上次成功快照和已入库论文；下一计划周期重试。",
        "data_availability": "历史论文元数据可继续查询，但不能宣称本周期已更新。",
        "manual_action": "检查 OpenAlex 服务状态和查询语法。",
    },
    "osv": {
        "failure_reason": "批量查询、详情请求超时或单次详情预算耗尽。",
        "degradation": "只把本轮成功解析的记录标记为成功，预算未处理项标记为部分成功。",
        "data_availability": "历史 OSV 事件可继续使用；缺口保留并进入下一轮。",
        "manual_action": "提高详情预算或增加下一轮排空任务。",
    },
    "msrc": {
        "failure_reason": "微软 CVRF 索引或月度文档不可用、结构变化或超时。",
        "degradation": "保留最近成功的厂商公告和快照，本轮明确标记失败或部分成功。",
        "data_availability": "历史厂商公告仍可用；新月份更新不能视为已完成。",
        "manual_action": "核对 MSRC API 和 CVRF 字段结构。",
    },
    "ghsa": {
        "failure_reason": "未配置 GITHUB_TOKEN 或 GitHub API 限流。",
        "degradation": "未配置令牌时主动跳过，不使用空结果冒充成功。",
        "data_availability": "已保存的 GHSA 历史事件仍可检索。",
        "manual_action": "在 .env 中配置具有只读权限的 GITHUB_TOKEN。",
    },
}


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.year < 1990:
        return None
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(item) for item in values if item is not None)
    if not ordered:
        return None
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 3)


def _first_observation(event: dict) -> dict[str, Any] | None:
    observations = [
        dict(item) for item in event.get("monitoring_observations") or []
        if item.get("discovered_at")
    ]
    if observations:
        observations.sort(key=lambda item: str(item.get("discovered_at") or ""))
        return observations[0]
    monitoring = event.get("monitoring")
    return dict(monitoring) if monitoring else None


def latency_records(
    events: Iterable[dict], *, monitoring_started_at: datetime | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for event in events:
        observation = _first_observation(event)
        published = _parse(
            (observation or {}).get("source_published_at")
            or (observation or {}).get("published_at")
            or event.get("published_at")
        )
        discovered = _parse((observation or {}).get("discovered_at") or event.get("collected_at"))
        record = {
            "event_id": event.get("id"),
            "source_id": (observation or {}).get("source_id"),
            "published_at": _iso(published) if published else None,
            "discovered_at": _iso(discovered) if discovered else None,
            "latency_seconds": None,
            "latency_hours": None,
            "valid": False,
            "is_post_monitoring": (
                monitoring_started_at is None
                or discovered is None
                or discovered >= monitoring_started_at
            ),
            "unknown_reason": None,
        }
        stored_latency = (observation or {}).get("publication_to_discovery_seconds")
        explicit_publisher_time = bool(
            (observation or {}).get("source_published_at") or event.get("published_at")
        )
        if (
            published is not None
            and monitoring_started_at is not None
            and published < monitoring_started_at
        ):
            record["unknown_reason"] = "baseline_backfill_before_monitoring_start"
        elif published is None and stored_latency is not None and not explicit_publisher_time:
            latency = max(0.0, float(stored_latency))
            record["latency_seconds"] = round(latency, 3)
            record["latency_hours"] = round(latency / 3600, 3)
            record["valid"] = True
        elif published is None:
            record["unknown_reason"] = "invalid_or_missing_publisher_time"
        elif discovered is None:
            record["unknown_reason"] = "missing_discovery_time"
        elif published > discovered:
            record["unknown_reason"] = "publisher_time_after_discovery"
        else:
            latency = max(0.0, (discovered - published).total_seconds())
            record["latency_seconds"] = round(latency, 3)
            record["latency_hours"] = round(latency / 3600, 3)
            record["valid"] = True
        records.append(record)
    return records


def timeliness_stats(
    events: Iterable[dict], *, monitoring_started_at: datetime | None = None,
) -> dict[str, Any]:
    records = latency_records(events, monitoring_started_at=monitoring_started_at)
    valid = [item for item in records if item["valid"]]
    baseline = [
        item for item in records
        if item["unknown_reason"] == "baseline_backfill_before_monitoring_start"
    ]
    unknown = [
        item for item in records
        if not item["valid"]
        and item["unknown_reason"] != "baseline_backfill_before_monitoring_start"
    ]
    post_monitoring = [item for item in records if item["is_post_monitoring"]]
    result: dict[str, Any] = {
        "sample_size": len(records),
        "post_monitoring_samples": len(post_monitoring),
        "computable_samples": len(valid),
        "effective_denominator": len(valid),
        "unknown_samples": len(unknown),
        "baseline_excluded_samples": len(baseline),
        "monitoring_started_at": _iso(monitoring_started_at) if monitoring_started_at else None,
        "unknown_reasons": dict(Counter(item["unknown_reason"] for item in unknown)),
        "latency_seconds_p50": _percentile(
            [item["latency_seconds"] for item in valid], 0.50,
        ),
        "latency_seconds_p95": _percentile(
            [item["latency_seconds"] for item in valid], 0.95,
        ),
        "records": records,
    }
    for key, threshold, target_label in TIMELINESS_TARGETS:
        count = sum(float(item["latency_seconds"]) <= threshold for item in valid)
        result[key] = {
            "count": count,
            "rate": round(count / len(valid), 4) if valid else None,
            "target": target_label,
        }
    return result


def _run_results(run: dict) -> list[dict[str, Any]]:
    return [
        item for item in (run.get("detail") or {}).get("results") or []
        if item.get("source_id")
    ]


def _is_scheduled_run(run: dict) -> bool:
    return (run.get("detail") or {}).get("trigger") == "scheduled"


def _is_collect_run(run: dict) -> bool:
    return run.get("kind") in {"collect", "scheduled_collect"}


def source_health(runs: Iterable[dict]) -> dict[str, Any]:
    states = storage.all_source_states()
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        if run.get("kind") not in {"collect", "scheduled_collect"}:
            continue
        for result in _run_results(run):
            history[str(result["source_id"])].append({
                **result,
                "run_id": run.get("id"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "trigger": (run.get("detail") or {}).get("trigger") or "unknown",
            })

    items: list[dict[str, Any]] = []
    for spec in sources.SOURCES:
        state = states.get(spec.id, {})
        attempts = history.get(spec.id, [])
        succeeded = [item for item in attempts if item.get("status") in {"ok", "partial"}]
        failed = [item for item in attempts if item.get("status") == "failed"]
        stale = [item for item in attempts if item.get("status") == "stale"]
        skipped = [item for item in attempts if item.get("status") == "skipped"]
        durations = [
            float(item.get("duration_ms")) for item in attempts
            if item.get("duration_ms") is not None
        ]
        classified = len(succeeded) + len(failed) + len(stale)
        current_status = str(state.get("status") or "idle")
        if current_status in {"failed", "stale"} and int(state.get("events_count") or 0) > 0:
            health_class = "real_failure_historical_data_available"
        elif current_status in {"failed", "stale"}:
            health_class = "real_failure_no_historical_data"
        elif current_status == "skipped":
            health_class = "intentional_skip"
        elif current_status == "partial":
            health_class = "partial_success"
        elif current_status == "ok":
            health_class = "succeeded"
        else:
            health_class = "not_run"
        items.append({
            "id": spec.id,
            "name": spec.name,
            "category": spec.category,
            "auto_default": spec.auto_default,
            "events_count": int(state.get("events_count") or 0),
            "last_run": state.get("last_run"),
            "last_success": state.get("last_success"),
            "last_error": state.get("last_error"),
            "attempts": len(attempts),
            "successful_attempts": len(succeeded),
            "failed_attempts": len(failed),
            "stale_attempts": len(stale),
            "skipped_attempts": len(skipped),
            "partial_attempts": sum(item.get("status") == "partial" for item in attempts),
            "success_rate": round(len(succeeded) / classified, 4) if classified else None,
            "duration_ms_p50": _percentile(durations, 0.50),
            "duration_ms_p95": _percentile(durations, 0.95),
            "current_status": current_status,
            "health_class": health_class,
            "failure_reason": state.get("last_error"),
            "degradation_strategy": DEGRADATION_STRATEGIES.get(spec.id, {
                "failure_reason": state.get("last_error") or "当前无失败记录。",
                "degradation": "保留历史证据并在下一计划周期重试。",
                "data_availability": (
                    "历史事件可继续查询。" if int(state.get("events_count") or 0) > 0
                    else "当前没有可用历史事件。"
                ),
                "manual_action": "检查上游状态、鉴权和响应结构。",
            }),
        })
    return {
        "version": config.APP_VERSION,
        "generated_at": storage.utcnow(),
        "source_count": len(items),
        "healthy_source_count": sum(
            item["health_class"] in {"succeeded", "partial_success"} for item in items
        ),
        "items": items,
    }


def _date_range(days: int, runs: Iterable[dict]) -> list[str]:
    run_dates = [
        str(run.get("started_at"))[:10] for run in runs
        if run.get("started_at")
    ]
    end = datetime.now(timezone.utc).date()
    if run_dates:
        earliest = datetime.fromisoformat(min(run_dates)).date()
        days = max(days, (end - earliest).days + 1)
    return [(end - timedelta(days=offset)).isoformat() for offset in reversed(range(days))]


def continuous_run_evidence(days: int = 7, runs: Iterable[dict] | None = None) -> dict[str, Any]:
    source_runs = list(runs or storage.list_runs(limit=2000))
    actual = [
        run for run in source_runs
        if _is_collect_run(run) and run.get("started_at")
    ]
    scheduled = [run for run in actual if _is_scheduled_run(run)]
    actual_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scheduled_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in actual:
        actual_by_day[str(run["started_at"])[:10]].append(run)
    for run in scheduled:
        scheduled_by_day[str(run["started_at"])[:10]].append(run)
    date_strings = _date_range(days, actual)
    ledger = []
    for date_string in date_strings:
        day_actual = sorted(
            actual_by_day.get(date_string, []),
            key=lambda run: str(run.get("started_at") or ""),
        )
        day_scheduled = sorted(
            scheduled_by_day.get(date_string, []),
            key=lambda run: str(run.get("started_at") or ""),
        )
        ledger.append({
            "date": date_string,
            "actual_executed": bool(day_actual),
            "actual_run_count": len(day_actual),
            "actual_successful_run_count": sum(
                run.get("status") == "completed" for run in day_actual
            ),
            "actual_partial_run_count": sum(
                run.get("status") == "partial" for run in day_actual
            ),
            "actual_failed_run_count": sum(
                run.get("status") == "failed" for run in day_actual
            ),
            "actual_run_ids": [run.get("id") for run in day_actual],
            "scheduled_executed": bool(day_scheduled),
            "scheduled_run_count": len(day_scheduled),
            "scheduled_successful_run_count": sum(
                run.get("status") == "completed" for run in day_scheduled
            ),
            "scheduled_partial_run_count": sum(
                run.get("status") == "partial" for run in day_scheduled
            ),
            "scheduled_failed_run_count": sum(
                run.get("status") == "failed" for run in day_scheduled
            ),
            "scheduled_run_ids": [run.get("id") for run in day_scheduled],
            # Backward-compatible fields mean scheduled execution.
            "executed": bool(day_scheduled),
            "run_count": len(day_scheduled),
            "successful_run_count": sum(
                run.get("status") == "completed" for run in day_scheduled
            ),
            "partial_run_count": sum(
                run.get("status") == "partial" for run in day_scheduled
            ),
            "failed_run_count": sum(
                run.get("status") == "failed" for run in day_scheduled
            ),
            "run_ids": [run.get("id") for run in day_scheduled],
        })
    consecutive = 0
    for item in reversed(ledger):
        if not item["scheduled_executed"]:
            break
        consecutive += 1
    return {
        "target_days": days,
        "actual_run_days": sum(item["actual_executed"] for item in ledger),
        "scheduled_run_days": sum(item["scheduled_executed"] for item in ledger),
        "observed_days": sum(item["scheduled_executed"] for item in ledger),
        "consecutive_executed_days": consecutive,
        "target_met": consecutive >= days,
        "ledger": ledger,
        "actual_run_count": len(actual),
        "scheduled_run_count": len(scheduled),
        "note": (
            "actual_run_days 统计任一采集运行；scheduled_run_days 只统计 "
            "trigger=scheduled 的外部计划任务运行。"
        ),
    }


def build_reliability_report(
    *, days: int = 7, events: list[dict] | None = None,
    runs: list[dict] | None = None,
) -> dict[str, Any]:
    event_items = events if events is not None else storage.all_events(limit=5000)
    run_items = runs if runs is not None else storage.list_runs(limit=2000)
    collect_runs = [
        run for run in run_items
        if _is_collect_run(run) and run.get("started_at")
    ]
    monitoring_started_at = None
    if collect_runs:
        monitoring_started_at = min(
            (
                _parse(run.get("started_at"))
                for run in collect_runs
                if _parse(run.get("started_at")) is not None
            ),
            default=None,
        )
    timeliness = timeliness_stats(
        event_items, monitoring_started_at=monitoring_started_at,
    )
    source_report = source_health(run_items)
    continuous = continuous_run_evidence(days=days, runs=run_items)
    warnings: list[dict[str, Any]] = []
    for item in source_report["items"]:
        if item["health_class"].startswith("real_failure"):
            warnings.append({
                "severity": "warning",
                "code": "source_failure",
                "source_id": item["id"],
                "message": item["last_error"] or "来源采集失败",
            })
    if not continuous["target_met"]:
        warnings.append({
            "severity": "info",
            "code": "continuous_evidence_incomplete",
            "message": (
                f"定时运行证据 {continuous['consecutive_executed_days']}/"
                f"{continuous['target_days']} 天，尚未满足连续 7 天要求。"
            ),
        })
    return {
        "version": config.APP_VERSION,
        "generated_at": storage.utcnow(),
        "definition": {
            "first_observation": "每个事件只取最早一次 discovered_at，重复更新不重复计入时延。",
            "invalid_publisher_time": "缺失、0001 等异常年份、发布时间晚于发现时间均记为未知。",
            "scheduled_run": "运行详情中 trigger=scheduled，即由外部计划任务触发。",
            "actual_run": "任一 kind=collect 的采集运行，包括人工和计划任务。",
            "monitoring_started_at": "数据库中最早一次持久化采集运行的开始时间。",
        },
        "timeliness": timeliness,
        "sources": source_report,
        "continuous_runs": continuous,
        "degradation_strategies": DEGRADATION_STRATEGIES,
        "warnings": warnings,
    }


def source_health_rows(report: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = report or build_reliability_report()
    rows: list[dict[str, Any]] = []
    for item in payload["sources"]["items"]:
        rows.append({
            "version": config.APP_VERSION,
            "source_id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "auto_default": item["auto_default"],
            "current_status": item["current_status"],
            "health_class": item["health_class"],
            "events_count": item["events_count"],
            "attempts": item["attempts"],
            "successful_attempts": item["successful_attempts"],
            "failed_attempts": item["failed_attempts"],
            "stale_attempts": item["stale_attempts"],
            "skipped_attempts": item["skipped_attempts"],
            "success_rate": item["success_rate"],
            "duration_ms_p50": item["duration_ms_p50"],
            "duration_ms_p95": item["duration_ms_p95"],
            "last_success": item["last_success"],
            "last_error": item["last_error"],
            "degradation": item["degradation_strategy"]["degradation"],
        })
    return rows
