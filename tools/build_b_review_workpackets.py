"""B 任务 P1：生成人工核验工作包（问答 + 关系），供 Excel 直接打开。

输出：

* `artifacts/b_eval/qa_review_worksheet.csv`      —— 50 道题的逐题审核表
* `artifacts/b_eval/relation_review_worksheet.csv` —— 121 条关系候选的逐条审核表
* `artifacts/b_eval/review_workpacket_summary.json` —— 两份工作包的规模与覆盖情况

原则：

* CSV 用 UTF-8 **带 BOM**，Excel 直接双击即可正常显示中文。
* 只搬运已有数据，**不生成**任何人工判定；`人工判定` 列留空等待填写。
* 缺少证据的维度（POC / 资产关联）如实标注为"缺少证据"，不编造候选行。

用法::

    python tools/build_b_review_workpackets.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

QA_DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
QA_RESULTS = ROOT / "artifacts" / "b_eval" / "formal_qa_results.json"
RELATION_CANDIDATES = ROOT / "evaluation" / "b_relation_candidates.json"

QA_COLUMNS = [
    "question_id", "category", "difficulty", "question",
    "expected_answer_points", "expected_documents", "should_refuse",
    "system_answer", "system_refused", "cited_documents", "cited_chunk_ids",
    "auto_document_hit", "auto_term_hit", "auto_refusal_ok",
    "review_priority", "review_notes", "人工判定_答案正确性", "人工判定_引用支持性",
    "人工判定_拒答正确性", "人工核验人", "人工核验时间", "人工备注",
]

RELATION_COLUMNS = [
    "relation_id", "dimension", "subject", "relation", "object",
    "candidate_value", "evidence_summary", "verification_method", "uncertainty",
    "annotation_status", "人工判定", "人工核验人", "人工核验时间", "人工备注",
]

# v2：把自动核验结论与人工裁定放在同一张表，便于逐条复核
FINAL_RELATION_COLUMNS = [
    "relation_id", "dimension", "relation", "subject", "object",
    "source_id", "evidence_summary", "auto_judgment", "auto_confidence",
    "auto_reason", "rules_applied", "uncertainty",
    "待人工填写_最终标签", "人工核验人", "人工核验时间", "人工备注",
]

# v3：可直接交付人工填写的标注表（含优先级与证据 ID），使用新文件名，不覆盖旧表
ANNOTATION_COLUMNS = [
    "relation_id", "priority", "dimension", "relation", "subject", "object",
    "source_id", "evidence_ids", "evidence_summary",
    "auto_judgment", "auto_confidence", "auto_reason", "rules_applied",
    "verification_method", "uncertainty",
    "待人工填写_最终标签", "人工核验人", "人工核验时间", "人工备注",
]

# 人工标注优先级：先做证据最集中的维度
DIMENSION_PRIORITY = {
    "fixed_version": "1-最高",
    "cvss": "2-高",
    "version_range": "3-中",
    "paper_link": "4-较低",
    "poc": "5-缺数据",
    "asset_assessment": "5-缺数据",
}

# 人工判定列的允许取值（写在说明文档里，也写进 CSV 的表头注释）
QA_LABEL_OPTIONS = "correct|incorrect|partially_correct|undetermined"
RELATION_LABEL_OPTIONS = "positive|negative|unknown|not_applicable"


def _evidence_summary(evidence: dict) -> str:
    kind = evidence.get("type")
    if kind == "event_field":
        return f"event={evidence.get('event_id')} field={evidence.get('field')} source={evidence.get('source_id')}"
    if kind == "persisted_assessment":
        return (f"assessment event={evidence.get('event_id')} asset={evidence.get('asset_id')} "
                f"evidence_ids={evidence.get('evidence_ids')}")
    return json.dumps(evidence, ensure_ascii=False)[:300]


def _priority(case: dict, record: dict | None) -> tuple[str, str]:
    """给出"先核验哪些"的建议。这是编排建议，不是判定结论。"""
    if case.get("candidate_only"):
        return "low", "候选多跳题，当前系统无推理能力，先不核验答案"
    if case["should_refuse"]:
        return "medium", "拒答类；核对是否确实应拒答"
    if case["expected_document_keys"] and case["expected_answer_terms"]:
        if record and record.get("document_hit") and record.get("term_hit"):
            return "high", "证据清晰且系统已命中，最适合先核验"
        return "high", "证据清晰但系统未完全命中，值得优先核验"
    return "medium", "证据类型为事件而非文档，需按事件字段核验"


def build_qa(out_path: Path) -> dict:
    dataset = json.loads(QA_DATASET.read_text(encoding="utf-8"))
    results = json.loads(QA_RESULTS.read_text(encoding="utf-8"))
    by_id = {r["question_id"]: r for r in results["records"]}

    rows = []
    priority_counts = {"high": 0, "medium": 0, "low": 0}
    for case in dataset["cases"]:
        record = by_id.get(case["question_id"], {})
        priority, note = _priority(case, record)
        priority_counts[priority] += 1
        rows.append({
            "question_id": case["question_id"],
            "category": case["category"],
            "difficulty": case["difficulty"],
            "question": case["question"],
            "expected_answer_points": " ｜ ".join(case["expected_answer_terms"]),
            "expected_documents": ", ".join(case["expected_document_keys"]),
            "should_refuse": case["should_refuse"],
            "system_answer": (record.get("answer_head") or "").replace("\n", " "),
            "system_refused": record.get("refused"),
            "cited_documents": ", ".join(record.get("cited_document_keys") or []),
            "cited_chunk_ids": ", ".join(
                c.get("chunk_id", "") for c in (record.get("citations_detail") or [])),
            "auto_document_hit": record.get("document_hit"),
            "auto_term_hit": record.get("term_hit"),
            "auto_refusal_ok": record.get("refusal_correct"),
            "review_priority": priority,
            "review_notes": note,
            "人工判定_答案正确性": "",
            "人工判定_引用支持性": "",
            "人工判定_拒答正确性": "",
            "人工核验人": "",
            "人工核验时间": "",
            "人工备注": "",
        })
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QA_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "priority": priority_counts,
            "label_options": QA_LABEL_OPTIONS, "path": str(out_path)}


def build_relations(out_path: Path) -> dict:
    payload = json.loads(RELATION_CANDIDATES.read_text(encoding="utf-8"))
    rows = []
    per_dimension: dict[str, int] = {}
    for case in payload["cases"]:
        per_dimension[case["dimension"]] = per_dimension.get(case["dimension"], 0) + 1
        rows.append({
            "relation_id": case["relation_id"],
            "dimension": case["dimension"],
            "subject": case["subject"],
            "relation": case["relation"],
            "object": case["object"],
            "candidate_value": json.dumps(case["candidate_value"], ensure_ascii=False)[:400],
            "evidence_summary": _evidence_summary(case["evidence"]),
            "verification_method": case["verification_method"],
            "uncertainty": case["uncertainty"],
            "annotation_status": case["annotation"]["status"],
            "人工判定": "",
            "人工核验人": "",
            "人工核验时间": "",
            "人工备注": "",
        })
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RELATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    gaps = {gap["dimension"]: gap["reason"] for gap in payload.get("coverage_gaps", [])}
    return {"rows": len(rows), "per_dimension": per_dimension,
            "dimensions_without_evidence": gaps,
            "label_options": RELATION_LABEL_OPTIONS, "path": str(out_path)}


def build_final_review(out_path: Path) -> dict:
    """把自动核验结论并入复核表；人工列仍然留空。"""
    candidates = {c["relation_id"]: c
                  for c in json.loads(RELATION_CANDIDATES.read_text(encoding="utf-8"))["cases"]}
    review_path = ROOT / "artifacts" / "b_eval" / "relation_auto_review.json"
    if not review_path.is_file():
        return {"rows": 0, "path": str(out_path), "error": "缺少 relation_auto_review.json"}
    review = json.loads(review_path.read_text(encoding="utf-8"))

    rows = []
    judgment_counts: dict[str, int] = {}
    for item in review["cases"]:
        case = candidates.get(item["relation_id"], {})
        judgment_counts[item["auto_judgment"]] = judgment_counts.get(item["auto_judgment"], 0) + 1
        rows.append({
            "relation_id": item["relation_id"],
            "dimension": item["dimension"],
            "relation": item["relation"],
            "subject": item["subject"],
            "object": item["object"],
            "source_id": (case.get("evidence") or {}).get("source_id") or "",
            "evidence_summary": _evidence_summary(case.get("evidence") or {}),
            "auto_judgment": item["auto_judgment"],
            "auto_confidence": item["auto_confidence"],
            "auto_reason": item["auto_reason"],
            "rules_applied": " | ".join(
                f"{r['rule']}={r['result']}" for r in item.get("auto_rules") or []),
            "uncertainty": case.get("uncertainty", ""),
            "待人工填写_最终标签": "",
            "人工核验人": "",
            "人工核验时间": "",
            "人工备注": "",
        })
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FINAL_RELATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "auto_judgment_counts": judgment_counts,
            "label_options": RELATION_LABEL_OPTIONS, "path": str(out_path)}


def build_annotation_worksheet(out_path: Path) -> dict:
    """生成可直接填写的人工标注表（新文件名，不覆盖任何既有表）。"""
    candidates = {c["relation_id"]: c
                  for c in json.loads(RELATION_CANDIDATES.read_text(encoding="utf-8"))["cases"]}
    review_path = ROOT / "artifacts" / "b_eval" / "relation_auto_review.json"
    if not review_path.is_file():
        return {"rows": 0, "path": str(out_path), "error": "缺少 relation_auto_review.json"}
    review = json.loads(review_path.read_text(encoding="utf-8"))

    rows = []
    per_priority: dict[str, int] = {}
    for item in review["cases"]:
        case = candidates.get(item["relation_id"], {})
        evidence = case.get("evidence") or {}
        evidence_ids = [v for v in (
            evidence.get("source_id"),
            evidence.get("event_id"),
            evidence.get("asset_id"),
        ) if v]
        auto_evidence = item.get("auto_evidence") or {}
        if auto_evidence.get("snapshot_source"):
            evidence_ids.append(f"snapshot:{auto_evidence['snapshot_source']}")
        if auto_evidence.get("document_key"):
            evidence_ids.append(f"doc:{auto_evidence['document_key']}")
        priority = DIMENSION_PRIORITY.get(item["dimension"], "9-未知")
        per_priority[priority] = per_priority.get(priority, 0) + 1
        rows.append({
            "relation_id": item["relation_id"],
            "priority": priority,
            "dimension": item["dimension"],
            "relation": item["relation"],
            "subject": item["subject"],
            "object": item["object"],
            "source_id": evidence.get("source_id") or "",
            "evidence_ids": "; ".join(dict.fromkeys(evidence_ids)),
            "evidence_summary": _evidence_summary(evidence),
            "auto_judgment": item["auto_judgment"],
            "auto_confidence": item["auto_confidence"],
            "auto_reason": item["auto_reason"],
            "rules_applied": " | ".join(
                f"{r['rule']}={r['result']}" for r in item.get("auto_rules") or []),
            "verification_method": case.get("verification_method", ""),
            "uncertainty": case.get("uncertainty", ""),
            "待人工填写_最终标签": "",
            "人工核验人": "",
            "人工核验时间": "",
            "人工备注": "",
        })
    rows.sort(key=lambda row: (row["priority"], row["relation_id"]))
    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "per_priority": per_priority,
            "label_options": RELATION_LABEL_OPTIONS, "path": str(out_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 B 任务人工核验工作包")
    parser.add_argument("--outdir", type=Path, default=ROOT / "artifacts" / "b_eval")
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    qa = build_qa(args.outdir / "qa_review_worksheet.csv")
    relations = build_relations(args.outdir / "relation_review_worksheet.csv")
    final_review = build_final_review(args.outdir / "relation_final_review_worksheet.csv")
    annotation = build_annotation_worksheet(
        args.outdir / "relation_annotation_worksheet_v2.csv")
    summary = {
        "generated_at_note": "由 tools/build_b_review_workpackets.py 生成；不含任何人工作业结果",
        "qa_worksheet": qa,
        "relation_worksheet": relations,
        "relation_final_review_worksheet": final_review,
        "relation_annotation_worksheet_v2": annotation,
        "instructions": {
            "qa": "在'人工判定_*'列填写；答案正确性取值 " + QA_LABEL_OPTIONS,
            "relation": "在'人工判定'列填写；取值 " + RELATION_LABEL_OPTIONS,
            "relation_final": "在'待人工填写_最终标签'列填写；取值 " + RELATION_LABEL_OPTIONS
                               + "。该表同时给出自动核验结论与理由，便于逐条复核。",
            "then": "运行 python tools/score_b_relation_annotations.py 得到 TP/FP/FN",
        },
    }
    (args.outdir / "review_workpacket_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print("问答审核表:", qa["rows"], "行 ->", qa["path"])
    print("  优先核验分布:", qa["priority"])
    print("关系审核表:", relations["rows"], "行 ->", relations["path"])
    print("  维度分布:", relations["per_dimension"])
    print("  无证据维度:", list(relations["dimensions_without_evidence"]))
    print("关系复核表(v2):", final_review["rows"], "行 ->", final_review["path"])
    print("  自动判定分布:", final_review.get("auto_judgment_counts"))
    print("人工标注表(v2):", annotation["rows"], "行 ->", annotation["path"])
    print("  优先级分布:", annotation.get("per_priority"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
