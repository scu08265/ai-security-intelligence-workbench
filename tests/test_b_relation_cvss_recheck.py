"""B 任务：NVD CVSS 漏检复核批次（2026-10-06）的回归测试。

重点：

* 修复后 5 条原 cvss 漏检必须真的进了候选集，并被人工核验为 positive；
* 旧 5 个合成 gold id 与新 5 个候选 id 在主体 / 关系类型 / 对象 / 证据上一一对应；
* gold 的 expected 只能由"源头枚举 + 人工核验过的 positive"组成，不能靠标候选凑；
* 页面 active 用 10-06 重生成 gold 的评分（FN=0），冻结 gold 的评分留作对照（FN=5）；
* 10-04 的 gold 与旧评分产物字节不变；
* 候选集按内容（而不是 id）迁移标注。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_b_relation_gold as gold_tool  # noqa: E402
import relabel_b_relation_candidates as relabel  # noqa: E402
import score_b_relation_annotations as scoring  # noqa: E402
import verify_b_relation_cvss_recheck as recheck  # noqa: E402

BATCH = "20261006"
CANDIDATES = ROOT / "evaluation" / f"b_relation_candidates_{BATCH}.json"
GOLD = ROOT / "evaluation" / f"b_relation_gold_{BATCH}.json"
MISSED = ROOT / "artifacts" / "b_eval" / f"relation_missed_relations_{BATCH}.json"
LABELED = ROOT / "artifacts" / "b_eval" / f"relation_candidates_labeled_{BATCH}.json"
PROPOSALS = ROOT / "artifacts" / "b_eval" / f"relation_new_positive_proposals_{BATCH}.json"
VERIFICATION = ROOT / "artifacts" / "b_eval" / f"relation_cvss_recheck_verification_{BATCH}.json"
BACKFILL = ROOT / "artifacts" / "b_eval" / f"nvd_cvss_backfill_{BATCH}.json"

# 页面 active 取的是"日期最大"的那份；冻结 gold 的评分改名成带 frozen 前缀，避免抢 active。
SCORE_ACTIVE = ROOT / "artifacts" / "b_eval" / f"relation_score_gold_{BATCH}.json"
SCORE_FROZEN = ROOT / "artifacts" / "b_eval" / "relation_score_gold_frozen20261004_20261006.json"
SCORE_FROZEN_OLD = ROOT / "artifacts" / "b_eval" / "relation_score_gold_20261004.json"

FORMER_GOLD = ROOT / "evaluation" / "b_relation_gold_20261004.json"
FORMER_MISSED = ROOT / "artifacts" / "b_eval" / "relation_missed_relations_20261004.json"
FORMER_SCORE_SCOPE = ROOT / "artifacts" / "b_eval" / "relation_score_gold_scope_20261004.json"

FORMER_FN_IDS = {f"BREL-GOLD-FN-CV-{i:04d}" for i in range(1, 6)}

# 10-04 冻结产物：LF 归一化后的 SHA256（与 b3e09b3 的 git blob 一致）。
# 用归一化哈希是因为 Windows 检出会把行尾变成 CRLF，原始字节不可跨机器比较。
FROZEN_SHA256 = {
    FORMER_GOLD: "67a6ad58e2153867c1421ce23231c99dbc6ef5eaab496992406093b1df5afac1",
    SCORE_FROZEN_OLD: "fe21d84e87b6de66156c77efd671ec4aa6f52b440be2ae5afcee82c68fce0984",
    FORMER_SCORE_SCOPE: "1e1a3bae6060830635654ebbe05b891d1517ccc75c1562c591b68e2e6bae4a8f",
    FORMER_MISSED: "6ae544265e24e40e06e88d73af6b3d357be1225c898e63541d02cb6f665694d5",
}

COPY_DIR = Path(os.environ.get("B_CVSS_COPY_DIR", r"D:\ICT\intel-data-b-cvss-20261006"))


def _load(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _copy_paths() -> tuple[Path, Path]:
    db, snapshots = COPY_DIR / "intel.sqlite", COPY_DIR / "snapshots" / "nvd"
    if not db.is_file() or not snapshots.is_dir():
        pytest.skip(f"副本库不存在：{COPY_DIR}")
    return db, snapshots


def test_backfill_merged_cvss_into_the_target_events():
    report = _load(BACKFILL)
    assert report["cvss_events_updated"] >= 1
    assert report["snapshot_errors"] == 0


def test_all_five_former_fn_vectors_are_verified_and_positive():
    labeled = {c["relation_id"]: c for c in _load(LABELED)["cases"]}
    proposals = _load(PROPOSALS)["promotions"]
    verification = _load(VERIFICATION)

    assert verification["ok"] is True
    assert verification["verified"] == verification["total"] == 5
    for item in verification["items"]:
        assert item["library_match"] == "FOUND"
        assert item["byte_rereadable"] is True
        assert item["all_checks_passed"] is True

    promoted_ids = {item["relation_id"] for item in proposals}
    assert len(promoted_ids) == 5
    for rid in promoted_ids:
        annotation = labeled[rid]["annotation"]
        assert annotation["status"] == "human_verified"
        assert annotation["label"] == "positive"
        assert annotation["verified_by"]
        assert annotation["verified_at"]


def test_former_ids_and_new_candidates_correspond_one_to_one():
    """旧 5 个 gold id 与新 5 个候选 id 必须在主体 / 维度 / 对象上逐条对应。"""
    former = _load(FORMER_MISSED)["missed_relations"]
    system_cases = _load(CANDIDATES)["cases"]
    labeled = {c["relation_id"]: c for c in _load(LABELED)["cases"]}
    gold = _load(GOLD)["resolved_former_ids"]
    verification = _load(VERIFICATION)["resolved_former_ids"]

    def key_of(record: dict) -> tuple[str, str, str]:
        return (" ".join(str(record["dimension"]).split()).casefold(),
                " ".join(str(record["subject"]).split()).casefold(),
                " ".join(str(record["object"]).split()).casefold())

    index: dict[tuple[str, str, str], list[dict]] = {}
    for case in system_cases:
        index.setdefault(key_of(case), []).append(case)

    assert {entry["gold_relation_id"] for entry in former} == FORMER_FN_IDS
    assert set(gold) == FORMER_FN_IDS
    assert {old_id: item["new_relation_id"] for old_id, item in gold.items()} == verification, (
        "gold 的映射与核验清单必须一致")

    for entry in former:
        matched = index.get(key_of(entry)) or []
        assert len(matched) == 1, f"{entry['gold_relation_id']} 必须唯一对应一条新候选"
        candidate = matched[0]
        assert entry["relation"] == "has_cvss"
        mapping = gold[entry["gold_relation_id"]]
        assert mapping["new_relation_id"] == candidate["relation_id"]
        assert mapping["subject"] == entry["subject"]
        assert mapping["object"] == entry["object"]
        assert mapping["dimension"] == entry["dimension"]
        assert mapping["system_evidence_source_id"] == candidate["evidence"]["source_id"]
        assert mapping["human_label"] == "positive"
        assert labeled[candidate["relation_id"]]["annotation"]["verified_by"] == mapping["verified_by"]


def test_correspondence_check_rejects_a_tampered_vector(tmp_path):
    """防伪：把候选向量改一个字段，核验必须失败（证明检查不是摆设）。"""
    db, snapshots = _copy_paths()
    candidates = _load(CANDIDATES)
    for case in candidates["cases"]:
        if case["relation_id"] == "BREL-CV-0021":
            case["object"] = case["object"].replace("/AV:N/", "/AV:L/")
    tampered = tmp_path / "candidates_tampered.json"
    tampered.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")

    report = recheck.verify(db, snapshots, tampered, LABELED, FORMER_MISSED)
    assert report["ok"] is False
    assert report["verified"] == 4
    failed = [item["gold_relation_id"] for item in report["items"]
              if not item["all_checks_passed"]]
    assert failed == ["BREL-GOLD-FN-CV-0001"]


def test_verification_tool_reproduces_the_committed_artifact(tmp_path):
    db, snapshots = _copy_paths()
    out = tmp_path / "verification.json"
    report = recheck.verify(db, snapshots)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    assert report["ok"] is True
    assert report["resolved_former_ids"] == _load(VERIFICATION)["resolved_former_ids"]
    assert json.loads(out.read_text(encoding="utf-8"))["items"] == _load(VERIFICATION)["items"]


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
    assert result["counts"] == {"total": 1, "carried": 1, "promoted": 0,
                                "withheld": 0, "pending": 0}


def test_gold_enumerations_deduplicate_repeated_vectors(monkeypatch, tmp_path):
    monkeypatch.setattr(gold_tool, "SCOPE_EVENTS", ("CVE-X",))
    events = {"CVE-X": {"cvss": [{"vector": "V1", "source_id": "a"},
                                 {"vector": "V1", "source_id": "b"}],
                        "affected": [], "paper": {}}}
    relations = gold_tool.enumerate_source_relations(tmp_path, events)
    cvss = [r for r in relations if r["dimension"] == "cvss"]
    assert len(cvss) == 1


def test_new_gold_has_no_missed_relation_and_only_verified_positives():
    gold = _load(GOLD)
    system_ids = {c["relation_id"] for c in _load(CANDIDATES)["cases"]}
    labeled = {c["relation_id"]: (c.get("annotation") or {})
               for c in _load(LABELED)["cases"]}
    expected = set(gold["expected_relation_ids"])

    assert gold["completeness"]["missed"] == 0
    assert not (expected & FORMER_FN_IDS), "旧合成 FN id 不应出现在新 gold"
    assert expected <= system_ids, "新 gold 的 expected 必须都是真实候选 id"
    assert _load(MISSED)["counts"]["missed"] == 0
    # 防伪：expected 只能由"人工核验为 positive"的候选组成
    for relation_id in expected:
        annotation = labeled.get(relation_id) or {}
        assert annotation.get("status") == "human_verified", relation_id
        assert annotation.get("label") == "positive", relation_id
    # 防伪：上一批 5 条漏检被显式解析，而不是被删掉
    assert gold["completeness"]["former_missed_resolved"] == 5
    assert set(gold["resolved_former_ids"]) == FORMER_FN_IDS
    assert {m["new_relation_id"] for m in gold["resolved_former_ids"].values()} <= expected


def test_active_score_is_the_rerun_gold_and_reaches_zero_fn():
    score = _load(SCORE_ACTIVE)
    micro = score["micro"]
    assert score["gold_source"] == f"evaluation/b_relation_gold_{BATCH}.json"
    assert micro["fn"] == 0 and micro["fp"] == 0
    assert micro["recall"] == 1.0 and micro["f1"] == 1.0
    assert score["fn_source"]["missing_relation_ids"] == []
    assert micro["recall"] == pytest.approx(
        micro["tp"] / (micro["tp"] + micro["fn"]), abs=1e-4)
    for bucket in score["per_dimension"].values():
        if bucket["precision"] is not None and bucket["recall"] is not None:
            assert bucket["f1"] == pytest.approx(
                2 * bucket["precision"] * bucket["recall"]
                / (bucket["precision"] + bucket["recall"]), abs=1e-4)


def test_frozen_gold_score_is_the_task_command_baseline():
    score = _load(SCORE_FROZEN)
    micro = score["micro"]
    assert score["gold_source"] == "evaluation/b_relation_gold_20261004.json"
    assert micro["recall"] == pytest.approx(micro["tp"] / (micro["tp"] + micro["fn"]), abs=1e-4)
    assert micro["precision"] == 1.0 and micro["fp"] == 0
    assert micro["fn"] == 5
    assert (micro["tp"], micro["fn"]) == (52, 5)
    assert set(score["fn_source"]["missing_relation_ids"]) == FORMER_FN_IDS


def test_two_score_files_differ_only_by_gold_scope():
    """两份评分必须来自同一批标注，只差 gold：一个 0 漏检、一个 5 条旧 id。"""
    active, frozen = _load(SCORE_ACTIVE), _load(SCORE_FROZEN)
    assert active["input_source"] == frozen["input_source"] == (
        f"artifacts/b_eval/relation_candidates_labeled_{BATCH}.json")
    assert active["gold_source"] != frozen["gold_source"]
    assert (active["micro"]["tp"], frozen["micro"]["tp"]) == (52, 52)
    assert (active["micro"]["fn"], frozen["micro"]["fn"]) == (0, 5)


def test_frozen_20261004_artifacts_are_byte_identical():
    for path, expected in FROZEN_SHA256.items():
        assert path.is_file(), f"10-04 冻结产物不应被删除：{path}"
        assert _lf_sha256(path) == expected, f"10-04 冻结产物被改动：{path}"
    old_gold = _load(FORMER_GOLD)
    assert set(old_gold["expected_relation_ids"]) & FORMER_FN_IDS == FORMER_FN_IDS
    old_score = _load(SCORE_FROZEN_OLD)["micro"]
    assert (old_score["tp"], old_score["fp"], old_score["fn"]) == (47, 0, 5)
    assert old_score["recall"] == pytest.approx(0.9038, abs=1e-4)
    assert _load(FORMER_MISSED)["counts"]["missed"] == 5


def test_scoring_without_gold_still_reports_recall_unavailable():
    score = scoring.score(_load(LABELED), None)
    assert score["fn_source"]["available"] is False
    assert score["micro"]["recall"] is None
