"""B 任务：把关系与问答的自动核验结果合并成一份汇总。

汇总只做**加法与比率**，不改动任何输入文件，也不产生人工标签。

用法::

    python tools/summarise_auto_review.py --out artifacts/b_eval/auto_review_summary.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "b_eval"
RELATION_REVIEW = ARTIFACTS / "relation_auto_review.json"
QA_REVIEW = ARTIFACTS / "qa_auto_review.json"
QA_RESULTS = ARTIFACTS / "formal_qa_results.json"
RELATION_SCORE = ARTIFACTS / "relation_score.json"


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def build() -> dict:
    relations = json.loads(RELATION_REVIEW.read_text(encoding="utf-8"))
    qa = json.loads(QA_REVIEW.read_text(encoding="utf-8"))
    qa_results = json.loads(QA_RESULTS.read_text(encoding="utf-8"))
    human_relation = json.loads(RELATION_SCORE.read_text(encoding="utf-8")) \
        if RELATION_SCORE.is_file() else {"computable": False}

    rel_counts = relations["counts"]["by_judgment"]
    rel_total = relations["counts"]["total"]
    qa_counts = qa["counts"]["by_judgment"]
    qa_total = qa["counts"]["total"]

    return {
        "schema_version": "b-auto-review-summary-1.0",
        "generated_from": {
            "relation_auto_review": str(RELATION_REVIEW.relative_to(ROOT)),
            "qa_auto_review": str(QA_REVIEW.relative_to(ROOT)),
            "formal_qa_results": str(QA_RESULTS.relative_to(ROOT)),
        },
        "headline": {
            "relation_candidates_reviewed": rel_total,
            "relation_supported": rel_counts.get("supported", 0),
            "relation_contradicted": rel_counts.get("contradicted", 0),
            "relation_insufficient_evidence": rel_counts.get("insufficient_evidence", 0),
            "qa_questions_reviewed": qa_total,
            "qa_supported": qa_counts.get("supported", 0),
            "qa_contradicted": qa_counts.get("contradicted", 0),
            "qa_insufficient_evidence": qa_counts.get("insufficient_evidence", 0),
            "qa_not_applicable": qa_counts.get("not_applicable", 0),
        },
        "relation_metrics": {
            "auto_support_rate": {
                "numerator": rel_counts.get("supported", 0),
                "denominator": rel_total,
                "rate": _rate(rel_counts.get("supported", 0), rel_total),
                "scope": "自动核验判定；不是人工 precision/recall",
            },
            "explicit_contradictions": rel_counts.get("contradicted", 0),
            "insufficient_evidence": rel_counts.get("insufficient_evidence", 0),
            "by_dimension": relations["counts"]["by_dimension"],
            "coverage": relations["coverage"],
            "human_precision_recall": {
                "computable": human_relation.get("computable", False),
                "note": "需要人工填写 relation_review_worksheet.csv 的'人工判定'列",
            },
        },
        "qa_metrics": qa["metrics"],
        "qa_latency_ms": qa_results.get("latency_ms"),
        "qa_latency_source": "artifacts/b_eval/formal_qa_results.json（同一批 50 题的实测值）",
        "not_computable": {
            "semantic_answer_accuracy": "无人工核验标准答案",
            "relation_precision_recall_tp_fp_fn": "无人工标注标签",
            "multihop_reasoning_accuracy": "系统无关系抽取与路径搜索能力",
            "cross_document_synthesis": "答案由原文摘录拼接，无综合步骤",
        },
        "cautions": [
            "自动核验不等于人工核验；本汇总所有比率都是自动判定，不得命名为人工准确率。",
            "关系自动核验中'supported'只表示原始快照里能找到支撑字符串或内部逻辑自洽，"
            "不代表该关系在语义上一定成立。",
            "问答自动核验中'答案支持率'指答案由引用原文逐字构成，不代表答案语义正确。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总自动核验结果")
    parser.add_argument("--out", type=Path,
                        default=ARTIFACTS / "auto_review_summary.json")
    args = parser.parse_args()
    for path in (RELATION_REVIEW, QA_REVIEW):
        if not path.is_file():
            print("缺少输入:", path)
            return 2
    payload = build()
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(payload["headline"], ensure_ascii=False, indent=1))
    print("关系自动支持率:", payload["relation_metrics"]["auto_support_rate"])
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
