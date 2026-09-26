from app import agents, provenance, storage


def test_three_timestamps_and_24h_latency_are_distinct():
    event = {"id": "CVE-2099-1000", "published_at": "2099-01-01T00:00:00Z",
             "sources": [{"id": "src-1"}]}
    discovered = provenance.annotate_discovery(event, "official", "2099-01-01T12:00:00Z")
    ingested = provenance.mark_ingested(discovered, "2099-01-01T12:00:03Z")
    assert ingested["monitoring"]["publication_to_discovery_seconds"] == 43200
    assert ingested["monitoring"]["within_24h"] is True
    assert ingested["monitoring"]["discovery_to_ingest_seconds"] == 3
    assert ingested["sources"][0]["discovered_at"] == "2099-01-01T12:00:00Z"


def test_unknown_publisher_time_is_not_counted_as_success():
    event = provenance.annotate_discovery(
        {"id": "DOC-1", "published_at": None, "sources": []},
        "standard", "2099-01-01T12:00:00Z")
    summary = provenance.summarize([event])
    assert summary["events_seen"] == 1
    assert summary["events_with_publisher_time"] == 0
    assert summary["within_24h_rate"] is None


def test_seven_day_ledger_does_not_backfill_missing_runs():
    ledger = agents.monitoring_evidence(7)
    assert len(ledger["days"]) == 7
    assert ledger["complete_days"] == 0
    assert all(day["collection_runs"] == 0 for day in ledger["days"])


def test_ingested_observation_survives_storage():
    event = provenance.annotate_discovery({
        "id": "DOC-2", "kind": "knowledge", "status": "confirmed",
        "published_at": "2099-01-01T00:00:00Z", "collected_at": "2099-01-01T01:00:00Z",
        "sources": [], "ai_relevance": {"included": True},
    }, "official", "2099-01-01T01:00:00Z")
    stored = provenance.mark_ingested(event, "2099-01-01T01:00:01Z")
    storage.upsert_event(stored)
    loaded = storage.get_event("DOC-2")
    assert loaded["monitoring_observations"][0]["ingested_at"] == "2099-01-01T01:00:01Z"
