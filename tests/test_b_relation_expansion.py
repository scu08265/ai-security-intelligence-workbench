"""B 任务：关系评测扩样 + OSV 解析批次（2026-10-10）的回归测试。

重点：

* 扩样口径落在 gold 的 ``scope`` 里：16 篇论文 / 12 个生态事件 / 37 个 CVE 是
  **盘点**范围，CVE 再按证据覆盖分层，证据不足的不进任何分母；
* expected 只能由"人工核验 positive + 真实漏检"组成，不能靠标候选凑；
* 新增漏检必须能从源头原字节逐字回读，否则算枚举错误而不是漏检；
* 候选集与旧批次逐字节相同 —— 本轮的分数变化全部来自枚举口径，不掺候选变化；
* 10-04 / 10-06 的旧产物字节不变；
* 页面按金标准的 ``scope`` 展示抽样范围，不由批次日推测。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import b_relation_sources as sources  # noqa: E402
import build_b_relation_gold as gold_tool  # noqa: E402
import relabel_b_relation_candidates as relabel  # noqa: E402
import verify_b_relation_expansion as expansion  # noqa: E402

BATCH = "20261010"
FORMER_BATCH = "20261006"

CANDIDATES = ROOT / "evaluation" / f"b_relation_candidates_{BATCH}.json"
GOLD = ROOT / "evaluation" / f"b_relation_gold_{BATCH}.json"
MISSED = ROOT / "artifacts" / "b_eval" / f"relation_missed_relations_{BATCH}.json"
LABELED = ROOT / "artifacts" / "b_eval" / f"relation_candidates_labeled_{BATCH}.json"
PROPOSALS = ROOT / "artifacts" / "b_eval" / f"relation_new_positive_proposals_{BATCH}.json"
VERIFICATION = ROOT / "artifacts" / "b_eval" / f"relation_expansion_verification_{BATCH}.json"
SCORE_ACTIVE = ROOT / "artifacts" / "b_eval" / f"relation_score_gold_{BATCH}.json"
SCORE_CONTRAST = ROOT / "artifacts" / "b_eval" / f"relation_score_gold_frozen{FORMER_BATCH}_{BATCH}.json"

FORMER_CANDIDATES = ROOT / "evaluation" / f"b_relation_candidates_{FORMER_BATCH}.json"
FORMER_GOLD = ROOT / "evaluation" / f"b_relation_gold_{FORMER_BATCH}.json"
FORMER_LABELED = ROOT / "artifacts" / "b_eval" / f"relation_candidates_labeled_{FORMER_BATCH}.json"
FORMER_MISSED_10_04 = ROOT / "artifacts" / "b_eval" / "relation_missed_relations_20261004.json"

# 旧批次产物在本次批次里必须逐字不变（LF 归一化，Windows 检出会把行尾变 CRLF）。
FROZEN_SHA256 = {
    ROOT / "evaluation" / "b_relation_gold_20261004.json":
        "67a6ad58e2153867c1421ce23231c99dbc6ef5eaab496992406093b1df5afac1",
    ROOT / "artifacts" / "b_eval" / "relation_score_gold_20261004.json":
        "fe21d84e87b6de66156c77efd671ec4aa6f52b440be2ae5afcee82c68fce0984",
    ROOT / "artifacts" / "b_eval" / "relation_score_gold_scope_20261004.json":
        "1e1a3bae6060830635654ebbe05b891d1517ccc75c1562c591b68e2e6bae4a8f",
    FORMER_MISSED_10_04:
        "6ae544265e24e40e06e88d73af6b3d357be1225c898e63541d02cb6f665694d5",
    FORMER_CANDIDATES:
        "0faf7bd3ec1f75fd33d1a0ec75ffc3073f6807381d7dc81cb71c0a279b9ad79c",
    FORMER_GOLD:
        "3c88e8ff50649058540fe05062a4d149f67293787951e8b66b93043158b43039",
    ROOT / "artifacts" / "b_eval" / f"relation_missed_relations_{FORMER_BATCH}.json":
        "8895aa0dd734b968112250129ef99de84cf7458b7a16f4de3fd6dda55684b61b",
    FORMER_LABELED:
        "df00c2efd2a0958c9637c166e011e8b22fda453791c7dce136fcde7a3b288fd2",
    ROOT / "artifacts" / "b_eval" / f"relation_new_positive_proposals_{FORMER_BATCH}.json":
        "c9ebb47a9c3ee4bc2d7a5b7ade868f61189af6b35938270c478a1f82058b50d4",
    ROOT / "artifacts" / "b_eval" / f"relation_cvss_recheck_verification_{FORMER_BATCH}.json":
        "67a194b6725a58dfa56fc53dce1bca124b63c420e17fbc2cdd30fef060d4d98d",
    ROOT / "artifacts" / "b_eval" / f"relation_score_gold_{FORMER_BATCH}.json":
        "65a11f166f48a099d37ea0cb212f2c09d050646c9039fd3b6d386e29e0031943",
    ROOT / "artifacts" / "b_eval" / "relation_score_gold_frozen20261004_20261006.json":
        "a55375aa385ca013fad0af2dc0c5d022aefd489c76fdfe711f852e1c92b474f1",
    ROOT / "artifacts" / "b_eval" / f"relation_candidates_labeled_gold_scope_{FORMER_BATCH}.json":
        "c46c1b4761f51faaeb5679f5734b6c00ce6e8a80164830e7dfd5f3d5f0007127",
}

# 候选集在本批次必须与 10-06 逐字节相同（原始字节，两边同为 CRLF）。
CANDIDATE_SHA256 = "415430c46ae9224cd2788e159f8f8fb6effcbcfa62f6a6ae7ec3b1a58978ae53"

COPY_DIR = Path(os.environ.get("B_EXPANSION_COPY_DIR", r"D:\ICT\intel-data-b-cvss-20261006"))


def _load(path: Path) -> dict:
    if not path.is_file():
        pytest.skip(f"文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _copy_dir() -> Path:
    if not (COPY_DIR / "intel.sqlite").is_file():
        pytest.skip(f"副本库不存在：{COPY_DIR}")
    return COPY_DIR


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _mini_corpus(root: Path, *, fixed: str = "2.0.0") -> Path:
    """隔离的最小语料：一个生态事件 + 一份 OSV 快照，只写在临时目录里。

    **不接触任何真实数据目录**：事件表、文档表、快照都在 ``tmp_path`` 下现造。
    """
    (root / "snapshots" / "osv").mkdir(parents=True, exist_ok=True)
    (root / "snapshots" / "osv" / "GHSA-test-0000.json").write_text(json.dumps({
        "id": "GHSA-test-0000",
        "affected": [{
            "package": {"name": "pkg", "ecosystem": "PyPI"},
            "ranges": [{"type": "ECOSYSTEM",
                        "events": [{"introduced": "0"}, {"fixed": fixed}]}],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    connection = sqlite3.connect(root / "intel.sqlite")
    connection.execute("create table events (id text primary key, doc text)")
    connection.execute("create table rag_documents (document_key text primary key)")
    connection.execute("insert into events values (?, ?)", (
        "GHSA-test-0000",
        json.dumps({"id": "GHSA-test-0000", "cvss": [], "affected": [
            {"package": "pkg", "ecosystem": "PyPI", "range": f"< {fixed}",
             "fixed_version": fixed, "source_id": "osv:test0000"}]})))
    connection.commit()
    connection.close()
    return root


def _source_relation(obj: str) -> dict:
    return {
        "dimension": "fixed_version", "subject": "GHSA-test-0000", "relation": "fixed_by",
        "object": obj, "source": "osv_snapshot",
        "source_path": "snapshots/osv/GHSA-test-0000.json",
        "source_locator": "affected[0].ranges[0].events[1]",
        "detail": {"package": "pkg", "fixed_version": obj.partition("@")[2]},
    }


def _replay_corpus(tmp_path: Path) -> Path:
    """把复现 10-06 批次所需的真实数据**复制**进临时目录再跑。

    真实副本以只读方式打开（``mode=ro``），写入的全部是临时副本；测试结束时
    临时目录由 pytest 回收，真实库不会留下任何改动。
    """
    source = _copy_dir()
    target = tmp_path / "replay"
    (target / "snapshots" / "nvd").mkdir(parents=True)
    src = sqlite3.connect(f"file:{source / 'intel.sqlite'}?mode=ro", uri=True)
    dst = sqlite3.connect(target / "intel.sqlite")
    dst.execute("create table events (id text primary key, doc text)")
    dst.execute("create table rag_documents (document_key text primary key)")
    dst.executemany("insert into events values (?, ?)",
                    src.execute("select id, doc from events"))
    dst.executemany("insert into rag_documents values (?)",
                    src.execute("select document_key from rag_documents"))
    dst.commit()
    dst.close()
    src.close()
    for cve in (name for name in gold_tool.SCOPE_EVENTS if name.startswith("CVE-")):
        snapshot = source / "snapshots" / "nvd" / f"{cve}.json"
        if snapshot.is_file():
            shutil.copy2(snapshot, target / "snapshots" / "nvd" / snapshot.name)
    return target


def test_earlier_batches_are_byte_identical():
    for path, expected in FROZEN_SHA256.items():
        assert path.is_file(), f"旧批次产物不应被删除：{path}"
        assert _lf_sha256(path) == expected, f"旧批次产物被改动：{path}"


def test_candidate_set_is_unchanged_so_the_delta_comes_from_the_scope():
    """候选零变化：本轮的分数变化只能来自枚举口径，不掺候选变化。"""
    assert hashlib.sha256(CANDIDATES.read_bytes()).hexdigest() == CANDIDATE_SHA256
    assert CANDIDATES.read_bytes() == FORMER_CANDIDATES.read_bytes()


def test_full_scope_inventory_and_evidence_tiers_are_self_consistent():
    scope = _load(GOLD)["scope"]
    assert scope["mode"] == "full"
    assert scope["inventory"] == {"papers": 16, "ecosystem_events": 12, "cve_events": 37}
    tiers = scope["tiers"]
    # 盘点范围不等于同一个分母：CVE 分层必须自洽
    assert tiers["cve_verifiable"]["count"] == 14
    assert tiers["cve_insufficient_evidence"]["count"] == 23
    assert (tiers["cve_verifiable"]["count"]
            + tiers["cve_insufficient_evidence"]["count"]) == 37
    assert tiers["papers_full"]["count"] == 16
    assert tiers["ecosystem_events_verifiable"]["count"] == 12
    # 分层要有依据，不是按数量硬编
    verifiable = tiers["cve_verifiable"]["items"]
    insufficient = tiers["cve_insufficient_evidence"]["items"]
    assert len({item["event"] for item in verifiable}) == 14
    assert all(item["evidence"] for item in verifiable)
    assert all(item["reason"] for item in insufficient)
    # 源头无版本事实的条目如实单列，且没有被算成"应抽取关系"
    excluded = scope["excluded_not_enumerable"]
    assert excluded["count"] == 37
    assert {item["kind"] for item in excluded["items"]} == {"range_unknown"}
    assert excluded["count"] == len(excluded["items"])


def test_expected_set_is_verified_positives_plus_real_misses():
    gold = _load(GOLD)
    missed = _load(MISSED)["missed_relations"]
    system_ids = {case["relation_id"] for case in _load(CANDIDATES)["cases"]}
    labeled = {case["relation_id"]: (case.get("annotation") or {})
               for case in _load(LABELED)["cases"]}
    expected = set(gold["expected_relation_ids"])
    fn_ids = {item["gold_relation_id"] for item in missed}

    assert len(missed) == gold["completeness"]["missed"] == 25
    assert fn_ids <= expected
    # 真实漏检用合成 id，绝不能与候选 id 混同
    assert fn_ids.isdisjoint(system_ids)
    # 防伪：expected 去掉漏检，必须正好等于"人工核验 positive"的那批候选
    positives = {rid for rid, annotation in labeled.items()
                 if annotation.get("status") == "human_verified"
                 and annotation.get("label") == "positive"}
    assert expected - fn_ids == positives
    # 每条漏检都要有可回读的源头定位和不猜不补的说明
    for item in missed:
        evidence = item.get("evidence") or {}
        assert evidence.get("source_path") and evidence.get("source_locator"), item
        assert item.get("why_expected") and item.get("why_missed"), item
    # 证据不足的 CVE 一条都不许进分子/分母
    insufficient = {item["event"]
                    for item in gold["scope"]["tiers"]["cve_insufficient_evidence"]["items"]}
    touched = {item["subject"] for item in missed}
    touched |= {case["subject"] for case in _load(LABELED)["cases"]
                if case["relation_id"] in expected}
    assert insufficient.isdisjoint(touched)


def test_expansion_verification_only_promotes_source_readback_items():
    report = _load(VERIFICATION)
    assert report["ok"] is True
    assert report["blocked"] == 0
    assert report["missed_unreadable"] == 0
    assert report["promotable"] == 17
    assert report["missed_new"] == report["total"] - report["promotable"] == 25
    for item in report["items"]:
        assert item["checks"]["event_exists"] is True
        assert item["source_verified"] is True, item["relation_id"]
        if item["candidate_found"]:
            assert item["all_checks_passed"] is True
            assert item["checks"]["candidate_object_matches"] is True
        else:
            assert item["checks"]["candidate_found"] is False

    promotions = _load(PROPOSALS)["promotions"]
    assert len(promotions) == report["promotable"] == 17
    # 这 17 条已由签核人逐条确认，清单因此不再要求签名
    assert _load(PROPOSALS)["signature_required"] is False
    for item in promotions:
        assert item["label"] == "positive"
        assert item["verified_by"] == "人工复核-用户确认"
        assert item["verified_at"] == "2026-10-10"
        evidence = item["evidence"]
        assert evidence["source_path"] and evidence["source_locator"]
        assert evidence["enumerated_value"]


def test_verification_tool_refuses_to_self_sign():
    """工具只逐字回读证据：不给 ``--verified-by`` 时一律停在"待签核"。"""
    report = _load(VERIFICATION)

    unsigned = expansion.build_promotions(report, verified_by=None,
                                          verified_at="2026-10-10", note="n")
    assert unsigned["signature_required"] is True
    assert {item["verified_by"] for item in unsigned["promotions"]} == {
        expansion.PLACEHOLDER_VERIFIED_BY}
    # 把占位串显式传回来也不算签核，不能借它把状态"签"成已确认
    placeholder = expansion.build_promotions(
        report, verified_by=expansion.PLACEHOLDER_VERIFIED_BY,
        verified_at="2026-10-10", note="n")
    assert placeholder["signature_required"] is True
    # 只有显式给出的真实署名才把 signature_required 置为 false
    signed = expansion.build_promotions(report, verified_by="人工复核-用户确认",
                                        verified_at="2026-10-10", note="n")
    assert signed["signature_required"] is False
    assert {item["verified_by"] for item in signed["promotions"]} == {"人工复核-用户确认"}


def test_note_suffix_only_touches_the_named_subject():
    """审计补充说明按主体追加，不能糊到别的关系上。"""
    report = _load(VERIFICATION)
    proposals = expansion.build_promotions(
        report, verified_by="人工复核-用户确认", verified_at="2026-10-10",
        note="base", note_suffixes={"CVE-2025-6558": "extra"})
    by_subject = {item["subject"]: item["note"] for item in proposals["promotions"]}
    assert by_subject["CVE-2025-6558"] == "base extra"
    assert {note for subject, note in by_subject.items()
            if subject != "CVE-2025-6558"} == {"base"}
    with pytest.raises(SystemExit):
        expansion.parse_note_suffixes(["没有等号的补充说明"])


def _signed_relation_fixture() -> tuple[dict, dict, dict]:
    """一条"上一批次已带人工签名"的候选，用来跑 promote / withhold 两阶段。"""
    case = {"relation_id": "BREL-CV-0001", "dimension": "cvss",
            "subject": "CVE-9999-00001", "relation": "has_cvss", "object": "CVSS:3.1/x"}
    source = {"cases": [{**case,
                         "annotation": {"status": "human_verified", "label": "positive",
                                        "verified_by": "人工复核-用户确认",
                                        "verified_at": "2026-10-09", "note": "旧签名"},
                         "promotion_evidence": {"source": "old"}}]}
    system = {"cases": [dict(case)]}
    proposals = {"promotions": [{**case, "label": "positive",
                                 "verified_by": "人工复核-用户确认",
                                 "verified_at": "2026-10-10", "note": "新签名",
                                 "evidence": {"source_path": "p", "source_locator": "l"}}]}
    return source, system, proposals


def test_withhold_then_promote_round_trip_clears_and_restores_signature():
    """撤回要把签名 / 标签 / promotion_evidence 一起清掉，签核时再按清单写回。"""
    source, system, proposals = _signed_relation_fixture()

    withheld = relabel.relabel(source, system, None, proposals)
    assert withheld["counts"]["withheld"] == 1
    assert withheld["unmatched_withholdings"] == []
    stored = withheld["cases"][0]
    assert stored["annotation"] == {"status": "pending_human_review", "label": None,
                                    "verified_by": None, "verified_at": None, "note": None}
    assert "promotion_evidence" not in stored

    promoted = relabel.relabel(withheld, system, proposals)
    assert promoted["counts"]["promoted"] == 1
    assert promoted["unmatched_promotions"] == []
    stored = promoted["cases"][0]
    assert stored["annotation"]["status"] == "human_verified"
    assert stored["annotation"]["label"] == "positive"
    assert stored["annotation"]["verified_by"] == "人工复核-用户确认"
    assert stored["annotation"]["verified_at"] == "2026-10-10"
    assert stored["promotion_evidence"] == {"source_path": "p", "source_locator": "l"}


def test_signed_batch_matches_the_promotion_manifest():
    """本批次落地后的真实标注：17 条带签名，其余维持在上一批次或待审核。"""
    promotions = _load(PROPOSALS)["promotions"]
    labeled = {case["relation_id"]: case for case in _load(LABELED)["cases"]}
    system = {(case["dimension"], case["subject"], _norm(case["object"])): case
              for case in _load(CANDIDATES)["cases"]}

    promoted_ids = set()
    for item in promotions:
        key = (item["dimension"], item["subject"], _norm(item["object"]))
        stored = labeled[system[key]["relation_id"]]
        promoted_ids.add(stored["relation_id"])
        annotation = stored["annotation"]
        assert annotation["status"] == "human_verified"
        assert annotation["label"] == "positive"
        assert annotation["verified_by"] == item["verified_by"] == "人工复核-用户确认"
        assert annotation["verified_at"] == item["verified_at"] == "2026-10-10"
        assert stored["promotion_evidence"]["source_path"] == item["evidence"]["source_path"]

    signed = {rid for rid, case in labeled.items()
              if (case.get("annotation") or {}).get("verified_by") == "人工复核-用户确认"}
    pending = {rid for rid, case in labeled.items()
               if (case.get("annotation") or {}).get("status") == "pending_human_review"}
    # 签核只动这 17 条：上一批次沿用的人工签核没被误删，poc 的既有待审项原样保留
    assert promoted_ids <= signed
    assert len(signed) == 127
    assert pending == {"BREL-PO-0001", "BREL-PO-0002", "BREL-PO-0003",
                       "BREL-PO-0004", "BREL-PO-0005"}
    # 工具核验记录与待审核清单都保留，变化的只是"人工已确认"这个结论
    assert _load(VERIFICATION)["promotable"] == len(promotions) == 17


def test_cvss_6558_template_clarification_survives_the_signature():
    """CVE-2025-6558 候选有"分数为 null"的通用模板，审计必须留澄清且不动候选字节。"""
    promotions = _load(PROPOSALS)["promotions"]
    entry = next(item for item in promotions if item["subject"] == "CVE-2025-6558")
    assert "不适用于本条" in entry["note"] and "baseScore=8.8" in entry["note"]
    stored = {case["relation_id"]: case for case in _load(LABELED)["cases"]}["BREL-CV-0028"]
    assert stored["annotation"]["note"] == entry["note"]
    # 候选本身（含那条通用模板 uncertainty）一个字节都没动
    candidate = next(case for case in _load(CANDIDATES)["cases"]
                     if case["relation_id"] == "BREL-CV-0028")
    assert candidate["candidate_value"]["score"] == 8.8
    assert "分数为 null" in candidate["uncertainty"]


def test_new_score_is_self_consistent_and_the_former_gold_is_the_contrast():
    active, contrast = _load(SCORE_ACTIVE), _load(SCORE_CONTRAST)
    micro = active["micro"]
    # 候选关系都是系统自己抽的，precision=1.0 是构造口径造成的上限；
    # 真正有区分度的是 recall / FN —— 它由 25 条"源头写着、候选没有"的真实漏检构成。
    assert micro["precision"] == 1.0
    assert micro["fp"] == 0
    # 17 条已签核的关系从此进 TP；FN 仍然只有那 25 条真实漏检
    assert (micro["tp"], micro["fn"]) == (69, 25)
    assert micro["recall"] == pytest.approx(micro["tp"] / (micro["tp"] + micro["fn"]), abs=1e-4)
    assert micro["f1"] == pytest.approx(
        2 * micro["precision"] * micro["recall"] / (micro["precision"] + micro["recall"]), abs=1e-4)
    assert set(active["fn_source"]["missing_relation_ids"]) == {
        item["gold_relation_id"] for item in _load(MISSED)["missed_relations"]}
    for bucket in active["per_dimension"].values():
        if bucket["precision"] is not None and bucket["recall"] is not None:
            assert bucket["f1"] == pytest.approx(
                2 * bucket["precision"] * bucket["recall"]
                / (bucket["precision"] + bucket["recall"]), abs=1e-4)

    # 两份评分来自同一批标注，只差 gold：新版口径 vs 上一批冻结口径
    assert active["input_source"] == contrast["input_source"] == (
        f"artifacts/b_eval/relation_candidates_labeled_{BATCH}.json")
    assert active["gold_source"] == f"evaluation/b_relation_gold_{BATCH}.json"
    assert contrast["gold_source"] == f"evaluation/b_relation_gold_{FORMER_BATCH}.json"
    assert active["micro"]["tp"] == contrast["micro"]["tp"] == 69
    assert (active["micro"]["fn"], contrast["micro"]["fn"]) == (25, 0)
    assert contrast["micro"]["recall"] == 1.0
    # 四维口径里已无 pending：17 条签核落地，剩下的 5 条 poc 待审项不在四维口径
    assert active["per_dimension"]["cvss"]["pending"] == 0
    assert active["per_dimension"]["version_range"]["pending"] == 0
    assert active["per_dimension"]["fixed_version"]["pending"] == 0
    assert active["per_dimension"]["poc"]["pending"] == 5
    assert active["micro"]["evaluable_samples"] == 94
    # frozen 对照的 100% 只代表 10-06 抽样 gold 的 10 条预期，不是全语料召回率
    assert contrast["micro"]["evaluable_samples"] == 69
    assert contrast["fn_source"]["expected_relation_ids"] == 10


def test_legacy_scope_still_reproduces_the_former_expected_set(tmp_path):
    db_dir = _replay_corpus(tmp_path)
    result = gold_tool.build(db_dir, FORMER_CANDIDATES, FORMER_LABELED,
                             FORMER_MISSED_10_04, gold_tool.SCOPE_MODE_LEGACY)
    gold = result["gold"]
    assert gold["expected_relation_ids"] == _load(FORMER_GOLD)["expected_relation_ids"]
    assert gold["completeness"]["missed"] == 0
    assert set(gold["resolved_former_ids"]) == {f"BREL-GOLD-FN-CV-{i:04d}" for i in range(1, 6)}
    # 10-10 起 unknown 区间不再被当成"应抽取关系"，改记为不可枚举
    excluded = gold["scope"]["excluded_not_enumerable"]["items"]
    assert "CVE-2026-64849" in {item["subject"] for item in excluded}
    assert all(item["kind"] == "range_unknown" for item in excluded)


def test_verifier_refuses_a_relation_the_source_does_not_say(monkeypatch, tmp_path):
    """反例：把版本号改成源头没有的值，核验必须失败、且不得产出升级清单。"""
    db_dir = _mini_corpus(tmp_path / "corpus")
    candidates = _write_json(tmp_path / "candidates.json", {"cases": [
        {"relation_id": "BREL-FI-9001", "dimension": "fixed_version",
         "subject": "GHSA-test-0000", "object": "pkg@9.9.9",
         "prediction": {"verdict": "present"}}]})
    labeled = _write_json(tmp_path / "labeled.json", {"cases": [
        {"relation_id": "BREL-FI-9001",
         "annotation": {"status": "human_verified", "label": "unknown"}}]})
    fabricated = [_source_relation("pkg@9.9.9")]
    monkeypatch.setattr(gold_tool, "enumerate_source_relations",
                        lambda db_dir, events, scope=None, **kwargs: fabricated)
    report = expansion.verify(db_dir, candidates, labeled)
    assert report["ok"] is False
    assert report["blocked"] == 1
    item = report["items"][0]
    assert item["candidate_found"] is True
    assert item["source_verified"] is False
    assert item["checks"]["source_value_matches"] is False
    assert item["checks"]["source_byte_rereadable"] is False
    promotions = expansion.build_promotions(report, verified_by="x", verified_at="d", note="n")
    assert promotions["promotions"] == []


def test_verifier_accepts_a_relation_the_source_states(monkeypatch, tmp_path):
    """正例：源头逐字写着、候选对象一致、标签不冲突时才允许升级。"""
    db_dir = _mini_corpus(tmp_path / "corpus")
    candidates = _write_json(tmp_path / "candidates.json", {"cases": [
        {"relation_id": "BREL-FI-9001", "dimension": "fixed_version",
         "subject": "GHSA-test-0000", "object": "pkg@2.0.0",
         "prediction": {"verdict": "present"},
         "evidence": {"source_id": "osv:test0000"}}]})
    labeled = _write_json(tmp_path / "labeled.json", {"cases": [
        {"relation_id": "BREL-FI-9001",
         "annotation": {"status": "human_verified", "label": "unknown"}}]})
    monkeypatch.setattr(gold_tool, "enumerate_source_relations",
                        lambda db_dir, events, scope=None, **kwargs: [_source_relation("pkg@2.0.0")])
    report = expansion.verify(db_dir, candidates, labeled)
    assert report["ok"] is True
    assert report["promotable"] == 1 and report["missed_new"] == 0
    item = report["items"][0]
    assert item["checks"]["source_locator_resolves"] is True
    assert item["checks"]["source_value_matches"] is True
    assert item["checks"]["source_byte_rereadable"] is True
    promotions = expansion.build_promotions(report, verified_by="x", verified_at="d", note="n")
    assert [p["object"] for p in promotions["promotions"]] == ["pkg@2.0.0"]


def test_verifier_does_not_promote_when_the_annotation_contradicts(monkeypatch, tmp_path):
    """已经人工判 negative 的关系不许被覆盖。"""
    db_dir = _mini_corpus(tmp_path / "corpus")
    candidates = _write_json(tmp_path / "candidates.json", {"cases": [
        {"relation_id": "BREL-FI-9001", "dimension": "fixed_version",
         "subject": "GHSA-test-0000", "object": "pkg@2.0.0"}]})
    labeled = _write_json(tmp_path / "labeled.json", {"cases": [
        {"relation_id": "BREL-FI-9001",
         "annotation": {"status": "human_verified", "label": "negative"}}]})
    monkeypatch.setattr(gold_tool, "enumerate_source_relations",
                        lambda db_dir, events, scope=None, **kwargs: [_source_relation("pkg@2.0.0")])
    report = expansion.verify(db_dir, candidates, labeled)
    assert report["ok"] is False
    assert report["blocked"] == 1
    assert report["items"][0]["checks"]["annotation_not_contradictory"] is False
    promotions = expansion.build_promotions(report, verified_by="x", verified_at="d", note="n")
    assert promotions["promotions"] == []


def test_osv_batch_response_without_body_is_reported_as_uncovered():
    """批量响应只有 id/modified：必须如实记为缺口，不能伪装成已覆盖。"""
    gold = _load(GOLD)
    osv = gold["scope"]["snapshot_coverage"]["osv"]
    assert osv["batch_advisory_ids"] > osv["detail_records"]
    assert osv["batch_records_with_body"] == 0
    assert gold["completeness"]["source_of_truth"]
    assert any("OSV 批量查询响应" in note
               for note in gold["completeness"]["sources_not_covered"])


def test_page_scope_projection_comes_from_the_scored_gold():
    from app import b_evaluation

    scope = b_evaluation._relation_scope(_load(SCORE_ACTIVE))
    assert scope["mode"] == "full"
    assert scope["inventory"] == {"papers": 16, "ecosystem_events": 12, "cve_events": 37}
    assert scope["tiers"]["cve_verifiable"]["count"] == 14
    assert scope["tiers"]["cve_insufficient_evidence"]["count"] == 23
    assert scope["excluded_not_enumerable"]["count"] == 37
    # 没有 gold_source 就不给范围，绝不按批次日猜
    assert b_evaluation._relation_scope({"gold_source": "evaluation/missing.json"}) == {
        "available": False, "gold_source": "evaluation/missing.json"}
    assert b_evaluation._relation_scope({}) == {}
