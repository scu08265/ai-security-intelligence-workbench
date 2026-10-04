"""B 任务：对 50 题固定评测集做**自动评审**（不改人工列、不改共享问答流程）。

评审规则（结果与规则名一起输出）：

* `R-QA-EVIDENCE`   答案非空，且带引用或带结构化事件证据
* `R-QA-QUOTE`      答案正文除模板外必须**逐字**来自被引用的原文（长度上界 + 引用原文逐一出现）
* `R-QA-REFUSAL`    拒答判定与 `should_refuse` 是否一致
* `R-QA-CONSISTENCY` 不得同时出现"拒答文案"与"文档引用"
* `R-QA-AMBIGUOUS`  标准答案本身是否含糊（候选多跳题、或应作答题却没命中预期文档）

输出字段：`auto_judgment` / `auto_reason` / `auto_evidence` / `auto_confidence`。
**不写** `人工判定*`、`人工核验人`、`人工核验时间`。

多轮追问、跨文档、多跳三类一律降置信度，并在理由里注明"需人工复核"。

用法::

    python tools/auto_review_qa.py --out artifacts/b_eval/qa_auto_review.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
RESULTS = ROOT / "artifacts" / "b_eval" / "formal_qa_results.json"
DOCUMENT_TEMPLATE = "根据命中的原文证据："
REFUSAL_FRAGMENT = "未找到可匹配的事件"

# 这三类题目的自动判定置信度一律降低
LOW_CONFIDENCE_CATEGORIES = {"多轮追问", "跨文档问答", "真实多跳问答"}


def _answer_budget(citations: list[dict]) -> int:
    quoted = citations[:3]
    return len(DOCUMENT_TEMPLATE) + 1 + sum(len(c.get("quote") or "") + 2 for c in quoted) + len(quoted)


def _answer_bullets(answer: str) -> list[str] | None:
    """把文档答案拆成引用条目；不是文档答案时返回 None。

    文档答案的格式固定为：``根据命中的原文证据：`` + 若干条 ``- <quote>``。
    答案正文只允许由这些条目组成——这条规则用来验证"答案没有模板之外的自造文字"。

    注意：引用原文自身**含换行**，因此不能用 ``split("\\n")`` 切分，
    必须按条目分隔符 ``"\\n- "`` 切分，否则一条引言会被拆成多段。
    """
    if not answer.startswith(DOCUMENT_TEMPLATE):
        return None
    body = answer[len(DOCUMENT_TEMPLATE):].lstrip("\n")
    if not body.startswith("- "):
        return None
    return body[2:].split("\n- ")


def review_case(case: dict, record: dict) -> dict:
    citations = record.get("citations_detail") or []
    # 优先用完整答案；旧结果只有 200 字截断版，截断会导致引用核验误判
    answer = record.get("answer_full") or record.get("answer_head") or ""
    rules: list[dict] = []

    has_event = bool(record.get("related_event_ids"))
    has_citation = bool(citations)

    # R-QA-EVIDENCE
    if not answer:
        rules.append({"rule": "R-QA-EVIDENCE", "result": "fail", "detail": "答案为空"})
    elif has_event or has_citation:
        rules.append({"rule": "R-QA-EVIDENCE", "result": "pass",
                      "detail": f"事件证据 {len(record.get('related_event_ids') or [])} 条 / 文档引用 {len(citations)} 条"})
    else:
        rules.append({"rule": "R-QA-EVIDENCE", "result": "unavailable",
                      "detail": "既无事件证据也无文档引用（可能是正确拒答）"})

    # R-QA-QUOTE：只有走文档路径时才适用
    if has_citation:
        bullets = _answer_bullets(answer)
        shown = citations[:3]
        if bullets is None:
            rules.append({"rule": "R-QA-QUOTE", "result": "unavailable",
                          "detail": "答案不是文档引用格式（可能来自事件路径），不适用"})
        else:
            # 答案只能由前 3 条引用的原文逐字组成；第 4 条起只作为附加引用挂载
            exact = len(bullets) == len(shown) and all(
                bullet == (shown[i].get("quote") or "") for i, bullet in enumerate(bullets)
            )
            only_quotes = len(answer) <= _answer_budget(citations) + 40
            ok = exact and only_quotes
            rules.append({
                "rule": "R-QA-QUOTE", "result": "pass" if ok else "fail",
                "detail": (f"答案由 {len(bullets)} 条引言组成，与前 {len(shown)} 条引用逐字一致={exact}；"
                           f"长度 {len(answer)} ≤ 上界 {_answer_budget(citations) + 40}={only_quotes}；"
                           f"另有 {max(0, len(citations) - 3)} 条引用仅挂载未出现在答案正文"),
            })
    else:
        rules.append({"rule": "R-QA-QUOTE", "result": "unavailable",
                      "detail": "没有文档引用，无法核验引用支持性"})

    # R-QA-REFUSAL
    refused = bool(record.get("refused"))
    should = bool(case["should_refuse"])
    rules.append({"rule": "R-QA-REFUSAL", "result": "pass" if refused == should else "fail",
                  "detail": f"应拒答={should} 实际拒答={refused}"})

    # R-QA-CONSISTENCY
    contradiction = (REFUSAL_FRAGMENT in answer) and has_citation
    rules.append({"rule": "R-QA-CONSISTENCY", "result": "fail" if contradiction else "pass",
                  "detail": "拒答文案与文档引用同时出现" if contradiction else "无矛盾"})

    # R-QA-AMBIGUOUS
    ambiguous = bool(case.get("candidate_only"))
    if not ambiguous and not should and not has_event and not has_citation:
        ambiguous = True
    rules.append({"rule": "R-QA-AMBIGUOUS", "result": "fail" if ambiguous else "pass",
                  "detail": "候选多跳题或无任何证据可依据，标准答案存在歧义" if ambiguous else "标准答案有明确依据"})

    failed = [r for r in rules if r["result"] == "fail"]
    if any(r["rule"] == "R-QA-CONSISTENCY" and r["result"] == "fail" for r in rules):
        judgment, reason = "contradicted", "答案与引用自相矛盾"
    elif any(r["rule"] == "R-QA-AMBIGUOUS" and r["result"] == "fail" for r in rules):
        judgment, reason = "insufficient_evidence", "标准答案或证据不足，无法自动判定对错"
    elif failed:
        judgment, reason = "contradicted", "；".join(f"{r['rule']}: {r['detail']}" for r in failed)
    elif not has_citation and not has_event:
        judgment, reason = "not_applicable", "系统拒答且应拒答，无需判定答案支持性"
    else:
        judgment, reason = "supported", "答案由引用原文或结构化事件证据支撑"

    if case["category"] in LOW_CONFIDENCE_CATEGORIES:
        # 多轮追问 / 跨文档 / 多跳：自动规则只能核对"答案是否由引用原文构成"，
        # 无法验证指代解析、跨文档综合或推理链，因此置信度一律保持 low。
        confidence = "low"
    elif judgment == "supported" and has_citation and not failed:
        confidence = "high"
    elif judgment == "supported":
        confidence = "medium"
    else:
        confidence = "medium" if judgment == "contradicted" else "low"

    return {
        "question_id": case["question_id"],
        "category": case["category"],
        "should_refuse": should,
        "actual_refused": refused,
        "auto_judgment": judgment,
        "auto_reason": reason,
        "auto_confidence": confidence,
        "auto_evidence": {
            "citation_count": len(citations),
            "cited_document_keys": record.get("cited_document_keys") or [],
            "cited_chunk_ids": [c.get("chunk_id") for c in citations],
            "event_ids": record.get("related_event_ids") or [],
            "expected_document_keys": record.get("expected_document_keys") or [],
        },
        "auto_rules": rules,
        "manual_review_required": case["category"] in LOW_CONFIDENCE_CATEGORIES
                                  or judgment != "supported",
        "manual_label_preserved": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="问答自动评审")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "qa_auto_review.json")
    parser.add_argument("--results", type=Path, default=RESULTS,
                        help="问答运行结果文件（默认正式集基线；重评测批次请显式指定，"
                             "以免与旧批次混淆）")
    args = parser.parse_args()

    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    results = json.loads(args.results.read_text(encoding="utf-8"))
    by_id = {r["question_id"]: r for r in results["records"]}

    reviewed = [review_case(case, by_id.get(case["question_id"], {}))
                for case in dataset["cases"]]

    by_judgment: dict[str, int] = {}
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for item in reviewed:
        by_judgment[item["auto_judgment"]] = by_judgment.get(item["auto_judgment"], 0) + 1
        by_category[item["category"]][item["auto_judgment"]] += 1

    should_answer = [r for r in reviewed if not r["should_refuse"]]
    with_citation = [r for r in reviewed if r["auto_evidence"]["citation_count"] > 0]
    quote_ok = [r for r in reviewed
                if any(x["rule"] == "R-QA-QUOTE" and x["result"] == "pass" for x in r["auto_rules"])]
    quote_applicable = [r for r in reviewed
                        if any(x["rule"] == "R-QA-QUOTE" and x["result"] in {"pass", "fail"}
                               for x in r["auto_rules"])]
    quote_not_applicable = [r for r in with_citation if r not in quote_applicable]
    supported_on_answerable = [r for r in should_answer if r["auto_judgment"] == "supported"]
    contradicted = [r for r in reviewed if r["auto_judgment"] == "contradicted"]
    conflicting = [r for r in reviewed
                   if any(x["rule"] == "R-QA-CONSISTENCY" and x["result"] == "fail"
                          for x in r["auto_rules"])]
    low_conf = [r for r in reviewed if r["auto_confidence"] == "low"]

    confusion = {
        "should_refuse_true": {
            "n": len([r for r in reviewed if r["should_refuse"]]),
            "refused_ok": len([r for r in reviewed if r["should_refuse"] and r["actual_refused"]]),
            "answered_wrongly": len([r for r in reviewed if r["should_refuse"] and not r["actual_refused"]]),
        },
        "should_refuse_false": {
            "n": len(should_answer),
            "answered_ok": len([r for r in should_answer if not r["actual_refused"]]),
            "refused_wrongly": len([r for r in should_answer if r["actual_refused"]]),
        },
    }

    latency = results.get("latency_ms") or {}
    payload = {
        "schema_version": "b-qa-auto-review-1.0",
        "method": "规则化自动评审；结果只写入 auto_* 字段，不写人工列。"
                  "字符串/长度规则只能证明答案由引用原文组成，不能证明答案语义正确。",
        "evidence_sources": ["artifacts/b_eval/formal_qa_results.json（逐题输出与引用明细）",
                             "evaluation/b_formal_qa_set.json（期望证据与是否应拒答）"],
        "caution": "自动评审 ≠ 人工核验；本文件不构成语义答案准确率。",
        "counts": {
            "total": len(reviewed),
            "by_judgment": by_judgment,
            "by_category": {k: dict(v) for k, v in sorted(by_category.items())},
        },
        "metrics": {
            "answer_support_rate_auto": {
                "numerator": len(supported_on_answerable),
                "denominator": len(should_answer),
                "rate": round(len(supported_on_answerable) / len(should_answer), 4)
                        if should_answer else None,
                "scope": "仅对'应作答'的题；是自动评审判定，不是人工准确率",
            },
            "citation_support_rate_auto": {
                "numerator": len(quote_ok),
                "denominator": len(quote_applicable),
                "rate": round(len(quote_ok) / len(quote_applicable), 4) if quote_applicable else None,
                "scope": "答案正文是否逐字由被引用原文构成；不代表引用内容语义上支持答案。"
                         "分母只含'答案是文档引用格式'的题。",
                "with_citations": len(with_citation),
                "not_applicable": len(quote_not_applicable),
                "not_applicable_reason": "有文档引用，但答案来自结构化事件路径，"
                                         "答案正文不是引用拼接，无法用该规则核验",
            },
            "confusion": confusion,
            "refusal_recall": {
                "numerator": confusion["should_refuse_true"]["refused_ok"],
                "denominator": confusion["should_refuse_true"]["n"],
                "rate": round(confusion["should_refuse_true"]["refused_ok"]
                              / confusion["should_refuse_true"]["n"], 4)
                        if confusion["should_refuse_true"]["n"] else None,
            },
            "answer_rate": {
                "numerator": confusion["should_refuse_false"]["answered_ok"],
                "denominator": confusion["should_refuse_false"]["n"],
                "rate": round(confusion["should_refuse_false"]["answered_ok"]
                              / confusion["should_refuse_false"]["n"], 4)
                        if confusion["should_refuse_false"]["n"] else None,
            },
            "coverage": {
                "auto_reviewed": len(reviewed),
                "total": len(reviewed),
                "coverage_rate": round(len(reviewed) / len(reviewed), 4),
                "undetermined": len([r for r in reviewed
                                     if r["auto_judgment"] == "insufficient_evidence"]),
                "undetermined_rate": round(
                    len([r for r in reviewed if r["auto_judgment"] == "insufficient_evidence"])
                    / len(reviewed), 4),
                "low_confidence": len(low_conf),
                "manual_review_required": len([r for r in reviewed if r["manual_review_required"]]),
            },
            "consistency_violations": len(conflicting),
            "contradicted": len(contradicted),
            "latency_ms_from_previous_run": latency,
            "latency_source": "artifacts/b_eval/formal_qa_results.json（上一轮同一批 50 题的实测值，"
                              "本轮未重新计时）",
            "failures": {"errors": results["totals"]["errors"],
                         "timeouts": results["totals"]["timeouts"]},
        },
        "computable": {
            "semantic_answer_accuracy": None,
            "relation_precision_recall": None,
            "reason": "缺少人工核验标签；自动评审不能替代人工准确率",
        },
        "cases": reviewed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("自动评审题数:", payload["counts"]["total"])
    print("判定分布:", json.dumps(by_judgment, ensure_ascii=False))
    print("答案支持率(自动):", payload["metrics"]["answer_support_rate_auto"])
    print("引用支持率(自动):", payload["metrics"]["citation_support_rate_auto"])
    print("混淆矩阵:", json.dumps(confusion, ensure_ascii=False))
    print("覆盖率/无法判定:", json.dumps(payload["metrics"]["coverage"], ensure_ascii=False))
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
