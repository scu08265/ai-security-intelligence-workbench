"""B 任务 2026-10-10：扩样批次里"源头已声明、候选却尚未判 positive"的关系逐条核验。

本工具只回答一个问题：**这些关系能不能在源头里逐字回读？** 每条关系按下面 7 项检查，
任一项不通过就记为 FAIL 并让进程以 exit=1 结束，不写"看起来没问题"的结论：

1. ``event_exists``：主体在副本库 ``events`` 表里存在；
2. ``candidate_found``：候选集里有 ``(dimension, subject, object)`` 完全一致的候选；
3. ``candidate_object_matches``：候选 object 与源头枚举出的 object 逐字一致；
4. ``source_locator_resolves``：按 ``source_path`` + ``source_locator`` 能回到源头那一项；
5. ``source_value_matches``：回到的那一项里的版本/向量值与枚举值逐字一致；
6. ``source_byte_rereadable``：这些值在源头文件原始字节里逐字出现（可回读，不是推理出来的）；
7. ``annotation_not_contradictory``：候选当前标注不是 ``negative`` / ``not_applicable``
   （是的话不许覆盖）。

第 7 项只保证"不覆盖相反结论"。**升级成 ``human_verified/positive`` 属于人工签核**，
所以本工具**不能自签**：不显式给 ``--verified-by`` 时，清单署名是占位串
``源快照逐字比对-待用户签核``、``signature_required`` 为 ``true``；只有签核人显式传入
``--verified-by``（例如 ``--verified-by 人工复核-用户确认``）时，才把
``signature_required`` 置为 ``false``，再交给 ``relabel_b_relation_candidates.py
--promote`` 落地。

用法::

    python tools/verify_b_relation_expansion.py \
        --db-dir D:\\ICT\\intel-data-b-cvss-20261006 \
        --candidates evaluation/b_relation_candidates_20261010.json \
        --labeled artifacts/b_eval/relation_candidates_labeled_20261006.json \
        --out artifacts/b_eval/relation_expansion_verification_20261010.json \
        --proposals-out artifacts/b_eval/relation_new_positive_proposals_20261010.json

``--labeled`` 要指向**升级前**的标注状态（上一批次，或本批次尚未升级的标注）：
已经被判为 ``human_verified/positive`` 的候选会被跳过，拿升级后的文件来跑会得到 0 条，
那是自证而不是核验。
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_b_relation_gold as gold_tool  # noqa: E402

VERIFIED = "human_verified"
POSITIVE = "positive"
CONTRADICTORY = {"negative", "not_applicable"}
SOURCE_CHECKS = ("event_exists", "source_locator_resolves", "source_value_matches",
                 "source_byte_rereadable")

# 未显式签核时的占位署名：语义是"证据已备好、结论还没签"，不是人工确认。
PLACEHOLDER_VERIFIED_BY = "源快照逐字比对-待用户签核"

_STEP = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")
_EVENT_PATH = re.compile(r"^events\[(?P<subject>.+?)\]\.(?P<rest>.+)$")
_VERSION_TOKEN = re.compile(r"\d[0-9A-Za-z.\-+]*")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk(document: object, locator: str) -> object:
    current = document
    for raw_step in locator.split("."):
        match = _STEP.match(raw_step)
        if not match:
            raise ValueError(f"无法解析定位符片段：{raw_step}")
        name, index = match.group(1), match.group(2)
        if not isinstance(current, dict) or name not in current:
            raise KeyError(f"定位符 `{locator}` 在 `{raw_step}` 处中断")
        current = current[name]
        if index is not None:
            current = current[int(index)]
    return current


def _values(node: object) -> list[str]:
    if isinstance(node, dict):
        return [str(value) for value in node.values()]
    return [str(node)]


def _tokens(text: str) -> list[str]:
    return _VERSION_TOKEN.findall(str(text))


def _snapshot_document(payload: dict, subject: str) -> dict | None:
    """在快照文件里找到属于 ``subject`` 的那份记录（OSV 单条 / MITRE / NVD 页）。"""
    if payload.get("id") == subject:
        return payload
    if (payload.get("cveMetadata") or {}).get("cveId") == subject:
        return payload
    for vulnerability in payload.get("vulnerabilities") or []:
        cve = (vulnerability or {}).get("cve") or {}
        if cve.get("id") == subject:
            return cve
    return None


def verify(db_dir: Path, candidates_path: Path, labeled_path: Path,
           scope_mode: str = gold_tool.SCOPE_MODE_FULL) -> dict:
    candidates = _load(candidates_path)["cases"]
    annotations = {case["relation_id"]: (case.get("annotation") or {})
                   for case in _load(labeled_path)["cases"]}
    index = {(case["dimension"], case["subject"], gold_tool._norm(case["object"])): case
             for case in candidates}

    connection = sqlite3.connect(f"file:{db_dir / 'intel.sqlite'}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        events = {row["id"]: json.loads(row["doc"])
                  for row in connection.execute("select id, doc from events")}
    finally:
        connection.close()

    scope = gold_tool.resolve_scope(db_dir, events, gold_tool._doc_keys(db_dir), scope_mode)
    relations = gold_tool.enumerate_source_relations(db_dir, events, scope)

    items: list[dict] = []
    for relation in relations:
        candidate = index.get((relation["dimension"], relation["subject"],
                               gold_tool._norm(relation["object"])))
        annotation = (annotations.get(candidate["relation_id"]) if candidate else {}) or {}
        if (annotation.get("status") == VERIFIED
                and annotation.get("label") == POSITIVE):
            continue
        items.append(_verify_one(db_dir, events, relation, candidate, annotation))

    # 有候选的：要么可升级（全部检查通过），要么被挡住（源不对/与相反结论冲突）。
    # 没候选的：源头写着、候选里没有 —— 这正是本次要如实计入的**新增漏检**，
    # 但前提是它能从源头原字节逐字回读，否则不算漏检、算枚举错误。
    promotable = [item for item in items
                  if item["candidate_found"] and item["all_checks_passed"]]
    blocked = [item for item in items
               if item["candidate_found"] and not item["all_checks_passed"]]
    missed = [item for item in items if not item["candidate_found"]]
    missed_unreadable = [item for item in missed if not item["source_verified"]]
    return {
        "schema_version": "b-relation-expansion-verification-1.0",
        "scope_mode": scope_mode,
        "candidates_ref": gold_tool._repo_rel(candidates_path),
        "labeled_ref": gold_tool._repo_rel(labeled_path),
        "total": len(items),
        "candidate_backed": len(promotable) + len(blocked),
        "promotable": len(promotable),
        "blocked": len(blocked),
        "missed_new": len(missed),
        "missed_unreadable": len(missed_unreadable),
        "ok": not blocked and not missed_unreadable,
        "items": items,
    }


def _verify_one(db_dir: Path, events: dict, relation: dict, candidate: dict,
                annotation: dict) -> dict:
    candidate = candidate or {}
    subject = relation["subject"]
    expected_object = relation["object"]
    package, separator, value = expected_object.partition("@")
    if not separator:  # cvss 向量 / 论文链接没有 package@value 结构
        package, value = None, expected_object
    checks: dict[str, bool] = {}

    event = events.get(subject)
    checks["event_exists"] = event is not None
    checks["candidate_found"] = bool(candidate.get("relation_id"))
    checks["candidate_object_matches"] = (bool(candidate)
                                         and candidate.get("object") == expected_object)
    checks["annotation_not_contradictory"] = annotation.get("label") not in CONTRADICTORY

    source_path = str(relation.get("source_path") or "")
    locator = str(relation.get("source_locator") or "")
    if relation.get("dimension") == "fixed_version":
        tokens = [value]
    elif relation.get("dimension") == "version_range":
        tokens = _tokens(value)
    else:
        tokens = [value]

    source_file = None
    node: object = None
    match = _EVENT_PATH.match(source_path)
    if match:
        source_file = db_dir / "intel.sqlite"
        try:
            node = _walk(events.get(match.group("subject")) or {}, match.group("rest"))
        except (KeyError, ValueError, IndexError, TypeError):
            node = None
    else:
        candidate_file = db_dir / source_path
        if candidate_file.is_file():
            source_file = candidate_file
            payload = json.loads(candidate_file.read_text(encoding="utf-8"))
            document = _snapshot_document(payload, subject)
            if document is not None:
                try:
                    node = _walk(document, locator)
                except (KeyError, ValueError, IndexError, TypeError):
                    node = None

    checks["source_locator_resolves"] = node is not None
    node_values = _values(node) if node is not None else []
    checks["source_value_matches"] = bool(node is not None) and all(
        any(token == candidate_value or token in candidate_value
            for candidate_value in node_values)
        for token in tokens)

    if source_file is not None and source_file.suffix in {".json", ".sqlite"}:
        raw = source_file.read_bytes()
        checks["source_byte_rereadable"] = all(
            token.encode("utf-8") in raw for token in tokens)
    else:
        checks["source_byte_rereadable"] = False

    source_id = (candidate.get("evidence") or {}).get("source_id")
    source_verified = all(checks[name] for name in SOURCE_CHECKS)
    return {
        "relation_id": candidate.get("relation_id"),
        "dimension": relation["dimension"],
        "subject": subject,
        "object": expected_object,
        "package": package,
        "enumerated_value": value,
        "source": relation.get("source"),
        "source_path": source_path,
        "source_locator": locator,
        "source_file": str(source_file) if source_file else None,
        "source_node_values": node_values,
        "tokens": tokens,
        "current_annotation": {"status": annotation.get("status"),
                               "label": annotation.get("label")},
        "candidate_source_id": source_id,
        "candidate_found": checks["candidate_found"],
        "checks": checks,
        "source_verified": source_verified,
        "all_checks_passed": all(checks.values()),
    }


def resolve_signature(verified_by: str | None) -> tuple[str, bool]:
    """把 ``--verified-by`` 解析成（清单署名, 是否仍需人工签核）。

    只有**显式传入、且不是占位串**的署名才算人工签核；``None``（未传）或占位串一律
    退回待签核状态 —— 本工具只负责逐字回读证据，不许拿自己的核验结论冒充人工确认。
    """
    name = (verified_by or "").strip()
    if not name or name == PLACEHOLDER_VERIFIED_BY:
        return PLACEHOLDER_VERIFIED_BY, True
    return name, False


def parse_note_suffixes(raw: list[str] | None) -> dict[str, str]:
    """把 ``--note-suffix Subject=补充说明`` 解析成 {subject: 补充说明}。"""
    suffixes: dict[str, str] = {}
    for entry in raw or []:
        subject, sep, text = entry.partition("=")
        subject, text = subject.strip(), text.strip()
        if not sep or not subject or not text:
            raise SystemExit(f"--note-suffix 需要写成 Subject=补充说明，收到：{entry!r}")
        suffixes[subject] = text
    return suffixes


def build_promotions(report: dict, *, verified_by: str | None, verified_at: str,
                     note: str, note_suffixes: dict[str, str] | None = None) -> dict:
    signer, signature_required = resolve_signature(verified_by)
    promotions = []
    for item in report["items"]:
        if not (item["candidate_found"] and item["all_checks_passed"]):
            continue
        item_note = note
        suffix = (note_suffixes or {}).get(item["subject"])
        if suffix:
            item_note = f"{note} {suffix}"
        promotions.append({
            "dimension": item["dimension"],
            "subject": item["subject"],
            "object": item["object"],
            "label": POSITIVE,
            "verified_by": signer,
            "verified_at": verified_at,
            "note": item_note,
            "evidence": {
                "source": item["source"],
                "source_path": item["source_path"],
                "source_locator": item["source_locator"],
                "enumerated_value": item["enumerated_value"],
                "source_node_values": item["source_node_values"],
            },
        })
    return {
        "schema_version": "b-relation-promotions-1.0",
        "source_verification": report.get("candidates_ref"),
        "signature_required": signature_required,
        "counts": {"promotions": len(promotions)},
        "promotions": promotions,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="核验扩样批次里尚未标注 positive 的关系能否在源头逐字回读")
    parser.add_argument("--db-dir", type=Path, default=gold_tool.DEFAULT_DB_DIR,
                        help="副本库目录；默认取 app.config.DATA_DIR"
                             "（显式 INTEL_DATA_DIR > .env > BASE_DIR/data）")
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--labeled", type=Path, required=True)
    parser.add_argument("--scope", choices=(gold_tool.SCOPE_MODE_FULL,
                                            gold_tool.SCOPE_MODE_LEGACY),
                        default=gold_tool.SCOPE_MODE_FULL)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--proposals-out", type=Path, default=None)
    parser.add_argument("--verified-by", default=None,
                        help="签核人；不传时署名占位串、signature_required=true，"
                             "显式传入才把 signature_required 置为 false")
    parser.add_argument("--verified-at", default="2026-10-10")
    parser.add_argument("--note", default="工具按 source_path/source_locator 逐字比对通过；"
                                          "签名以人工签核为准")
    parser.add_argument("--note-suffix", action="append", default=None,
                        metavar="SUBJECT=补充说明",
                        help="可选：给某条主体的 note 追加一句审计说明（可重复）")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    report = verify(args.db_dir, args.candidates, args.labeled, args.scope)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    for item in report["items"]:
        failed = [name for name, passed in item["checks"].items() if not passed]
        if not item["candidate_found"]:
            flag = "MISS" if item["source_verified"] else "FAIL"
            failed = [name for name in failed if name in SOURCE_CHECKS]
        else:
            flag = "OK  " if item["all_checks_passed"] else "FAIL"
        print(f"  [{flag}] {item['relation_id']} {item['dimension']} "
              f"{item['subject']} → {item['object']}")
        if failed:
            print(f"         未通过：{', '.join(failed)}")

    if args.proposals_out:
        promotions = build_promotions(report, verified_by=args.verified_by,
                                      verified_at=args.verified_at, note=args.note,
                                      note_suffixes=parse_note_suffixes(args.note_suffix))
        args.proposals_out.parent.mkdir(parents=True, exist_ok=True)
        args.proposals_out.write_text(
            json.dumps(promotions, ensure_ascii=False, indent=1), encoding="utf-8")
        print("升级清单:", args.proposals_out, promotions["counts"])

    print(f"核验 {report['total']} 条：可升级 {report['promotable']}，"
          f"被挡 {report['blocked']}，新增漏检 {report['missed_new']}"
          f"（其中源头不可回读 {report['missed_unreadable']}）；写入 {args.out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
