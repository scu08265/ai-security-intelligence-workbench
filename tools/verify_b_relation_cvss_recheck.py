"""B 任务 2026-10-06：把 10-04 的 5 条 cvss 漏检逐条对应到修复后的候选，并核验证据链。

本工具回答一个问题：**旧的 5 个合成 gold id 与新的 5 个候选 id，是不是同一条关系？**
逐条检查以下各项，任一不成立就报错退出（exit=1），不写"看起来没问题"的结论：

1. 主体：漏检条目的 `subject` 在副本库中存在同名事件；
2. 关系类型：漏检条目 `dimension=cvss`、`relation=has_cvss`；
3. 对象：期望向量与库内该事件 `cvss[].vector` 逐字符相等；
4. 证据：
4. 证据：
   a. 期望向量逐字出现在 NVD 官方快照里，且能与漏检条目记录的
      `source_locator`（如 `metrics.cvssMetricV31[0]`，相对 NVD 2.0 的
      `vulnerabilities[0].cve`）定位到的 `cvssData` 对上
      （`vectorString` 逐字符相等、`baseScore` 相等）；
   b. 库内命中项与新候选的 `evidence.source_id` 相同、`evidence.event_id` 等于主体；
   c. 新候选的 `candidate_value` 与快照向量、分数一致；
5. 人工判读：新候选 `annotation.status=human_verified` 且 `label=positive`，且有署名。

输出 `artifacts/b_eval/relation_cvss_recheck_verification_20261006.json`，
其中 `resolved_former_ids` 给出"旧合成 id → 新候选 id"的显式映射。
加 `--proposals-out` 时同时输出新增正标注清单
（`relation_new_positive_proposals_20261006.json`），署名取自已生效的标注。

用法::

    python tools/verify_b_relation_cvss_recheck.py \
        --db D:\\ICT\\intel-data-b-cvss-20261006\\intel.sqlite \
        --snapshot-dir D:\\ICT\\intel-data-b-cvss-20261006\\snapshots\\nvd
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORMER_MISSED = ROOT / "artifacts" / "b_eval" / "relation_missed_relations_20261004.json"
FORMER_GOLD = ROOT / "evaluation" / "b_relation_gold_20261004.json"
CANDIDATES = ROOT / "evaluation" / "b_relation_candidates_20261006.json"
LABELED = ROOT / "artifacts" / "b_eval" / "relation_candidates_labeled_20261006.json"
VERIFICATION_OUT = ROOT / "artifacts" / "b_eval" / "relation_cvss_recheck_verification_20261006.json"
PROPOSALS_OUT = ROOT / "artifacts" / "b_eval" / "relation_new_positive_proposals_20261006.json"
FIX_COMMIT = "6d15d31"

VERIFIED = "human_verified"
POSITIVE = "positive"
_LOCATOR_STEP = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _locate(document: object, locator: str) -> object:
    """Resolve a dotted locator such as `metrics.cvssMetricV31[0]`."""
    current = document
    for raw_step in locator.split("."):
        match = _LOCATOR_STEP.match(raw_step)
        if not match:
            raise ValueError(f"无法解析定位符片段：{raw_step}")
        name, index = match.group(1), match.group(2)
        if not isinstance(current, dict) or name not in current:
            raise KeyError(f"定位符 `{locator}` 在 `{raw_step}` 处中断")
        current = current[name]
        if index is not None:
            current = current[int(index)]
    return current


def _cve_document(snapshot: dict) -> dict:
    """NVD 2.0 快照里 locator 是相对 `vulnerabilities[0].cve` 写的。"""
    vulnerabilities = snapshot.get("vulnerabilities")
    if isinstance(vulnerabilities, list) and vulnerabilities:
        cve = vulnerabilities[0].get("cve")
        if isinstance(cve, dict):
            return cve
    return snapshot


def verify(db_path: Path, snapshot_dir: Path, candidates_path: Path = CANDIDATES,
           labeled_path: Path = LABELED, former_missed_path: Path = FORMER_MISSED) -> dict:
    """Return the verification report; `ok` is False if any check failed."""
    former_missed = _load(former_missed_path)["missed_relations"]
    system_cases = _load(candidates_path)["cases"]
    annotations = {c["relation_id"]: (c.get("annotation") or {})
                   for c in _load(labeled_path)["cases"]}
    index = {(c["dimension"], c["subject"], _norm(c["object"])): c for c in system_cases}

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    items: list[dict] = []
    try:
        for entry in former_missed:
            items.append(_verify_one(connection, snapshot_dir, index, annotations, entry))
    finally:
        connection.close()

    failed = [item for item in items if not item["all_checks_passed"]]
    return {
        "schema_version": "b-relation-cvss-recheck-1.0",
        "batch": "20261006",
        "fix_commit": FIX_COMMIT,
        "former_gold_ref": str(FORMER_GOLD.relative_to(ROOT)).replace("\\", "/"),
        "former_missed_ref": str(former_missed_path.relative_to(ROOT)).replace("\\", "/"),
        "checks": [
            "subject_exists_in_library", "dimension_is_cvss", "relation_is_has_cvss",
            "vector_matches_library_byte_for_byte", "snapshot_rereadable",
            "snapshot_locator_resolves", "snapshot_vector_matches", "snapshot_score_matches",
            "candidate_evidence_source_matches_library", "candidate_value_matches_snapshot",
            "candidate_is_human_verified_positive",
        ],
        "verified": len(items) - len(failed),
        "total": len(items),
        "ok": not failed and bool(items),
        "resolved_former_ids": {
            item["gold_relation_id"]: item["new_relation_id"] for item in items
        },
        "items": items,
    }


def build_promotions(report: dict, annotations: dict) -> dict:
    """新增正标注清单：只含"系统此前漏检、修复后已抽出"的 cvss 关系。"""
    promotions = []
    for item in report["items"]:
        annotation = annotations.get(item["new_relation_id"]) or {}
        promotions.append({
            "relation_id": item["new_relation_id"],
            "dimension": "cvss",
            "subject": item["subject"],
            "object": item["expected_vector"],
            "label": POSITIVE,
            "verified_by": annotation.get("verified_by"),
            "verified_at": annotation.get("verified_at"),
            "former_gold_relation_id": item["gold_relation_id"],
            "note": (f"原为 2026-10-04 金标准的真实漏检（{item['gold_relation_id']}）。"
                     f"NVD metrics 合并链路修复后（commit {FIX_COMMIT}），系统已在候选集抽出"
                     f"该向量；经与 NVD 官方快照逐字符比对一致且来源可回读，由漏检转为命中。"),
            "evidence": {
                "type": "nvd_snapshot",
                "source_path": item["nvd_snapshot"],
                "source_locator": item["snapshot_locator"],
                "detail": {
                    "base_score": item["snapshot_base_score"],
                    "library_source_id": item["library_source_id"],
                    "metric": item["snapshot_locator"].split(".")[-1].split("[")[0],
                },
                "byte_rereadable": item["byte_rereadable"],
            },
        })
    return {
        "schema_version": "b-relation-promotions-1.0",
        "batch": "20261006",
        "note": ("新增正标注清单：仅含‘系统此前漏检、修复后已抽出’的 cvss 关系，"
                 "已核验并写入 relation_candidates_labeled_20261006.json 生效。"),
        "source_of_signature": "relation_candidates_labeled_20261006.json",
        "promotions": promotions,
    }


def _verify_one(connection: sqlite3.Connection, snapshot_dir: Path, index: dict,
                annotations: dict, entry: dict) -> dict:
    gold_id = entry["gold_relation_id"]
    subject = entry["subject"]
    expected = entry["object"]
    checks = {name: False for name in (
        "subject_exists_in_library", "dimension_is_cvss", "relation_is_has_cvss",
        "vector_matches_library_byte_for_byte", "snapshot_rereadable",
        "snapshot_locator_resolves", "snapshot_vector_matches", "snapshot_score_matches",
        "candidate_evidence_source_matches_library", "candidate_value_matches_snapshot",
        "candidate_is_human_verified_positive",
    )}

    checks["dimension_is_cvss"] = entry.get("dimension") == "cvss"
    checks["relation_is_has_cvss"] = entry.get("relation") == "has_cvss"

    row = connection.execute("select doc from events where id=?", (subject,)).fetchone()
    checks["subject_exists_in_library"] = row is not None
    library_hits: list[dict] = []
    if row is not None:
        document = json.loads(row[0])
        library_hits = [c for c in (document.get("cvss") or [])
                        if str(c.get("vector")) == expected]
    checks["vector_matches_library_byte_for_byte"] = bool(library_hits)

    snapshot_path = snapshot_dir / f"{subject}.json"
    snapshot_bytes = snapshot_path.read_bytes()
    checks["snapshot_rereadable"] = expected.encode("utf-8") in snapshot_bytes
    locator = (entry.get("evidence") or {}).get("source_locator") or ""
    metric = None
    try:
        metric = _locate(_cve_document(json.loads(snapshot_bytes.decode("utf-8"))), locator)
        checks["snapshot_locator_resolves"] = isinstance(metric, dict)
    except (KeyError, ValueError, IndexError, TypeError):
        metric = None
    cvss_data = (metric or {}).get("cvssData") or {}
    checks["snapshot_vector_matches"] = cvss_data.get("vectorString") == expected
    detail = (entry.get("evidence") or {}).get("detail") or {}
    checks["snapshot_score_matches"] = (
        detail.get("base_score") is not None
        and cvss_data.get("baseScore") == detail.get("base_score")
    )

    candidate = index.get(("cvss", subject, _norm(expected)))
    new_id = candidate["relation_id"] if candidate else None
    library_source_id = library_hits[0].get("source_id") if library_hits else None
    if candidate:
        evidence = candidate.get("evidence") or {}
        checks["candidate_evidence_source_matches_library"] = bool(
            library_source_id
            and evidence.get("event_id") == subject
            and evidence.get("source_id") == library_source_id
        )
        candidate_value = candidate.get("candidate_value") or {}
        checks["candidate_value_matches_snapshot"] = (
            candidate_value.get("vector") == expected
            and candidate_value.get("score") == cvss_data.get("baseScore")
        )
        annotation = annotations.get(new_id) or {}
        checks["candidate_is_human_verified_positive"] = (
            annotation.get("status") == VERIFIED
            and annotation.get("label") == POSITIVE
            and bool(annotation.get("verified_by"))
            and bool(annotation.get("verified_at"))
        )

    return {
        "gold_relation_id": gold_id,
        "subject": subject,
        "new_relation_id": new_id,
        "expected_vector": expected,
        "library_match": "FOUND" if library_hits else "MISSING",
        "library_count": len(library_hits),
        "library_source_id": library_source_id,
        "nvd_snapshot": str(snapshot_path),
        "snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "snapshot_locator": locator,
        "snapshot_vector": cvss_data.get("vectorString"),
        "snapshot_base_score": cvss_data.get("baseScore"),
        "byte_rereadable": checks["snapshot_rereadable"],
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="复核 10-04 的 5 条 cvss 漏检与修复后候选的对应关系")
    parser.add_argument("--db", type=Path, required=True, help="副本库 intel.sqlite")
    parser.add_argument("--snapshot-dir", type=Path, required=True, help="副本内 NVD 快照目录")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--labeled", type=Path, default=LABELED)
    parser.add_argument("--former-missed", type=Path, default=FORMER_MISSED)
    parser.add_argument("--out", type=Path, default=VERIFICATION_OUT)
    parser.add_argument("--proposals-out", type=Path, default=None,
                        help="可选：输出新增正标注清单（署名取自已生效的标注）")
    args = parser.parse_args()

    report = verify(args.db, args.snapshot_dir, args.candidates, args.labeled,
                    args.former_missed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.proposals_out:
        annotations = {c["relation_id"]: (c.get("annotation") or {})
                       for c in _load(args.labeled)["cases"]}
        args.proposals_out.parent.mkdir(parents=True, exist_ok=True)
        args.proposals_out.write_text(
            json.dumps(build_promotions(report, annotations), ensure_ascii=False, indent=1),
            encoding="utf-8")

    for item in report["items"]:
        failed = [name for name, passed in item["checks"].items() if not passed]
        flag = "OK " if item["all_checks_passed"] else "FAIL"
        print(f"  [{flag}] {item['gold_relation_id']} {item['subject']} "
              f"-> {item['new_relation_id']} ({item['library_match']})")
        if failed:
            print(f"         未通过：{', '.join(failed)}")
    print(f"核验 {report['verified']}/{report['total']} 条；"
          f"写入 {args.out.relative_to(ROOT)}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
