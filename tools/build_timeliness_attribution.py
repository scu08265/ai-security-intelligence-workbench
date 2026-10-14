"""Attribute collection latency to source category and to upstream publish rhythm.

The competition asks for the delay between a *vulnerability's* publication and
our collection of it.  Mixing academic papers and policy feeds into that
denominator measures something else, so this report keeps the mixed figure
visible while splitting it by source category, and gives the upstream
attribution evidence: the same CVE published by two registries with different
timestamps.

Writes ``reports/timeliness-attribution.json`` and prints the markdown tables
that go into the technical report.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, reliability, sources, storage  # noqa: E402

# Buckets used in the report.  The registry's own `category` is the input; this
# only decides which of the three comparison groups a category belongs to.
BUCKETS: dict[str, tuple[str, ...]] = {
    "vulnerability": (
        "cve_database", "ecosystem_advisory", "community_advisory",
        "exploitation_intel", "vendor_advisory", "security_blog",
    ),
    "academic": ("academic_paper",),
    "policy": ("policy_regulation", "technical_standard", "risk_framework", "threat_framework"),
}
BUCKET_LABELS = {
    "vulnerability": "漏洞类（赛题口径）",
    "academic": "学术类（不计入赛题分母）",
    "policy": "政策类（不计入赛题分母）",
    "other": "未归类",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _bucket_for(category: str | None) -> str:
    for bucket, categories in BUCKETS.items():
        if category in categories:
            return bucket
    return "other"


def _registry() -> dict[str, sources.SourceSpec]:
    return {spec.id: spec for spec in sources.SOURCES}


def _hours(value: float | None) -> float | None:
    return None if value is None else round(value / 3600.0, 2)


def _summarise(values: Iterable[float]) -> dict[str, Any]:
    ordered = sorted(float(item) for item in values if item is not None)
    if not ordered:
        return {"n": 0, "p50_hours": None, "p95_hours": None, "max_hours": None, "within_24h": 0}
    return {
        "n": len(ordered),
        "p50_hours": _hours(reliability._percentile(ordered, 0.50)),
        "p95_hours": _hours(reliability._percentile(ordered, 0.95)),
        "max_hours": _hours(max(ordered)),
        "within_24h": sum(1 for item in ordered if item <= 86400),
    }


def _monitoring_started_at(runs: list[dict]) -> datetime | None:
    starts = [
        reliability._parse(run.get("started_at"))
        for run in runs
        if reliability._is_collect_run(run)
    ]
    starts = [item for item in starts if item is not None]
    return min(starts) if starts else None


def _multi_source_events(events: list[dict]) -> list[dict[str, Any]]:
    result = []
    for event in events:
        observations = [
            {
                "source_id": item.get("source_id"),
                "source_published_at": item.get("source_published_at") or item.get("published_at"),
                "discovered_at": item.get("discovered_at"),
                "ingested_at": item.get("ingested_at"),
            }
            for item in event.get("monitoring_observations") or []
            if item.get("source_id") and (item.get("source_published_at") or item.get("published_at"))
        ]
        distinct = {item["source_id"] for item in observations}
        if len(distinct) < 2:
            continue
        # One observation per source keeps the latest discovery for that source.
        newest: dict[str, dict] = {}
        for item in observations:
            current = newest.get(item["source_id"])
            if current is None or str(item["discovered_at"] or "") > str(current["discovered_at"] or ""):
                newest[item["source_id"]] = item
        ordered = sorted(newest.values(), key=lambda x: str(x["source_published_at"]))
        result.append({"event_id": event.get("id"), "sources": sorted(distinct), "observations": ordered})
    return result


def _pair_deltas(multi: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for item in multi:
        for first, second in zip(item["observations"], item["observations"][1:]):
            start = reliability._parse(first["source_published_at"])
            end = reliability._parse(second["source_published_at"])
            if start is None or end is None or end < start:
                continue
            key = f"{first['source_id']} -> {second['source_id']}"
            grouped[key].append((end - start).total_seconds())
    return {
        key: {"n": len(values), **_summarise(values)}
        for key, values in sorted(grouped.items(), key=lambda kv: -len(kv[1]))
    }


def _discovery_gaps(events: list[dict]) -> dict[str, Any]:
    stamps = sorted({
        str(item.get("discovered_at"))
        for event in events
        for item in event.get("monitoring_observations") or []
        if item.get("discovered_at")
    })
    parsed = [reliability._parse(item) for item in stamps]
    parsed = [item for item in parsed if item is not None]
    gaps = [
        (second - first).total_seconds()
        for first, second in zip(parsed, parsed[1:])
        if second > first
    ]
    return {
        "distinct_discovery_timestamps": len(parsed),
        **_summarise(gaps),
        "note": ("同一轮采集里多个来源会前后差几秒，所以这个中位数不是轮询间隔；"
                 "轮询间隔看 run_gaps。"),
    }


def _run_gaps(runs: list[dict]) -> dict[str, Any]:
    """Gaps between consecutive *collection run* starts: the polling cadence."""
    def _stamps(only_scheduled: bool) -> list[datetime]:
        selected = []
        for run in runs:
            if not reliability._is_collect_run(run):
                continue
            detail = run.get("detail") or {}
            if only_scheduled and detail.get("trigger") != "scheduled":
                continue
            stamp = reliability._parse(run.get("started_at"))
            if stamp is not None:
                selected.append(stamp)
        return sorted(selected)

    def _gap_stats(starts: list[datetime]) -> dict[str, Any]:
        gaps = [
            (second - first).total_seconds()
            for first, second in zip(starts, starts[1:])
            if second > first
        ]
        return {
            "runs": len(starts),
            "first_started_at": starts[0].isoformat() if starts else None,
            "last_started_at": starts[-1].isoformat() if starts else None,
            **_summarise(gaps),
        }

    return {
        "all": _gap_stats(_stamps(only_scheduled=False)),
        "scheduled_only": _gap_stats(_stamps(only_scheduled=True)),
        "note": ("相邻两次采集运行开始时间的间隔。人工补跑会夹在中间，所以 scheduled_only "
                 "才是轮询节奏的证据；计划任务配的是每 1 小时一次。"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "reports" / "timeliness-attribution.json")
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args()

    events = storage.all_events()
    runs = storage.list_runs(limit=None)
    monitoring = _monitoring_started_at(runs)
    stats = reliability.timeliness_stats(events, monitoring_started_at=monitoring)
    registry = _registry()

    valid = [item for item in stats["records"] if item["valid"]]
    by_source: dict[str, list[float]] = defaultdict(list)
    for item in valid:
        by_source[item["source_id"] or "(none)"].append(float(item["latency_seconds"]))

    source_rows = []
    for source_id, values in sorted(by_source.items(), key=lambda kv: -len(kv[1])):
        spec = registry.get(source_id)
        source_rows.append({
            "source_id": source_id,
            "category": spec.category if spec else None,
            "category_label": spec.category_label if spec else None,
            "bucket": _bucket_for(spec.category if spec else None),
            **_summarise(values),
        })

    buckets: dict[str, dict[str, Any]] = {}
    for bucket in list(BUCKETS) + ["other"]:
        values = [value for row in source_rows if row["bucket"] == bucket
                  for value in by_source[row["source_id"]]]
        if not values:
            continue
        buckets[bucket] = {
            "label": BUCKET_LABELS[bucket],
            "sources": [row["source_id"] for row in source_rows if row["bucket"] == bucket],
            **_summarise(values),
        }

    multi = _multi_source_events(events)
    pairs = _pair_deltas(multi)
    combos = Counter(" + ".join(item["sources"]) for item in multi)

    examples = sorted(
        (item for item in multi if len(item["observations"]) >= 2),
        key=lambda item: (-len(item["sources"]), item["event_id"]),
    )[: args.examples]

    payload = {
        "version": config.APP_VERSION,
        "generated_at": _utcnow(),
        "database": str(config.DB_PATH),
        "monitoring_started_at": stats["monitoring_started_at"],
        "definition": {
            "per_event": "每个事件只取最早一次 discovered_at，重复更新不重复计入时延。",
            "bucket_vulnerability": "赛题问的是漏洞信息从发布到采集的延迟，故分母只含发布漏洞信息的来源。",
            "bucket_others": "学术论文与政策法规的发布节奏与漏洞无关，单列但不进赛题分母。",
            "upstream_attribution": "同一 CVE 在两个登记源上的 source_published_at 差值即上游发布节奏。",
        },
        "mixed": {
            "label": "混合口径（附录，不删）",
            "sample_size": stats["sample_size"],
            "computable_samples": stats["computable_samples"],
            "latency_seconds_p50": stats["latency_seconds_p50"],
            "latency_seconds_p95": stats["latency_seconds_p95"],
            "p50_hours": _hours(stats["latency_seconds_p50"]),
            "p95_hours": _hours(stats["latency_seconds_p95"]),
            "within_6h": stats["within_6h"],
            "within_12h": stats["within_12h"],
            "within_24h": stats["within_24h"],
        },
        "by_source": source_rows,
        "by_bucket": buckets,
        "upstream": {
            "multi_source_events": len(multi),
            "combinations": dict(combos.most_common()),
            "publish_deltas": pairs,
        },
        "discovery_cadence": _discovery_gaps(events),
        "run_cadence": _run_gaps(runs),
        "timeline_examples": examples,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"written {args.output}")
    print(f"events={len(events)} valid={len(valid)} mixed_p50={payload['mixed']['p50_hours']}h")
    print()
    print("| 来源 | 类别 | 样本 | 中位(小时) | P95(小时) | 最大(小时) | ≤24h |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in source_rows:
        print(f"| {row['source_id']} | {row['category_label'] or row['category'] or '-'} "
              f"| {row['n']} | {row['p50_hours']} | {row['p95_hours']} | {row['max_hours']} "
              f"| {row['within_24h']} |")
    print()
    print("| 类别 | 来源 | 样本 | 中位(小时) | P95(小时) | 最大(小时) |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for bucket, data in buckets.items():
        print(f"| {data['label']} | {', '.join(data['sources'])} | {data['n']} "
              f"| {data['p50_hours']} | {data['p95_hours']} | {data['max_hours']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
