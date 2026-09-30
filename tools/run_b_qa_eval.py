"""B 任务：在数据库副本上运行固定问答评测集（默认 50 题）。

设计要点：

* **真实库只读**。脚本先把 `INTEL_DATA_DIR` 指向一份临时副本，再调用既有问答链路
  （`app.agents.answer`），因此不会写入 `D:\\ICT\\intel-data-b`。
* **只做机械性判定**。答案关键词命中是"预期词是否逐字出现在答案里"，
  不是语义正确性；引用判定只检查"引用的 chunk_id 能否在库中取回"。
* **语义答案准确率不计算**。评测集里的标准答案要点由任务执行者编写，
  全部标记为 `pending_human_review`；在人工核验完成前不能作为准确率金标准。

用法::

    python tools/run_b_qa_eval.py --out artifacts/b_eval/formal_qa_results.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import agents, config, rag_corpus, storage  # noqa: E402

DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
SOURCE_DATA_DIR = Path(r"D:\ICT\intel-data-b")
TIMEOUT_MS = 5000  # 赛题"完整响应 ≤5s"的合格线，仅用于统计超时数


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 1)


def _prepare_workdir(workdir: Path) -> None:
    if workdir.exists():
        shutil.rmtree(workdir)
    (workdir / "snapshots").mkdir(parents=True)
    shutil.copy2(SOURCE_DATA_DIR / "intel.sqlite", workdir / "intel.sqlite")


def _document_keys() -> dict[str, str]:
    with storage.connect() as conn:
        return {
            row["id"]: row["document_key"]
            for row in conn.execute("SELECT id, document_key FROM rag_documents").fetchall()
        }


def run(limit: int | None = None) -> dict:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = payload["cases"]
    if limit:
        cases = cases[:limit]

    keys = _document_keys()
    records: list[dict] = []
    for case in cases:
        started = time.perf_counter()
        error: str | None = None
        try:
            result = agents.answer(case["question"], history=case.get("history") or [])
        except Exception as exc:  # noqa: BLE001 - 失败要如实记录
            result, error = {}, f"{type(exc).__name__}: {exc}"
        elapsed = round((time.perf_counter() - started) * 1000, 1)

        citations = result.get("document_citations") or []
        cited_keys = {keys.get(c.get("document_id"), "") for c in citations}
        answer = (result.get("answer") or "")
        answer_folded = answer.casefold()
        expected_keys = set(case["expected_document_keys"])
        expected_terms = list(case["expected_answer_terms"])

        refused = not (result.get("related_event_ids") or citations)
        retrievable = sum(1 for c in citations
                          if rag_corpus.get_chunk(c.get("chunk_id") or "") is not None)

        records.append({
            "question_id": case["question_id"],
            "category": case["category"],
            "difficulty": case["difficulty"],
            "question": case["question"],
            "should_refuse": case["should_refuse"],
            "candidate_only": bool(case.get("candidate_only")),
            "error": error,
            "refused": refused,
            "refusal_correct": (refused == case["should_refuse"]) if not error else None,
            "related_event_ids": result.get("related_event_ids") or [],
            "document_citation_count": len(citations),
            "cited_document_keys": sorted(k for k in cited_keys if k),
            "expected_document_keys": sorted(expected_keys),
            "citations_detail": [{
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("document_id"),
                "document_key": keys.get(c.get("document_id"), ""),
                "char_start": c.get("char_start"),
                "char_end": c.get("char_end"),
                "quote": c.get("quote") or "",
            } for c in citations],
            "document_hit": (expected_keys <= cited_keys) if expected_keys else None,
            "expected_answer_terms": expected_terms,
            "term_hit": (all(t.casefold() in answer_folded for t in expected_terms)
                         if expected_terms else None),
            "citations_retrievable": retrievable,
            "answer_head": answer[:200],
            "answer_full": answer,
            "latency_ms": elapsed,
            "timeout": elapsed > TIMEOUT_MS,
        })
    return _summarise(records, payload)


def _summarise(records: list[dict], payload: dict) -> dict:
    latencies = [r["latency_ms"] for r in records]
    by_category: dict[str, dict] = defaultdict(lambda: {
        "cases": 0, "answered": 0, "refused": 0, "errors": 0,
        "document_hit_n": 0, "document_hit_ok": 0,
        "term_hit_n": 0, "term_hit_ok": 0,
        "refusal_n": 0, "refusal_ok": 0,
    })
    for r in records:
        bucket = by_category[r["category"]]
        bucket["cases"] += 1
        bucket["answered"] += 0 if r["refused"] or r["error"] else 1
        bucket["refused"] += 1 if r["refused"] else 0
        bucket["errors"] += 1 if r["error"] else 0
        if r["document_hit"] is not None:
            bucket["document_hit_n"] += 1
            bucket["document_hit_ok"] += 1 if r["document_hit"] else 0
        if r["term_hit"] is not None:
            bucket["term_hit_n"] += 1
            bucket["term_hit_ok"] += 1 if r["term_hit"] else 0
        if r["refusal_correct"] is not None:
            bucket["refusal_n"] += 1
            bucket["refusal_ok"] += 1 if r["refusal_correct"] else 0

    for bucket in by_category.values():
        for prefix, n_key, ok_key in (
            ("document_hit_rate", "document_hit_n", "document_hit_ok"),
            ("term_hit_rate", "term_hit_n", "term_hit_ok"),
            ("refusal_accuracy", "refusal_n", "refusal_ok"),
        ):
            n = bucket[n_key]
            bucket[prefix] = round(bucket[ok_key] / n, 4) if n else None

    total_citations = sum(r["document_citation_count"] for r in records)
    total_retrievable = sum(r["citations_retrievable"] for r in records)
    doc_n = sum(1 for r in records if r["document_hit"] is not None)
    doc_ok = sum(1 for r in records if r["document_hit"])
    term_n = sum(1 for r in records if r["term_hit"] is not None)
    term_ok = sum(1 for r in records if r["term_hit"])
    refusal_n = sum(1 for r in records if r["refusal_correct"] is not None)
    refusal_ok = sum(1 for r in records if r["refusal_correct"])

    # 应答/拒答的分类指标：分别统计"应该拒答"与"应该回答"两组，避免把两类错误混成一个数字
    should_refuse = [r for r in records if r["should_refuse"]]
    should_answer = [r for r in records if not r["should_refuse"]]
    confusion = {
        "should_refuse_true": {
            "n": len(should_refuse),
            "refused_ok": sum(1 for r in should_refuse if r["refused"]),
            "answered_wrongly": sum(1 for r in should_refuse if not r["refused"]),
        },
        "should_refuse_false": {
            "n": len(should_answer),
            "answered_ok": sum(1 for r in should_answer if not r["refused"]),
            "refused_wrongly": sum(1 for r in should_answer if r["refused"]),
        },
    }
    confusion["should_refuse_true"]["refusal_recall"] = (
        round(confusion["should_refuse_true"]["refused_ok"] / len(should_refuse), 4)
        if should_refuse else None
    )
    confusion["should_refuse_false"]["answer_rate"] = (
        round(confusion["should_refuse_false"]["answered_ok"] / len(should_answer), 4)
        if should_answer else None
    )

    return {
        "dataset": {
            "path": str(DATASET.relative_to(ROOT)),
            "schema_version": payload["schema_version"],
            "cases_run": len(records),
            "categories": sorted({r["category"] for r in records}),
        },
        "metric_definitions": {
            "refused": "没有任何结构化事件证据、也没有任何文档引用时为拒答",
            "document_hit_rate": "预期 document_key 全部被引用命中的比例；分母=带预期文档的题目数",
            "term_hit_rate": "预期答案要点逐字出现在答案中的比例；分母=带预期词的题目数。"
                             "这是机械性字符串判定，**不是**语义答案准确率",
            "refusal_accuracy": "拒答判定与 should_refuse 一致的比例；分母=全部题目数",
            "answer_semantic_accuracy": "未计算——标准答案要点由任务执行者编写，全部 pending_human_review",
            "latency": "单题端到端耗时（含本地检索）；超时阈值 %d ms" % TIMEOUT_MS,
        },
        "totals": {
            "cases": len(records),
            "answered": sum(1 for r in records if not r["refused"] and not r["error"]),
            "refused": sum(1 for r in records if r["refused"]),
            "errors": sum(1 for r in records if r["error"]),
            "timeouts": sum(1 for r in records if r["timeout"]),
            "failures": sum(1 for r in records if r["error"] or r["timeout"]),
            "document_hit": {"ok": doc_ok, "n": doc_n,
                             "rate": round(doc_ok / doc_n, 4) if doc_n else None,
                             "scope": "只表示预期 document_key 是否被引用命中；"
                                      "不代表引用内容支持答案"},
            "term_hit": {"ok": term_ok, "n": term_n,
                         "rate": round(term_ok / term_n, 4) if term_n else None,
                         "scope": "预期要点是否逐字出现在答案里；**不是**语义答案准确率"},
            "refusal_accuracy": {"ok": refusal_ok, "n": refusal_n,
                                 "rate": round(refusal_ok / refusal_n, 4) if refusal_n else None},
            "citations": {"total": total_citations, "retrievable": total_retrievable,
                          "rate": round(total_retrievable / total_citations, 4)
                                  if total_citations else None},
            "answer_semantic_accuracy": {"value": None,
                                         "reason": "无人工核验标准答案，按规则不计入正式准确率"},
        },
        "answer_refusal_confusion": confusion,
        "target_comparison": {
            "note": "仅作客观对照，不构成达标声明；且引用/词命中并非赛题口径的语义准确率。",
            "document_hit_rate": round(doc_ok / doc_n, 4) if doc_n else None,
            "refusal_rate": round(refusal_ok / refusal_n, 4) if refusal_n else None,
            "gaps_vs_75_90_95": {
                "document_hit": [round((t / 100) - (doc_ok / doc_n), 4) if doc_n else None
                                 for t in (75, 90, 95)],
                "refusal": [round((t / 100) - (refusal_ok / refusal_n), 4) if refusal_n else None
                            for t in (75, 90, 95)],
            },
        },
        "latency_ms": {
            "samples": len(latencies),
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
        },
        "by_category": dict(sorted(by_category.items())),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="B 任务固定问答评测（真实库只读）")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "formal_qa_results.json")
    parser.add_argument("--workdir", type=Path, default=None)
    args = parser.parse_args()

    if not (SOURCE_DATA_DIR / "intel.sqlite").is_file():
        print("找不到源数据库：", SOURCE_DATA_DIR / "intel.sqlite")
        return 2

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="b_qa_eval_"))
    _prepare_workdir(workdir)
    config.DATA_DIR = workdir
    config.SNAPSHOT_DIR = workdir / "snapshots"
    config.DB_PATH = workdir / "intel.sqlite"
    print("副本工作目录:", workdir)
    print("源数据库（只读）:", SOURCE_DATA_DIR / "intel.sqlite")

    summary = run(args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("题目数:", summary["totals"]["cases"],
          "| 作答:", summary["totals"]["answered"],
          "| 拒答:", summary["totals"]["refused"],
          "| 异常:", summary["totals"]["errors"],
          "| 超时:", summary["totals"]["timeouts"])
    print("引用命中率:", summary["totals"]["document_hit"],
          "| 预期词命中率:", summary["totals"]["term_hit"])
    print("拒答一致率:", summary["totals"]["refusal_accuracy"])
    print("引用可追溯:", summary["totals"]["citations"])
    print("响应耗时:", summary["latency_ms"])
    print("应答/拒答分类:", json.dumps(summary["answer_refusal_confusion"], ensure_ascii=False))
    print("对照目标档位(仅客观对照，不构成达标声明):",
          json.dumps(summary["target_comparison"]["gaps_vs_75_90_95"], ensure_ascii=False))
    print("语义答案准确率: 未计算（无人工核验标准答案）")
    print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
