"""B 任务：把"引用支持"维度的判定拆成可复算的三个信号，并给出子类归属。

背景：10-02 批次里 27 题判 `partially_supported` 是一个黑洞——"引用句与答案无关"和
"答案需要多句证据、只引了一句"被混在同一个取值里，A1 的第 2 类修复因此没有明确目标。

本工具不替人做判定，只把**可机械复算**的部分算出来，作为判定细则的输入与复核依据：

* ``S1 备而不用``：引用集合里有几条没有被答案正文使用。答案的摘录标签里带 chunk id
  （形如 ``[标题 · chunk-xxxx]``），与 ``citations_detail[].chunk_id`` 精确对应，
  因此"哪条引用真的被答案用了"是可精确复算的。
* ``S2 引用落点``：引用是否来自期望文档（``expected_document_keys``）。
* ``S3 要点覆盖``：答案里出现的期望要点，是否在引用集合的引文中至少出现一次。

子类按细则给出（只对 ``partially_supported`` 的题给子类）：

* ``off_topic`` —— 存在引用既不来自期望文档，也没有被答案使用（引非所答）
* ``insufficient`` —— 存在备而不用的引用（引用选了多条，答案只用了其中几条甚至一条）
* ``off_topic+insufficient`` —— 两者同时成立
* ``not_signalled`` —— 三个信号都没触发，需要人重新读一遍原答案与引文

用法::

    python tools/classify_citation_support.py \
        --results artifacts/b_eval/formal_qa_results_20261012.json \
        --worksheet artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv \
        --out artifacts/b_eval/qa_citation_support_classification_20261012.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "artifacts" / "b_eval" / "formal_qa_results_20261012.json"
WORKSHEET = ROOT / "artifacts" / "b_eval" / "qa_final_confirmation_worksheet_20261002.csv"

# 答案里的证据摘录，形如： - “引文…” [标题 · chunk-1e26fb499bb6dbae04a358d4]
_EXCERPT_TAG = re.compile(r"\[([^\]]*?)(chunk-[0-9a-f]+)\s*\]")
_CITATION_LABEL = "人工判定_引用准确性"


def _load_results(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {record["question_id"]: record for record in payload["records"]}


def _load_labels(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return {row["question_id"]: row for row in csv.DictReader(handle)}


def signals(record: dict) -> dict:
    """The three reproducible signals for one question."""
    answer = record.get("answer_full") or ""
    used_chunks = {match[1] for match in _EXCERPT_TAG.findall(answer)}
    citations = record.get("citations_detail") or []
    cited_docs = {c.get("document_key") for c in citations}
    expected_docs = set(record.get("expected_document_keys") or [])
    expected_terms = [t for t in (record.get("expected_answer_terms") or []) if t and t.strip()]
    quotes = [(c.get("quote") or "") for c in citations]

    used_citations = [c for c in citations if c.get("chunk_id") in used_chunks]
    unused_citations = [c for c in citations if c.get("chunk_id") not in used_chunks]
    off_document = [c for c in citations if expected_docs and c.get("document_key") not in expected_docs]
    # "引非所答"看的是**引用文档**是否落在期望文档里，与"这条引用有没有被答案使用"无关：
    # 答案自己引用了一条无关论文的句子，同样是引非所答。
    # 没有期望文档的题（多跳类）无法判落点，不参与该信号。
    off_topic = [c for c in citations
                 if expected_docs and c.get("document_key") not in expected_docs]
    terms_in_answer = [t for t in expected_terms if t.casefold() in answer.casefold()]
    terms_in_quotes = [t for t in expected_terms
                       if any(t.casefold() in q.casefold() for q in quotes)]
    uncited_terms = [t for t in terms_in_answer if t not in terms_in_quotes]

    return {
        "excerpts_used": len(used_citations),
        "citations_total": len(citations),
        "citations_unused": len(unused_citations),
        "citations_off_expected_document": len(off_document),
        "cited_documents": sorted(d for d in cited_docs if d),
        "expected_documents": sorted(expected_docs),
        "covers_expected_document": (bool(cited_docs & expected_docs) if expected_docs else None),
        "expected_terms_in_answer": terms_in_answer,
        "expected_terms_not_in_citations": uncited_terms,
        "off_topic_candidates": [c.get("chunk_id") for c in off_topic],
    }


def subclass(sig: dict) -> str:
    """细则给出的子类（只用于 partially_supported 的题）。

    ``citations_unused``（备而不用）是**质量信号**，不进子类：既有判定里 `supported` 的题
    也有"答案用 1 条、引用挂 5 条"的情况，只凭它区分不了主标签。
    """
    off_topic = sig["citations_off_expected_document"] >= 1 or sig["covers_expected_document"] is False
    insufficient = (
        (sig["excerpts_used"] <= 1 and sig["citations_total"] >= 3)
        or bool(sig["expected_terms_not_in_citations"])
    )
    if off_topic and insufficient:
        return "off_topic+insufficient"
    if off_topic:
        return "off_topic"
    if insufficient:
        return "insufficient"
    return "not_signalled"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--worksheet", type=Path, default=WORKSHEET)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    records = _load_results(args.results)
    labels = _load_labels(args.worksheet)

    cases = []
    for question_id, label_row in labels.items():
        record = records.get(question_id)
        if record is None:
            continue
        sig = signals(record)
        label = (label_row.get(_CITATION_LABEL) or "").strip()
        cases.append({
            "question_id": question_id,
            "category": record.get("category"),
            "human_label": label,
            "proposed_subclass": (subclass(sig) if label == "partially_supported" else None),
            "signals": sig,
        })

    partial = [c for c in cases if c["human_label"] == "partially_supported"]
    by_subclass = Counter(c["proposed_subclass"] for c in partial)
    payload = {
        "schema_version": "b-citation-support-classification-1.0",
        "rule_ref": "docs/B_CITATION_SUPPORT_RUBRIC.md",
        "results_source": str(args.results.relative_to(ROOT)),
        "worksheet_source": str(args.worksheet.relative_to(ROOT)),
        "note": (
            "子类是机械信号给出的建议归类，用于统一重签尺度与给 A1 的第 2 类修复定位；"
            "supported / partially_supported 的最终边界仍由人工按细则判定。"
        ),
        "partially_supported_total": len(partial),
        "by_subclass": dict(by_subclass),
        "cases": cases,
    }

    print("partially_supported 共", len(partial), "题")
    for key, value in sorted(by_subclass.items()):
        print(f"  {key:26s} {value}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
