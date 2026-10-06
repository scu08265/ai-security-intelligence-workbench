"""B 任务：关系抽取"抽样穷尽"金标准的回归测试。

重点：

* gold 必须真的包含系统没抽到的关系（否则说明没在找漏检）；
* 漏检清单要能自证（可回读的证据 + 为什么应抽取 + 系统为什么漏）；
* 有 gold 时 Recall/F1 必须是数值，且与 TP/FP/FN 自洽；
* 没有 gold 时 Recall/F1 仍为 null（不给自己造分母）；
* 不确定项不进任何分母，也不写进 expected_relation_ids；
* 旧冻结产物不被改动。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import score_b_relation_annotations as scoring  # noqa: E402

GOLD = ROOT / "evaluation" / "b_relation_gold_20261004.json"
MISSED = ROOT / "artifacts" / "b_eval" / "relation_missed_relations_20261004.json"
LABELED = ROOT / "artifacts" / "b_eval" / "relation_candidates_labeled_all.json"
SCOPE_INPUT = ROOT / "artifacts" / "b_eval" / "relation_candidates_labeled_gold_scope_20261004.json"
SYSTEM_OUTPUT = ROOT / "evaluation" / "b_relation_candidates_20261002_full.json"
SCORE_FULL = ROOT / "artifacts" / "b_eval" / "relation_score_gold_20261004.json"
SCORE_SCOPE = ROOT / "artifacts" / "b_eval" / "relation_score_gold_scope_20261004.json"
OLD_SCORE = ROOT / "artifacts" / "b_eval" / "relation_score_all.json"

DIMENSIONS = {"paper_link", "version_range", "fixed_version", "cvss",
              "poc", "asset_assessment"}


def _load(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _system_ids() -> set[str]:
    return {c["relation_id"] for c in _load(SYSTEM_OUTPUT)["cases"]}


def test_gold_declares_sample_scope_and_expected_ids():
    gold = _load(GOLD)
    expected = gold["expected_relation_ids"]
    assert isinstance(expected, dict), "expected_relation_ids 必须是 {id: 维度} 映射，FN 才能归到维度"
    assert expected, "gold 不能为空"
    assert set(expected.values()) <= DIMENSIONS
    scope = gold["scope"]
    assert scope["kind"] == "sample_exhaustive"
    assert len(scope["events"]) >= 5 and len(scope["papers"]) >= 3
    assert scope["dimensions_excluded"]["poc"]      # 明确说明为什么排除 poc
    assert scope["dimensions_excluded"]["asset_assessment"]


def test_gold_contains_at_least_one_relation_the_system_missed():
    """验收：gold 里必须至少有一条系统未抽到的关系，否则等于没在找漏检。"""
    gold = _load(GOLD)
    expected = set(gold["expected_relation_ids"])
    missing = expected - _system_ids()
    assert missing, "expected_relation_ids 里没有任何系统未抽取的关系"
    assert len(missing) >= 1


def test_missed_relations_are_absent_from_system_output_and_self_explanatory():
    payload = _load(MISSED)
    missed = payload["missed_relations"]
    system_ids = _system_ids()
    gold_expected = set(_load(GOLD)["expected_relation_ids"])
    assert missed, "漏检清单不能为空"
    for item in missed:
        assert item["dimension"] in DIMENSIONS
        for field in ("subject", "relation", "object"):
            assert item.get(field), f"{item['gold_relation_id']} 缺 {field}"
        evidence = item["evidence"]
        assert evidence["source_path"] and evidence["type"]
        assert item["why_expected"] and item["why_missed"]
        assert item["gold_relation_id"] in gold_expected
        assert item["gold_relation_id"] not in system_ids


def test_uncertain_items_stay_out_of_expected_ids_and_denominators():
    gold = _load(GOLD)
    expected = gold["expected_relation_ids"]
    uncertain_ids = {item.get("relation_id") for item in gold["uncertain"]
                     if item.get("relation_id")}
    assert uncertain_ids, "本批次应有待定候选被单列"
    assert not (uncertain_ids & set(expected)), "待定候选不得写进 expected_relation_ids"
    # 评分里这些条目应体现为 undetermined，而不是 TP/FP/FN
    score = _load(SCORE_FULL)
    undetermined = sum(b["undetermined"] for b in score["per_dimension"].values())
    assert undetermined >= len(uncertain_ids)


def test_scoring_with_gold_makes_recall_numeric_and_self_consistent():
    score = _load(SCORE_FULL)
    assert score["fn_source"]["available"] is True
    micro = score["micro"]
    tp, fp, fn = micro["tp"], micro["fp"], micro["fn"]
    assert tp > 0 and fp == 0 and fn > 0          # 有命中、无误报、有漏检
    assert micro["precision"] == pytest.approx(tp / (tp + fp), abs=1e-4)
    assert micro["recall"] == pytest.approx(tp / (tp + fn), abs=1e-4)
    expected_f1 = 2 * micro["precision"] * micro["recall"] / (
        micro["precision"] + micro["recall"])
    assert micro["f1"] == pytest.approx(expected_f1, abs=1e-4)
    for bucket in score["per_dimension"].values():
        if bucket["precision"] is not None and bucket["recall"] is not None:
            assert bucket["f1"] is not None


def test_scope_aligned_score_uses_only_sampled_candidates():
    scope_input = _load(SCOPE_INPUT)
    score = _load(SCORE_SCOPE)
    micro = score["micro"]
    assert scope_input["counts"]["cases"] == micro["tp"] + micro["fp"] + \
        sum(b["undetermined"] for b in score["per_dimension"].values())
    assert micro["recall"] == pytest.approx(micro["tp"] / (micro["tp"] + micro["fn"]),
                                            abs=1e-4)
    # 口径一致版的 TP 必须小于全量版（分母范围更小）
    assert micro["tp"] < _load(SCORE_FULL)["micro"]["tp"]


def test_scoring_without_gold_keeps_recall_unavailable():
    payload = _load(LABELED)
    score = scoring.score(payload, None)
    assert score["fn_source"]["available"] is False
    assert score["micro"]["recall"] is None
    assert score["micro"]["f1"] is None
    assert score["micro"]["precision"] is not None


def test_old_frozen_relation_score_is_unchanged():
    old = _load(OLD_SCORE)
    assert old["micro"]["tp"] == 47 and old["micro"]["fp"] == 0
    assert old["micro"]["recall"] is None and old["micro"]["f1"] is None
    assert old["fn_source"]["available"] is False
