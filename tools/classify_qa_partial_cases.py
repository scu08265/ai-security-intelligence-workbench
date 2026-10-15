"""Split the human "partial" verdicts into three actionable buckets.

The A1 brief asks for the 26 answer-partial and 27 citation-partially-supported
questions to be sorted into three groups so each can be fixed at its own layer:

1. ``answer_missing_terms`` -- the answer really is missing expected terms.
2. ``citation_does_not_support`` -- the answer carries the terms but the quoted
   evidence sentences do not, so the fix belongs in sentence selection.
3. ``rubric_review`` -- machine facts say both are present, so the partial
   verdict is a standard question for B, not a code defect.

Both inputs already exist: the human labels live in the confirmation worksheet
and the machine facts (expected terms, citation quotes) in the batch results.
This tool only joins them -- it never re-scores anything.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

WORKSHEET = ROOT / "artifacts" / "b_eval" / "qa_final_confirmation_worksheet_20261002.csv"
RESULTS = ROOT / "artifacts" / "b_eval" / "formal_qa_results_20261002.json"

ANSWER_COLUMN = "人工判定_答案正确性"
CITATION_COLUMN = "人工判定_引用准确性"


def _norm(text: Any) -> str:
    return " ".join(str(text or "").casefold().split())


def _contains(haystack: str, needle: str) -> bool:
    return _norm(needle) in haystack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worksheet", type=Path, default=WORKSHEET)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "reports" / "qa-partial-classification.json")
    args = parser.parse_args()

    with args.worksheet.open(encoding="utf-8-sig") as stream:
        label_rows = {row["question_id"]: row for row in csv.DictReader(stream)}
    payload = json.loads(args.results.read_text(encoding="utf-8-sig"))
    records = {row["question_id"]: row for row in payload["records"]}

    rows: list[dict[str, Any]] = []
    for question_id, record in records.items():
        label = label_rows.get(question_id) or {}
        answer_verdict = (label.get(ANSWER_COLUMN) or "").strip()
        citation_verdict = (label.get(CITATION_COLUMN) or "").strip()
        if answer_verdict != "partial" and citation_verdict != "partially_supported":
            continue

        answer_text = _norm(record.get("answer_full") or record.get("answer_head"))
        quotes = " \n ".join(
            _norm(item.get("quote")) for item in record.get("citations_detail") or []
        )
        expected_terms = [term for term in record.get("expected_answer_terms") or [] if term]
        missing_in_answer = [term for term in expected_terms if not _contains(answer_text, term)]
        missing_in_quotes = [term for term in expected_terms if not _contains(quotes, term)]
        expected_docs = [key for key in record.get("expected_document_keys") or [] if key]
        cited_docs = set(record.get("cited_document_keys") or [])
        missing_docs = [key for key in expected_docs if key not in cited_docs]

        if missing_in_answer:
            bucket = "answer_missing_terms"
        elif missing_in_quotes:
            bucket = "citation_does_not_support"
        else:
            bucket = "rubric_review"

        rows.append({
            "question_id": question_id,
            "category": record.get("category"),
            "question": record.get("question"),
            "human_answer": answer_verdict or None,
            "human_citation": citation_verdict or None,
            "bucket": bucket,
            "expected_terms": expected_terms,
            "missing_in_answer": missing_in_answer,
            "missing_in_quotes": missing_in_quotes,
            "missing_expected_documents": missing_docs,
            "cited_documents": sorted(cited_docs),
            "citation_count": len(record.get("citations_detail") or []),
            "refused": bool(record.get("refused")),
            "answer_head": (record.get("answer_head") or "")[:220],
        })

    order = {"citation_does_not_support": 0, "answer_missing_terms": 1, "rubric_review": 2}
    rows.sort(key=lambda item: (order[item["bucket"]], item["question_id"]))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["bucket"]] = counts.get(row["bucket"], 0) + 1

    summary = {
        "generated_at": payload.get("dataset", {}).get("generated_at"),
        "source_worksheet": str(args.worksheet),
        "source_results": str(args.results),
        "scoped_questions": len(rows),
        "answer_partial_total": sum(1 for row in rows if row["human_answer"] == "partial"),
        "citation_partial_total": sum(
            1 for row in rows if row["human_citation"] == "partially_supported"),
        "buckets": counts,
        "policy": ("分类只使用已有事实：期望术语是否出现在答案里、是否出现在引用原文里。"
                   "③ 类是给 B 的判定标准复核项，本工具不做任何重新评分。"),
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"written {args.output}")
    print(f"scoped {len(rows)} questions "
          f"(answer-partial {summary['answer_partial_total']}, "
          f"citation-partial {summary['citation_partial_total']})")
    print("buckets:", counts)
    print()
    print("| 题号 | 类别 | 分桶 | 期望术语缺失(答案) | 期望术语缺失(引用) | 引用数 |")
    print("| --- | --- | --- | --- | --- | ---: |")
    for row in rows:
        print(f"| {row['question_id']} | {row['category']} | {row['bucket']} "
              f"| {', '.join(row['missing_in_answer']) or '—'} "
              f"| {', '.join(row['missing_in_quotes']) or '—'} | {row['citation_count']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
