"""B 任务问答评测：金标准工作表、证据包与人工指标工具的测试。

重点：

* 50 题工作表结构完整、**人工列一律留空**（不得预填、不得把自动结果写成人工结论）；
* 评分工具在无人工判定时必须 `computable=false`，不得用自动结果顶替；
* 有合成人工判定时，各指标的分子/分母与口径必须正确（含 partial、not_applicable、unknown）；
* 自动评审结果单独成段，不混入人工指标。
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import score_b_qa_annotations as scoring  # noqa: E402
import apply_b_qa_labels as qa_labels  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
GOLD_SHEET = ARTIFACTS / "qa_gold_standard_worksheet.csv"
GOLD_PACKET = ARTIFACTS / "qa_gold_evidence_packet.md"
QA_DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}（先运行 tools/build_b_evidence_packets.py）")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _row(question_id, category, should_refuse, refused, answer, citation, refusal,
         latency="100.0"):
    return {
        "question_id": question_id, "category": category,
        "should_refuse": str(should_refuse), "system_refused": str(refused),
        "latency_ms": latency, "question": "q",
        "人工判定_答案正确性": answer, "人工判定_引用准确性": citation,
        "人工判定_拒答正确性": refusal,
        "人工最终标签": "reviewed" if (answer or citation or refusal) else "",
    }


# --------------------------------------------------------------------------
# 工作表与证据包结构
# --------------------------------------------------------------------------

JUDGEMENTS = ("人工判定_答案正确性", "人工判定_引用准确性", "人工判定_拒答正确性")


def _decided_ids(path):
    return {r["question_id"] for r in _read_csv(path)
            if any((r[c] or "").strip() for c in JUDGEMENTS)}


def test_gold_sheet_covers_all_fifty_questions_with_consistent_human_columns():
    """人工列必须自洽：填了判定就必须有署名；没填判定就必须整行留空。"""
    rows = _read_csv(GOLD_SHEET)
    dataset = json.loads(QA_DATASET.read_text(encoding="utf-8"))
    assert len(rows) == 50
    assert [r["question_id"] for r in rows] == [c["question_id"] for c in dataset["cases"]]
    assert Counter(r["category"] for r in rows) == Counter(
        c["category"] for c in dataset["cases"])
    assert Counter(r["expected_action"] for r in rows) == {"应回答": 38, "应拒答": 12}
    for row in rows:
        decided = any((row[c] or "").strip() for c in JUDGEMENTS)
        if decided:
            assert row["人工判定_答案正确性"] in {"", "correct", "incorrect", "partial", "unknown"}
            assert row["人工判定_引用准确性"] in {
                "", "supported", "partially_supported", "unsupported",
                "not_applicable", "unknown"}
            assert row["人工判定_拒答正确性"] in {
                "", "correct", "incorrect", "not_applicable", "unknown"}
            assert row["人工核验人"] and row["人工核验时间"], row["question_id"]
        else:
            for column in JUDGEMENTS + ("人工核验人", "人工核验时间", "人工备注"):
                assert row[column] == "", f"{row['question_id']} 的 {column} 不应预填"


def test_gold_sheet_keeps_auto_and_human_separate():
    rows = _read_csv(GOLD_SHEET)
    for row in rows:
        assert row["auto_judgment"] in {
            "supported", "contradicted", "insufficient_evidence", "not_applicable"}
        assert row["corpus_probe_summary"]
        assert row["evidence_location"] == "" or "@" in row["evidence_location"]
    # 35 题有可逐条核对的引用原文
    assert sum(1 for r in rows if r["cited_chunk_ids"]) == 35
    assert sum(1 for r in rows if r["evidence_excerpt"]) == 35


def test_gold_evidence_packet_covers_fifty_questions():
    if not GOLD_PACKET.is_file():
        pytest.skip("证据包不存在（先运行 tools/build_b_evidence_packets.py）")
    heads = [b.split("\n")[0] for b in GOLD_PACKET.read_text(encoding="utf-8").split("### ")[1:]]
    assert len(heads) == 50
    assert {h.split(" · ")[0] for h in heads} == {
        f"BQA-{i:03d}" for i in range(1, 51)}


# --------------------------------------------------------------------------
# 指标口径
# --------------------------------------------------------------------------

def test_metrics_are_computed_only_from_decided_rows():
    """人工指标分母 = 实际做出该维度判定的题数；unknown/空白/not_applicable 不进分母。"""
    rows = _read_csv(GOLD_SHEET)
    result = scoring.score(rows)
    decided_answer = sum(
        1 for r in rows if (r["人工判定_答案正确性"] or "").strip()
        in {"correct", "incorrect", "partial"})
    decided_citation = sum(
        1 for r in rows if (r["人工判定_引用准确性"] or "").strip()
        in {"supported", "partially_supported", "unsupported"})
    decided_refusal = sum(
        1 for r in rows if (r["人工判定_拒答正确性"] or "").strip()
        in {"correct", "incorrect"})
    assert result["answer"]["denominator"] == decided_answer
    assert result["citation"]["denominator"] == decided_citation
    assert result["refusal"]["judged_cases"] == decided_refusal
    assert result["human_judged_cases"] == len(
        _decided_ids(GOLD_SHEET))
    assert result["human_judged_cases"] + result["pending_human_cases"] == 50
    # 无判定时不给数值；有判定时给出数值
    assert (result["answer"]["rate"] is None) == (decided_answer == 0)
    assert (result["citation"]["rate"] is None) == (decided_citation == 0)
    assert (result["computable"] is False) == (result["human_judged_cases"] == 0)
    # unknown 与 not_applicable 一律单列，不当作正确
    assert result["answer"]["undecided"] >= sum(
        1 for r in rows if (r["人工判定_答案正确性"] or "").strip() == "unknown")
    assert result["refusal"]["not_applicable"] == sum(
        1 for r in rows if (r["人工判定_拒答正确性"] or "").strip() == "not_applicable")
    # 机器时延仍可报告
    assert result["latency_ms"]["samples"] == 50
    assert result["latency_ms"]["p95"] is not None


def test_answer_and_citation_metrics_follow_the_declared_rules():
    rows = [
        _row("Q1", "基础事实问答", False, False, "correct", "supported", "correct"),
        _row("Q2", "基础事实问答", False, False, "incorrect", "unsupported", "incorrect"),
        _row("Q3", "跨文档问答", False, False, "partial", "partially_supported", "correct"),
        _row("Q4", "跨文档问答", False, True, "unknown", "unknown", "unknown"),
    ]
    result = scoring.score(rows)
    assert result["computable"] is True
    answer = result["answer"]
    assert (answer["numerator"], answer["denominator"], answer["rate"]) == (1, 3, 0.3333)
    assert answer["strict_rate"] == 0.5          # partial 不计入严格分母
    assert answer["partial_counted_not_correct"] == 1
    assert answer["undecided"] == 1
    citation = result["citation"]
    assert (citation["numerator"], citation["denominator"], citation["rate"]) == (1, 3, 0.3333)
    assert citation["undecided"] == 1


def test_refusal_metrics_separate_recall_precision_and_not_applicable():
    rows = [
        # 应拒答但系统作答 → 拒答召回失败
        _row("Q1", "拒答及证据不足", True, False, "incorrect", "unsupported", "incorrect"),
        # 应拒答且正确拒答
        _row("Q2", "拒答及证据不足", True, True, "correct", "not_applicable", "correct"),
        # 应回答且作答正确
        _row("Q3", "基础事实问答", False, False, "correct", "supported", "correct"),
        # 未判定
        _row("Q4", "基础事实问答", False, False, "", "", ""),
    ]
    refusal = scoring.score(rows)["refusal"]
    assert refusal["judged_cases"] == 3
    assert refusal["should_refuse"]["n"] == 2
    assert refusal["should_refuse"]["correctly_refused"] == 1
    assert refusal["should_refuse"]["refused_recall"] == 0.5
    assert refusal["should_refuse"]["answered_by_system"] == 1
    assert refusal["refused_precision"] == 1.0     # 实际拒答 1 次且正确
    assert refusal["refusal_accuracy"] == 0.6667   # 3 题中 2 题判定正确
    assert refusal["undecided"] == 1
    # not_applicable 的引用判定单列、不进引用分母
    citation = scoring.score(rows)["citation"]
    assert citation["not_applicable"] == 1
    assert citation["denominator"] == 2      # 只统计 supported/partially/unsupported
    assert citation["rate"] == 0.5


def test_by_category_only_lists_categories_with_human_judgement():
    rows = [
        _row("Q1", "基础事实问答", False, False, "correct", "supported", "correct"),
        _row("Q2", "多跳问答", False, False, "", "", ""),
    ]
    result = scoring.score(rows)
    assert list(result["by_category"]) == ["基础事实问答"]
    assert result["by_category"]["基础事实问答"]["answer"]["rate"] == 1.0


def test_auto_review_is_kept_separate_from_human_metrics():
    rows = [_row("Q1", "基础事实问答", False, False, "correct", "supported", "correct")]
    auto = {"source": "qa_auto_review.json",
            "metrics": {"answer_support_rate_auto": {"rate": 0.8684}},
            "warning": "自动评审判定，**不是**人工指标；不得当作准确率使用"}
    result = scoring.score(rows, auto)
    assert result["auto_review"] == auto
    # 人工指标只来自人工列，与自动结果无关
    assert result["answer"]["rate"] == 1.0
    assert "answer_support_rate_auto" not in json.dumps(
        {k: v for k, v in result.items() if k != "auto_review"}, ensure_ascii=False)


def test_percentile_helper_matches_expected_quantiles():
    assert scoring._percentile([], 0.5) is None
    assert scoring._percentile([10.0], 0.95) == 10.0
    values = [float(i) for i in range(1, 101)]
    # 采用最近秩（nearest-rank）口径、不做线性插值：p50 取第 51 个样本
    assert scoring._percentile(values, 0.5) == 51.0
    assert scoring._percentile(values, 0.95) == 95.0


# --------------------------------------------------------------------------
# 机器候选标准答案与统一裁定表
# --------------------------------------------------------------------------

CANDIDATE_ANSWERS = ARTIFACTS / "qa_candidate_answers.json"
ADJUDICATION = ARTIFACTS / "qa_adjudication_table.csv"


def test_candidate_answers_are_labelled_as_machine_suggestions():
    if not CANDIDATE_ANSWERS.is_file():
        pytest.skip("候选标准答案不存在（先运行 tools/build_b_qa_candidate_answers.py）")
    payload = json.loads(CANDIDATE_ANSWERS.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert len(cases) == 50
    assert payload["suggestion_level"] == "machine_candidate"
    assert "不是人工金标准" in payload["warning"]
    for case in cases:
        assert case["suggestion_level"] == "machine_candidate"
        assert case["human_confirmed"] is False
        assert case["candidate_answer"], case["question_id"]
        assert case["minimal_human_judgment"], case["question_id"]
        assert case["alternatives"], case["question_id"]
        # 机器建议必须单独存放，不能出现人工标签字段
        assert "人工最终标签" not in case
    counts = payload["counts"]
    assert counts["questions"] == 50
    assert counts["refusal_recommended"] == 12
    assert counts["with_citations"] == 35
    assert counts["contested"] == 10


def test_cross_document_answers_list_per_source_facts_and_flag_synthesis():
    payload = json.loads(CANDIDATE_ANSWERS.read_text(encoding="utf-8"))
    cross = [c for c in payload["cases"]
             if c["question_id"] in {f"BQA-{i:03d}" for i in range(31, 39)}]
    assert len(cross) == 8
    for case in cross:
        assert case["contested"] is True
        facts = case.get("cross_document_facts") or []
        assert facts, case["question_id"]
        assert all(f["document_key"] and f["supports"] for f in facts)
        # 不得仅凭多文档引用宣称已完成综合
        assert case.get("synthesis_conclusion")
        assert ("无法证明综合" in case["synthesis_conclusion"]
                or "只命中单一文档" in case["synthesis_conclusion"])


def test_adjudication_table_covers_all_questions_and_separates_contested():
    rows = _read_csv(ADJUDICATION)
    assert len(rows) == 50
    assert len({r["question_id"] for r in rows}) == 50
    priorities = Counter(r["priority"] for r in rows)
    assert priorities == {"P0-争议": 10, "P1-拒答": 10, "P2-多轮": 6, "P3-常规": 24}
    # 争议题排在最前
    assert all(r["priority"] == "P0-争议" for r in rows[:10])
    assert not any(r["priority"] == "P0-争议" for r in rows[10:])
    for row in rows:
        assert row["question"] and row["minimal_judgment"]
        assert row["suggested_label_machine"] and row["suggestion_rationale"]
        assert row["option_a"] and row["consequence_a"]
        decided = any((row[c] or "").strip() for c in JUDGEMENTS)
        if decided:
            assert row["人工核验人"] and row["人工核验时间"], row["question_id"]
        else:
            assert row["人工最终标签"] == "" and row["人工核验人"] == ""


def test_target_comparison_is_per_metric_and_marks_human_gaps():
    rows = _read_csv(GOLD_SHEET)
    result = scoring.score(rows, None, scoring._machine_metrics())
    comparison = result["target_comparison"]
    assert comparison["targets"] == ["75%", "90%", "95%"]
    by_metric = {m["metric"]: m for m in comparison["metrics"]}
    # 人工指标：分母 = 实际判定数；分母为 0 时必须标"不可对照"
    rows = _read_csv(GOLD_SHEET)
    decided_answer = sum(
        1 for r in rows if (r["人工判定_答案正确性"] or "").strip()
        in {"correct", "incorrect", "partial"})
    assert by_metric["人工·答案准确率"]["denominator"] == decided_answer
    for name in ("人工·答案准确率", "人工·引用准确率", "人工·拒答召回率"):
        metric = by_metric[name]
        if metric["denominator"] == 0:
            assert metric["value"] is None
            assert metric["comparison"]["75%"].startswith("不可对照")
        else:
            assert metric["value"] is not None
            assert metric["comparison"]["75%"].endswith("pt")
    # 机器指标：有真实数值与分母
    assert by_metric["机器·引用命中率"]["numerator"] == 31
    assert by_metric["机器·引用命中率"]["denominator"] == 36
    assert by_metric["机器·引用可追溯率"]["value"] == 1.0
    assert "不等于准确率" in result["machine_metrics"]["warning"]
    assert result["machine_metrics"]["source"].endswith("formal_qa_results.json")


# --------------------------------------------------------------------------
# 裁定表 → 金标准工作表的回填
# --------------------------------------------------------------------------

def _decision(**overrides) -> dict:
    row = {
        "question_id": "BQA-001",
        "人工判定_答案正确性": "correct",
        "人工判定_引用准确性": "supported",
        "人工判定_拒答正确性": "not_applicable",
        "人工核验人": "人工复核-用户确认",
        "人工核验时间": "2026-09-28",
        "人工备注": "",
    }
    row.update(overrides)
    return row


def test_apply_labels_rejects_illegal_values_and_unknown_ids():
    with pytest.raises(qa_labels.LabelImportError):
        qa_labels.collect([_decision(人工判定_答案正确性="yes")], {"BQA-001"})
    with pytest.raises(qa_labels.LabelImportError):
        qa_labels.collect([_decision(question_id="BQA-999")], {"BQA-001"})
    with pytest.raises(qa_labels.LabelImportError):
        qa_labels.collect([_decision(人工核验人="")], {"BQA-001"})
    with pytest.raises(qa_labels.LabelImportError):
        qa_labels.collect([_decision(), _decision()], {"BQA-001"})


def test_apply_labels_keeps_blank_rows_and_preserves_existing_labels():
    blank = _decision(question_id="BQA-002", 人工判定_答案正确性="",
                      人工判定_引用准确性="", 人工判定_拒答正确性="",
                      人工核验人="", 人工核验时间="")
    decisions, summary = qa_labels.collect([_decision(), blank], {"BQA-001", "BQA-002"})
    assert summary == {"blank": 1, "decided": 1}
    worksheet = [
        {c: "" for c in qa_labels.VALID} | {"question_id": "BQA-001"},
        {c: "" for c in qa_labels.VALID} | {"question_id": "BQA-002"},
        {c: "" for c in qa_labels.VALID} | {"question_id": "BQA-003"},
    ]
    counts = qa_labels.apply(decisions, worksheet)
    assert counts["written"] == 1 and not counts["skipped_preserved"]
    assert worksheet[0]["人工判定_答案正确性"] == "correct"
    assert worksheet[0]["人工核验人"] == "人工复核-用户确认"
    assert all(worksheet[1][c] == "" for c in qa_labels.VALID)
    assert all(worksheet[2][c] == "" for c in qa_labels.VALID)
    # 已有判定的行默认保留，force 才覆盖
    counts = qa_labels.apply(decisions, worksheet)
    assert counts["skipped_preserved"] == 1
    counts = qa_labels.apply(decisions, worksheet, force=True)
    assert counts["written"] == 1


def test_adjudication_table_exposes_the_three_judgement_columns():
    rows = _read_csv(ADJUDICATION)
    for column in qa_labels.VALID:
        assert column in rows[0]
    # 工具必须能读取裁定表：已填的行解析成判定，未填的行计为 blank
    decided_rows = [r for r in rows
                    if any((r[c] or "").strip() for c in qa_labels.VALID)]
    decisions, summary = qa_labels.collect(rows, {r["question_id"] for r in rows})
    assert len(decisions) == len(decided_rows)
    assert summary.get("blank", 0) == len(rows) - len(decided_rows)
    for column, allowed in qa_labels.VALID.items():
        assert all((r[column] or "").strip() in ("", *allowed) for r in rows)


# --------------------------------------------------------------------------
# 机器辅助裁定（B 类）、争议清单与三层隔离
# --------------------------------------------------------------------------

MACHINE_ADJ = ARTIFACTS / "qa_machine_adjudication.json"
MACHINE_ADJ_CSV = ARTIFACTS / "qa_machine_adjudication.csv"
PENDING_CSV = ARTIFACTS / "qa_pending_human_cases.csv"


def test_machine_adjudication_covers_fifty_cases_with_three_dimensions():
    if not MACHINE_ADJ.is_file():
        pytest.skip("机器辅助裁定不存在（先运行 tools/build_b_qa_candidate_answers.py）")
    payload = json.loads(MACHINE_ADJ.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert len(cases) == 50
    for case in cases:
        assert case["tier"] == "B_machine_assisted_suggestion"
        assert case["human_confirmed"] is False
        for dimension in ("answer_correctness", "citation_support", "refusal_correctness"):
            block = case[dimension]
            assert block["suggestion"], case["question_id"]
            assert block["status"] in {"suggested", "pending_human_review"}
            assert block["confidence"] in {"high", "medium", "low"}
            assert block["rationale"], case["question_id"]
        # 不得出现任何人工署名/人工结论字段
        assert not [k for k in case if k.startswith("人工")]


def test_machine_adjudication_separates_the_three_tiers():
    payload = json.loads(MACHINE_ADJ.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["tier_A_machine_auto_detection"] == 50
    assert summary["tier_B_machine_assisted_suggestion"] == 50
    # C 类（人工金标准）必须为 0——没有人工确认就不能凭空产生
    assert summary["tier_C_human_confirmed_gold"] == 0
    assert "不是人工金标准" in summary["note"]
    assert set(payload["tiers"]) == {
        "A_machine_auto_detection", "B_machine_assisted_suggestion",
        "C_human_confirmed_gold"}


def test_machine_adjudication_refusal_and_answer_dimensions_are_sane():
    payload = json.loads(MACHINE_ADJ.read_text(encoding="utf-8"))
    by_id = {c["question_id"]: c for c in payload["cases"]}
    # 应拒答题：答案正确性不适用；拒答维度给出 correct/incorrect
    for case in payload["cases"]:
        if case["expected_action"] == "应拒答":
            assert case["answer_correctness"]["suggestion"] == "not_applicable"
            assert case["refusal_correctness"]["suggestion"] in {"correct", "incorrect"}
    # 多轮题被错误拒答的 5 条：answer=incorrect
    for qid in ("BQA-025", "BQA-026", "BQA-028", "BQA-029", "BQA-030"):
        assert by_id[qid]["answer_correctness"]["suggestion"] == "incorrect"
        assert by_id[qid]["refusal_correctness"]["suggestion"] == "incorrect"
    # 跨文档题：明确"未能证明综合"
    for qid in ("BQA-031", "BQA-038"):
        capability = by_id[qid]["capability_analysis"]["cross_document"]
        assert capability["synthesis_proven"] is False
        assert "不能宣称已综合" in capability["conclusion"]
    # 多跳题：本地无路径
    for qid in ("BQA-039", "BQA-040"):
        assert by_id[qid]["capability_analysis"]["multihop"]["path_available"] is False


def test_machine_adjudication_csv_and_pending_list_are_consistent():
    rows = _read_csv(MACHINE_ADJ_CSV)
    assert len(rows) == 50
    assert all(r["tier"] == "B_machine_assisted_suggestion" for r in rows)
    assert all(r["answer_rationale"] and r["citation_rationale"]
               and r["refusal_rationale"] for r in rows)
    pending = _read_csv(PENDING_CSV)
    expected = [r["question_id"] for r in rows
                if r["contested"] == "True" or r["needs_human_review"] == "True"]
    assert [r["question_id"] for r in pending] == expected
    assert len(pending) == 16
    assert all(r["missing_evidence_or_criteria"] for r in pending)


def test_final_review_groups_split_the_fifty_questions():
    rows = _read_csv(MACHINE_ADJ_CSV)
    groups = Counter(r["final_review_group"] for r in rows)
    assert groups == {"A": 21, "B": 19, "C": 10}
    for row in rows:
        assert row["group_reason"], row["question_id"]
        assert row["confirm_field"] in {"答案正确性", "引用支持性", "拒答正确性",
                                        "评价口径/判据"}
        assert row["key_evidence"], row["question_id"]
    # C 组必须与"争议题"完全一致；A 组不得含有争议题
    contested = {r["question_id"] for r in rows if r["contested"] == "True"}
    group_c = {r["question_id"] for r in rows if r["final_review_group"] == "C"}
    assert group_c == contested
    assert not [r for r in rows if r["final_review_group"] == "A"
                and r["question_id"] in contested]


FINAL_SHEET = ARTIFACTS / "qa_final_confirmation_worksheet.csv"


def test_final_confirmation_worksheet_covers_all_fifty_with_consistent_human_columns():
    rows = _read_csv(FINAL_SHEET)
    assert len(rows) == 50
    assert len({r["question_id"] for r in rows}) == 50
    groups = Counter(r["final_review_group"] for r in rows)
    assert groups == {"A": 21, "B": 19, "C": 10}
    # 排序：A → B → C
    order = {"A": 0, "B": 1, "C": 2}
    assert [order[r["final_review_group"]] for r in rows] == sorted(
        order[r["final_review_group"]] for r in rows)
    for row in rows:
        for column in ("question", "system_answer", "key_evidence", "rationale",
                       "suggested_answer_correctness", "suggested_citation_support",
                       "suggested_refusal_correctness", "confirm_field"):
            assert row[column] not in (None, ""), f"{row['question_id']} 缺 {column}"
        decided = any((row[c] or "").strip() for c in JUDGEMENTS)
        if decided:
            assert row["人工核验人"] and row["人工核验时间"], row["question_id"]
        else:
            for column in JUDGEMENTS + ("人工核验人", "人工核验时间", "人工备注"):
                assert row[column] == "", f"{row['question_id']} 的 {column} 不应预填"
    # 三份表的已确认集合必须一致（防止只更新一处）
    assert _decided_ids(FINAL_SHEET) == _decided_ids(GOLD_SHEET) == _decided_ids(ADJUDICATION)


def test_cross_document_answers_are_capped_at_partial_by_the_unified_rule():
    payload = json.loads(MACHINE_ADJ.read_text(encoding="utf-8"))
    cross = [c for c in payload["cases"]
             if c["question_id"] in {f"BQA-{i:03d}" for i in range(31, 39)}]
    assert len(cross) == 8
    for case in cross:
        assert case["answer_correctness"]["suggestion"] == "partial"
        assert case["answer_correctness"]["status"] == "pending_human_review"
        assert "跨来源" in case["answer_correctness"]["rationale"]


def test_failure_samples_are_reported_without_touching_human_metrics():
    rows = _read_csv(GOLD_SHEET)
    adjudication = json.loads(MACHINE_ADJ.read_text(encoding="utf-8"))["cases"]
    result = scoring.score(rows, None, scoring._machine_metrics(), adjudication)
    samples = result["failure_samples"]
    # 24 条：多轮 5 + 拒答漏判 4 + 泛词 2 + 跨文档 8 + 引用待判 5
    assert len(samples) == 24
    assert all(s["tier"] == "B_machine_assisted_suggestion" for s in samples)
    assert all(s["issues"] and s["reason"] for s in samples)
    ids = {s["question_id"] for s in samples}
    assert {"BQA-039", "BQA-044", "BQA-047"} <= ids
    # B 类失败样本不得改变人工指标：去掉 adjudication 后人工部分必须完全相同
    baseline = scoring.score(rows, None, scoring._machine_metrics())
    for block in ("answer", "citation", "refusal", "by_category", "human_judged_cases"):
        assert result[block] == baseline[block]


def test_partial_human_labels_enter_denominators_but_unknown_and_blank_do_not():
    """部分确认也必须能算：unknown/空白不进分母，partial 计入分母但不计严格正确。"""
    def gold(qid, answer, citation, refusal, should_refuse=False, refused=False):
        return {"question_id": qid, "category": "基础事实问答",
                "should_refuse": str(should_refuse), "system_refused": str(refused),
                "latency_ms": "100.0", "question": "q",
                "人工判定_答案正确性": answer, "人工判定_引用准确性": citation,
                "人工判定_拒答正确性": refusal,
                "人工最终标签": "reviewed" if (answer or citation or refusal) else ""}
    rows = [
        gold("Q1", "correct", "supported", ""),
        gold("Q2", "correct", "supported", ""),
        gold("Q3", "partial", "partially_supported", ""),
        gold("Q4", "unknown", "unknown", ""),          # 明确 unknown，不进分母
        gold("Q5", "", "", ""),                        # 空白，不进任何分母
        gold("Q6", "", "not_applicable", "correct", should_refuse=True, refused=True),
        gold("Q7", "", "not_applicable", "incorrect", should_refuse=True, refused=False),
    ]
    result = scoring.score(rows)
    answer = result["answer"]
    assert (answer["numerator"], answer["denominator"], answer["rate"]) == (2, 3, 0.6667)
    assert answer["strict_rate"] == 1.0            # 严格口径排除 partial
    assert answer["undecided"] == 4                # unknown 1 + 空白 2 + 拒答题 1
    citation = result["citation"]
    assert (citation["numerator"], citation["denominator"]) == (2, 3)
    refusal = result["refusal"]
    assert refusal["judged_cases"] == 2
    assert refusal["should_refuse"]["n"] == 2
    assert refusal["should_refuse"]["refused_recall"] == 0.5
    assert refusal["refused_precision"] == 1.0
    assert result["by_category"]["基础事实问答"]["answer"]["numerator"] == 2
