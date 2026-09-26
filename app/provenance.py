"""Auditable publication, discovery, and ingestion timestamps."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def _parse(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def annotate_discovery(event: dict, source_id: str, discovered_at: str) -> dict:
    """Record when a fetched record was first observed, without inventing dates."""
    result = deepcopy(event)
    discovered = _parse(discovered_at)
    published = _parse(result.get("published_at"))
    latency = max(0.0, (discovered - published).total_seconds()) if discovered and published else None
    result["monitoring"] = {
        "source_id": source_id,
        "source_published_at": result.get("published_at"),
        "discovered_at": _iso(discovered) if discovered else discovered_at,
        "ingested_at": None,
        "publication_to_discovery_seconds": round(latency, 3) if latency is not None else None,
        "within_24h": latency <= 86400 if latency is not None else None,
        "latency_basis": "publisher timestamp to collector observation",
    }
    result["monitoring_observations"] = [dict(result["monitoring"])]
    for source in result.get("sources") or []:
        source.setdefault("discovered_at", result["monitoring"]["discovered_at"])
    return result


def mark_ingested(event: dict, ingested_at: str) -> dict:
    result = deepcopy(event)
    timing = dict(result.get("monitoring") or {})
    timing["ingested_at"] = ingested_at
    discovered, ingested = _parse(timing.get("discovered_at")), _parse(ingested_at)
    timing["discovery_to_ingest_seconds"] = (
        round(max(0.0, (ingested - discovered).total_seconds()), 3)
        if discovered and ingested else None
    )
    result["monitoring"] = timing
    observations = [dict(item) for item in result.get("monitoring_observations") or []]
    if observations:
        observations[-1].update({
            "ingested_at": ingested_at,
            "discovery_to_ingest_seconds": timing["discovery_to_ingest_seconds"],
        })
    else:
        observations = [dict(timing)]
    result["monitoring_observations"] = observations
    return result


def summarize(events: list[dict]) -> dict:
    measured = [
        (event.get("monitoring") or {}).get("publication_to_discovery_seconds")
        for event in events
    ]
    measured = sorted(float(value) for value in measured if value is not None)
    within = sum(value <= 86400 for value in measured)

    def percentile(fraction: float) -> float | None:
        if not measured:
            return None
        index = min(len(measured) - 1, max(0, round((len(measured) - 1) * fraction)))
        return round(measured[index], 3)

    return {
        "events_seen": len(events),
        "events_with_publisher_time": len(measured),
        "within_24h": within,
        "over_24h": len(measured) - within,
        "within_24h_rate": round(within / len(measured), 4) if measured else None,
        "latency_seconds_p50": percentile(0.50),
        "latency_seconds_p95": percentile(0.95),
        "note": "仅统计来源提供公开时间的条目；未知时间不计为达标。",
    }
