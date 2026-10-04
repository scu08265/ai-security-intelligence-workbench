"""B 任务重评测（20261002）回归测试。

覆盖队长布置的五项验收里可自动化的部分：

* 新批次产物齐全（50 题），且**旧基线文件仍在**（旧结果必须保留）；
* 性能统计按批次分开，不跨批次合并分位数；
* 机器辅助裁定仍声明 C 类（人工确认）= 0，不得冒充人工金标准；
* 新工作表人工列留空时不给指标（不得把空值当 0% 或 100%）；
* 拒答分类的计数自洽（正确拒答 + 错误作答 = 应拒答题数）；
* 赛题指标页面与权威冻结 JSON 逐字段一致，并优先展示 20261002 活动批次。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_b_scorecard_consistency as consistency  # noqa: E402
import score_b_qa_annotations as scoring  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
NEW_RESULTS = ARTIFACTS / "formal_qa_results_20261002.json"
NEW_PERFORMANCE = ARTIFACTS / "qa_performance_20261002.json"
NEW_ADJUDICATION = ARTIFACTS / "qa_machine_adjudication_20261002.json"
NEW_WORKSHEET = ARTIFACTS / "qa_final_confirmation_worksheet_20261002.csv"
NEW_REFUSALS = ARTIFACTS / "refusal_failure_classification_20261002.json"
POC_WORKSHEET = ARTIFACTS / "relation_poc_review_20261002.csv"
POC_CLASSIFICATION = ARTIFACTS / "relation_poc_classification_20261002.json"
OLD_RESULTS = ARTIFACTS / "formal_qa_results.json"
OLD_HUMAN_SCORE = ARTIFACTS / "qa_human_score.json"

JUDGEMENTS = ("人工判定_答案正确性", "人工判定_引用准确性", "人工判定_拒答正确性")


def _load(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}（先运行 20261002 批次工具）")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_new_run_covers_fifty_questions_and_old_files_are_preserved():
    new = _load(NEW_RESULTS)
    assert new["totals"]["cases"] == 50
    assert len(new["records"]) == 50
    assert len({r["question_id"] for r in new["records"]}) == 50
    # 旧基线必须仍然存在，且不是被新结果覆盖的那一份
    assert OLD_RESULTS.is_file() and OLD_HUMAN_SCORE.is_file()
    old = json.loads(OLD_RESULTS.read_text(encoding="utf-8"))
    assert len(old["records"]) == 50
    assert old["totals"]["answered"] != new["totals"]["answered"] or \
        old["records"] != new["records"]


def test_new_run_reports_latency_timeouts_and_citation_traceability():
    payload = _load(NEW_RESULTS)
    latency = payload["latency_ms"]
    assert latency["samples"] == 50
    assert latency["p50"] is not None and latency["p95"] is not None
    assert payload["totals"]["timeouts"] == 0
    assert payload["totals"]["errors"] == 0
    citations = payload["totals"]["citations"]
    assert citations["total"] > 0
    assert 0.0 <= citations["rate"] <= 1.0
    # 语义答案准确率不得被机器指标顶替
    assert payload["totals"]["answer_semantic_accuracy"]["value"] is None


def test_performance_batches_are_kept_separate_per_batch():
    stats = _load(NEW_PERFORMANCE)
    batches = stats["batches"]
    assert len(batches) >= 2
    for batch in batches:
        assert batch["cases"] == 50
        assert batch["latency_ms"]["samples"] <= batch["cases"]
    labels = {b["label"] for b in batches}
    assert any("20261002" in label for label in labels)
    assert "绝不合并" in stats["notes"]["no_mixing"]
    # 逐题对照只在题号集合一致时出现，且是差值而非合并
    comparison = stats["comparison"]
    assert comparison["question_count"] == 50
    assert "−" in comparison["delta_ms"]["scope"]


def test_machine_adjudication_still_declares_zero_human_confirmed_cases():
    payload = _load(NEW_ADJUDICATION)
    assert payload["summary"]["tier_C_human_confirmed_gold"] == 0
    assert len(payload["cases"]) == 50
    assert "不得写入人工标签列" in payload["warning"]
    for case in payload["cases"]:
        for dimension in ("answer_correctness", "citation_support", "refusal_correctness"):
            block = case[dimension]
            assert block["status"] in {"suggested", "pending_human_review"}
            assert block["suggestion"]
        assert case["human_confirmed"] is False


def test_new_worksheet_human_labels_are_complete_and_signed():
    rows = _read_csv(NEW_WORKSHEET)
    assert len(rows) == 50
    for row in rows:
        decided = any((row.get(column) or "").strip() for column in JUDGEMENTS)
        if not decided:
            continue
        assert (row.get("人工核验人") or "").strip()
        assert (row.get("人工核验时间") or "").strip()
    decided_rows = [row for row in rows
                    if any((row.get(column) or "").strip() for column in JUDGEMENTS)]
    assert len(decided_rows) == 50
    assert {(row["人工核验人"], row["人工核验时间"]) for row in decided_rows} == {
        ("人工复核-用户确认", "2026-10-04")}


def test_blank_new_worksheet_yields_no_metrics_rather_than_zero_percent():
    rows = []
    for row in _read_csv(NEW_WORKSHEET):
        blank = dict(row)
        for column in JUDGEMENTS + ("人工核验人", "人工核验时间", "人工最终标签",
                                    "human_final_judgment_人工最终判定"):
            blank[column] = ""
        rows.append(blank)
    result = scoring.score(rows, {}, {}, [])
    assert result["human_judged_cases"] == 0
    assert result["pending_human_cases"] == 50
    assert result["answer"]["rate"] is None
    assert result["answer"]["numerator"] == 0
    assert result["citation"]["rate"] is None
    assert result["refusal"]["refusal_accuracy"] is None


def test_new_human_score_reports_fifty_confirmed_cases_and_blanks_stay_out():
    payload = _load(ARTIFACTS / "qa_human_score_20261002.json")
    assert payload["human_judged_cases"] == 50
    assert payload["pending_human_cases"] == 0
    assert payload["computable"] is True
    # 拒答维度：应作答且作答记 not_applicable，因此分母是 12 而不是 50
    assert payload["refusal"]["judged_cases"] == 12
    assert payload["refusal"]["should_refuse"]["n"] == 12
    # 答案维度：空值不进分母（38 条参与，12 条 undecided）
    assert payload["answer"]["denominator"] + payload["answer"]["undecided"] == 50
    assert payload["citation"]["denominator"] + payload["citation"]["undecided"] + \
        payload["citation"]["not_applicable"] == 50


def test_blank_answer_correctness_stays_out_of_the_answer_denominator():
    rows = [
        {"question_id": "BQA-001", "category": "基础问答", "should_refuse": "False",
         "system_refused": "False", "latency_ms": "100.0", "question": "q",
         "人工判定_答案正确性": "correct", "人工判定_引用准确性": "supported",
         "人工判定_拒答正确性": "not_applicable", "人工最终标签": "reviewed"},
        {"question_id": "BQA-002", "category": "拒答及证据不足", "should_refuse": "True",
         "system_refused": "False", "latency_ms": "120.0", "question": "q",
         "人工判定_答案正确性": "", "人工判定_引用准确性": "not_applicable",
         "人工判定_拒答正确性": "incorrect", "人工最终标签": "reviewed"},
    ]
    result = scoring.score(rows, {}, {}, [])
    assert result["answer"]["numerator"] == 1
    assert result["answer"]["denominator"] == 1        # 空值那一题不进分母
    assert result["answer"]["undecided"] == 1
    assert result["refusal"]["judged_cases"] == 1      # 拒答维度照常计入
    assert result["refusal"]["refusal_accuracy"] == 0.0


def test_refusal_classification_counts_are_self_consistent():
    payload = _load(NEW_REFUSALS)
    counts = payload["counts"]
    refused = sum(1 for c in payload["cases"] if c["actually_refused"])
    answered = sum(1 for c in payload["cases"] if not c["actually_refused"])
    assert counts["should_refuse_cases"] == len(payload["cases"])
    assert counts["correctly_refused"] == refused
    assert counts["wrongly_answered"] == answered
    assert counts["correctly_refused"] + counts["wrongly_answered"] == \
        counts["should_refuse_cases"]


def test_scorecard_page_matches_frozen_json_and_prefers_active_batch():
    payload = consistency.build()
    assert payload["mismatches"] == []
    assert payload["conclusion"]["page_matches_frozen_json"] is True
    assert payload["conclusion"]["page_shows_new_batch"] is True
    assert payload["active_batch"]["batch_id"] == "20261002"


def test_poc_review_worksheet_covers_every_candidate_with_signed_human_labels():
    rows = _read_csv(POC_WORKSHEET)
    classification = _load(POC_CLASSIFICATION)
    assert len(rows) == classification["candidates"]
    assert classification["events"] == len({row["event_id"] for row in rows})
    signed = set()
    for row in rows:
        # 机器建议只能是 yes/no；人工判定必须是合法值且带署名
        assert row["建议_是否可利用证据"] in {"yes", "no"}
        assert row["人工判定_是否可利用证据"] in {"yes", "no", "unknown", "not_applicable"}
        assert (row["人工核验人"] or "").strip()
        assert (row["人工核验时间"] or "").strip()
        signed.add((row["人工核验人"], row["人工核验时间"]))
        assert row["nvd_status"] == "public_exploit_reference"
    assert signed == {("人工复核-用户确认", "2026-10-04")}
    assert classification["never_executed"] is True


def test_poc_classification_counts_match_the_rows():
    rows = _read_csv(POC_WORKSHEET)
    classification = _load(POC_CLASSIFICATION)
    from collections import Counter as _Counter
    assert classification["url_type_counts"] == dict(
        _Counter(row["url_type"] for row in rows))
    assert classification["machine_suggestion_counts"] == dict(
        _Counter(row["建议_是否可利用证据"] for row in rows))


# --------------------------------------------------------------------------
# 跨文档真实关系边（选项 A：新增来源后）
# --------------------------------------------------------------------------

CROSS_DOC_EDGES = ROOT / "evaluation" / "b_cross_document_edges_20261002_v2.json"
MULTIHOP_V2 = ARTIFACTS / "multihop_path_validation_20261002_v2.json"
NEW_DOCUMENTS = ARTIFACTS / "new_documents_20261002.json"
COPY_DB = Path(r"D:\ICT\intel-data-b-poc-20261002\intel.sqlite")


def test_cross_document_edges_carry_verifiable_chunk_evidence():
    payload = _load(CROSS_DOC_EDGES)
    edges = payload["edges"]
    assert payload["counts"]["new_documents"] >= 5          # 队长要求 5–8 篇
    assert payload["counts"]["new_documents"] <= 8
    assert payload["counts"]["document_edges"] >= 5         # ≥5 条文档间边
    assert any(e["predicate"] == "mentioned_in" for e in edges)   # 术语第一跳
    if not COPY_DB.is_file():
        pytest.skip(f"库副本不存在：{COPY_DB}")
    import sqlite3
    with sqlite3.connect(f"file:{COPY_DB}?mode=ro", uri=True) as conn:
        texts = {row[0]: row[1] for row in conn.execute("select id, text from rag_chunks")}
    for edge in edges:
        evidence = edge["evidence"]
        assert edge["verified"] is True
        assert evidence["quote"]
        assert evidence["char_end"] - evidence["char_start"] == len(evidence["quote"])
        text = texts.get(evidence["chunk_id"])
        assert text is not None, evidence["chunk_id"]
        # 独立回读：偏移处必须真的等于 quote
        assert text[evidence["char_start"]:evidence["char_end"]] == evidence["quote"]


def test_new_documents_are_ingested_and_have_goal_edges():
    documents = _load(NEW_DOCUMENTS)["papers"]
    assert len(documents) >= 5
    assert all(doc["status"] == "fulltext" for doc in documents)
    assert all(doc["goal_edges"] >= 1 for doc in documents)
    assert all(doc["pdf_sha256"] and doc["snapshot_hash"] for doc in documents)


def test_multihop_v2_reports_paths_term_reachability_and_keeps_no_path():
    payload = _load(MULTIHOP_V2)
    counts = payload["counts"]
    by_type = counts["by_chain_type"]["cross_document"]
    assert by_type["path_found"] >= 1            # 验收：≥1/21
    assert counts["no_path"] >= 1                # 未连通必须保留，不得隐藏
    assert counts["term_reachable"] >= 5         # 术语第一跳独立诊断字段
    found = [c for c in payload["cases"]
             if c["chain_type"] == "cross_document" and c["path_found"]]
    for case in found:
        assert len(case["path_nodes"]) == len(case["path_edges"]) + 1
        assert case["evidence_ids"]
        assert all(edge_id for edge_id in case["evidence_ids"])
        # 路径必须跨文档：起点是术语、终点是目标文档
        assert case["path_nodes"][0].startswith("term:")
        assert case["declared_path"][-1].split(":")[0] in case["path_nodes"][-1]
    unresolved = [c for c in payload["cases"]
                  if c["chain_type"] == "cross_document" and not c["path_found"]]
    for case in unresolved:
        assert case["failure_reason"] or case.get("missing_edges")
        assert "term_diagnostics" in case
