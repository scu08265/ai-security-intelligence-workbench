"""Evidence-backed competition metric projection.

Every value is derived from persisted events, source state, evaluations or run
records.  A metric that cannot be supported by those records is ``None``.
"""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from . import agents, b_evaluation, evaluation, reliability, sources, storage


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _metric(value: Any, *, source: str, sample_size: int | None = None,
            note: str | None = None) -> dict:
    result = {"value": value, "source": source}
    if sample_size is not None:
        result["sample_size"] = sample_size
    if note:
        result["note"] = note
    return result


def _source_metrics() -> dict:
    states = storage.all_source_states()
    producing = [spec for spec in sources.SOURCES
                 if int((states.get(spec.id) or {}).get("events_count") or 0) > 0]
    categories = sorted({spec.category for spec in producing})
    display_categories = sorted({sources.display_group(spec.id) for spec in producing})
    return {
        "actual_producing_sources": _metric(len(producing), source="source_state.events_count"),
        "registered_sources": _metric(len(sources.SOURCES), source="sources.SOURCES",
                                      note="登记数不计作实际产出数。"),
        "actual_categories": _metric(len(categories), source="producing source registry categories"),
        "category_ids": categories,
        "display_categories": display_categories,
        "independent_sources": _metric(
            sum(1 for spec in producing if spec.independent_origin),
            source="source_state + SourceSpec.independent_origin"),
        "realtime_capable_sources": _metric(
            sum(1 for spec in producing if spec.realtime),
            source="source_state + SourceSpec.realtime",
            note="表示实际产出来源中具备实时能力者，不等同于本次延迟达标。"),
        "items": [{
            "id": spec.id, "name": spec.name, "category": spec.category,
            "display_category": sources.display_group(spec.id),
            "independent_origin": spec.independent_origin, "realtime": spec.realtime,
            "events_count": int((states.get(spec.id) or {}).get("events_count") or 0),
            "last_success": (states.get(spec.id) or {}).get("last_success"),
        } for spec in producing],
    }


def _monitoring_metrics(runs: list[dict] | None = None) -> dict:
    runs = list(runs) if runs is not None else storage.list_runs(limit=2000)
    evidence = agents.monitoring_evidence(days=7, runs=runs)
    report = reliability.build_reliability_report(days=7, runs=runs)
    cumulative = reliability.cumulative_run_evidence(runs)
    timeliness = report["timeliness"]
    continuous = report["continuous_runs"]
    measured = timeliness["effective_denominator"]
    within_6h = timeliness["within_6h"]["count"]
    within_12h = timeliness["within_12h"]["count"]
    within = timeliness["within_24h"]["count"]
    observed = timeliness["post_monitoring_samples"]
    unknown = timeliness["unknown_samples"]
    return {
        "window_days": 7,
        "monitoring_started_at": _metric(
            timeliness["monitoring_started_at"],
            source="earliest persisted collect run started_at",
        ),
        "actual_run_days": _metric(
            continuous["actual_run_days"],
            source="runs(kind=collect)",
        ),
        "scheduled_run_days": _metric(
            continuous["scheduled_run_days"],
            source="runs(kind=collect,detail.trigger=scheduled)",
            note="只有外部计划任务触发的采集才计入赛题连续运行天数。"),
        "scheduled_run_evidence": [{
            "id": run.get("id"), "started_at": run.get("started_at"),
            "status": run.get("status"),
            "task_id": (run.get("detail") or {}).get("scheduler", {}).get("task_id"),
        } for run in storage.list_runs(limit=500)
          if run.get("kind") == "collect"
          and (run.get("detail") or {}).get("trigger") == "scheduled"][:20],
        "observed_events": _metric(observed, source="event.monitoring_observations"),
        "publication_latency_samples": _metric(measured, source="event.monitoring_observations"),
        "effective_denominator": _metric(
            timeliness["effective_denominator"],
            source="event.monitoring_observations",
        ),
        "post_monitoring_samples": _metric(
            timeliness["post_monitoring_samples"],
            source="event.monitoring_observations",
        ),
        "baseline_excluded_samples": _metric(
            timeliness["baseline_excluded_samples"],
            source="event.monitoring_observations",
            note="系统首次监测前发布的历史回填，不进入正式时延分母。",
        ),
        "unknown_latency_samples": _metric(unknown, source="event.monitoring_observations"),
        "within_6h_samples": _metric(within_6h, source="event.monitoring_observations"),
        "within_6h_rate": _metric(_rate(within_6h, measured), source="event.monitoring_observations",
                                  sample_size=measured),
        "within_12h_samples": _metric(within_12h, source="event.monitoring_observations"),
        "within_12h_rate": _metric(_rate(within_12h, measured), source="event.monitoring_observations",
                                   sample_size=measured),
        "within_24h_samples": _metric(within, source="event.monitoring_observations"),
        "within_24h_rate": _metric(_rate(within, measured), source="event.monitoring_observations",
                                   sample_size=measured),
        "cumulative_actual_run_days": _metric(
            cumulative["actual_run_days"],
            source="runs(kind=collect) distinct started_at dates",
            note="累计有采集日期；不受滚动窗口影响。"),
        "cumulative_scheduled_run_days": _metric(
            cumulative["scheduled_run_days"],
            source="runs(kind=collect,detail.trigger=scheduled) distinct started_at dates",
            note="累计定时运行日期；只有 trigger=scheduled 的计划任务计入。"),
        "cumulative_first_collection_date": _metric(
            cumulative["first_collection_date"],
            source="runs(kind=collect) distinct started_at dates"),
        "cumulative_last_collection_date": _metric(
            cumulative["last_collection_date"],
            source="runs(kind=collect) distinct started_at dates"),
        "cumulative_actual_run_count": _metric(
            cumulative["actual_run_count"], source="runs(kind=collect)"),
        "cumulative_scheduled_run_count": _metric(
            cumulative["scheduled_run_count"],
            source="runs(kind=collect,detail.trigger=scheduled)"),
        "days": evidence["days"],
        "note": (
            evidence["note"]
            + " actual_run_days 统计任一采集运行；scheduled_run_days 只统计计划任务。"
            + " 时延指标与可靠性 Markdown/JSON 使用同一口径。"

            + " cumulative_actual_run_days / cumulative_scheduled_run_days 为累计不同自然日。"
        ),
    }


def _enrichment_metrics(events: list[dict]) -> dict:
    total = len(events)
    dimensions = {
        "paper_link": lambda event: (
            sources.event_group(event) == "论文" or
            any(str(item.get("id") or "").split(":", 1)[0] == "arxiv"
                for item in event.get("sources") or [])
        ),
        "asset_assessment": None,
        "poc": lambda event: bool(event.get("poc")),
        "cvss": lambda event: bool(event.get("cvss")),
        "fixed_version": lambda event: any(item.get("fixed_version")
                                             for item in event.get("affected") or []),
        "evidence_relationship": lambda event: any(item.get("evidence_ids")
                                                     for item in event.get("relationships") or []),
    }
    assessment_event_ids = {str(item.get("event_id")) for item in storage.list_assessments(limit=2000)
                            if item.get("event_id")}
    result = {}
    for name, predicate in dimensions.items():
        present = (sum(1 for event in events if str(event.get("id")) in assessment_event_ids)
                   if predicate is None else sum(1 for event in events if predicate(event)))
        result[name] = {
            "present_events": present, "total_events": total,
            "coverage": _rate(present, total),
            "source": ("assessments" if name == "asset_assessment" else "events.doc"),
        }
    return {
        "event_sample_size": total,
        "dimensions": result,
        "definitions": {
            "paper_link": "事件本身属于论文类，或带已保存的 arxiv 来源。",
            "asset_assessment": "事件存在已持久化的资产研判记录。",
            "poc": "事件保存了至少一条 POC 记录；未收录不代表不存在。",
            "cvss": "事件保存了至少一条 CVSS 记录。",
            "fixed_version": "affected 中保存了修复版本。",
            "evidence_relationship": "relationships 中至少一条关系带 evidence_ids。",
        },
    }


def _evaluation_metrics() -> dict:
    latest = evaluation.latest_evaluation()
    metrics = latest.get("metrics") or {}
    if latest.get("status") != "completed":
        return {
            "status": "not_run",
            "retrieval_precision": None, "retrieval_recall": None,
            "answer_accuracy": None, "citation_accuracy": None,
            "refusal_accuracy": None, "response_duration_ms": None,
            "sample_counts": None,
            "source": "latest persisted evaluation run",
            "note": "尚未执行评测，所有评测指标保持 null。",
        }
    duration = metrics.get("qa_response_duration_ms")
    return {
        "status": "completed", "executed_at": latest.get("executed_at"),
        "retrieval_precision": metrics.get("retrieval_precision"),
        "retrieval_recall": metrics.get("retrieval_recall"),
        "answer_accuracy": metrics.get("answer_accuracy"),
        "citation_accuracy": metrics.get("citation_accuracy"),
        "refusal_accuracy": metrics.get("refusal_accuracy"),
        "response_duration_ms": duration,
        "sample_counts": metrics.get("labelled_counts"),
        "source": "runs(kind=evaluation).detail.metrics",
        "note": "响应耗时为标注问答逐题实测的平均值、最大值与样本数；旧评测记录为 null。",
        "limitations": latest.get("limitations") or [],
    }


def _agent_metrics(events: list[dict]) -> dict:
    runs = storage.list_runs(limit=200)
    scheduled_runs = [
        run for run in runs
        if (run.get("detail") or {}).get("trigger") == "scheduled"
    ]
    role_counts: Counter[str] = Counter()
    for event in events:
        pipeline = event.get("pipeline") or {}
        for item in pipeline.get("history") or []:
            if item.get("role"):
                role_counts[str(item["role"])] += 1
        for item in pipeline.get("scheduler_trace") or []:
            if item.get("role"):
                role_counts[str(item["role"])] += 1
    tool_calls = 0
    tool_call_runs = 0
    for run in runs:
        detail = run.get("detail") or {}
        calls = detail.get("tool_calls")
        if isinstance(calls, int):
            tool_calls += calls
            tool_call_runs += 1
    run_counts = Counter(str(run.get("kind") or "unknown") for run in runs)
    status_counts = Counter(str(run.get("status") or "unknown") for run in runs)
    return {
        "observed_roles": [{"role": role, "steps": count}
                           for role, count in sorted(role_counts.items())],
        "role_evidence_source": "event.pipeline.history + scheduler_trace",
        "tool_calls": _metric(tool_calls if tool_call_runs else None,
                              source="runs.detail.tool_calls", sample_size=tool_call_runs,
                              note="仅汇总明确保存 tool_calls 的运行，避免从事件轨迹重复计数。"),
        "persisted_runs": _metric(len(runs), source="runs"),
        "runs_by_kind": dict(run_counts),
        "runs_by_status": dict(status_counts),
        "external_automation_verified": _metric(
            True if scheduled_runs else None,
            source="runs.detail.trigger",
            sample_size=len(scheduled_runs),
            note=("存在外部计划任务触发的采集记录。" if scheduled_runs
                  else "尚无外部计划任务触发记录，保持未知。"),
        ),
        "scheduled_runs": _metric(
            len(scheduled_runs) if scheduled_runs else None,
            source="runs.detail.trigger",
            sample_size=len(scheduled_runs),
        ),
        "scheduled_evidence": [{
            "id": run.get("id"),
            "status": run.get("status"),
            "started_at": run.get("started_at"),
            "task_id": (run.get("detail") or {}).get("scheduler", {}).get("task_id"),
            "planned_at": (run.get("detail") or {}).get("scheduler", {}).get("planned_at"),
            "actual_at": (run.get("detail") or {}).get("scheduler", {}).get("actual_at"),
        } for run in scheduled_runs[:10]],
        "recent_evidence": [{"id": run.get("id"), "kind": run.get("kind"),
                             "status": run.get("status"), "started_at": run.get("started_at"),
                             "finished_at": run.get("finished_at")}
                            for run in runs[:20]],
    }


def scorecard() -> dict:
    events, total = storage.list_events(limit=500)
    return {
        "generated_at": storage.utcnow(),
        "evidence_policy": "只聚合现有数据库、评测与运行记录；无证据的指标返回 null。",
        "corpus": {"events_loaded": len(events), "events_total": total,
                   "truncated": total > len(events)},
        "sources": _source_metrics(),
        "monitoring_7d": _monitoring_metrics(),
        "enrichment": _enrichment_metrics(events),
        "question_answer_evaluation": _evaluation_metrics(),
        "b_evaluation": b_evaluation.summary(),
        "agent_execution": _agent_metrics(events),
    }
