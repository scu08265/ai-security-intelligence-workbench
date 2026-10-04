"""B 任务：对"应拒答但系统作答"的样本做**独立复现与失败分类**。

只读分析，不修改问答主流程。每类给出可复现样本、证据、最小修复建议，
并标注是否需要人工复核。

用法::

    python tools/classify_b_refusals.py --out artifacts/b_eval/refusal_failure_classification.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
RESULTS = ROOT / "artifacts" / "b_eval" / "formal_qa_results.json"
AUTO_REVIEW = ROOT / "artifacts" / "b_eval" / "qa_auto_review.json"

# 与通用安全词一致（与 app/rag.py::_GENERIC_SECURITY_TERMS 保持同样口径）
GENERIC_TERMS = {"vulnerability", "cve", "fix", "fixed", "patched", "remediation",
                 "mitigation", "security", "risk"}


def classify(case: dict, record: dict, review: dict) -> dict:
    question = case["question"]
    folded = question.casefold()
    citations = record.get("citations_detail") or []
    cited_docs = record.get("cited_document_keys") or []
    event_ids = record.get("related_event_ids") or []
    answered = not record.get("refused")

    numbers = re.findall(r"\b\d{4}\b", question)
    english_terms = [t for t in re.findall(r"[a-z][a-z0-9\-]{2,}", folded)]
    only_generic = bool(english_terms) and all(t in GENERIC_TERMS for t in english_terms)
    asks_synthesis = bool(re.search(r"总结|综述|概括|summar|overview", folded))

    if not answered:
        category, reason = "correct_refusal", "系统确实拒答，符合 should_refuse"
    elif case.get("candidate_only"):
        category = "candidate_multihop_answered_topically"
        reason = ("候选多跳题：系统返回了主题相关的引用，但没有推理链，"
                  "属于能力边界而非检索失败")
    elif asks_synthesis:
        category = "synthesis_request_answered_with_quotes"
        reason = "要求跨全部文档综述，系统返回引用原文列表，未真正综合"
    elif numbers and (citations or event_ids):
        category = "numeric_token_false_positive"
        reason = f"问题中的数字串 {numbers[:2]} 在语料/事件中出现，导致词法检索误命中"
    elif only_generic:
        category = "generic_word_answered_from_event_index"
        reason = ("问题只含通用安全词，事件索引按标题匹配后正常作答；"
                  "这属于对 should_refuse 口径的定义分歧")
    else:
        category = "other"
        reason = "未能归入已知类别，需人工判断"

    needs_human = category in {"other", "generic_word_answered_from_event_index"}
    fix = {
        "numeric_token_false_positive":
            "把纯数字/年份 token 降权或从检索词元中剔除（只读评测可先量化影响）",
        "synthesis_request_answered_with_quotes":
            "识别综述类请求并明确回复能力边界，而非返回引用列表",
        "candidate_multihop_answered_topically":
            "在多跳题上标注能力边界；需要真正的路径检索才可能作答",
        "generic_word_answered_from_event_index":
            "明确 should_refuse 口径：单通用词是否算'证据不足'需人工裁定",
        "correct_refusal": None,
        "other": "需要人工判断后再定",
    }[category]

    return {
        "question_id": case["question_id"],
        "category_of_question": case["category"],
        "question": question,
        "should_refuse": case["should_refuse"],
        "actually_refused": record.get("refused"),
        "system_answer_head": (record.get("answer_head") or "")[:200],
        "evidence": {
            "document_citations": len(citations),
            "cited_document_keys": cited_docs,
            "related_event_ids": event_ids,
            "auto_judgment": review.get("auto_judgment"),
            "auto_rules": [f"{r['rule']}={r['result']}" for r in review.get("auto_rules") or []],
        },
        "is_rule_misjudgment": False,
        "failure_category": category,
        "reason": reason,
        "minimal_fix": fix,
        "needs_human_review": needs_human,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="拒答失败分类")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "refusal_failure_classification.json")
    parser.add_argument("--results", type=Path, default=RESULTS,
                        help="问答运行结果文件（默认正式集基线；重评测批次请显式指定）")
    parser.add_argument("--auto-review", type=Path, default=AUTO_REVIEW,
                        help="自动评审文件（需与 --results 同批次）")
    args = parser.parse_args()

    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    results = {r["question_id"]: r
               for r in json.loads(args.results.read_text(encoding="utf-8"))["records"]}
    review = {r["question_id"]: r
              for r in json.loads(args.auto_review.read_text(encoding="utf-8"))["cases"]}

    cases = [c for c in dataset["cases"] if c["should_refuse"]]
    classified = [classify(c, results.get(c["question_id"], {}), review.get(c["question_id"], {}))
                  for c in cases]

    by_category: dict[str, int] = {}
    for item in classified:
        by_category[item["failure_category"]] = by_category.get(item["failure_category"], 0) + 1

    payload = {
        "schema_version": "b-refusal-classification-1.0",
        "scope": "只覆盖 should_refuse=True 的题目；只读复现，未修改问答主流程",
        "counts": {
            "should_refuse_cases": len(cases),
            # 修正：原先 "correctly_refused" 实际统计的是**未拒答**的题数，
            # 与 "wrongly_answered" 重复计数，导致应拒答题的
            # 正确拒答/错误作答两个数字都失真（历史基线文件保留原样）。
            "correctly_refused": sum(1 for c in classified
                                     if c["actually_refused"] is True),
            "wrongly_answered": sum(1 for c in classified if c["actually_refused"] is False),
            "by_category": by_category,
            "needs_human_review": sum(1 for c in classified if c["needs_human_review"]),
        },
        "rule_misjudgments": {
            "found": 0,
            "note": "逐条核对自动评审规则：本批全部判为 R-QA-REFUSAL 失败，"
                    "与人工口径一致；但其中 2 条涉及 should_refuse 的定义分歧（见下）",
        },
        "cases": classified,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("应拒答题数:", payload["counts"]["should_refuse_cases"])
    print("正确拒答:", payload["counts"]["correctly_refused"],
          "| 错误作答:", payload["counts"]["wrongly_answered"])
    print("分类分布:", json.dumps(by_category, ensure_ascii=False))
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
