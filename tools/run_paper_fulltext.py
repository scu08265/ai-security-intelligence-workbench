"""B 任务：对已入库事件关联的 arXiv PDF 做小批量全文入库。

这个工具刻意独立于采集主链路：它不改动任何现有模块，只按操作者显式给出的
篇数，把已入库事件里能解析出 arXiv 标识符的那些逐篇走一遍
``下载 → PDF 头校验 → 快照 → 解析分块 → RAG 入库 → 事件状态回写``。

与 ``paper_fulltext.ingest_arxiv_paper`` 的唯一区别是下载步骤：
本工具显式传 ``retries=0``，保证每篇**只发出一次请求**；既有函数用的是默认
``retries=3``（最多 4 次尝试），不适合受限流保护约束的批量作业。
解析、分块、快照与入库全部复用既有函数，没有第二套实现。

本工具不写入任何"金标准"数据，也不修改 ``full_text.status`` 以外的字段语义。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, paper_fulltext, rag_corpus, storage  # noqa: E402
from app.collectors import FetchError, http_request  # noqa: E402

DEFAULT_LIMIT = 3
# 本阶段的硬上限：一次最多 3 篇，避免误传参数变成批量下载。
MAX_LIMIT = 3
MIN_INTERVAL_SECONDS = 3.0
DOWNLOAD_TIMEOUT_SECONDS = 45.0
# 与 rag_corpus.MAX_INPUT_BYTES 保持一致，避免下载后才在解析阶段才被拒绝。
MAX_PDF_BYTES = 20 * 1024 * 1024
RATE_LIMIT_STATUS = 429


def _candidates() -> tuple[list[tuple[dict, str]], int]:
    """返回 (候选列表, 因已入库而跳过的数量)。

    只接受 ``paper_fulltext._paper_identity`` 能解析出 arXiv 标识符的事件；
    已经完成全文入库的事件不再重复处理。
    """
    events, _total = storage.list_events(limit=500)
    candidates: list[tuple[dict, str]] = []
    already = 0
    for event in events:
        status = ((event.get("paper") or {}).get("full_text") or {}).get("status")
        identifier = paper_fulltext._paper_identity(event)
        if not identifier:
            continue
        if status == "fulltext":
            already += 1
            continue
        candidates.append((event, identifier))
    return candidates, already


def _annotate(event: dict, identifier: str, abstract_url: str, pdf_url: str,
              *, status: str, reason: str | None = None,
              snapshot_hash: str | None = None, ingestion: dict | None = None) -> dict:
    """按既有数据模型回写 ``paper.full_text``（复用 paper_fulltext.annotate_event）。"""
    result: dict = {
        "status": status,
        "has_full_text": status == "fulltext",
        "attempted_at": storage.utcnow(),
        "arxiv_id": identifier,
        "abstract_url": abstract_url,
        "pdf_url": pdf_url,
    }
    if reason:
        result["reason"] = reason
    if snapshot_hash:
        result["snapshot_hash"] = snapshot_hash
    if status == "fulltext":
        result["media_type"] = "application/pdf"
        result["locator"] = "page + extracted-text character range"
        result.update(ingestion or {})
    updated = paper_fulltext.annotate_event(event, result)
    storage.upsert_event(updated)
    return updated


def _process(event: dict, identifier: str) -> tuple[dict, str]:
    """处理一篇。返回 (记录, 结果标签)；结果标签为 ok / failed / stop。"""
    abstract_url, pdf_url = paper_fulltext.canonical_urls(identifier)
    started = time.monotonic()
    record: dict = {
        "event_id": event.get("id"), "arxiv_id": identifier, "pdf_url": pdf_url,
        "request_url": pdf_url, "final_url": None, "redirect_count": None,
        "redirects": [],
        "http_status": None, "download_status": None, "parse_status": None,
        "pdf_bytes": None, "characters": None, "chunks": None,
        "snapshot_path": None, "document_id": None, "version_id": None,
        "version_created": None, "elapsed_ms": None, "reason": None,
    }

    def finish(label: str) -> tuple[dict, str]:
        record["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return record, label

    # 1) 下载：显式 retries=0，单次尝试；429 由调用方决定是否终止整批。
    try:
        response = http_request(
            "GET", pdf_url, timeout=DOWNLOAD_TIMEOUT_SECONDS, retries=0,
            headers={"Accept": "application/pdf"},
        )
    except FetchError as exc:
        record["download_status"] = "failed"
        record["reason"] = f"下载失败：{exc}"
        _annotate(event, identifier, abstract_url, pdf_url,
                  status="failed", reason=record["reason"])
        return finish("failed")

    record["http_status"] = response.status_code
    # 重定向链来自 httpx.Response 本身；不改动公共模块即可获得。
    record["final_url"] = str(response.url)
    record["redirect_count"] = len(response.history)
    record["redirects"] = [
        {"status": hop.status_code, "url": str(hop.url),
         "location": hop.headers.get("location")}
        for hop in response.history
    ]
    if response.status_code == RATE_LIMIT_STATUS:
        record["download_status"] = "failed"
        record["reason"] = "HTTP 429 限流，按约束终止整批（不换 URL、不重试）"
        _annotate(event, identifier, abstract_url, pdf_url,
                  status="failed", reason=record["reason"])
        return finish("stop")
    if response.status_code >= 400:
        record["download_status"] = "failed"
        record["reason"] = f"下载失败：HTTP {response.status_code}"
        _annotate(event, identifier, abstract_url, pdf_url,
                  status="failed", reason=record["reason"])
        return finish("failed")

    raw = response.content
    record["pdf_bytes"] = len(raw)
    if not raw.startswith(b"%PDF-"):
        record["download_status"] = "failed"
        record["reason"] = "下载结果不是 PDF，未入库为全文"
        _annotate(event, identifier, abstract_url, pdf_url,
                  status="failed", reason=record["reason"])
        return finish("failed")
    if len(raw) > MAX_PDF_BYTES:
        record["download_status"] = "failed"
        record["reason"] = f"PDF 超过 {MAX_PDF_BYTES} 字节上限，未入库"
        _annotate(event, identifier, abstract_url, pdf_url,
                  status="failed", reason=record["reason"])
        return finish("failed")
    record["download_status"] = "ok"

    # 2) 快照 + 解析 + 分块 + 入库：全部复用既有函数。
    try:
        snapshot_hash = storage.save_snapshot("arxiv", raw, suffix="pdf")
        record["snapshot_path"] = str(
            storage.snapshot_path("arxiv", snapshot_hash, "pdf")
        )
        ingestion = rag_corpus.ingest_bytes(
            raw, source_id="arxiv", document_key=f"paper:{identifier}",
            title=str(event.get("title") or identifier), canonical_url=abstract_url,
            media_type="application/pdf", snapshot_hash=snapshot_hash,
            metadata={
                "document_type": "academic_paper", "content_scope": "fulltext",
                "publisher": "arXiv", "arxiv_id": identifier, "pdf_url": pdf_url,
                "source_event_id": event.get("id"),
                "ingested_by": "tools/run_paper_fulltext.py",
            },
        )
    except (OSError, ValueError) as exc:
        record["parse_status"] = "failed"
        record["reason"] = f"解析或入库失败：{type(exc).__name__}: {exc}"
        # 快照可能已落盘；与既有实现一致，此时不回报 snapshot_hash。
        _annotate(event, identifier, abstract_url, pdf_url,
                  status="failed", reason=record["reason"])
        return finish("failed")

    record.update({
        "parse_status": "fulltext",
        "characters": ingestion.get("characters"),
        "chunks": ingestion.get("chunks"),
        "document_id": ingestion.get("document_id"),
        "version_id": ingestion.get("version_id"),
        "version_created": ingestion.get("version_created"),
    })
    _annotate(event, identifier, abstract_url, pdf_url, status="fulltext",
              snapshot_hash=snapshot_hash, ingestion=ingestion)
    return finish("ok")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="B 任务小批量 arXiv 全文入库（串行、限流保护、不改主链路）"
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"本次处理篇数，1..{MAX_LIMIT}")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列出候选，不发起任何请求")
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_LIMIT:
        parser.error(f"--limit 必须在 1 到 {MAX_LIMIT} 之间")

    print("数据目录 :", config.DATA_DIR)
    print("数据库   :", config.DB_PATH)
    print("快照目录 :", config.SNAPSHOT_DIR)
    if not config.DB_PATH.is_file():
        print("错误：数据库不存在，停止。")
        return 2

    candidates, already = _candidates()
    print(f"可解析 arXiv 标识符的候选事件 : {len(candidates)}")
    print(f"已入库（status=fulltext）跳过   : {already}")

    selected = candidates[: args.limit]
    print()
    print(f"本次选中 {len(selected)} 篇：")
    for index, (event, identifier) in enumerate(selected, 1):
        _abstract, pdf_url = paper_fulltext.canonical_urls(identifier)
        print(f"  {index}. event={event.get('id')}  arxiv_id={identifier}")
        print(f"     url={pdf_url}")

    if args.dry_run:
        print()
        print("dry-run：未发起任何请求。")
        return 0
    if not selected:
        print()
        print("没有可处理的候选，结束。")
        return 0

    print()
    print(f"请求上限：{len(selected)} 次（每篇 1 次，retries=0）；"
          f"篇间隔 {MIN_INTERVAL_SECONDS:.0f} 秒；超时 {DOWNLOAD_TIMEOUT_SECONDS:.0f} 秒")
    print("=" * 72)

    records: list[dict] = []
    stopped = False
    for index, (event, identifier) in enumerate(selected, 1):
        if index > 1:
            time.sleep(MIN_INTERVAL_SECONDS)
        record, label = _process(event, identifier)
        record["batch_index"] = index
        record["result"] = label
        records.append(record)
        print(f"[{index}/{len(selected)}] {record['event_id']} arxiv={identifier} "
              f"http={record['http_status']} download={record['download_status']} "
              f"parse={record['parse_status']} chunks={record['chunks']} "
              f"{record['elapsed_ms']}ms")
        print(f"        final_url={record['final_url']} "
              f"redirects={record['redirect_count']}")
        if record.get("reason"):
            print(f"        reason: {record['reason']}")
        if label == "stop":
            stopped = True
            print("        遇到 HTTP 429，按约束终止整批。")
            break

    print("=" * 72)
    print(json.dumps({
        "processed": len(records),
        "succeeded": sum(1 for r in records if r["result"] == "ok"),
        "failed": sum(1 for r in records if r["result"] == "failed"),
        "stopped_early": stopped,
        "records": records,
    }, ensure_ascii=False, indent=1))
    return 0 if not stopped else 3


if __name__ == "__main__":
    raise SystemExit(main())
