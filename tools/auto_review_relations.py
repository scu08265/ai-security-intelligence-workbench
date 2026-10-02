"""B 任务：对 121 条关系候选做**自动核验**（不改数据库、不写人工列）。

每个维度使用与该维度匹配的规则，规则名与结果一起输出：

* `fixed_version`
  - `R-FV-PARSE`     固定版本可解析（PEP 440 版本或 `>= X` 形式）
  - `R-FV-CONSISTENCY` 固定版本**不得**落在受影响区间内（落在里面即自相矛盾）
  - `R-FV-SNAPSHOT`  该版本字符串出现在来源的**原始快照**里
* `version_range`
  - `R-VR-PARSE`     区间可解析；不可解析只记"证据不足"，不判定为假
  - `R-VR-SNAPSHOT`  区间字符串出现在原始快照里
* `cvss`
  - `R-CV-RANGE`     score 在 0–10
  - `R-CV-VECTOR`    vector 形如 `CVSS:3.1/...` 且度量项 ≥ 6
  - `R-CV-SNAPSHOT`  vector 或 score 出现在原始快照里
* `paper_link`
  - `R-PL-ARXIV`     `pdf_url` 可解析出合法 arXiv 标识符
  - `R-PL-DOC`       本地 RAG 中存在 `paper:<id>` 全文文档
  - `R-PL-TITLE`     事件标题与文档首块的词元重合 ≥ 3

判定取值：`supported` / `contradicted` / `insufficient_evidence` / `not_applicable`。
自动判定写入独立字段（`auto_judgment` 等），**绝不写 `人工判定` 列**，
也不会写 `人工核验人` / `人工核验时间`。

用法::

    python tools/auto_review_relations.py --out artifacts/b_eval/relation_auto_review.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, paper_fulltext, storage  # noqa: E402

SOURCE_DATA_DIR = Path(r"D:\ICT\intel-data-b")
CANDIDATES = ROOT / "evaluation" / "b_relation_candidates.json"
MAX_SNAPSHOT_BYTES = 30 * 1024 * 1024

_snapshot_cache: dict[str, str] = {}

# 原始快照里缺失某个字符串**不等于**关系为假：来源可能用结构化字段
# （例如 OSV 的 introduced/fixed）表达区间，而候选值是归一化推导出来的。
# 因此"未命中"一律记为 unavailable（证据不足），只有逻辑自相矛盾才判 contradicted。
_VERSION_TOKEN = re.compile(r"\d+\.\d+(?:\.\d+)*")


def _version_tokens(text: str) -> list[str]:
    return _VERSION_TOKEN.findall(text or "")


def _snapshot_text(source_dir: str) -> str | None:
    """返回某个来源目录下所有原始快照的拼接文本（PDF 跳过）。"""
    if source_dir in _snapshot_cache:
        return _snapshot_cache[source_dir] or None
    directory = config.SNAPSHOT_DIR / source_dir
    if not directory.is_dir():
        return None
    parts: list[str] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.casefold() in {".pdf"}:
            continue
        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            continue
        parts.append(path.read_bytes().decode("utf-8", errors="replace"))
    _snapshot_cache[source_dir] = "\n".join(parts)
    return _snapshot_cache[source_dir] or None


def _source_dir(event: dict) -> str | None:
    for source in event.get("sources") or []:
        prefix = str(source.get("id") or "").split(":", 1)[0]
        if prefix:
            return prefix
    return None


def _load_osv_index() -> dict[str, dict]:
    """把本地 OSV 快照按漏洞 ID 建索引，用于**结构化**语义核验。"""
    index: dict[str, dict] = {}
    directory = config.SNAPSHOT_DIR / "osv"
    if not directory.is_dir():
        return index
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        if isinstance(payload, dict) and payload.get("id"):
            payload["_snapshot_file"] = path.name
            index[str(payload["id"])] = payload
    return index


def _osv_events_for(record: dict, package: str) -> list[dict]:
    for entry in record.get("affected") or []:
        name = str((entry.get("package") or {}).get("name") or "")
        if package and name.casefold() != package.casefold():
            continue
        events: list[dict] = []
        for rng in entry.get("ranges") or []:
            events.extend(rng.get("events") or [])
        return events
    return []


def _derive_range(events: list[dict]) -> str | None:
    """把 OSV 的 introduced/fixed 事件还原成候选用的区间写法。"""
    introduced = next((str(e["introduced"]) for e in events if "introduced" in e), None)
    fixed = next((str(e["fixed"]) for e in events if "fixed" in e), None)
    last = next((str(e["last_affected"]) for e in events if "last_affected" in e), None)
    if fixed is not None:
        lower_ok = introduced in (None, "0")
        return f"< {fixed}" if lower_ok else f">= {introduced}, < {fixed}"
    if last is not None:
        return f"<= {last}"
    return None


def _review_fixed_version_structured(case: dict, osv: dict) -> list[dict]:
    record = osv.get(case["subject"])
    if not record:
        return [_rule("R-FV-STRUCTURED", "unavailable",
                      "本地没有该事件的 OSV 结构化快照（可能来自其他来源）")]
    package = str(case["candidate_value"].get("package") or "")
    events = _osv_events_for(record, package)
    if not events:
        return [_rule("R-FV-STRUCTURED", "unavailable",
                      f"OSV 记录中没有 {package} 的区间事件")]
    fixed_values = {str(e["fixed"]) for e in events if "fixed" in e}
    candidate = str(case["candidate_value"].get("fixed_version") or "")
    token = candidate.split()[-1] if candidate else ""
    ok = token in fixed_values
    return [_rule("R-FV-STRUCTURED", "pass" if ok else "fail",
                  f"OSV 结构化事件 fixed={sorted(fixed_values)}，候选={candidate!r}")]


def _review_version_range_structured(case: dict, osv: dict) -> list[dict]:
    record = osv.get(case["subject"])
    if not record:
        return [_rule("R-VR-STRUCTURED", "unavailable",
                      "本地没有该事件的 OSV 结构化快照（可能来自其他来源）")]
    package = str(case["candidate_value"].get("package") or "")
    events = _osv_events_for(record, package)
    if not events:
        return [_rule("R-VR-STRUCTURED", "unavailable",
                      f"OSV 记录中没有 {package} 的区间事件")]
    derived = _derive_range(events)
    candidate_range = str(case["candidate_value"].get("range") or "")
    if derived is None:
        return [_rule("R-VR-STRUCTURED", "unavailable", "OSV 事件无法还原成区间")]
    rules = []
    same = derived.replace(" ", "") == candidate_range.replace(" ", "")
    rules.append(_rule("R-VR-STRUCTURED", "pass" if same else "fail",
                       f"OSV 结构化事件还原出 {derived!r}，候选={candidate_range!r}"))
    # 一致性抽查：OSV 列出的受影响版本应当全部落在候选区间内
    versions = [str(v) for entry in record.get("affected") or []
                for v in (entry.get("versions") or [])]
    if versions:
        try:
            spec = SpecifierSet(candidate_range)
        except InvalidSpecifier:
            rules.append(_rule("R-VR-VERSIONS", "unavailable", "候选区间不可解析"))
        else:
            outside = []
            for token in versions:
                try:
                    if Version(token) not in spec:
                        outside.append(token)
                except InvalidVersion:
                    continue
            rules.append(_rule(
                "R-VR-VERSIONS", "pass" if not outside else "fail",
                f"OSV 列出的 {len(versions)} 个受影响版本中，"
                f"{len(outside)} 个不在候选区间内" + (f"（如 {outside[:3]}）" if outside else "")))
    return rules


def _has_range_and_fixed(case: dict, events: dict[str, dict]) -> tuple[str, str] | None:
    event = events.get(case["subject"])
    if not event:
        return None
    package = case["candidate_value"].get("package")
    for item in event.get("affected") or []:
        if item.get("package") != package:
            continue
        return str(item.get("range") or ""), str(item.get("fixed_version") or "")
    return None


def _verdict(rules: list[dict]) -> tuple[str, str, str]:
    """由规则结果推出 (auto_judgment, auto_reason, auto_confidence)。"""
    failed = [r for r in rules if r["result"] == "fail"]
    passed = [r for r in rules if r["result"] == "pass"]
    unavailable = [r for r in rules if r["result"] == "unavailable"]
    if failed:
        return ("contradicted",
                "；".join(f"{r['rule']}: {r['detail']}" for r in failed), "high")
    if unavailable and not passed:
        return ("insufficient_evidence",
                "；".join(f"{r['rule']}: {r['detail']}" for r in unavailable), "low")
    if passed:
        confidence = "high" if len(passed) >= 2 else "medium"
        if unavailable:
            confidence = "medium"
        return ("supported",
                "；".join(f"{r['rule']}: {r['detail']}" for r in passed), confidence)
    return ("insufficient_evidence", "没有可执行的规则", "low")


def _rule(name: str, result: str, detail: str) -> dict:
    return {"rule": name, "result": result, "detail": detail}


def _review_fixed_version(case: dict, events: dict[str, dict], snapshots: dict) -> tuple[list[dict], dict]:
    value = case["candidate_value"]
    fixed = str(value.get("fixed_version") or "")
    pair = _has_range_and_fixed(case, events)
    rules: list[dict] = []
    evidence: dict = {"candidate_value": value}

    parsed: Version | None = None
    if fixed:
        try:
            parsed = Version(fixed)
            rules.append(_rule("R-FV-PARSE", "pass", f"{fixed} 可解析为版本"))
        except InvalidVersion:
            match = re.fullmatch(r"(>=|<=|>|<)\s*([0-9][0-9A-Za-z.\-+]*)", fixed)
            if match:
                rules.append(_rule("R-FV-PARSE", "pass",
                                   f"{fixed} 是区间下界表达（{match.group(1)}）"))
            else:
                rules.append(_rule("R-FV-PARSE", "unavailable",
                                   f"{fixed!r} 不是可解析的版本，无法判断"))
    else:
        rules.append(_rule("R-FV-PARSE", "fail", "fixed_version 为空"))

    if pair and parsed is not None:
        rng, _ = pair
        try:
            spec = SpecifierSet(rng)
        except InvalidSpecifier:
            rules.append(_rule("R-FV-CONSISTENCY", "unavailable",
                               f"受影响区间 {rng!r} 无法解析，未做一致性判断"))
        else:
            inside = parsed in spec
            rules.append(_rule(
                "R-FV-CONSISTENCY", "fail" if inside else "pass",
                f"fixed={fixed} {'落在' if inside else '不落在'}受影响区间 {rng}"))
            evidence["affected_range"] = rng

    source_dir = _source_dir(events.get(case["subject"]) or {})
    text = snapshots.get(source_dir or "") if source_dir else None
    if text:
        tokens = _version_tokens(fixed) or ([fixed] if fixed else [])
        found = any(token and token in text for token in tokens)
        rules.append(_rule(
            "R-FV-SNAPSHOT", "pass" if found else "unavailable",
            f"原始快照 {'包含' if found else '未逐字包含'} {fixed!r} 的版本号"
            + ("" if found else "（来源可能以结构化字段表达，需人工核验）")))
        evidence["snapshot_source"] = source_dir
    else:
        rules.append(_rule("R-FV-SNAPSHOT", "unavailable",
                           f"来源 {source_dir} 没有可读的文本快照"))
    return rules, evidence


def _review_version_range(case: dict, events: dict[str, dict], snapshots: dict) -> tuple[list[dict], dict]:
    value = case["candidate_value"]
    rng = str(value.get("range") or "")
    rules: list[dict] = []
    evidence: dict = {"candidate_value": value}
    try:
        SpecifierSet(rng)
        rules.append(_rule("R-VR-PARSE", "pass", f"{rng!r} 可解析为版本区间"))
    except InvalidSpecifier:
        rules.append(_rule("R-VR-PARSE", "unavailable",
                           f"{rng!r} 不是 PEP 440 区间（可能是厂商自有版本号），无法判定"))
    source_dir = _source_dir(events.get(case["subject"]) or {})
    text = snapshots.get(source_dir or "") if source_dir else None
    if text:
        tokens = _version_tokens(rng)
        hit = [t for t in tokens if t in text]
        if hit:
            rules.append(_rule("R-VR-SNAPSHOT", "pass",
                               f"原始快照包含区间端点 {hit[:3]}"))
        else:
            rules.append(_rule(
                "R-VR-SNAPSHOT", "unavailable",
                f"原始快照未出现 {rng!r} 的任何版本端点；"
                "来源可能以结构化 introduced/fixed 表达区间，需人工核验"))
        evidence["snapshot_source"] = source_dir
    else:
        rules.append(_rule("R-VR-SNAPSHOT", "unavailable",
                           f"来源 {source_dir} 没有可读的文本快照"))
    return rules, evidence


def _review_cvss(case: dict, events: dict[str, dict], snapshots: dict) -> tuple[list[dict], dict]:
    value = case["candidate_value"]
    score, vector = value.get("score"), str(value.get("vector") or "")
    rules: list[dict] = []
    evidence: dict = {"candidate_value": value}
    if isinstance(score, (int, float)):
        ok = 0.0 <= float(score) <= 10.0
        rules.append(_rule("R-CV-RANGE", "pass" if ok else "fail",
                           f"score={score} {'在' if ok else '不在'} 0–10"))
    else:
        rules.append(_rule("R-CV-RANGE", "unavailable", "来源未给出数值分数（不得当作 0）"))
    if vector:
        metrics = [m for m in vector.split("/")[1:] if m]
        ok = vector.startswith("CVSS:") and len(metrics) >= 6
        rules.append(_rule("R-CV-VECTOR", "pass" if ok else "fail",
                           f"vector 含 {len(metrics)} 个度量项，前缀{'正确' if vector.startswith('CVSS:') else '异常'}"))
    else:
        rules.append(_rule("R-CV-VECTOR", "unavailable", "没有 vector"))
    source_dir = _source_dir(events.get(case["subject"]) or {})
    text = snapshots.get(source_dir or "") if source_dir else None
    if text:
        found_vec = bool(vector) and vector in text
        found_score = (str(score) in text) if isinstance(score, (int, float)) else False
        rules.append(_rule(
            "R-CV-SNAPSHOT", "pass" if (found_vec or found_score) else "unavailable",
            f"原始快照 vector={'命中' if found_vec else '未命中'} "
            f"score={'命中' if found_score else '未命中'}"
            + ("" if (found_vec or found_score) else "（未命中不等于矛盾，需人工核验）")))
        evidence["snapshot_source"] = source_dir
    else:
        rules.append(_rule("R-CV-SNAPSHOT", "unavailable",
                           f"来源 {source_dir} 没有可读的文本快照"))
    return rules, evidence


def _review_paper_link(case: dict, events: dict[str, dict], documents: dict[str, str]) -> tuple[list[dict], dict]:
    value = case["candidate_value"]
    event = events.get(case["subject"]) or {}
    rules: list[dict] = []
    evidence: dict = {"candidate_value": value}
    identifier = paper_fulltext._paper_identity(event)
    if identifier:
        rules.append(_rule("R-PL-ARXIV", "pass", f"可解析出 arXiv 标识符 {identifier}"))
    else:
        rules.append(_rule("R-PL-ARXIV", "unavailable",
                           "pdf_url 指向非 arXiv 出版商，本地未抓取该 PDF，无法核对正文"))
    document_key = f"paper:{identifier}" if identifier else ""
    if document_key and document_key in documents:
        rules.append(_rule("R-PL-DOC", "pass", f"本地存在全文文档 {document_key}"))
        first_chunk = documents[document_key]
        title_tokens = {t for t in re.findall(r"[a-z0-9]{4,}", (event.get("title") or "").casefold())}
        chunk_tokens = {t for t in re.findall(r"[a-z0-9]{4,}", first_chunk[:1500].casefold())}
        overlap = len(title_tokens & chunk_tokens)
        ok = overlap >= 3
        rules.append(_rule("R-PL-TITLE", "pass" if ok else "fail",
                           f"事件标题与文档首块词元重合 {overlap} 个（阈值 3）"))
        evidence["document_key"] = document_key
    elif identifier:
        rules.append(_rule("R-PL-DOC", "fail", f"本地缺少全文文档 {document_key}"))
    else:
        rules.append(_rule("R-PL-DOC", "unavailable", "没有 arXiv 标识符，无法定位本地文档"))
    return rules, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="关系候选自动核验")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "relation_auto_review.json")
    parser.add_argument("--source-data-dir", type=Path, default=SOURCE_DATA_DIR)
    args = parser.parse_args()

    if not (args.source_data_dir / "intel.sqlite").is_file():
        print("找不到数据库:", args.source_data_dir / "intel.sqlite")
        return 2
    config.DATA_DIR = args.source_data_dir
    config.SNAPSHOT_DIR = args.source_data_dir / "snapshots"
    config.DB_PATH = args.source_data_dir / "intel.sqlite"

    payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    events = {e["id"]: e for e, _ in [(e, None) for e in storage.list_events(limit=500)[0]]}
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT d.document_key, v.extracted_text
               FROM rag_documents d JOIN rag_document_versions v ON v.id=d.current_version_id"""
        ).fetchall()
    documents = {row["document_key"]: (row["extracted_text"] or "") for row in rows}
    osv_index = _load_osv_index()

    # 只加载一次快照文本，避免重复 IO
    snapshots: dict[str, str] = {}
    for directory in sorted((args.source_data_dir / "snapshots").iterdir()):
        if directory.is_dir():
            text = _snapshot_text(directory.name)
            if text:
                snapshots[directory.name] = text

    def review_fixed_version(case: dict):
        rules, evidence = _review_fixed_version(case, events, snapshots)
        return rules + _review_fixed_version_structured(case, osv_index), evidence

    def review_version_range(case: dict):
        rules, evidence = _review_version_range(case, events, snapshots)
        return rules + _review_version_range_structured(case, osv_index), evidence

    reviewers = {
        "fixed_version": review_fixed_version,
        "version_range": review_version_range,
        "cvss": lambda case: _review_cvss(case, events, snapshots),
        "paper_link": lambda case: _review_paper_link(case, events, documents),
    }

    # 先把 fixed_version 处理完（证据最集中），再处理其余维度
    order = sorted(payload["cases"], key=lambda c: 0 if c["dimension"] == "fixed_version" else 1)
    reviewed = []
    for case in order:
        dimension = case["dimension"]
        reviewer = reviewers.get(dimension)
        if reviewer is None:
            reviewed.append({
                **{k: case[k] for k in ("relation_id", "dimension", "subject", "relation", "object")},
                "auto_judgment": "insufficient_evidence",
                "auto_reason": f"维度 {dimension} 当前没有数据来源，无法自动核验",
                "auto_evidence": {},
                "auto_rules": [],
                "auto_confidence": "low",
                "manual_label_preserved": case["annotation"]["status"],
            })
            continue
        rules, evidence = reviewer(case)
        judgment, reason, confidence = _verdict(rules)
        reviewed.append({
            **{k: case[k] for k in ("relation_id", "dimension", "subject", "relation", "object")},
            "auto_judgment": judgment,
            "auto_reason": reason,
            "auto_evidence": evidence,
            "auto_rules": rules,
            "auto_confidence": confidence,
            "manual_label_preserved": case["annotation"]["status"],
        })

    by_dimension: dict[str, dict[str, int]] = {}
    by_judgment: dict[str, int] = {}
    for item in reviewed:
        bucket = by_dimension.setdefault(item["dimension"], {})
        bucket[item["auto_judgment"]] = bucket.get(item["auto_judgment"], 0) + 1
        by_judgment[item["auto_judgment"]] = by_judgment.get(item["auto_judgment"], 0) + 1

    result = {
        "schema_version": "b-relation-auto-review-1.0",
        "method": "按维度匹配规则；规则结果与判定一起输出。"
                  "自动判定只写入 auto_* 字段，不写人工列。",
        "evidence_sources": ["本地 SQLite 事件字段",
                             "来源原始快照（JSON/HTML/XML，PDF 跳过）",
                             "本地 RAG 全文文档与分块"],
        "caution": "自动判定不等于人工核验；字符串命中不等于关系成立。",
        "counts": {
            "total": len(reviewed),
            "by_judgment": by_judgment,
            "by_dimension": by_dimension,
        },
        "coverage": {
            "reviewed": len(reviewed),
            "auto_judged": sum(1 for r in reviewed
                               if r["auto_judgment"] in {"supported", "contradicted"}),
            "undetermined": sum(1 for r in reviewed
                                if r["auto_judgment"] == "insufficient_evidence"),
        },
        "cases": reviewed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("自动核验条数:", result["counts"]["total"])
    print("判定分布:", json.dumps(by_judgment, ensure_ascii=False))
    for dim, bucket in sorted(by_dimension.items()):
        print("  %-18s %s" % (dim, json.dumps(bucket, ensure_ascii=False)))
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
