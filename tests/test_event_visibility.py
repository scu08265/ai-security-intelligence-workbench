"""The answering path must see the whole event corpus, not one page of it."""

from __future__ import annotations

import json

from app import agents, storage

PAGE = 500
TARGET = "CVE-2099-00000"


def _seed(count: int) -> None:
    """Insert ``count`` events where TARGET is the oldest one.

    ``list_events`` orders newest first, so an event older than the newest page
    is exactly the case a page-limited read drops.
    """
    rows = []
    for index in range(count):
        event_id = f"CVE-2099-{index:05d}"
        old = event_id == TARGET
        rows.append((
            event_id,
            "2099-01-01T00:00:00Z" if old else "2099-06-01T00:00:00Z",
            "2099-06-01T00:00:00Z",
            json.dumps({
                "id": event_id, "kind": "vulnerability", "status": "confirmed",
                "title": f"Synthetic advisory {index}",
                "ai_relevance": {"included": True, "reason": "test"},
            }),
        ))
    with storage.connect() as conn:
        conn.executemany(
            "INSERT INTO events (id, status, published_at, collected_at, doc)"
            " VALUES (?, 'confirmed', ?, ?, ?)",
            rows,
        )


def test_an_event_older_than_the_newest_page_is_still_answerable():
    _seed(PAGE + 5)
    newest_page, _ = storage.list_events(limit=PAGE)
    assert TARGET not in {item.get("id") for item in newest_page}, "前提：目标不在最新一页里"

    result = agents.answer(f"{TARGET} 是什么漏洞？", history=[])
    assert TARGET in (result.get("related_event_ids") or []), \
        "回答链路读不到新一页之外的事件，等于对老情报失明"


def test_the_evidence_path_reads_every_event_not_a_page():
    _seed(PAGE + 5)
    everything, total = storage.list_events(limit=None)
    assert len(everything) == total == PAGE + 5
