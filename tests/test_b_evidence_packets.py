"""B 任务（人工核验准备）：证据工作包的结构与诚实性测试。

两类重点：

1. **产物结构**——关系 12 + 22 条、问答 36 条，标签列与署名列一律留空，
   关系标签表能被既有回灌工具直接读取。
2. **不编造证据**——本地读不到证据时必须标 `missing`，不得写入推测片段；
   候选向量与证据向量不一致时必须留下冲突提示。
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

import build_b_evidence_packets as packets  # noqa: E402
from app import config  # noqa: E402
from apply_b_relation_labels import apply_labels, load_candidates  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
RELATION_MD = ARTIFACTS / "evidence_packet_relations.md"
QA_MD = ARTIFACTS / "evidence_packet_qa.md"
RELATION_SHEET = ARTIFACTS / "evidence_relation_label_sheet.csv"
QA_SHEET = ARTIFACTS / "evidence_qa_label_sheet.csv"
COVERAGE = ARTIFACTS / "evidence_packet_coverage.json"

BLANK_COLUMNS = ("人工核验人", "人工核验时间", "人工备注")
VALID_LABELS = {"positive", "negative", "unknown", "not_applicable"}


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        pytest.skip(f"工作包不存在：{path}（先运行 tools/build_b_evidence_packets.py）")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _headings(path: Path) -> list[str]:
    if not path.is_file():
        pytest.skip(f"工作包不存在：{path}（先运行 tools/build_b_evidence_packets.py）")
    return [block.split("\n")[0] for block in path.read_text(encoding="utf-8").split("### ")[1:]]


# --------------------------------------------------------------------------
# 产物结构
# --------------------------------------------------------------------------

def test_relation_packet_has_twelve_fixed_version_and_twenty_two_cvss():
    heads = _headings(RELATION_MD)
    assert len(heads) == 34
    assert sum(1 for h in heads if "fixed_version" in h) == 12
    assert sum(1 for h in heads if "cvss" in h) == 22


def test_relation_packet_keeps_priority_order_fixed_version_first():
    heads = _headings(RELATION_MD)
    assert all("fixed_version" in h for h in heads[:12])
    assert all("cvss" in h for h in heads[12:])


def test_qa_packet_has_thirty_six_items_and_focus_questions_first():
    heads = _headings(QA_MD)
    assert len(heads) == 36
    focus = {h.split(" · ")[0] for h in heads[:6]}
    assert focus == {"BQA-044", "BQA-047", "BQA-039", "BQA-040", "BQA-046", "BQA-050"}


def test_qa_packet_covers_every_refusal_and_multiturn_question():
    ids = {h.split(" · ")[0] for h in _headings(QA_MD)}
    dataset = json.loads((ROOT / "evaluation" / "b_formal_qa_set.json").read_text(encoding="utf-8"))
    refusal = {c["question_id"] for c in dataset["cases"] if c["should_refuse"]}
    multiturn = {c["question_id"] for c in dataset["cases"] if c.get("history")}
    assert refusal <= ids, f"未覆盖的拒答题：{sorted(refusal - ids)}"
    assert multiturn <= ids, f"未覆盖的多轮题：{sorted(multiturn - ids)}"


def test_relation_label_sheet_labels_are_valid_and_signed():
    """已填标签必须是合法值，且带核验人、核验时间与备注；未填行不得有署名。"""
    relation_rows = _read_csv(RELATION_SHEET)
    assert len(relation_rows) == 34
    for row in relation_rows:
        label = row["待人工填写_最终标签"].strip()
        if not label:
            for column in BLANK_COLUMNS:
                assert row[column] == "", f"{row['relation_id']} 未填标签却有 {column}"
            continue
        assert label in VALID_LABELS, f"{row['relation_id']} 标签非法：{label}"
        assert row["人工核验人"], f"{row['relation_id']} 缺少核验人"
        assert row["人工核验时间"], f"{row['relation_id']} 缺少核验时间"
        assert row["人工备注"], f"{row['relation_id']} 缺少备注（本批统一要求写备注）"
        # 备注必须写明证据来源（MSRC / OSV / NVD 快照之一），便于回溯
        assert row["人工备注"].startswith("依据"), \
            f"{row['relation_id']} 备注未以证据来源开头"
        assert any(source in row["人工备注"] for source in ("MSRC", "OSV", "NVD")), \
            f"{row['relation_id']} 备注未指明证据来源"


def test_qa_label_sheet_is_still_blank():
    """本轮只核验关系；问答标签列必须保持空白，不得被顺带填写。"""
    qa_rows = _read_csv(QA_SHEET)
    assert len(qa_rows) == 36
    for row in qa_rows:
        assert row["待人工填写_最终判定"] == ""
        for column in BLANK_COLUMNS:
            assert row[column] == "", f"{row['question_id']} 的 {column} 不应被填写"


def test_label_sheets_have_unique_ids_matching_their_packet():
    relation_rows = _read_csv(RELATION_SHEET)
    qa_rows = _read_csv(QA_SHEET)
    relation_ids = [r["relation_id"] for r in relation_rows]
    qa_ids = [r["question_id"] for r in qa_rows]
    assert len(set(relation_ids)) == len(relation_ids)
    assert len(set(qa_ids)) == len(qa_ids)
    assert relation_ids == [h.split(" · ")[0] for h in _headings(RELATION_MD)]
    assert qa_ids == [h.split(" · ")[0] for h in _headings(QA_MD)]


def test_relation_label_sheet_is_directly_consumable_by_label_pipeline():
    rows = _read_csv(RELATION_SHEET)
    assert {"relation_id", "待人工填写_最终标签"} <= set(rows[0])
    # 直接走既有回灌工具：ID 不合法会抛 LabelImportError，未填标签的行必须记为 blank
    _labeled, summary = apply_labels(rows, load_candidates())
    assert summary["worksheet_rows"] == 34
    assert summary["illegal_labels"] == {}
    assert summary["blank"] + summary["human_verified_total"] == 34
    assert summary["human_verified_total"] == sum(
        1 for r in rows if r["待人工填写_最终标签"].strip())
    # 已填标签的行都带了核验人与时间，因此不应有"缺署名"告警
    assert summary["missing_signature_count"] == 0


def test_coverage_report_counts_match_the_packets():
    if not COVERAGE.is_file():
        pytest.skip("覆盖率报告不存在（先运行 tools/build_b_evidence_packets.py）")
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    counts = coverage["counts"]
    assert {k: counts[k] for k in (
        "relations_fixed_version", "relations_cvss", "qa_high_priority", "total_items",
    )} == {
        "relations_fixed_version": 12,
        "relations_cvss": 22,
        "qa_high_priority": 36,
        "total_items": 70,
    }
    # 剩余 87 条在同一个覆盖率报告里单列
    assert counts["remaining_total"] == counts["relations_paper_link"] + \
        counts["relations_version_range"]
    by_group = coverage["evidence"]["by_group"]
    # fixed_version 的 OSV 结构化证据应当全部可读
    assert by_group["fixed_version"]["direct"] == 12
    assert coverage["missing_evidence_items"] == []


def test_evidence_locations_point_at_real_snapshot_files_or_declare_missing():
    data_dir = Path(r"D:\ICT\intel-data-b")
    if not (data_dir / "snapshots").is_dir():
        pytest.skip("本机没有独立数据目录快照，跳过落盘核对")
    text = RELATION_MD.read_text(encoding="utf-8")
    locations = [line.split("`")[1] for line in text.splitlines()
                 if line.startswith("- **证据定位**：") and "snapshots/" in line]
    assert locations, "工作包里没有任何快照定位信息"
    for location in locations:
        relative = location.split(" → ")[0].strip()
        assert (data_dir / relative).is_file(), f"证据定位指向不存在的文件：{location}"


def test_cvss_evidence_only_comes_from_local_snapshot_sources():
    """CVSS 证据必须来自本地快照（MSRC / OSV / NVD），不允许引用外部或虚构来源。"""
    if not RELATION_MD.is_file():
        pytest.skip(f"工作包不存在：{RELATION_MD}")
    blocks = [b for b in RELATION_MD.read_text(encoding="utf-8").split("### ")[1:]
              if "cvss" in b.split("\n")[0]]
    assert len(blocks) == 22
    sources = Counter()
    for block in blocks:
        location = next(line for line in block.splitlines()
                        if line.startswith("- **证据定位**："))
        assert "snapshots/" in location, block.split("\n")[0]
        sources[location.split("snapshots/")[1].split("/")[0]] += 1
    assert sources == {"msrc": 9, "osv": 12, "nvd": 1}


def test_human_fill_slots_are_empty_in_markdown():
    for path in (RELATION_MD, QA_MD):
        if not path.is_file():
            pytest.skip(f"工作包不存在：{path}")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("**人工填写**") or line.startswith("**人工填写**："):
                assert "______" in line and "=" in line
                # 不能出现任何预填的标签值
                for label in ("positive", "negative", "supported", "contradicted"):
                    assert label not in line


# --------------------------------------------------------------------------
# 诚实性：读不到证据时标 missing，不编造
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# 安全边界：不产生数据目录副作用、不覆盖人工核验成果
# --------------------------------------------------------------------------

def test_readonly_uri_uses_immutable_when_no_pending_wal(tmp_path):
    """无未合并 WAL 时必须用 immutable，避免 SQLite 创建 -shm / -wal。"""
    db = tmp_path / "intel.sqlite"
    db.write_bytes(b"")
    assert packets._readonly_uri(db) == f"file:{db.as_posix()}?mode=ro&immutable=1"


def test_readonly_uri_falls_back_when_wal_has_content(tmp_path):
    """一旦 WAL 里有未合并内容，必须退回普通只读模式，避免读到过期数据。"""
    db = tmp_path / "intel.sqlite"
    db.write_bytes(b"")
    (tmp_path / "intel.sqlite-wal").write_bytes(b"x" * 32)
    assert packets._readonly_uri(db) == f"file:{db.as_posix()}?mode=ro"


def test_sheet_has_labels_distinguishes_blank_and_labeled(tmp_path):
    sheet = tmp_path / "s.csv"
    sheet.write_text("relation_id,待人工填写_最终标签\na,\nb,\n", encoding="utf-8")
    assert packets._sheet_has_labels(sheet, "待人工填写_最终标签") is False
    sheet.write_text("relation_id,待人工填写_最终标签\na,positive\nb,\n", encoding="utf-8")
    assert packets._sheet_has_labels(sheet, "待人工填写_最终标签") is True
    assert packets._sheet_has_labels(tmp_path / "missing.csv", "x") is False


def test_generator_does_not_clobber_labeled_sheet(tmp_path, monkeypatch):
    """生成器再次运行时，已有人工标签的回收表必须原样保留。"""
    if not RELATION_SHEET.is_file():
        pytest.skip("回收表不存在")
    original = RELATION_SHEET.read_text(encoding="utf-8-sig")
    if "positive" not in original:
        pytest.skip("当前回收表还没有人工标签，无需验证保护逻辑")
    data_dir = Path(r"D:\ICT\intel-data-b")
    if not (data_dir / "intel.sqlite").is_file():
        pytest.skip("本机没有独立数据目录（CI 的 ubuntu runner 上不存在），跳过生成器落盘测试")
    import shutil
    shutil.copy2(RELATION_SHEET, tmp_path / RELATION_SHEET.name)
    shutil.copy2(QA_SHEET, tmp_path / QA_SHEET.name)
    monkeypatch.setattr(sys, "argv", [
        "build_b_evidence_packets.py", "--outdir", str(tmp_path),
        "--source-data-dir", str(data_dir)])
    # main() 会改写全局 config，注册还原以免污染后续测试
    for name in ("DATA_DIR", "SNAPSHOT_DIR", "DB_PATH"):
        monkeypatch.setattr(config, name, getattr(config, name))
    assert packets.main() == 0
    assert (tmp_path / RELATION_SHEET.name).read_text(
        encoding="utf-8-sig") == original, "已标注的回收表被生成器覆盖"
    # 生成器仍应产出正文工作包
    assert (tmp_path / "evidence_packet_relations.md").is_file()
    assert (tmp_path / "evidence_packet_coverage.json").is_file()

@pytest.fixture()
def snapshot_root(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SNAPSHOT_DIR", tmp_path)
    packets._CACHE.clear()
    yield tmp_path
    packets._CACHE.clear()


def _cvss_case(subject: str, vector: str, score):
    return {
        "relation_id": "BREL-CV-TEST",
        "dimension": "cvss",
        "subject": subject,
        "relation": "has_cvss",
        "object": subject,
        "candidate_value": {"version": "3.1", "score": score, "vector": vector},
        "verification_method": "对照来源公告原文。",
    }


def test_cvss_without_local_evidence_is_marked_missing(snapshot_root):
    record = packets.build_cvss(
        _cvss_case("CVE-1999-0001", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", None),
        {}, {})
    assert record["evidence_status"] == "missing"
    assert record["evidence_fragment"] is None
    assert any("无法核对" in q for q in record["questions_for_human"])


def test_cvss_falls_back_to_osv_severity(snapshot_root):
    osv_dir = snapshot_root / "osv"
    osv_dir.mkdir()
    (osv_dir / "deadbeef.json").write_text(json.dumps({
        "id": "PYSEC-2026-9999",
        "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N"}],
        "summary": "probe",
    }), encoding="utf-8")
    record = packets.build_cvss(
        _cvss_case("PYSEC-2026-9999", "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N", None),
        {}, {})
    assert record["evidence_status"] == "direct"
    assert "snapshots/osv/deadbeef.json" in record["evidence_location"]
    assert "CVSS_V3" in record["evidence_fragment"]
    # 候选没有基础分，必须如实提示，而不是补一个分数进去
    assert any("score=null" in c for c in record["conflicts"])


def test_cvss_falls_back_to_nvd_metrics(snapshot_root):
    nvd_dir = snapshot_root / "nvd"
    nvd_dir.mkdir()
    (nvd_dir / "cafe.json").write_text(json.dumps({"vulnerabilities": [{"cve": {
        "id": "CVE-2025-9999",
        "descriptions": [{"lang": "en", "value": "probe description"}],
        "metrics": {"cvssMetricV31": [{
            "source": "nvd@nist.gov", "type": "Primary",
            "cvssData": {"version": "3.1", "baseScore": 7.6,
                         "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:H/A:L"}}]},
    }}]}), encoding="utf-8")
    record = packets.build_cvss(
        _cvss_case("CVE-2025-9999", "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:H/A:L", 7.6),
        {}, {})
    assert record["evidence_status"] == "direct"
    assert "snapshots/nvd/cafe.json" in record["evidence_location"]
    assert record["conflicts"] == []


def test_vector_mismatch_is_reported_as_conflict_not_silently_passed():
    record = {"candidate_value": {"vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"},
              "conflicts": []}
    packets._check_vector_match(record, ["CVSS:3.1/AV:L/AC:H/PR:H/UI:N/S:U/C:H/I:H/A:H"],
                              source="MSRC")
    assert record["conflicts"] and "MSRC" in record["conflicts"][0]
    record["conflicts"].clear()
    packets._check_vector_match(record, ["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"],
                                source="MSRC")
    assert record["conflicts"] == []


def test_fixed_version_without_snapshot_is_marked_missing(snapshot_root):
    case = {
        "relation_id": "BREL-FI-TEST",
        "dimension": "fixed_version",
        "subject": "PYSEC-2026-0000",
        "relation": "fixed_by",
        "object": "pkg@1.2.3",
        "candidate_value": {"package": "pkg", "fixed_version": "1.2.3"},
        "verification_method": "对照来源公告原文。",
    }
    record = packets.build_fixed_version(case, {}, {})
    assert record["evidence_status"] == "missing"
    assert record["evidence_fragment"] is None
    assert any("无法核对" in q for q in record["questions_for_human"])


def test_qa_priority_orders_focus_then_refusal_then_multiturn():
    cases = [
        {"question_id": "BQA-999", "should_refuse": False, "history": []},
        {"question_id": "BQA-044", "should_refuse": True, "history": []},
        {"question_id": "BQA-500", "should_refuse": True, "history": ["上一轮"]},
        {"question_id": "BQA-600", "should_refuse": False, "history": []},
    ]
    ordered = [c["question_id"] for c in sorted(cases, key=packets._qa_priority)]
    assert ordered[0] == "BQA-044"
    assert ordered[1] == "BQA-500"
    assert ordered.index("BQA-600") < ordered.index("BQA-999")


# --------------------------------------------------------------------------
# 第一批人工核验（fixed_version 12 条）结果锁定
# --------------------------------------------------------------------------

LABELED_FI12 = ARTIFACTS / "relation_candidates_labeled_fi12.json"
SCORE_FI12 = ARTIFACTS / "relation_score_fi12.json"


def test_first_verified_batch_records_twelve_fixed_version_labels():
    if not LABELED_FI12.is_file():
        pytest.skip("第一批回灌结果不存在（先运行 tools/apply_b_relation_labels.py）")
    payload = json.loads(LABELED_FI12.read_text(encoding="utf-8"))
    fixed = [c for c in payload["cases"] if c["dimension"] == "fixed_version"]
    assert len(fixed) == 12
    assert all(c["annotation"]["status"] == "human_verified" for c in fixed)
    labels = [c["annotation"]["label"] for c in fixed]
    assert labels.count("positive") == 10
    assert labels.count("unknown") == 2
    assert labels.count("negative") == 0
    # 其余维度不得被顺带标注
    others = {c["annotation"]["status"] for c in payload["cases"]
              if c["dimension"] != "fixed_version"}
    assert others == {"pending_human_review"}


def test_first_verified_batch_scoring_is_reproducible():
    if not SCORE_FI12.is_file():
        pytest.skip("第一批评分结果不存在（先运行 tools/score_b_relation_annotations.py）")
    result = json.loads(SCORE_FI12.read_text(encoding="utf-8"))
    assert result["computable"] is True
    fixed = result["per_dimension"]["fixed_version"]
    assert fixed["total"] == 12 and fixed["pending"] == 0
    assert fixed["undetermined"] == 2
    assert fixed["tp"] == 10 and fixed["fp"] == 0
    assert fixed["precision"] == 1.0
    # FN 无来源时 recall / F1 必须保持 null，不能被"算成"数字
    assert fixed["recall"] is None and fixed["f1"] is None
    assert result["per_dimension"]["cvss"]["pending"] == 22


# --------------------------------------------------------------------------
# 第二批人工核验（CVSS 22 条）结果锁定
# --------------------------------------------------------------------------

LABELED_HUMAN = ARTIFACTS / "relation_candidates_labeled_human.json"
SCORE_HUMAN = ARTIFACTS / "relation_score_human.json"


def test_second_verified_batch_records_cvss_labels():
    if not LABELED_HUMAN.is_file():
        pytest.skip("第二批复核结果不存在（先运行 tools/apply_b_relation_labels.py）")
    payload = json.loads(LABELED_HUMAN.read_text(encoding="utf-8"))
    cvss = [c for c in payload["cases"] if c["dimension"] == "cvss"]
    assert len(cvss) == 22
    assert all(c["annotation"]["status"] == "human_verified" for c in cvss)
    by_id = {c["relation_id"]: c for c in cvss}
    msrc = [f"BREL-CV-{i:04d}" for i in range(1, 10)]
    osv = [f"BREL-CV-{i:04d}" for i in range(10, 22)]
    assert all(by_id[r]["annotation"]["label"] == "positive" for r in msrc)
    # OSV 条目只有向量、没有数值分数：结构不支持字段级判定 → 整体保留 unknown
    assert all(by_id[r]["annotation"]["label"] == "unknown" for r in osv)
    assert all("score=null" in by_id[r]["annotation"]["note"] for r in osv)
    assert by_id["BREL-CV-0022"]["annotation"]["label"] == "positive"
    nvd_note = by_id["BREL-CV-0022"]["annotation"]["note"]
    assert "reefs@jfrog.com" in nvd_note and "Secondary" in nvd_note


def test_second_verified_batch_scoring_and_scope():
    if not SCORE_HUMAN.is_file():
        pytest.skip("第二批评分结果不存在（先运行 tools/score_b_relation_annotations.py）")
    result = json.loads(SCORE_HUMAN.read_text(encoding="utf-8"))
    assert result["computable"] is True
    cvss = result["per_dimension"]["cvss"]
    assert cvss["total"] == 22 and cvss["pending"] == 0
    # 12 条只有向量、没有分数 → 单列 undetermined，不得计入分母
    assert cvss["undetermined"] == 12
    assert cvss["tp"] == 10 and cvss["fp"] == 0
    assert cvss["precision"] == 1.0
    assert cvss["recall"] is None and cvss["f1"] is None
    # fixed_version 不受本批影响
    fixed = result["per_dimension"]["fixed_version"]
    assert (fixed["tp"], fixed["undetermined"], fixed["precision"]) == (10, 2, 1.0)
    # 未核验的维度必须仍是 pending，不得被顺带计入指标
    assert result["per_dimension"]["paper_link"]["pending"] == 37
    assert result["per_dimension"]["version_range"]["pending"] == 50
    assert result["micro"]["precision"] == 1.0
    assert result["micro"]["recall"] is None and result["micro"]["f1"] is None
    assert result["micro"]["evaluable_samples"] == 20


# --------------------------------------------------------------------------
# 剩余 87 条（paper_link / version_range）证据包与工作表同步
# --------------------------------------------------------------------------

REMAINING_MD = ARTIFACTS / "evidence_packet_remaining.md"
REMAINING_SHEET = ARTIFACTS / "evidence_remaining_label_sheet.csv"
V2_SHEET = ARTIFACTS / "relation_annotation_worksheet_v2.csv"
SCORE_V2 = ARTIFACTS / "relation_score_v2.json"


def test_remaining_packet_covers_paper_link_and_version_range():
    heads = _headings(REMAINING_MD)
    assert len(heads) == 87
    assert sum(1 for h in heads if "paper_link" in h) == 37
    assert sum(1 for h in heads if "version_range" in h) == 50


def test_remaining_label_sheet_labels_are_valid_and_signed():
    """剩余 87 条已按口径批量核验：标签合法、带署名与备注，且口径分布固定。"""
    rows = _read_csv(REMAINING_SHEET)
    assert len(rows) == 87
    ids = [r["relation_id"] for r in rows]
    assert len(set(ids)) == 87
    for row in rows:
        label = row["待人工填写_最终标签"].strip()
        assert label in VALID_LABELS, f"{row['relation_id']} 标签非法：{label}"
        assert row["人工核验人"] and row["人工核验时间"] and row["人工备注"]
    counts = Counter((r["dimension"], r["待人工填写_最终标签"]) for r in rows)
    assert counts[("paper_link", "positive")] == 16
    assert counts[("paper_link", "unknown")] == 21
    assert counts[("version_range", "positive")] == 11
    assert counts[("version_range", "unknown")] == 39
    _labeled, summary = apply_labels(rows, load_candidates())
    assert summary["worksheet_rows"] == 87
    assert summary["blank"] == 0
    assert summary["human_verified_total"] == 87
    assert summary["missing_signature_count"] == 0
    assert summary["illegal_labels"] == {}


def test_coverage_reports_remaining_counts():
    if not COVERAGE.is_file():
        pytest.skip("覆盖率报告不存在")
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    assert coverage["counts"]["relations_paper_link"] == 37
    assert coverage["counts"]["relations_version_range"] == 50
    assert coverage["counts"]["remaining_total"] == 87
    remaining = coverage["remaining"]
    assert remaining["paper_link_direct"] == 37
    assert remaining["version_range_direct"] == 50
    assert remaining["with_conflicts"] == []


def test_v2_worksheet_sync_matches_evidence_sheet_for_the_34_rows():
    evidence = {r["relation_id"]: r for r in _read_csv(RELATION_SHEET)}
    remaining = {r["relation_id"]: r for r in _read_csv(REMAINING_SHEET)}
    v2_rows = _read_csv(V2_SHEET)
    assert len(v2_rows) == 121
    columns = ("待人工填写_最终标签", "人工核验人", "人工核验时间", "人工备注")
    from_evidence = from_remaining = 0
    for row in v2_rows:
        source = evidence.get(row["relation_id"]) or remaining.get(row["relation_id"])
        assert source is not None, f"v2 表出现来源表里没有的 ID：{row['relation_id']}"
        assert row["待人工填写_最终标签"].strip(), row["relation_id"]
        for column in columns:
            assert row[column] == source[column], f"{row['relation_id']} 的 {column} 与来源表不一致"
        if row["relation_id"] in evidence:
            from_evidence += 1
        else:
            from_remaining += 1
    assert from_evidence == 34 and from_remaining == 87


# --------------------------------------------------------------------------
# 全量标注与最终评分（121 条全部已核验）
# --------------------------------------------------------------------------

LABELED_ALL = ARTIFACTS / "relation_candidates_labeled_all.json"
SCORE_ALL = ARTIFACTS / "relation_score_all.json"


def test_all_candidates_are_labeled_with_expected_distribution():
    if not LABELED_ALL.is_file():
        pytest.skip("全量回灌结果不存在（先运行 tools/apply_b_relation_labels.py）")
    payload = json.loads(LABELED_ALL.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 121
    assert all(c["annotation"]["status"] == "human_verified" for c in payload["cases"])
    counts = Counter((c["dimension"], c["annotation"]["label"]) for c in payload["cases"])
    assert counts == {
        ("fixed_version", "positive"): 10, ("fixed_version", "unknown"): 2,
        ("cvss", "positive"): 10, ("cvss", "unknown"): 12,
        ("paper_link", "positive"): 16, ("paper_link", "unknown"): 21,
        ("version_range", "positive"): 11, ("version_range", "unknown"): 39,
    }
    # 没有任何 negative / not_applicable：当前证据不支持"明确反驳"
    assert not [c for c in payload["cases"]
                if c["annotation"]["label"] in {"negative", "not_applicable"}]


def test_final_scoring_covers_forty_seven_evaluable_samples():
    if not SCORE_ALL.is_file():
        pytest.skip("全量评分结果不存在（先运行 tools/score_b_relation_annotations.py）")
    result = json.loads(SCORE_ALL.read_text(encoding="utf-8"))
    assert result["computable"] is True
    per_dim = result["per_dimension"]
    assert (per_dim["fixed_version"]["tp"], per_dim["fixed_version"]["undetermined"]) == (10, 2)
    assert (per_dim["cvss"]["tp"], per_dim["cvss"]["undetermined"]) == (10, 12)
    assert (per_dim["paper_link"]["tp"], per_dim["paper_link"]["undetermined"]) == (16, 21)
    assert (per_dim["version_range"]["tp"], per_dim["version_range"]["undetermined"]) == (11, 39)
    assert all(b["pending"] == 0 for b in per_dim.values())
    assert all(b["fp"] == 0 and b["fn"] == 0 for b in per_dim.values())
    assert result["micro"]["tp"] == 47
    assert result["micro"]["precision"] == 1.0
    assert result["micro"]["evaluable_samples"] == 47
    # 无金标准全集时 recall / F1 必须保持 null
    assert result["micro"]["recall"] is None and result["micro"]["f1"] is None
    # 74 条 undetermined 单列，不进入任何分母
    assert sum(b["undetermined"] for b in per_dim.values()) == 74


def test_v2_pipeline_matches_the_evidence_sheet_outputs():
    if not SCORE_V2.is_file():
        pytest.skip("v2 评分结果不存在（先运行 tools/score_b_relation_annotations.py）")
    assert json.loads(SCORE_V2.read_text(encoding="utf-8")) == json.loads(
        SCORE_HUMAN.read_text(encoding="utf-8"))
    v2 = json.loads((ARTIFACTS / "relation_candidates_labeled_v2.json").read_text(encoding="utf-8"))
    human = json.loads(LABELED_HUMAN.read_text(encoding="utf-8"))
    assert ({c["relation_id"]: c["annotation"] for c in v2["cases"]}
            == {c["relation_id"]: c["annotation"] for c in human["cases"]})


def test_range_derivation_helpers():
    # OSV 的 {introduced, fixed} 事件
    assert packets._derive_range_from_ranges(
        [{"events": [{"introduced": "0"}, {"fixed": "0.30.0"}]}]) == "< 0.30.0"
    assert packets._derive_range_from_ranges(
        [{"events": [{"introduced": "0.9.0"}, {"fixed": "0.11.1"}]}]) == ">= 0.9.0, < 0.11.1"
    # MITRE 的 {version, lessThan} 版本声明：下界 0 必须保留
    assert packets._derive_range_from_versions(
        [{"version": "0", "lessThan": "1.21.0"}]) == ">= 0, < 1.21.0"
    assert packets._derive_range_from_versions([]) is None
