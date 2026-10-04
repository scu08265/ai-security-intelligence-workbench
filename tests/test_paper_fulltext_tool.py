"""B 任务：`tools/run_paper_fulltext.py` 的离线回归测试。

全部测试都不联网、也不触碰真实数据目录：

- HTTP 由假响应替换（monkeypatch 工具模块内的 ``http_request``）；
- 数据目录由 ``tests/conftest.py::isolated_data_dir`` 隔离到 ``tmp_path``。

本文件只验证 B 任务脚本自身的边界（限额、429 停止、重定向可观测性、跳过逻辑、
主机白名单、解析失败的落库安全），不评价采集主链路。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from app import storage

ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "run_paper_fulltext.py"


def _load_tool():
    """按路径加载工具脚本（``tools/`` 不是包，没有 ``__init__.py``）。"""
    spec = importlib.util.spec_from_file_location("b_paper_fulltext_tool", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(event_id: str, pdf_url: str, status: str = "not_attempted") -> dict:
    return {
        "id": event_id, "kind": "knowledge", "status": "confirmed",
        "title": f"Title for {event_id}", "component": "", "ecosystem": "OpenAlex",
        "affected": [], "conditions": [], "cvss": [], "poc": [], "cwes": [],
        "relationships": [], "aliases": [], "tags": [],
        "sources": [{
            "id": f"openalex:{event_id}", "url": pdf_url, "title": "t",
            "publisher": "OpenAlex", "source_type": "scholarly_index",
            "excerpt": "", "trust": "scholarly_index",
        }],
        "references": [pdf_url],
        "paper": {"openalex_id": event_id, "pdf_url": pdf_url,
                  "full_text": {"status": status,
                                "has_full_text": status == "fulltext"}},
    }


def _fulltext_status(event_id: str) -> str:
    return storage.get_event(event_id)["paper"]["full_text"]["status"]


def _rag_counts() -> tuple[int, int, int]:
    with storage.connect() as conn:
        return (
            conn.execute("SELECT COUNT(*) c FROM rag_documents").fetchone()["c"],
            conn.execute("SELECT COUNT(*) c FROM rag_document_versions").fetchone()["c"],
            conn.execute("SELECT COUNT(*) c FROM rag_chunks").fetchone()["c"],
        )


@pytest.mark.parametrize("bad", ["0", "4", "-1", "13"])
def test_limit_is_hard_capped_at_three(monkeypatch, bad):
    """`--limit` 越界必须直接退出，不能退化成批量下载。"""
    tool = _load_tool()
    monkeypatch.setattr(sys, "argv", ["run_paper_fulltext.py", "--limit", bad])
    with pytest.raises(SystemExit):
        tool.main()


def test_429_stops_the_whole_batch_after_one_request(monkeypatch):
    """429 时只发一次请求，立即终止整批，且不重试、不换 URL。"""
    tool = _load_tool()
    monkeypatch.setattr(tool, "MIN_INTERVAL_SECONDS", 0)
    ids = ["OPENALEX-W900", "OPENALEX-W901", "OPENALEX-W902"]
    for index, event_id in enumerate(ids):
        storage.upsert_event(_event(event_id, f"https://arxiv.org/pdf/9000.0000{index}"))

    calls: list[dict] = []

    def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, "retries": kwargs.get("retries")})
        return httpx.Response(429, request=httpx.Request("GET", url))

    monkeypatch.setattr(tool, "http_request", fake_request)
    monkeypatch.setattr(sys, "argv", ["run_paper_fulltext.py", "--limit", "3"])

    assert tool.main() == 3          # 3 = 遇到 429 提前终止的退出码
    assert len(calls) == 1           # 只发一次
    assert calls[0]["retries"] == 0  # 且禁止重试
    assert calls[0]["method"] == "GET"

    statuses = sorted(_fulltext_status(event_id) for event_id in ids)
    assert statuses == ["failed", "not_attempted", "not_attempted"]
    failed = [e for e in ids if _fulltext_status(e) == "failed"][0]
    assert "429" in storage.get_event(failed)["paper"]["full_text"]["reason"]
    assert _rag_counts() == (0, 0, 0)


def test_redirect_chain_is_recorded_and_parse_failure_leaves_no_document(monkeypatch):
    """重定向链必须来自 httpx 响应本身；解析失败不得留下 RAG 文档。"""
    tool = _load_tool()
    requested = "https://arxiv.org/pdf/9100.00001"
    final_url = "https://arxiv.org/pdf/9100.00001v2"
    storage.upsert_event(_event("OPENALEX-W910", requested))

    def fake_request(method, url, **kwargs):
        assert url == requested
        hop_one = httpx.Response(
            301, request=httpx.Request("GET", requested),
            headers={"location": "https://arxiv.org/pdf/9100.00001v1"})
        hop_two = httpx.Response(
            302, request=httpx.Request("GET", "https://arxiv.org/pdf/9100.00001v1"),
            headers={"location": final_url})
        response = httpx.Response(
            200, content=b"%PDF-1.4 not a parseable document body",
            request=httpx.Request("GET", final_url))
        response.history = [hop_one, hop_two]
        return response

    monkeypatch.setattr(tool, "http_request", fake_request)

    event = storage.get_event("OPENALEX-W910")
    identifier = tool.paper_fulltext._paper_identity(event)
    record, label = tool._process(event, identifier)

    assert record["request_url"] == requested
    assert record["final_url"] == final_url
    assert record["redirect_count"] == 2
    assert [hop["status"] for hop in record["redirects"]] == [301, 302]
    assert record["http_status"] == 200
    assert record["download_status"] == "ok"
    assert record["parse_status"] == "failed"
    assert label == "failed"

    assert _fulltext_status("OPENALEX-W910") == "failed"
    assert "解析或入库失败" in storage.get_event("OPENALEX-W910")["paper"]["full_text"]["reason"]
    assert _rag_counts() == (0, 0, 0)


def test_events_already_ingested_are_skipped():
    """已成功入库的事件不再进入候选。"""
    tool = _load_tool()
    storage.upsert_event(_event("OPENALEX-W920", "https://arxiv.org/pdf/9200.00001",
                                status="fulltext"))
    storage.upsert_event(_event("OPENALEX-W921", "https://arxiv.org/pdf/9200.00002"))

    candidates, already = tool._candidates()
    assert already == 1
    assert [event["id"] for event, _ident in candidates] == ["OPENALEX-W921"]


def test_non_arxiv_hosts_are_never_candidates():
    """非 arXiv 出版商链接必须被主机白名单挡在候选之外。"""
    tool = _load_tool()
    storage.upsert_event(_event(
        "OPENALEX-W930", "https://link.springer.com/content/pdf/10.1186/x.pdf"))
    storage.upsert_event(_event(
        "OPENALEX-W931", "https://www.nature.com/articles/s41586-026-00001-2.pdf"))

    candidates, already = tool._candidates()
    assert candidates == []
    assert already == 0
