"""B 任务 P1：人工核验工作包与 TP/FP/FN 统计程序的结构测试。

这些测试**不产生**任何人工判定，只保证：

* 工作包 CSV 的列齐全、人工填写列留空；
* 关系工作包至少 100 行，且缺失证据的维度被如实标注而不是编造；
* 统计程序只在 `human_verified` 且标签明确时才计入分母（用合成数据验证）；
* 真实候选文件在无标注时返回 `computable: false`。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from score_b_relation_annotations import score  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
QA_CSV = ARTIFACTS / "qa_review_worksheet.csv"
RELATION_CSV = ARTIFACTS / "relation_review_worksheet.csv"
FINAL_RELATION_CSV = ARTIFACTS / "relation_final_review_worksheet.csv"
RELATION_JSON = ROOT / "evaluation" / "b_relation_candidates.json"

QA_HUMAN_COLUMNS = ("人工判定_答案正确性", "人工判定_引用支持性", "人工判定_拒答正确性",
                    "人工核验人", "人工核验时间", "人工备注")
RELATION_HUMAN_COLUMNS = ("人工判定", "人工核验人", "人工核验时间", "人工备注")
FINAL_RELATION_HUMAN_COLUMNS = ("待人工填写_最终标签", "人工核验人", "人工核验时间", "人工备注")


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        pytest.skip(f"工作包不存在：{path}（先运行 tools/build_b_review_workpackets.py）")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


# --------------------------------------------------------------------------
# 工作包结构
# --------------------------------------------------------------------------

def test_qa_worksheet_has_fifty_rows_and_blank_human_columns():
    rows = _read_csv(QA_CSV)
    assert len(rows) == 50
    for row in rows:
        for column in QA_HUMAN_COLUMNS:
            assert row[column] == "", f"{row['question_id']} 的 {column} 不应预填"


def test_qa_worksheet_carries_the_information_a_reviewer_needs():
    rows = _read_csv(QA_CSV)
    for row in rows:
        assert row["question"], row["question_id"]
        assert row["should_refuse"] in {"True", "False"}
        assert row["system_answer"] is not None
        assert row["review_priority"] in {"high", "medium", "low"}
    # 至少要有题带预期文档与引用 chunk，否则无法核对引用
    assert sum(1 for r in rows if r["expected_documents"]) >= 30
    assert sum(1 for r in rows if r["cited_chunk_ids"]) >= 10


def test_relation_worksheet_has_at_least_one_hundred_rows_and_blank_labels():
    rows = _read_csv(RELATION_CSV)
    assert len(rows) >= 100, f"关系工作包只有 {len(rows)} 行"
    for row in rows:
        assert row["annotation_status"] == "pending_human_review"
        for column in RELATION_HUMAN_COLUMNS:
            assert row[column] == "", f"{row['relation_id']} 的 {column} 不应预填"
        assert row["verification_method"], row["relation_id"]
        assert row["evidence_summary"], row["relation_id"]


def test_relation_worksheet_dimensions_are_honest_about_missing_evidence():
    rows = _read_csv(RELATION_CSV)
    dimensions = {row["dimension"] for row in rows}
    assert dimensions <= {"paper_link", "version_range", "fixed_version", "cvss",
                           "poc", "asset_assessment"}
    # POC 与资产关联当前没有数据来源，工作包不得为它们编造行
    assert "poc" not in dimensions or all(
        row["evidence_summary"] for row in rows if row["dimension"] == "poc"
    )
    summary = json.loads((ARTIFACTS / "review_workpacket_summary.json").read_text(encoding="utf-8"))
    gaps = summary["relation_worksheet"]["dimensions_without_evidence"]
    assert "poc" in gaps and "asset_assessment" in gaps


def test_final_review_worksheet_merges_auto_verdict_and_keeps_human_columns_empty():
    """v2 复核表：带自动核验结论，但最终裁定列必须留空。"""
    rows = _read_csv(FINAL_RELATION_CSV)
    assert len(rows) == 121
    for row in rows:
        assert row["auto_judgment"] in {"supported", "contradicted",
                                        "insufficient_evidence", "not_applicable"}
        assert row["auto_reason"], row["relation_id"]
        assert row["rules_applied"], row["relation_id"]
        for column in FINAL_RELATION_HUMAN_COLUMNS:
            assert row[column] == "", f"{row['relation_id']} 的 {column} 不应预填"


def test_final_review_worksheet_auto_counts_match_the_auto_review_artifact():
    rows = _read_csv(FINAL_RELATION_CSV)
    auto = json.loads((ARTIFACTS / "relation_auto_review.json").read_text(encoding="utf-8"))
    expected = auto["counts"]["by_judgment"]
    actual: dict[str, int] = {}
    for row in rows:
        actual[row["auto_judgment"]] = actual.get(row["auto_judgment"], 0) + 1
    assert actual == expected


# --------------------------------------------------------------------------
# TP / FP / FN 统计规则
# --------------------------------------------------------------------------

def _case(label: str, verdict: str, status: str = "human_verified", dimension: str = "cvss") -> dict:
    return {"dimension": dimension,
            "annotation": {"status": status, "label": label},
            "prediction": {"verdict": verdict}}


def test_scorer_counts_only_human_verified_labels():
    payload = {"cases": [
        _case("positive", "present"),          # TP
        _case("negative", "present"),          # FP
        _case("positive", "missing"),          # FN
        _case("negative", "missing"),          # TN
        _case("positive", "present", status="pending_human_review"),  # 不计
        _case("unknown", "present"),           # 单列
        _case("not_applicable", "missing"),    # 单列
    ]}
    result = score(payload)
    assert result["computable"] is True
    bucket = result["per_dimension"]["cvss"]
    assert (bucket["tp"], bucket["fp"], bucket["fn"], bucket["tn"]) == (1, 1, 1, 1)
    assert bucket["pending"] == 1
    assert bucket["undetermined"] == 2
    assert bucket["precision"] == 0.5
    # 候选集本身就是系统输出，没有"应抽取但未抽取"的金标准清单，
    # 因此 recall / F1 必须为 null，而不是从候选内部推出 0.5。
    assert bucket["recall"] is None
    assert bucket["f1"] is None
    assert result["fn_source"]["available"] is False


def test_scorer_reports_not_computable_without_any_verified_label():
    payload = {"cases": [_case("positive", "present", status="pending_human_review")]}
    result = score(payload)
    assert result["computable"] is False
    assert result["micro"]["precision"] is None
    assert result["micro"]["recall"] is None
    assert "不可计算" in result["note"]


def test_scorer_defaults_missing_prediction_to_present_and_records_it():
    """候选即系统输出：缺少 prediction.verdict 时按 present 计数，并如实记录假设。"""
    payload = {"cases": [{"dimension": "cvss",
                          "annotation": {"status": "human_verified", "label": "positive"}}]}
    result = score(payload)
    assert result["computable"] is True
    assert result["per_dimension"]["cvss"]["tp"] == 1
    assert result["prediction_default"]["used"] == 1
    assert "present" in result["prediction_default"]["assumption"]


def test_recall_and_f1_become_computable_with_an_external_gold_list():
    """只有提供"应抽取关系全集"才可能得到 FN，从而算出 recall 与 F1。"""
    payload = {"cases": [
        {"relation_id": "R1", "dimension": "cvss",
         "annotation": {"status": "human_verified", "label": "positive"}},
        {"relation_id": "R2", "dimension": "cvss",
         "annotation": {"status": "human_verified", "label": "negative"}},
    ]}
    # 金标准用 {ID: 维度} 形式，缺失的 R3 才会归到 cvss 维度上
    result = score(payload, {"expected_relation_ids": {"R1": "cvss", "R3": "cvss"}})
    bucket = result["per_dimension"]["cvss"]
    assert (bucket["tp"], bucket["fp"], bucket["fn"]) == (1, 1, 1)
    assert bucket["precision"] == 0.5
    assert bucket["recall"] == 0.5
    assert bucket["f1"] == 0.5
    assert result["fn_source"]["available"] is True
    assert "R3" in result["fn_source"]["missing_relation_ids"]


def test_micro_and_macro_f1_are_reported_when_computable():
    payload = {"cases": [
        {"relation_id": "R1", "dimension": "cvss",
         "annotation": {"status": "human_verified", "label": "positive"}},
        {"relation_id": "R2", "dimension": "cvss",
         "annotation": {"status": "human_verified", "label": "negative"}},
    ]}
    result = score(payload, {"expected_relation_ids": ["R1"]})
    # 1 TP、1 FP、0 FN → precision 0.5、recall 1.0 → F1 = 2*0.5*1/1.5 = 0.6667
    assert result["micro"]["precision"] == 0.5
    assert result["micro"]["recall"] == 1.0
    assert result["micro"]["f1"] == 0.6667
    assert result["macro"]["f1"] == 0.6667


def test_f1_is_null_rather_than_wrong_when_precision_and_recall_are_both_zero():
    payload = {"cases": [
        {"relation_id": "R1", "dimension": "cvss",
         "annotation": {"status": "human_verified", "label": "negative"}},
    ]}
    result = score(payload, {"expected_relation_ids": []})
    assert result["per_dimension"]["cvss"]["precision"] == 0.0
    assert result["per_dimension"]["cvss"]["f1"] is None


def test_scorer_returns_null_rather_than_zero_or_one_hundred():
    payload = {"cases": []}
    result = score(payload)
    assert result["micro"]["precision"] is None
    assert result["micro"]["recall"] is None
    assert result["computable"] is False


def test_real_candidate_file_is_not_computable_yet():
    payload = json.loads(RELATION_JSON.read_text(encoding="utf-8"))
    result = score(payload)
    assert result["computable"] is False
    assert len(result["per_dimension"]) >= 4
