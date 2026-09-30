"""B 任务：人工标注流水线（CSV → JSON → 指标）的测试。

覆盖：空白标签、unknown/not_applicable、非法标签、重复 ID、未知 ID、
缺少署名，以及"标完之后指标确实算得出来"的端到端验证。

所有测试都在 tmp_path 上做，不触碰真实候选文件或工作包。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_b_relation_labels import (  # noqa: E402
    LABEL_COLUMN, LabelImportError, apply_labels,
)
from score_b_relation_annotations import score  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
WORKSHEET = ARTIFACTS / "relation_annotation_worksheet_v2.csv"


def _candidates(n: int = 3) -> dict[str, dict]:
    return {
        f"BREL-T-{i:04d}": {"relation_id": f"BREL-T-{i:04d}", "dimension": "fixed_version",
                            "subject": "E", "relation": "fixed_by", "object": "x@1",
                            "evidence": {}, "annotation": {"status": "pending_human_review",
                                                           "label": None}}
        for i in range(1, n + 1)
    }


def _row(relation_id: str, label: str = "", verifier: str = "reviewer",
         when: str = "2026-09-30T12:00:00Z") -> dict:
    return {"relation_id": relation_id, LABEL_COLUMN: label,
            "人工核验人": verifier, "人工核验时间": when, "人工备注": ""}


# --------------------------------------------------------------------------
# 标签回灌规则
# --------------------------------------------------------------------------

def test_blank_labels_stay_pending_and_are_counted():
    labeled, summary = apply_labels([_row("BREL-T-0001")], _candidates())
    assert labeled["BREL-T-0001"]["annotation"]["status"] == "pending_human_review"
    assert summary["blank"] == 1
    assert summary["human_verified_total"] == 0


@pytest.mark.parametrize("label", ["positive", "negative", "unknown", "not_applicable"])
def test_valid_labels_are_accepted_and_records_the_verifier(label):
    labeled, summary = apply_labels([_row("BREL-T-0001", label)], _candidates())
    annotation = labeled["BREL-T-0001"]["annotation"]
    assert annotation["status"] == "human_verified"
    assert annotation["label"] == label
    assert annotation["verified_by"] == "reviewer"
    assert annotation["verified_at"] == "2026-09-30T12:00:00Z"
    assert summary[label] == 1


@pytest.mark.parametrize("label", ["POSITIVE", "Positive", " negative "])
def test_labels_are_case_and_whitespace_insensitive(label):
    labeled, _summary = apply_labels([_row("BREL-T-0001", label)], _candidates())
    assert labeled["BREL-T-0001"]["annotation"]["label"] in {"positive", "negative"}


def test_illegal_label_aborts_instead_of_silently_dropping():
    with pytest.raises(LabelImportError) as excinfo:
        apply_labels([_row("BREL-T-0001", "true")], _candidates())
    assert "非法" in str(excinfo.value)


def test_duplicate_relation_id_aborts():
    rows = [_row("BREL-T-0001", "positive"), _row("BREL-T-0001", "negative")]
    with pytest.raises(LabelImportError) as excinfo:
        apply_labels(rows, _candidates())
    assert "重复" in str(excinfo.value)


def test_unknown_relation_id_aborts():
    with pytest.raises(LabelImportError) as excinfo:
        apply_labels([_row("BREL-NOT-EXIST", "positive")], _candidates())
    assert "不在候选集" in str(excinfo.value)


def test_missing_signature_is_warned_but_not_fatal():
    labeled, summary = apply_labels([_row("BREL-T-0001", "positive", verifier="", when="")],
                                    _candidates())
    assert labeled["BREL-T-0001"]["annotation"]["label"] == "positive"
    assert summary["missing_signature_count"] == 1
    assert summary["missing_signature"] == ["BREL-T-0001"]


def test_unlabeled_candidates_are_preserved_untouched():
    labeled, _summary = apply_labels([_row("BREL-T-0001", "positive")], _candidates(3))
    assert set(labeled) == {"BREL-T-0001", "BREL-T-0002", "BREL-T-0003"}
    assert labeled["BREL-T-0002"]["annotation"]["status"] == "pending_human_review"


# --------------------------------------------------------------------------
# 端到端：标完之后指标确实算得出来
# --------------------------------------------------------------------------

def test_pipeline_from_labels_to_precision(tmp_path):
    rows = [_row("BREL-T-0001", "positive"), _row("BREL-T-0002", "negative"),
            _row("BREL-T-0003")]
    labeled, summary = apply_labels(rows, _candidates())
    payload = {"cases": list(labeled.values())}
    result = score(payload)
    assert summary["human_verified_total"] == 2
    assert result["computable"] is True
    assert result["per_dimension"]["fixed_version"]["tp"] == 1
    assert result["per_dimension"]["fixed_version"]["fp"] == 1
    assert result["per_dimension"]["fixed_version"]["precision"] == 0.5
    assert result["per_dimension"]["fixed_version"]["recall"] is None


def test_pipeline_can_write_and_reload_a_labeled_file(tmp_path):
    """验证 JSON 往返：写出去再读回来，标签不丢。"""
    labeled, _summary = apply_labels([_row("BREL-T-0001", "positive")], _candidates())
    target = tmp_path / "labeled.json"
    target.write_text(json.dumps({"cases": list(labeled.values())}, ensure_ascii=False),
                      encoding="utf-8")
    reloaded = json.loads(target.read_text(encoding="utf-8"))
    assert reloaded["cases"][0]["annotation"]["label"] == "positive"


# --------------------------------------------------------------------------
# 交付给人工的表格结构
# --------------------------------------------------------------------------

def test_delivered_worksheet_has_priority_evidence_and_consistent_label_columns():
    """交付表的标签列必须自洽：已核验的行带标签+署名，未核验的行保持空白。"""
    if not WORKSHEET.is_file():
        pytest.skip("先运行 tools/build_b_review_workpackets.py")
    with WORKSHEET.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 121
    priorities = [row["priority"] for row in rows]
    assert priorities == sorted(priorities), "应当按优先级排序，便于人工先做高优先项"
    assert sum(1 for row in rows if row["dimension"] == "fixed_version") == 12
    assert sum(1 for row in rows if row["dimension"] == "cvss") == 22
    for row in rows:
        label = (row[LABEL_COLUMN] or "").strip()
        if label:
            assert label in {"positive", "negative", "unknown", "not_applicable"}
            assert row["人工核验人"] and row["人工核验时间"], row["relation_id"]
        else:
            assert row["人工核验人"] == "" and row["人工核验时间"] == "", row["relation_id"]
        assert row["auto_judgment"] in {"supported", "contradicted",
                                        "insufficient_evidence", "not_applicable"}
        assert row["verification_method"], row["relation_id"]
    # 前 12 行应当是最优先的 fixed_version
    assert all(row["dimension"] == "fixed_version" for row in rows[:12])
    # 已核验的 34 条必须与证据工作表一致（口径见 B_EVIDENCE_PACKET_GUIDE.md）
    evidence_path = ARTIFACTS / "evidence_relation_label_sheet.csv"
    if evidence_path.is_file():
        with evidence_path.open(encoding="utf-8-sig", newline="") as handle:
            evidence = {r["relation_id"]: r for r in csv.DictReader(handle)}
        checked = 0
        for row in rows:
            source = evidence.get(row["relation_id"])
            if source and source[LABEL_COLUMN].strip():
                checked += 1
                assert row[LABEL_COLUMN] == source[LABEL_COLUMN]
                assert row["人工备注"] == source["人工备注"]
        assert checked == 34
