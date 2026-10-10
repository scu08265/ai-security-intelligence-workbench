"""Persistence, snapshots and the export snapshot."""

from __future__ import annotations

import json

from app import config, storage

from fixtures import OSV_SYNTHETIC
from app import normalize


def _event(event_id="CVE-2099-00001", **updates):
    base = {
        "id": event_id, "kind": "vulnerability", "status": "confirmed",
        "title": "Synthetic storage fixture", "summary": "Synthetic.",
        "component": "vllm", "ecosystem": "PyPI",
        "published_at": "2099-01-01T00:00:00Z", "collected_at": storage.utcnow(),
        "withdrawn": False, "aliases": ["GHSA-synth-alias"],
        "ai_relevance": {"included": True, "reason": "synthetic"},
        "content_hash": "hash-1",
    }
    base.update(updates)
    return base


def test_upsert_reports_creation_then_update():
    assert storage.upsert_event(_event()) == ("CVE-2099-00001", True)
    assert storage.upsert_event(_event(title="Changed")) == ("CVE-2099-00001", False)
    assert storage.get_event("CVE-2099-00001")["title"] == "Changed"


def test_event_requires_an_identifier():
    import pytest

    with pytest.raises(ValueError):
        storage.upsert_event({"title": "no id"})


def test_aliases_are_searchable():
    storage.upsert_event(_event())
    assert storage.find_event_by_identifier("GHSA-synth-alias")["id"] == "CVE-2099-00001"
    assert storage.find_event_by_identifier("CVE-2099-00001")["id"] == "CVE-2099-00001"
    assert storage.find_event_by_identifier("CVE-2099-99999") is None


def test_poc_backfill_merges_without_replacing_the_event():
    storage.upsert_event(_event(title="original", poc=[]))
    poc = [{
        "url": "https://example.invalid/exploit", "status": "public_exploit_reference",
        "source_id": "nvd:poc-1", "verified": False,
    }]
    assert storage.merge_event_poc("CVE-2099-00001", poc) is True
    assert storage.merge_event_poc("CVE-2099-00001", poc) is False
    stored = storage.get_event("CVE-2099-00001")
    assert stored["title"] == "original"
    assert stored["poc"] == poc


def test_search_matches_document_text_and_alias():
    storage.upsert_event(_event())
    assert storage.list_events(query="storage fixture")[1] == 1
    assert storage.list_events(query="GHSA-synth-alias")[1] == 1
    assert storage.list_events(query="nothing-matches-this")[1] == 0


def test_status_filter_is_applied():
    storage.upsert_event(_event())
    storage.upsert_event(_event("CVE-2099-00002", status="needs_review"))
    items, total = storage.list_events(status="needs_review")
    assert total == 1 and items[0]["id"] == "CVE-2099-00002"


def test_snapshot_is_content_addressed_and_deduplicated():
    first = storage.save_snapshot("nvd", b'{"a": 1}')
    second = storage.save_snapshot("nvd", b'{"a": 1}')
    other = storage.save_snapshot("nvd", b'{"a": 2}')
    assert first == second != other
    path = storage.snapshot_path("nvd", first)
    assert path.exists() and path.read_bytes() == b'{"a": 1}'
    assert len(list((config.SNAPSHOT_DIR / "nvd").iterdir())) == 2


def test_source_state_is_honest_about_failure():
    storage.update_source_state("nvd", status="failed", last_error="HTTP 503",
                                last_run=storage.utcnow())
    state = storage.source_state("nvd")
    assert state["status"] == "failed"
    assert state["last_error"] == "HTTP 503"
    assert state["last_success"] is None


def test_source_event_inventory_counts_unique_events_not_runs():
    storage.upsert_event(_event("CVE-2099-00010", sources=[{"id": "msrc:a"}]))
    storage.upsert_event(_event("CVE-2099-00011", sources=[{"id": "msrc:b"}]))
    storage.upsert_event(_event("CVE-2099-00010", title="updated", sources=[{"id": "msrc:a"}]))
    assert storage.count_events_for_source_prefix("msrc") == 2


def test_assets_round_trip_and_delete_cascades_assessments():
    asset = storage.upsert_asset({"name": "synthetic host", "component": "vllm",
                                  "version": "1.0.0", "authorized": True, "is_demo": True})
    storage.upsert_event(_event())
    storage.save_assessment({"event_id": "CVE-2099-00001", "asset_id": asset["id"],
                             "status": "affected", "priority": "high", "reasons": ["synthetic"]})
    assert storage.count_assessments() == 1

    items = storage.list_assessments()
    assert items[0]["asset_name"] == "synthetic host"
    assert items[0]["event_title"] == "Synthetic storage fixture"

    assert storage.delete_asset(asset["id"]) is True
    assert storage.count_assets() == 0
    assert storage.count_assessments() == 0


def test_assessment_upsert_replaces_rather_than_duplicates():
    asset = storage.upsert_asset({"name": "host", "component": "vllm", "authorized": True})
    for status in ("affected", "not_affected"):
        storage.save_assessment({"event_id": "CVE-2099-00001", "asset_id": asset["id"],
                                 "status": status, "priority": "low", "reasons": []})
    items = storage.list_assessments()
    assert len(items) == 1 and items[0]["status"] == "not_affected"


def test_counts_separate_knowledge_from_vulnerabilities():
    storage.upsert_event(_event())
    storage.upsert_event(_event("ARXIV-1", kind="knowledge", status="confirmed"))
    storage.upsert_event(_event("CVE-2099-00003", status="needs_review"))
    counts = storage.count_events()
    assert counts["events"] == 3
    assert counts["knowledge"] == 1
    assert counts["vulnerability"] == 2
    assert counts["needs_review"] == 1


def test_export_contains_no_credentials():
    storage.upsert_event(_event())
    payload = json.dumps(storage.export_snapshot(), ensure_ascii=False)
    assert "sk-" not in payload
    assert config.API_KEY_ENV not in payload
    assert config.API_KEY_ENV.lower() not in payload.lower()


def test_run_history_is_recorded_and_ordered():
    storage.save_run({"id": "run-a", "kind": "collect", "status": "completed",
                      "started_at": "2099-01-01T00:00:00Z", "finished_at": "2099-01-01T00:01:00Z",
                      "summary": "first", "detail": {"results": []}})
    storage.save_run({"id": "run-b", "kind": "collect", "status": "partial",
                      "started_at": "2099-01-02T00:00:00Z", "finished_at": "2099-01-02T00:01:00Z",
                      "summary": "second", "detail": None})
    runs = storage.list_runs()
    assert [r["id"] for r in runs] == ["run-b", "run-a"]
    assert storage.latest_run("collect")["id"] == "run-b"
    assert storage.latest_run("enrich") is None


def test_list_runs_without_limit_returns_every_row_not_just_one_page():
    """A cumulative day count must not depend on a page cap.

    Regression: every read was silently capped at 200 rows, so once a single
    day produced more than 200 runs the older days fell off the end and the
    continuous-monitoring day count went backwards day over day.
    """
    rows = [
        (
            f"run-{index:04d}", "collect", "completed",
            f"2099-01-01T00:{index // 60:02d}:{index % 60:02d}Z",
            f"2099-01-01T00:{index // 60:02d}:{index % 60:02d}Z",
            None, json.dumps({"results": []}),
        )
        for index in range(250)
    ]
    with storage.connect() as conn:
        conn.executemany(
            "INSERT INTO runs (id, kind, status, started_at, finished_at, summary, detail)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    # limit=None is the whole-table read the evidence aggregation relies on.
    assert len(storage.list_runs(limit=None)) == 250
    # A page-limited read stays bounded so the API cannot return unbounded rows.
    assert len(storage.list_runs(limit=2000)) == 200


def test_list_events_without_limit_returns_the_whole_corpus():
    """The same page-cap trap as list_runs, on the event corpus.

    ``all_events()`` used to claim "everything" while list_events quietly
    clamped it to 500 rows, so pulling the corpus past 500 re-scoped every
    metric computed from it.
    """
    stamp = "2099-01-01T00:00:00Z"
    rows = [
        (
            f"CVE-2099-{index:05d}", stamp, stamp,
            json.dumps({"id": f"CVE-2099-{index:05d}", "status": "confirmed"}),
        )
        for index in range(505)
    ]
    with storage.connect() as conn:
        conn.executemany(
            "INSERT INTO events (id, status, published_at, collected_at, doc)"
            " VALUES (?, 'confirmed', ?, ?, ?)",
            rows,
        )
    assert len(storage.all_events()) == 505
    assert len(storage.list_events(limit=None)[0]) == 505
    # A page-limited read stays bounded so the API cannot return unbounded rows.
    assert len(storage.list_events(limit=2000)[0]) == 500


def test_normalized_event_survives_a_storage_round_trip():
    event = normalize.osv_to_event(OSV_SYNTHETIC)
    storage.upsert_event(event)
    stored = storage.get_event(event["id"])
    assert stored["affected"] == event["affected"]
    assert stored["sources"] == event["sources"]
