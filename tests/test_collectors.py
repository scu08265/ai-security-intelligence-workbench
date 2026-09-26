"""Collector behaviour against stubbed upstreams, fully offline.

The point of these tests is the *accounting*: what happens on a rate-limit, a
missing token, or a truncated run.  A collector must never turn those into a
silent success or an invented record.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app import collectors, storage
from app.sources import BY_ID

from fixtures import (
    ARXIV_SYNTHETIC, GHSA_SYNTHETIC, HTML_SYNTHETIC, KEV_SYNTHETIC, NVD_SYNTHETIC,
    OPENALEX_SYNTHETIC, OSV_QUERYBATCH_SYNTHETIC, OSV_SYNTHETIC, RSS_SYNTHETIC,
)

MSRC_INDEX = {
    "value": [
        {"ID": "2099-Jan", "CvrfUrl": "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2099-Jan",
         "CurrentReleaseDate": "2099-01-10T00:00:00Z"},
        {"ID": "2098-Dec", "CvrfUrl": "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2098-Dec",
         "CurrentReleaseDate": "2099-09-09T00:00:00Z"},
    ]
}
MSRC_CVRF = {
    "DocumentTitle": {"Value": "Synthetic Security Updates"},
    "ProductTree": {"FullProductName": [
        {"ProductID": "17084", "Value": "Microsoft Copilot Studio"},
        {"ProductID": "10378", "Value": "Windows Server 2012"},
    ]},
    "Vulnerability": [
        {
            "CVE": "CVE-2099-00010",
            "Title": {"Value": "Synthetic Copilot Studio Elevation of Privilege Vulnerability"},
            "ReleaseDate": "2099-01-10T00:00:00Z",
            "ProductStatuses": [{"ProductID": ["20296-17084"], "Type": 3}],
            "Notes": [{"Title": "Description", "Value": "Synthetic description text."}],
            "Threats": [{"Type": "Severity", "Description": {"Value": "Important"}}],
        },
        {
            "CVE": "CVE-2099-00011",
            "Title": {"Value": "Synthetic Windows Server issue"},
            "ReleaseDate": "2099-01-10T00:00:00Z",
            "ProductStatuses": [{"ProductID": ["10378"], "Type": 3}],
            "Notes": [{"Title": "Description", "Value": "Synthetic description text."}],
            "Threats": [],
        },
    ],
}


def _json_response(payload, status=200):
    return httpx.Response(status, json=payload, headers={"content-type": "application/json"})


def _router(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "services.nvd.nist.gov":
        return _json_response(NVD_SYNTHETIC)
    if host == "api.osv.dev":
        if path.endswith("/querybatch"):
            return _json_response(OSV_QUERYBATCH_SYNTHETIC)
        return _json_response(OSV_SYNTHETIC)
    if host == "www.cisa.gov":
        return _json_response(KEV_SYNTHETIC)
    if host == "api.github.com":
        return _json_response(GHSA_SYNTHETIC)
    if host == "api.msrc.microsoft.com":
        return _json_response(MSRC_INDEX if path.endswith("/updates") else MSRC_CVRF)
    if host == "export.arxiv.org":
        return httpx.Response(200, text=ARXIV_SYNTHETIC,
                              headers={"content-type": "application/atom+xml"})
    if host == "api.openalex.org":
        return _json_response(OPENALEX_SYNTHETIC)
    if host == "github.blog":
        return httpx.Response(200, text=RSS_SYNTHETIC, headers={"content-type": "application/rss+xml"})
    if host == "genai.owasp.org":
        return httpx.Response(200, text=HTML_SYNTHETIC, headers={"content-type": "text/html"})
    return httpx.Response(404, json={"detail": "unrouted"})


@pytest.fixture(autouse=True)
def stub_network():
    collectors.set_transport(httpx.MockTransport(_router))
    yield


def test_nvd_collector_keeps_only_ai_relevant_records():
    outcome = collectors.collect("nvd")
    assert outcome.status in {"ok", "partial"}
    assert outcome.fetched >= 1
    assert [e["id"] for e in outcome.events] == ["CVE-2099-00003"]
    assert outcome.snapshot_hash


def test_osv_collector_resolves_ranges_and_fetches_details():
    outcome = collectors.collect("osv")
    assert outcome.status in {"ok", "partial"}
    event = next(e for e in outcome.events if e["id"] == "GHSA-synth-aaaa-bbbb")
    assert event["affected"][0]["range"] == ">= 0.8.3, < 0.14.1"
    assert event["aliases"] == ["CVE-2099-00001"]


def test_kev_collector_filters_unrelated_products():
    outcome = collectors.collect("cisa_kev")
    ids = {e["id"] for e in outcome.events}
    assert "CVE-2099-00004" in ids, "MLflow is AI-relevant"
    assert "CVE-2099-00005" not in ids, "an office suite must be filtered out"
    assert outcome.filtered >= 1


def test_msrc_collector_picks_the_latest_release_and_maps_products():
    outcome = collectors.collect("msrc")
    assert outcome.status == "ok"
    # The index lists 2099-Jan with a later CurrentReleaseDate than 2098-Dec,
    # but ordering must follow the document id.
    assert any("2099-Jan" in note for note in outcome.notes)
    ids = {e["id"] for e in outcome.events}
    assert "CVE-2099-00010" in ids
    assert "CVE-2099-00011" not in ids, "Windows Server is not an AI product"
    event = next(e for e in outcome.events if e["id"] == "CVE-2099-00010")
    assert event["component"] == "Microsoft Copilot Studio"
    assert not event["title"].startswith("{"), "CVRF Title must be unwrapped"


def test_rss_collector_keeps_only_ai_related_items():
    outcome = collectors.collect("security_blog")
    titles = [e["title"] for e in outcome.events]
    assert any("Prompt injection" in t for t in titles)
    assert not any("Unrelated" in t for t in titles)


def test_arxiv_collector_produces_knowledge_events():
    outcome = collectors.collect("arxiv")
    assert outcome.events
    assert all(e["kind"] == "knowledge" for e in outcome.events)
    assert outcome.events[0]["sources"][0]["trust"] == "preprint"


def test_arxiv_collector_uses_https_and_an_atom_accept_header():
    seen = {}

    def arxiv_router(request: httpx.Request) -> httpx.Response:
        seen["scheme"] = request.url.scheme
        seen["accept"] = request.headers.get("accept")
        return httpx.Response(200, text=ARXIV_SYNTHETIC,
                              headers={"content-type": "application/atom+xml"})

    collectors.set_transport(httpx.MockTransport(arxiv_router))
    outcome = collectors.collect("arxiv")
    assert outcome.status == "ok"
    assert seen["scheme"] == "https"
    assert "application/atom+xml" in (seen["accept"] or "")


def test_arxiv_406_is_retried_before_reporting_failure(monkeypatch):
    calls = {"n": 0}

    def flaky_arxiv(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(406, text="not acceptable")
        return httpx.Response(200, text=ARXIV_SYNTHETIC,
                              headers={"content-type": "application/atom+xml"})

    monkeypatch.setattr(collectors, "BACKOFF_SECONDS", (0.0, 0.0))
    collectors.set_transport(httpx.MockTransport(flaky_arxiv))
    outcome = collectors.collect("arxiv")
    assert calls["n"] == 2
    assert outcome.status == "ok"
    assert outcome.events


def test_openalex_collector_is_the_tokenless_paper_fallback():
    outcome = collectors.collect("openalex")
    assert outcome.status == "ok"
    assert outcome.fetched == 2
    assert len(outcome.events) == 1
    event = outcome.events[0]
    assert event["kind"] == "knowledge"
    assert event["sources"][0]["publisher"] == "OpenAlex"
    assert "prompt injection" in event["summary"].casefold()
    assert event["paper"]["pdf_url"].endswith("ai-security.pdf")


def test_page_collector_does_not_re_emit_unchanged_content():
    first = collectors.collect("owasp_genai")
    assert first.events, "first fetch should produce an event"
    storage.update_source_state("owasp_genai", last_hash=first.snapshot_hash)

    second = collectors.collect("owasp_genai")
    assert second.events == []
    assert any("未产生新事件" in note for note in second.notes)


def test_page_collector_strips_scripts_from_extracted_text():
    outcome = collectors.collect("owasp_genai")
    excerpt = outcome.events[0]["sources"][0]["excerpt"]
    assert "ignored()" not in excerpt
    assert "prompt injection" in excerpt.casefold()


def test_ghsa_without_a_token_is_skipped_and_says_so():
    """It must not attempt unauthenticated and dress a 403 up as success."""
    outcome = collectors.collect("ghsa")
    assert outcome.status == "skipped"
    assert "GITHUB_TOKEN" in (outcome.error or "")
    assert outcome.events == []


def test_unregistered_source_is_rejected():
    outcome = collectors.collect("not-a-real-source")
    assert outcome.status == "skipped"
    assert outcome.events == []


def test_rate_limit_produces_an_honest_failure_not_an_empty_success():
    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "API rate limit exceeded for 1.2.3.4."})

    collectors.set_transport(httpx.MockTransport(limited))
    outcome = collectors.collect("nvd")
    assert outcome.status == "failed"
    assert outcome.error and "403" in outcome.error
    assert outcome.events == []
    assert "速率限制" in outcome.error


def test_transient_server_errors_are_retried_then_reported(monkeypatch):
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"detail": "temporarily unavailable"})
        return _json_response(NVD_SYNTHETIC)

    monkeypatch.setattr(collectors, "BACKOFF_SECONDS", (0.0, 0.0, 0.0))
    collectors.set_transport(httpx.MockTransport(flaky))
    outcome = collectors.collect("nvd")
    assert calls["n"] == 3, "should retry transient 5xx then succeed"
    assert outcome.events


def test_malformed_json_is_reported_rather_than_parsed_loosely():
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>",
                              headers={"content-type": "application/json"})

    collectors.set_transport(httpx.MockTransport(broken))
    outcome = collectors.collect("nvd")
    assert outcome.status == "failed"
    assert "JSON" in (outcome.error or "")


def test_raw_payload_is_snapshotted_before_parsing():
    outcome = collectors.collect("nvd")
    path = storage.snapshot_path("nvd", outcome.snapshot_hash)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8"))["totalResults"] == 1


def test_collector_failure_is_recorded_against_the_source_by_the_runner():
    from app import agents

    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "API rate limit exceeded."})

    collectors.set_transport(httpx.MockTransport(limited))
    result = agents.run_collection(["nvd"])
    assert result["status"] == "failed"
    state = storage.source_state("nvd")
    assert state["status"] == "failed"
    assert state["last_success"] is None
    assert storage.latest_run("collect")["status"] == "failed"
