"""B 任务：NVD CVSS 漏检复核批次（2026-10-06）的回归测试。

重点：

* 修复后 5 条原 cvss 漏检必须真的进了候选集，并被人工核验为 positive；
* 新增标注必须带署名，且只改这 5 条，其余候选保持原样；
* 两种 gold 口径的分数都要与 TP/FP/FN 自洽；
* 10-04 冻结产物 0 改动；
* 候选集按内容（而不是 id）迁移标注。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_b_relation_gold as gold_tool  # noqa: E402
import relabel_b_relation_candidates as relabel  # noqa: E402
import score_b_relation_annotations as scoring  # noqa: E402

BATCH = "20261006"
CANDIDATES = ROOT / "evaluation" / f"b_relation_candidates_{BATCH}.json"
GOLD = ROOT / "evaluation" / f"b_relation_gold_{BATCH}.json"
MISSED = ROOT / "artifacts" / "b_eval" / f"relation_missed_relations_{BATCH}.json"
LABELED = ROOT / "artifacts" / "b_eval" / f"relation_candidates_labeled_{BATCH}.json"
PROPOSALS = ROOT / "artifacts" / "b_eval" / f"relation_new_positive_proposals_{BATCH}.json"
VERIFICATION = ROOT / "artifacts" / "b_eval" / f"relation_cvss_recheck_verification_{BATCH}.json"
BACKFILL = ROOT / "artifacts" / "b_eval" / f"nvd_cvss_backfill_{BATCH}.json"
SCORE_TASK = ROOT / "artifacts" / "b_eval" / f"relation_score_gold_{BATCH}.json"
SCORE_REGEN = ROOT / "artifacts" / "b_eval" / f"relation_score_gold_regenerated_{BATCH}.json"

OLD_GOLD = ROOT / "evaluation" / "b_relation_gold_20261004.json"
OLD_SCORE = ROOT / "artifacts" / "b_eval" / "relation_score_gold_20261004.json"
OLD_MISSED = ROOT / "artifacts" / "b_eval" / "relation_missed_relations_20261004.json"

FORMER_FN_IDS = {f"BREL-GOLD-FN-CV-{i:04d}" for i in range(1, 6)}


def _load(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def test_backfill_merged_cvss_into_the_target_events():
    report = _load(BACKFILL)
    assert report["cvss_events_updated"] >= 1
    assert report["snapshot_errors"] == 0


def test_all_five_former_fn_vectors_are_verified_and_positive():
    labeled = {c["relation_id"]: c for c in _load(LABELED)["cases"]}
    proposals = _load(PROPOSALS)["promotions"]
    verification = _load(VERIFICATION)
    assert verification["verified"] == verification["total"] == 5
    for item in verification["items"]:
        assert item["library_match"] == "FOUND"
        assert item["byte_rereadable"] is True
    promoted_ids = {item["relation_id"] for item in proposals}
    assert len(promoted_ids) == 5
    for rid in promoted_ids:
        annotation = labeled[rid]["annotation"]
        assert annotation["status"] == "human_verified"
        assert annotation["label"] == "positive"
        assert annotation["verified_by"]
        assert annotation["verified_at"]


def test_relabel_is_content_based_not_id_based():
    source = {"cases": [{"relation_id": "OLD-1", "dimension": "cvss",
                         "subject": "CVE-X", "object": "V1",
                         "annotation": {"status": "human_verified", "label": "positive",
                                        "verified_by": "x", "verified_at": "d", "note": None}}]}
    system = {"cases": [{"relation_id": "NEW-9", "dimension": "cvss",
                         "subject": "CVE-X", "object": "v1 "}]}
    result = relabel.relabel(source, system, None)
    case = result["cases"][0]
    assert case["relation_id"] == "NEW-9"
    assert case["annotation"]["label"] == "positive"
    assert result["counts"] == {"total": 1, "carried": 1, "promoted": 0, "pending": 0}


def test_gold_enumerations_deduplicate_repeated_vectors(monkeypatch, tmp_path):
    monkeypatch.setattr(gold_tool, "SCOPE_EVENTS", ("CVE-X",))
    events = {"CVE-X": {"cvss": [{"vector": "V1", "source_id": "a"},
                                 {"vector": "V1", "source_id": "b"}],
                        "affected": [], "paper": {}}}
    relations = gold_tool.enumerate_source_relations(tmp_path, events)
    cvss = [r for r in relations if r["dimension"] == "cvss"]
    assert len(cvss) == 1


def test_new_gold_has_no_missed_relation_and_expected_ids_exist_as_candidates():
    gold = _load(GOLD)
    system_ids = {c["relation_id"] for c in _load(CANDIDATES)["cases"]}
    expected = set(gold["expected_relation_ids"])
    assert gold["completeness"]["missed"] == 0
    assert not (expected & FORMER_FN_IDS), "旧合成 FN id 不应出现在新 gold"
    assert expected <= system_ids, "新 gold 的 expected 必须都是真实候选 id"
    assert _load(MISSED)["counts"]["missed"] == 0


def test_task_command_score_still_counts_the_frozen_synthetic_ids_as_fn():
    score = _load(SCORE_TASK)
    micro = score["micro"]
    assert micro["recall"] == pytest.approx(micro["tp"] / (micro["tp"] + micro["fn"]), abs=1e-4)
    assert micro["precision"] == 1.0 and micro["fp"] == 0
    assert micro["fn"] == 5
    assert set(score["fn_source"]["missing_relation_ids"]) == FORMER_FN_IDS


def test_regenerated_gold_score_reaches_zero_fn_and_is_self_consistent():
    score = _load(SCORE_REGEN)
    micro = score["micro"]
    assert micro["fn"] == 0 and micro["fp"] == 0
    assert micro["recall"] == 1.0 and micro["f1"] == 1.0
    for bucket in score["per_dimension"].values():
        if bucket["precision"] is not None and bucket["recall"] is not None:
            assert bucket["f1"] == pytest.approx(
                2 * bucket["precision"] * bucket["recall"]
                / (bucket["precision"] + bucket["recall"]), abs=1e-4)


def test_old_frozen_20261004_artifacts_are_unchanged():
    old_gold = _load(OLD_GOLD)
    assert set(old_gold["expected_relation_ids"]) & FORMER_FN_IDS == FORMER_FN_IDS
    old_score = _load(OLD_SCORE)["micro"]
    assert (old_score["tp"], old_score["fp"], old_score["fn"]) == (47, 0, 5)
    assert old_score["recall"] == pytest.approx(0.9038, abs=1e-4)
    assert _load(OLD_MISSED)["counts"]["missed"] == 5


def test_scoring_without_gold_still_reports_recall_unavailable():
    score = scoring.score(_load(LABELED), None)
    assert score["fn_source"]["available"] is False
    assert score["micro"]["recall"] is None
