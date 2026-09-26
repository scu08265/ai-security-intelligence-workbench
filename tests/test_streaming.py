"""Streaming tests.

The load-bearing test here is `test_streamed_text_matches_engine_answer`: the
streaming path re-implements the per-evidence assembly loop so it can emit
sentences as they are produced, and that duplication is only safe while the
two stay byte-identical.  If someone edits one loop and not the other, this
suite fails.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app import agents, api, collectors, config, intelligence, sources, storage, streaming
from tests.fixtures import (
    ARXIV_SYNTHETIC,
    HTML_SYNTHETIC,
    KEV_SYNTHETIC,
    NVD_SYNTHETIC,
    OSV_QUERYBATCH_SYNTHETIC,
    OSV_SYNTHETIC,
    RSS_SYNTHETIC,
)

# Matches a seeded research case (vLLM) that has three demo assets attached to
# it, so the answer path exercises affected / not_affected / not_applicable.
QUESTION = "CVE-2026-22778 会影响我的哪些资产？"


@pytest.fixture
def seeded():
    """One real-shaped event plus demo assets, all from local files."""
    agents.seed_research_cases()
    agents.seed_demo_assets()
    return storage.list_events(limit=500)[0]


def _router(request: httpx.Request) -> httpx.Response:
    host, path = request.url.host, request.url.path
    if host == "services.nvd.nist.gov":
        return httpx.Response(200, json=NVD_SYNTHETIC)
    if host == "api.osv.dev":
        if path.endswith("/querybatch"):
            return httpx.Response(200, json=OSV_QUERYBATCH_SYNTHETIC)
        return httpx.Response(200, json=OSV_SYNTHETIC)
    if host == "www.cisa.gov":
        return httpx.Response(200, json=KEV_SYNTHETIC)
    if host == "export.arxiv.org":
        return httpx.Response(200, text=ARXIV_SYNTHETIC,
                              headers={"content-type": "application/atom+xml"})
    if host == "github.blog":
        return httpx.Response(200, text=RSS_SYNTHETIC,
                              headers={"content-type": "application/rss+xml"})
    if host == "genai.owasp.org":
        return httpx.Response(200, text=HTML_SYNTHETIC,
                              headers={"content-type": "text/html"})
    return httpx.Response(404, json={"detail": "unrouted"})


@pytest.fixture
def stub_network():
    collectors.set_transport(httpx.MockTransport(_router))
    yield


def _frames(gen) -> list[tuple[str, dict]]:
    return list(gen)


def _of(frames, kind: str) -> list[dict]:
    return [payload for name, payload in frames if name == kind]


def _assemble(frames) -> str:
    """Rebuild the answer the way the engine does.

    `answer_question` joins its evidence sentences with a newline, and the
    stream emits exactly one `text` frame per sentence -- so the frame boundary
    *is* the newline.  This is the single definition of that contract; if the
    stream ever splits or merges sentences, these tests fail.
    """
    return "\n".join(p["delta"] for p in _of(frames, "text"))


# --------------------------------------------------------------------------
# answer streaming
# --------------------------------------------------------------------------

def test_streamed_text_matches_engine_answer(seeded):
    """The streamed sentences must equal the engine's recorded answer."""
    events, _ = storage.list_events(limit=500)
    assets = storage.list_assets()
    expected = intelligence.answer_question(QUESTION, events, assets, model_config=None)["answer"]

    frames = _frames(streaming.stream_answer(QUESTION, use_model=False))
    final = _of(frames, "final")[0]

    assert _assemble(frames) == expected
    assert final["answer"] == expected


def test_every_stage_frame_states_input_action_output_effect(seeded):
    """No answer-path frame may leave the four plain-language fields empty."""
    frames = _frames(streaming.stream_answer(QUESTION, use_model=False))
    stages = _of(frames, "stage")
    assert stages
    for stage in stages:
        for field in ("title", "action", "obtained", "output", "effect",
                      "role_label", "phase_label"):
            assert stage[field].strip(), f"frame {stage['seq']} left {field} empty"


def test_every_pipeline_frame_also_states_all_four(stub_network):
    """The same rule must hold on the pipeline path.

    It did not: the live panel and the guide both promise every card answers
    four questions, while a running-collect frame shipped an empty `effect`
    and a skipped-enrich frame shipped an empty `output`.  The UI hides empty
    rows, so the promise was quietly false rather than visibly broken.
    """
    frames = _frames(streaming.stream_pipeline(source_ids=["nvd"], enrich_limit=2))
    stages = _of(frames, "stage")
    assert stages
    for stage in stages:
        for field in ("title", "action", "obtained", "output", "effect"):
            assert stage[field].strip(), (
                f"pipeline frame {stage['seq']} ({stage['title']}) left {field} empty")


@pytest.mark.parametrize("question", [
    "CVE-2026-22778 会影响我的哪些资产？",
    "CVE-2026-22778 的攻击链是什么？",
    "CVE-2026-7482 影响哪些资产？",
    "vLLM 有什么漏洞？",
    "请问今天天气如何",
])
def test_streamed_text_equals_engine_answer_across_questions(seeded, question):
    """Byte-identity must hold on every branch, not just the happy one."""
    events, _ = storage.list_events(limit=500)
    expected = intelligence.answer_question(
        question, events, storage.list_assets(), model_config=None)["answer"]
    frames = _frames(streaming.stream_answer(question, use_model=False))
    assert _assemble(frames) == expected


def test_slash_in_component_does_not_diverge_from_engine(seeded):
    """Regression: a hand-copied `_norm` collapsed "/" and the engine's did not.

    So an event component of "apache/airflow" matched an asset component of
    "apache-airflow" in the stream but not in the engine, and the stream emitted
    an asset sentence the recorded answer never contained.  Slash-containing
    components are the normal case for Go/GitHub-style package names.
    """
    storage.upsert_event({
        "id": "CVE-2099-77777", "component": "apache/airflow",
        "title": "合成夹具：斜杠组件名回归", "summary": "合成夹具，仅用于回归测试。",
        "kind": "vulnerability", "status": "confirmed",
        "affected": [{"package": "apache/airflow", "ecosystem": "PyPI",
                      "range": ">= 1.0.0, < 2.0.0", "fixed_version": "2.0.0",
                      "source_id": "fixture"}],
        "sources": [{
            "id": "fixture:slash", "url": "https://example.invalid/synthetic",
            "title": "合成夹具", "publisher": "fixture", "source_type": "fixture",
            "excerpt": "合成夹具，不是真实数据。", "published_at": None,
            "collected_at": storage.utcnow(), "content_hash": "0" * 64,
            "trust": "fixture",
        }],
        "collected_at": storage.utcnow(),
    })
    storage.upsert_asset({
        "id": "asset-slash-fixture", "name": "合成夹具：斜杠组件资产",
        "component": "apache-airflow", "version": "1.5.0",
        "is_demo": True, "authorized": True,
    })

    question = "CVE-2099-77777 会影响我的哪些资产？"
    events, _ = storage.list_events(limit=500)
    expected = intelligence.answer_question(
        question, events, storage.list_assets(), model_config=None)["answer"]
    frames = _frames(streaming.stream_answer(question, use_model=False))

    assert _assemble(frames) == expected


def test_stage_sequence_is_monotonic(seeded):
    frames = _frames(streaming.stream_answer(QUESTION, use_model=False))
    seqs = [p["seq"] for _, p in frames]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_unmatched_question_refuses_instead_of_guessing(seeded):
    frames = _frames(streaming.stream_answer("请问今天天气如何", use_model=False))
    text = _assemble(frames)
    final = _of(frames, "final")[0]
    assert final["related_event_ids"] == []
    assert "未找到" in text
    warn = [s for s in _of(frames, "stage") if s["status"] == "warn"]
    assert any("没有找到匹配的事件" == s["title"] for s in warn)


def test_model_restatement_refused_without_key(seeded, monkeypatch):
    """Requesting the model without a key must degrade openly, not silently."""
    monkeypatch.delenv(config.API_KEY_ENV, raising=False)
    frames = _frames(streaming.stream_answer(QUESTION, use_model=True))
    failures = [s for s in _of(frames, "stage") if s["status"] == "failed"]
    assert failures and "未配置模型密钥" in failures[0]["obtained"]

    # The local answer is unaffected by the model failing.
    events, _ = storage.list_events(limit=500)
    expected = intelligence.answer_question(
        QUESTION, events, storage.list_assets(), model_config=None)["answer"]
    assert _assemble(frames) == expected
    assert not _of(frames, "final")[0].get("model_restatement")


def test_model_chunks_are_labelled_as_model_output(seeded, monkeypatch):
    """Model text must never be presented as evidence-bound local text."""
    frames = _frames(streaming.stream_answer(QUESTION, use_model=True))
    for payload in _of(frames, "text"):
        assert payload["source"] in {"local", "model"}
        if payload["source"] == "model":
            assert payload["evidence_ids"] == []


def test_answer_run_is_recorded(seeded):
    before = len(storage.list_runs(limit=200))
    _frames(streaming.stream_answer(QUESTION, use_model=False))
    runs = storage.list_runs(limit=200)
    assert len(runs) == before + 1
    assert runs[0]["kind"] == "chat"
    assert runs[0]["detail"]["streamed"] is True


# --------------------------------------------------------------------------
# pipeline streaming
# --------------------------------------------------------------------------

def test_pipeline_narrates_every_source_with_measured_timing(stub_network):
    frames = _frames(streaming.stream_pipeline(enrich_limit=2))
    stages = _of(frames, "stage")

    finished = [s for s in stages if s["title"].startswith("抓取完成：")]
    assert len(finished) == len(sources.SOURCES)
    for stage in finished:
        assert stage["status"] in {"done", "failed", "skipped"}
        assert stage["obtained"].strip()
        assert isinstance(stage["duration_ms"], int)


def test_skipped_source_is_reported_as_skipped_not_success(stub_network, monkeypatch):
    """ghsa needs a token; with none configured it must say so plainly."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    frames = _frames(streaming.stream_pipeline(source_ids=["ghsa"], enrich_limit=0))
    stage = [s for s in _of(frames, "stage") if s["title"].startswith("抓取完成：")][0]
    assert stage["status"] == "skipped"
    assert "GITHUB_TOKEN" in stage["obtained"]
    assert "冒充成功" in stage["obtained"] or "未尝试" in stage["obtained"]


def test_pipeline_rejects_unknown_source_before_starting():
    client = TestClient(api.app)
    response = client.post("/api/stream/pipeline", json={"source_ids": ["http://evil.test"]})
    assert response.status_code == 400
    assert "未登记的数据源" in response.json()["detail"]


def test_pipeline_reports_tool_calls_with_their_real_returns(stub_network):
    frames = _frames(streaming.stream_pipeline(source_ids=["nvd"], enrich_limit=3))
    calls = [s for s in _of(frames, "stage") if s["action"].startswith("第 ")]
    for call in calls:
        assert call["obtained"], "a tool call must report what it got back"
        assert call["tool" if "tool" in call else "title"]
    finals = _of(frames, "final")
    assert finals and finals[0]["tool_calls"] == len(calls)


def test_pipeline_final_frame_counters_agree_with_frames(stub_network):
    frames = _frames(streaming.stream_pipeline(source_ids=["nvd"], enrich_limit=2))
    final = _of(frames, "final")[0]
    assessed = [s for s in _of(frames, "stage") if s["title"].startswith("判断：")]
    assert final["assessments"] == len(assessed)


def test_interrupted_pipeline_still_leaves_a_run_record(stub_network):
    """A stopped run advances the cursors of whatever it finished.

    If it left no record, the store would show sources that moved with nothing
    explaining why -- and the UI tells the user the run log will show it.
    """
    before = len(storage.list_runs(limit=200))
    gen = streaming.stream_pipeline(source_ids=["nvd"], enrich_limit=0)
    next(gen)   # start frame
    next(gen)   # first source placeholder
    gen.close()  # client walks away mid-run

    runs = storage.list_runs(limit=200)
    assert len(runs) == before + 1
    assert runs[0]["status"] == "aborted"
    assert "已中断" in runs[0]["summary"]
    assert runs[0]["detail"]["aborted"] is True


def test_disconnect_at_final_yield_does_not_overwrite_completed_record(stub_network):
    """The narrow race the reviewer found.

    `save_run` upserts by id.  If completion were flagged *after* the final
    yield, a client that vanished while the generator sat suspended there would
    let the abort path write an "aborted" record over a good "completed" one.
    Stopping exactly at that yield is what this reproduces.
    """
    gen = streaming.stream_pipeline(source_ids=["nvd"], enrich_limit=0)
    for name, _payload in gen:
        if name == "final":
            break  # suspended at the final yield, not resumed past it

    gen.close()  # GeneratorExit lands on that yield; the finally block runs

    latest = storage.list_runs(limit=200)[0]
    assert latest["status"] == "completed", "abort path overwrote the completed record"
    assert not (latest["detail"] or {}).get("aborted")


def test_completed_pipeline_is_not_marked_aborted(stub_network):
    list(streaming.stream_pipeline(source_ids=["nvd"], enrich_limit=0))
    latest = storage.list_runs(limit=200)[0]
    assert latest["status"] == "completed"
    assert "已中断" not in latest["summary"]
    assert not latest["detail"].get("aborted")


# --------------------------------------------------------------------------
# transport and API surface
# --------------------------------------------------------------------------

def test_sse_encoding_is_well_formed():
    raw = streaming.encode_sse(("stage", {"seq": 1, "note": "含中文"}))
    assert raw.startswith("event: stage\ndata: ")
    assert raw.endswith("\n\n")
    assert "含中文" in raw
    assert "\\u" not in raw, "Chinese must not be escaped into ASCII"


def test_stream_answer_endpoint_serves_event_stream(seeded):
    client = TestClient(api.app)
    with client.stream("POST", "/api/stream/answer",
                       json={"question": QUESTION, "use_model": False}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    assert "event: stage" in body
    assert "event: final" in body


def test_stream_answer_endpoint_refuses_model_without_key(seeded, monkeypatch):
    monkeypatch.delenv(config.API_KEY_ENV, raising=False)
    client = TestClient(api.app)
    response = client.post("/api/stream/answer", json={"question": QUESTION, "use_model": True})
    assert response.status_code == 400
    assert "模型密钥" in response.json()["detail"]


def test_streams_do_not_leak_credentials(seeded, monkeypatch):
    """No frame may contain the key, whatever it is set to."""
    monkeypatch.setenv(config.API_KEY_ENV, "sk-canary-do-not-emit")
    frames = _frames(streaming.stream_answer(QUESTION, use_model=True))
    blob = "".join(streaming.encode_sse(f) for f in frames)
    assert "sk-canary-do-not-emit" not in blob
