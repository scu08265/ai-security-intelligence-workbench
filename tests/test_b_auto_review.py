"""B 任务：自动核验逻辑与产物的测试。

覆盖两类容易出错的地方：

1. **规则语义**——"字符串没找到"不得判成 contradicted（只能算证据不足）；
   只有逻辑自相矛盾才知道是 contradicted。
2. **答案解析**——引用原文内部含换行，解析必须按 `\\n- ` 切分。

产物结构另测，确保自动判定写在 `auto_*` 字段里，没有污染人工列。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from auto_review_qa import (  # noqa: E402
    DOCUMENT_TEMPLATE, REFUSAL_FRAGMENT, _answer_bullets, review_case,
)
from auto_review_relations import _verdict  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"


# --------------------------------------------------------------------------
# 规则语义
# --------------------------------------------------------------------------

def test_missing_string_is_insufficient_evidence_not_contradiction():
    """原始快照里没出现该字符串，只能算证据不足。"""
    rules = [{"rule": "R-VR-SNAPSHOT", "result": "unavailable", "detail": "未出现"}]
    judgment, _reason, confidence = _verdict(rules)
    assert judgment == "insufficient_evidence"
    assert confidence == "low"


def test_failed_rule_means_contradicted():
    rules = [{"rule": "R-FV-CONSISTENCY", "result": "fail", "detail": "落在区间内"}]
    judgment, reason, confidence = _verdict(rules)
    assert judgment == "contradicted"
    assert "R-FV-CONSISTENCY" in reason
    assert confidence == "high"


def test_two_passes_give_supported_with_high_confidence():
    rules = [{"rule": "A", "result": "pass", "detail": "ok"},
             {"rule": "B", "result": "pass", "detail": "ok"}]
    judgment, _reason, confidence = _verdict(rules)
    assert judgment == "supported"
    assert confidence == "high"


def test_one_pass_plus_unavailable_gives_medium_confidence():
    rules = [{"rule": "A", "result": "pass", "detail": "ok"},
             {"rule": "B", "result": "unavailable", "detail": "缺快照"}]
    judgment, _reason, confidence = _verdict(rules)
    assert judgment == "supported"
    assert confidence == "medium"


# --------------------------------------------------------------------------
# 答案解析：引用原文含换行
# --------------------------------------------------------------------------

def test_answer_bullets_handles_multiline_quotes():
    q1 = "line one\nline two\nline three"
    q2 = "another quote\nwith a newline"
    answer = f"{DOCUMENT_TEMPLATE}\n- {q1}\n- {q2}"
    assert _answer_bullets(answer) == [q1, q2]


def test_answer_bullets_returns_none_for_non_document_answer():
    assert _answer_bullets("CVE-2099-0001：some event summary") is None
    assert _answer_bullets("") is None


def test_answer_bullets_returns_none_when_template_has_no_bullets():
    assert _answer_bullets(DOCUMENT_TEMPLATE) is None


# --------------------------------------------------------------------------
# 问答评审规则
# --------------------------------------------------------------------------

def _case(category: str = "基础事实问答", should_refuse: bool = False,
          candidate_only: bool = False) -> dict:
    return {"question_id": "BQA-T", "category": category,
            "should_refuse": should_refuse, "candidate_only": candidate_only}


def _record(answer: str, citations: list[dict], refused: bool = False,
            events: list[str] | None = None) -> dict:
    return {"answer_full": answer, "citations_detail": citations, "refused": refused,
            "related_event_ids": events or [], "cited_document_keys": [],
            "expected_document_keys": [], "answer_head": answer[:200]}


def test_refusal_text_with_citations_is_flagged_as_contradiction():
    quote = "x" * 100
    record = _record(f"{REFUSAL_FRAGMENT}，无法可靠回答。",
                     [{"chunk_id": "c", "quote": quote}], refused=False)
    result = review_case(_case(), record)
    assert result["auto_judgment"] == "contradicted"
    assert any(r["rule"] == "R-QA-CONSISTENCY" and r["result"] == "fail"
               for r in result["auto_rules"])


def test_correct_refusal_is_not_applicable():
    record = _record(f"{REFUSAL_FRAGMENT}，无法可靠回答。", [], refused=True)
    result = review_case(_case(should_refuse=True), record)
    assert result["auto_judgment"] == "not_applicable"
    assert all(r["result"] != "fail" for r in result["auto_rules"])


def test_document_answer_built_only_from_quotes_is_supported():
    q1, q2 = "alpha " * 30, "beta " * 30
    answer = f"{DOCUMENT_TEMPLATE}\n- {q1}\n- {q2}"
    record = _record(answer, [{"chunk_id": "c1", "quote": q1},
                              {"chunk_id": "c2", "quote": q2}], refused=False)
    result = review_case(_case(), record)
    assert result["auto_judgment"] == "supported"
    quote_rule = next(r for r in result["auto_rules"] if r["rule"] == "R-QA-QUOTE")
    assert quote_rule["result"] == "pass"


def test_answer_with_extra_text_beyond_quotes_fails_quote_rule():
    q1 = "alpha " * 30
    answer = f"{DOCUMENT_TEMPLATE}\n- {q1}\n- 这是系统自己编出来的一句结论"
    record = _record(answer, [{"chunk_id": "c1", "quote": q1}], refused=False)
    result = review_case(_case(), record)
    quote_rule = next(r for r in result["auto_rules"] if r["rule"] == "R-QA-QUOTE")
    assert quote_rule["result"] == "fail"
    assert result["auto_judgment"] == "contradicted"


def test_should_refuse_but_answered_is_contradicted():
    record = _record("这里是一个普通回答。", [], refused=False)
    result = review_case(_case(should_refuse=True), record)
    assert result["auto_judgment"] == "contradicted"
    assert any(r["rule"] == "R-QA-REFUSAL" and r["result"] == "fail"
               for r in result["auto_rules"])


@pytest.mark.parametrize("category", ["多轮追问", "跨文档问答", "真实多跳问答"])
def test_low_confidence_categories_are_marked_for_manual_review(category):
    q1 = "alpha " * 30
    record = _record(f"{DOCUMENT_TEMPLATE}\n- {q1}", [{"chunk_id": "c", "quote": q1}])
    result = review_case(_case(category=category), record)
    assert result["auto_confidence"] == "low"
    assert result["manual_review_required"] is True


def test_candidate_multihop_is_ambiguous_not_judged_correct():
    record = _record(f"{DOCUMENT_TEMPLATE}\n- {('x' * 100)}",
                     [{"chunk_id": "c", "quote": "x" * 100}])
    result = review_case(_case(category="真实多跳问答", candidate_only=True), record)
    assert result["auto_judgment"] == "insufficient_evidence"
    assert any(r["rule"] == "R-QA-AMBIGUOUS" and r["result"] == "fail"
               for r in result["auto_rules"])


# --------------------------------------------------------------------------
# 产物结构
# --------------------------------------------------------------------------

def _load(name: str) -> dict:
    path = ARTIFACTS / name
    if not path.is_file():
        pytest.skip(f"产物不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_relation_auto_review_covers_all_candidates_without_touching_manual_columns():
    payload = _load("relation_auto_review.json")
    assert payload["counts"]["total"] == 121
    for case in payload["cases"]:
        assert case["auto_judgment"] in {"supported", "contradicted",
                                         "insufficient_evidence", "not_applicable"}
        assert case["auto_reason"]
        assert case["manual_label_preserved"] == "pending_human_review"
        assert "人工判定" not in json.dumps(case, ensure_ascii=False)


def test_qa_auto_review_covers_all_questions_without_manual_labels():
    payload = _load("qa_auto_review.json")
    assert payload["counts"]["total"] == 50
    assert payload["computable"]["semantic_answer_accuracy"] is None
    for case in payload["cases"]:
        assert case["auto_judgment"] in {"supported", "contradicted",
                                         "insufficient_evidence", "not_applicable"}
        assert case["manual_label_preserved"] is None


def test_summary_reports_only_auto_metrics_and_keeps_human_metrics_not_computable():
    payload = _load("auto_review_summary.json")
    assert payload["headline"]["relation_candidates_reviewed"] == 121
    assert payload["headline"]["qa_questions_reviewed"] == 50
    assert payload["relation_metrics"]["human_precision_recall"]["computable"] is False
    assert "semantic_answer_accuracy" in payload["not_computable"]
    assert payload["cautions"]
