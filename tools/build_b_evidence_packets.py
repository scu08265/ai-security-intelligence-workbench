"""B 任务：生成**带真实证据片段**的人工核验工作包。

复用已有的自动核验结果（`relation_auto_review.json`、`qa_auto_review.json`），
把每条候选对应的**可读取原文**抽出来，附上定位信息，方便人工逐条核对。

产出（全部为新文件，不覆盖既有产物）：

* `artifacts/b_eval/evidence_packet_relations.md` —— 12 条 fixed_version + 22 条 CVSS
* `artifacts/b_eval/evidence_packet_qa.md`        —— 36 道高优先级问答
* `artifacts/b_eval/evidence_relation_label_sheet.csv` —— 34 行关系标签回收表（标签列留空，
  列名与 `tools/apply_b_relation_labels.py` 对齐，可直接回灌）
* `artifacts/b_eval/evidence_qa_label_sheet.csv` —— 36 行问答标签回收表（判定列留空）
* `artifacts/b_eval/evidence_packet_coverage.json` —— 覆盖率与缺失证据报告

原则：证据只从本地快照/文档中**读取**，读不到就如实标注为"缺失"，
不补写任何推测内容。

**不会破坏人工核验成果**：如果目标目录里已存在带人工标签的回收表，
脚本会跳过该表的写入并打印警告（人工判定比重新生成更重要）。

用法::

    python tools/build_b_evidence_packets.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, paper_fulltext, storage  # noqa: E402

SOURCE_DATA_DIR = Path(r"D:\ICT\intel-data-b")
ARTIFACTS = ROOT / "artifacts" / "b_eval"
QA_DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"

LABEL_COLUMN = "待人工填写_最终判定"
# 关系表沿用既有回灌工具的列名（relation_id / 待人工填写_最终标签），
# 这样 `tools/apply_b_relation_labels.py` 可以**直接**读取，无需二次转换。
RELATION_LABEL_COLUMN = "待人工填写_最终标签"
RELATION_SHEET_COLUMNS = [
    "relation_id", "dimension", "subject", "relation", "object", "candidate_value",
    "auto_judgment", "auto_confidence", "auto_reason", "evidence_status", "evidence_location",
    RELATION_LABEL_COLUMN, "人工核验人", "人工核验时间", "人工备注",
]
QA_SHEET_COLUMNS = [
    "question_id", "category", "subject_or_question",
    "auto_judgment", "auto_confidence", "evidence_status", "evidence_location",
    LABEL_COLUMN, "人工核验人", "人工核验时间", "人工备注",
]
# 剩余 87 条（paper_link 37 + version_range 50）使用独立回收表，
# 列名同样对齐既有回灌工具，并额外给出「证据说明 / 主要缺口」两列便于人工判断。
REMAINING_SHEET_COLUMNS = [
    "relation_id", "dimension", "subject", "relation", "object", "candidate_value",
    "auto_judgment", "auto_confidence", "evidence_status", "evidence_location",
    "证据说明", "主要缺口", RELATION_LABEL_COLUMN,
    "人工核验人", "人工核验时间", "人工备注",
]
# 50 题问答人工金标准工作表：把「自动信号」与「人工判定」彻底分列。
QA_GOLD_HUMAN_COLUMNS = [
    "人工_标准答案", "人工_标准答案依据", "人工判定_答案正确性",
    "人工判定_引用准确性", "人工判定_拒答正确性", "人工最终标签",
    "人工核验人", "人工核验时间", "人工备注", "无法判断原因", "需补充证据",
]
QA_GOLD_SHEET_COLUMNS = [
    "question_id", "category", "difficulty", "question", "has_history",
    "expected_action", "should_refuse", "expected_answer_terms",
    "expected_document_keys", "expected_event_ids", "expected_reasoning_steps",
    "system_answer", "system_refused", "cited_document_keys", "cited_chunk_ids",
    "citations_retrievable", "answer_from_event_path",
    "auto_judgment", "auto_confidence", "auto_reason",
    "corpus_probe_summary", "evidence_excerpt", "evidence_location",
    "latency_ms", "timeout", "error",
] + QA_GOLD_HUMAN_COLUMNS

PRIORITY_QA = ("BQA-044", "BQA-047", "BQA-039", "BQA-040", "BQA-046", "BQA-050")


def _clip(text: str, limit: int = 480) -> str:
    text = (text or "").replace("\r", "")
    return text if len(text) <= limit else text[:limit] + " …（已截断）"


_CACHE: dict[str, dict] = {}


def _ro_connection() -> sqlite3.Connection | None:
    """只读连接真实数据库；为 None 表示当前环境读不到（不影响取证流程）。

    WAL 模式的库用普通 `mode=ro` 打开时，SQLite 会在数据目录里创建 `-shm`
    与空的 `-wal`，这属于对被测目录的副作用。这里在没有未合并 WAL 内容时
    改用 `immutable=1`，让 SQLite 完全不碰这两个文件；一旦 `-wal` 里确实
    有未合并内容，就退回普通只读模式，宁可产生副作用也不能读到过期数据。
    """
    if "ro" in _CACHE:
        return _CACHE["ro"]
    path = Path(config.DB_PATH)
    connection = None
    if path.is_file():
        try:
            connection = sqlite3.connect(_readonly_uri(path), uri=True)
        except sqlite3.Error:
            connection = None
    _CACHE["ro"] = connection
    return connection


def _readonly_uri(path: Path) -> str:
    """只读连接串：无未合并 WAL 时用 `immutable=1`，避免创建 `-shm` / `-wal`。"""
    wal = Path(f"{path}-wal")
    has_pending_wal = wal.is_file() and wal.stat().st_size > 0
    options = "mode=ro" if has_pending_wal else "mode=ro&immutable=1"
    return f"file:{Path(path).as_posix()}?{options}"


def _sheet_has_labels(path: Path, column: str) -> bool:
    """回收表里是否已经存在人工填写的标签（用于避免覆盖人工核验结果）。"""
    if not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return any((row.get(column) or "").strip() for row in csv.DictReader(handle))
    except (OSError, csv.Error):
        return True   # 读不动就当它有价值，别覆盖


def _corpus_probe(case: dict) -> dict | None:
    """只读探测：预期文档是否存在、预期词在语料里出现多少个分块。

    这是**词法与存在性信号**，不是"证据充分"的判定；结论仍由人工给出。
    """
    connection = _ro_connection()
    if connection is None:
        return None
    probe: dict[str, dict] = {"document_existence": {}, "term_chunk_hits": {},
                              "note": "只读词法探测：仅表示语料中是否出现，不代表证据充分。"}
    for key in (case.get("expected_document_keys") or [])[:8]:
        row = connection.execute(
            "select count(*) from rag_documents where document_key = ?", (key,)).fetchone()
        probe["document_existence"][key] = int(row[0])
    for term in (case.get("expected_answer_terms") or [])[:8]:
        text = str(term).strip()
        if not text:
            continue
        row = connection.execute(
            "select count(*) from rag_chunks where lower(text) like ?",
            (f"%{text.casefold()}%",)).fetchone()
        probe["term_chunk_hits"][text] = int(row[0])
    return probe


def _osv_index() -> dict[str, tuple[str, dict]]:
    if "osv" in _CACHE:
        return _CACHE["osv"]
    index: dict[str, tuple[str, dict]] = {}
    directory = config.SNAPSHOT_DIR / "osv"
    if not directory.is_dir():
        return index
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        if isinstance(payload, dict) and payload.get("id"):
            index[str(payload["id"])] = (path.name, payload)
    _CACHE["osv"] = index
    return index


def _msrc_index() -> dict[str, tuple[str, str, dict]]:
    """CVE → (快照文件, 文档标题, Vulnerability 记录)。"""
    if "msrc" in _CACHE:
        return _CACHE["msrc"]
    index: dict[str, tuple[str, str, dict]] = {}
    directory = config.SNAPSHOT_DIR / "msrc"
    if not directory.is_dir():
        return index
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        title = str((payload.get("DocumentTitle") or {}).get("Value") or path.name)
        for vuln in payload.get("Vulnerability") or []:
            cve = str(vuln.get("CVE") or "")
            if cve:
                index[cve] = (path.name, title, vuln)
    _CACHE["msrc"] = index
    return index


def _nvd_index() -> dict[str, tuple[str, dict]]:
    """CVE → (快照文件, cve 记录)，来源为 NVD 2.0 API 的 vulnerabilities[]。"""
    if "nvd" in _CACHE:
        return _CACHE["nvd"]
    index: dict[str, tuple[str, dict]] = {}
    directory = config.SNAPSHOT_DIR / "nvd"
    if not directory.is_dir():
        return index
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        for item in payload.get("vulnerabilities") or []:
            cve = (item or {}).get("cve") or {}
            if cve.get("id"):
                index[str(cve["id"])] = (path.name, cve)
    _CACHE["nvd"] = index
    return index


def _openalex_index() -> tuple[str, dict[str, dict]]:
    """OpenAlex 结果快照 → (文件名, {W-id: work})。"""
    if "openalex" in _CACHE:
        return _CACHE["openalex"]
    filename, works = "", {}
    directory = config.SNAPSHOT_DIR / "openalex"
    paths = sorted(directory.glob("*.json")) if directory.is_dir() else []
    if paths:
        filename = paths[0].name
        try:
            payload = json.loads(paths[0].read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            payload = {}
        for work in payload.get("results") or []:
            key = str((work or {}).get("id") or "").rstrip("/").split("/")[-1]
            if key:
                works[key] = work
    _CACHE["openalex"] = (filename, works)
    return _CACHE["openalex"]


def _work_urls(work: dict) -> set[str]:
    """收集 OpenAlex work 记录里所有可比较的链接（PDF/落地页/DOI）。"""
    urls: set[str] = set()

    def add(value) -> None:
        if isinstance(value, str) and value:
            urls.add(value)

    locations = [work.get("primary_location"), work.get("best_oa_location")]
    locations += list(work.get("locations") or [])
    for location in locations:
        if isinstance(location, dict):
            add(location.get("pdf_url"))
            add(location.get("landing_page_url"))
    add((work.get("open_access") or {}).get("oa_url"))
    content = work.get("content_urls")
    if isinstance(content, dict):
        for key in ("pdf", "landing_page", "grobid"):
            item = content.get(key)
            if isinstance(item, dict):
                add(item.get("url"))
    add(work.get("doi"))
    add((work.get("ids") or {}).get("doi"))
    return urls


def _rag_documents() -> dict[str, dict]:
    """RAG 文档清单（只读）：document_key → {title, source_id, chunks}。"""
    if "docs" in _CACHE:
        return _CACHE["docs"]
    index: dict[str, dict] = {}
    connection = _ro_connection()
    if connection is not None:
        try:
            for key, title, source, chunks in connection.execute(
                    "select d.document_key, d.title, d.source_id, count(c.id) "
                    "from rag_documents d left join rag_chunks c on c.document_id = d.id "
                    "group by d.id"):
                index[str(key)] = {"title": title, "source_id": source,
                                   "chunks": int(chunks or 0)}
        except sqlite3.Error:
            index = {}
    _CACHE["docs"] = index
    return index


def _event_docs() -> dict[str, dict]:
    """事件原始 JSON（只读）：event_id → 事件文档。"""
    if "events" in _CACHE:
        return _CACHE["events"]
    index: dict[str, dict] = {}
    connection = _ro_connection()
    if connection is not None:
        try:
            for event_id, doc in connection.execute("select id, doc from events"):
                try:
                    index[str(event_id)] = json.loads(doc)
                except (TypeError, ValueError):
                    continue
        except sqlite3.Error:
            index = {}
    _CACHE["events"] = index
    return index


def _mitre_index() -> dict[str, dict]:
    """MITRE CVE 记录 → {cveId: cna.affected[0]}。"""
    if "mitre" in _CACHE:
        return _CACHE["mitre"]
    index: dict[str, dict] = {}
    directory = config.SNAPSHOT_DIR / "mitre_cve"
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            payload = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        cve_id = str((payload.get("cveMetadata") or {}).get("cveId") or "")
        affected = ((payload.get("containers") or {}).get("cna") or {}).get("affected") or []
        if cve_id and affected:
            index[cve_id] = {"file": path.name, "affected": affected}
    _CACHE["mitre"] = index
    return index


def _kev_index() -> dict[str, dict]:
    """CISA KEV 目录 → {cveID: 记录}。"""
    if "kev" in _CACHE:
        return _CACHE["kev"]
    index: dict[str, dict] = {}
    directory = config.SNAPSHOT_DIR / "cisa_kev"
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            payload = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        for item in payload.get("vulnerabilities") or []:
            cve = str((item or {}).get("cveID") or "")
            if cve:
                index[cve] = {"file": path.name, "record": item}
    _CACHE["kev"] = index
    return index


def _derive_range_from_versions(versions: list) -> str | None:
    """把 `{version, lessThan}` 形式的版本声明还原成区间字符串。"""
    for item in versions or []:
        if not isinstance(item, dict):
            continue
        lower = item.get("version")
        upper = item.get("lessThan")
        if upper:
            if lower in (None, ""):
                return f"< {upper}"
            return f">= {lower}, < {upper}"
        if lower not in (None, "", "0", 0):
            return f">= {lower}"
    return None


def _derive_range_from_ranges(ranges: list) -> str | None:
    """把 OSV `{introduced, fixed}` 事件还原成区间字符串。"""
    introduced = fixed = None
    for rng in ranges or []:
        for event in (rng or {}).get("events") or []:
            if "introduced" in event:
                introduced = str(event["introduced"])
            if "fixed" in event:
                fixed = str(event["fixed"])
    if fixed and introduced and introduced != "0":
        return f">= {introduced}, < {fixed}"
    if fixed:
        return f"< {fixed}"
    return None


def build_paper_link(case: dict, review: dict) -> dict:
    """paper_link：事件保存的论文链接是否被本地 OpenAlex 记录直接支持。"""
    value = case["candidate_value"]
    filename, works = _openalex_index()
    subject = str(case["subject"])
    work_id = subject.split("-", 1)[1] if "-" in subject else subject
    work = works.get(work_id)
    record = {
        "item_id": case["relation_id"], "item_type": "relation",
        "category": "paper_link", "subject": subject, "relation": case["relation"],
        "object": case["object"], "candidate_value": value,
        "auto_judgment": review.get("auto_judgment"),
        "auto_reason": review.get("auto_reason"),
        "auto_confidence": review.get("auto_confidence"),
        "rules": [f"{r['rule']}={r['result']}: {r['detail']}"
                  for r in review.get("auto_rules") or []],
        "verification_method": case.get("verification_method"),
        "evidence_status": "missing", "evidence_location": None,
        "evidence_fragment": None, "conflicts": [], "gaps": [],
        "questions_for_human": [
            f"OpenAlex 记录中的链接是否就是候选 PDF 链接 {value.get('pdf_url')}？",
            "该论文与事件的题目/主题是否为同一工作？",
            "本地是否已有该论文全文可用于交叉核验？",
        ],
    }
    pdf_url = str(value.get("pdf_url") or "")
    if not work:
        record["gaps"].append("本地 OpenAlex 快照中没有该 work 记录，无法核对链接。")
        return record
    urls = _work_urls(work)
    if pdf_url in urls:
        match = "exact"
    elif value.get("arxiv_id") and any(str(value["arxiv_id"]) in url for url in urls):
        match = "normalized"
    else:
        match = "none"
    record["evidence_location"] = f"snapshots/openalex/{filename} → results[id={work_id}]"
    record["evidence_fragment"] = _clip(json.dumps({
        "id": work.get("id"), "doi": work.get("doi"),
        "title": work.get("display_name") or work.get("title"),
        "publication_year": work.get("publication_year"), "type": work.get("type"),
        "open_access": work.get("open_access"),
        "primary_location": {
            "landing_page_url": ((work.get("primary_location") or {}).get("landing_page_url")),
            "pdf_url": ((work.get("primary_location") or {}).get("pdf_url")),
        },
        "has_fulltext": work.get("has_fulltext"),
    }, ensure_ascii=False))
    if match == "exact":
        record["evidence_status"] = "direct"
    elif match == "normalized":
        record["evidence_status"] = "indirect"
        record["gaps"].append("候选链接与记录中的链接只是同一 arXiv ID 的不同形式（未逐字相同）。")
    else:
        record["evidence_status"] = "conflict"
        record["conflicts"].append("候选 PDF 链接未出现在该 work 记录的链接集合中。")
    document_key = value.get("linked_document_key")
    if document_key:
        info = _rag_documents().get(str(document_key))
        if info:
            record["evidence_fragment"] += (
                f" ｜ 本地 RAG 文档 {document_key}：标题={info['title']}，"
                f"分块={info['chunks']}（可交叉核验主题）")
        else:
            record["conflicts"].append(
                f"候选声明已关联 RAG 文档 {document_key}，但库中不存在该文档。")
    else:
        record["gaps"].append(
            "非 arXiv 链接未抓取全文：本地没有对应 RAG 文档，"
            "「论文与事件主题一致」无法本地核验。")
    return record


def build_version_range(case: dict, review: dict) -> dict:
    """version_range：候选 package/ecosystem/range 三元组是否有来源证据。"""
    value = case["candidate_value"]
    event_id = str(case["subject"])
    doc = _event_docs().get(event_id) or {}
    affected = [a for a in (doc.get("affected") or []) if isinstance(a, dict)]
    matches = [a for a in affected
               if str(a.get("package")) == str(value.get("package"))
               and str(a.get("ecosystem")) == str(value.get("ecosystem"))]
    record = {
        "item_id": case["relation_id"], "item_type": "relation",
        "category": "version_range", "subject": event_id, "relation": case["relation"],
        "object": case["object"], "candidate_value": value,
        "auto_judgment": review.get("auto_judgment"),
        "auto_reason": review.get("auto_reason"),
        "auto_confidence": review.get("auto_confidence"),
        "rules": [f"{r['rule']}={r['result']}: {r['detail']}"
                  for r in review.get("auto_rules") or []],
        "verification_method": case.get("verification_method"),
        "evidence_status": "missing", "evidence_location": None,
        "evidence_fragment": None, "conflicts": [], "gaps": [],
        "questions_for_human": [
            f"事件保存的三元组（package/ecosystem/range）是否与来源一致？",
            f"候选 range={value.get('range')!r} 是具体区间还是「来源未提供」？",
            "若区间来自结构化字段，能否用上游原始字段复核？",
        ],
    }
    if not matches:
        record["gaps"].append("事件文档里找不到与候选 package/ecosystem 匹配的 affected 记录。")
        if affected:
            record["evidence_fragment"] = _clip(json.dumps(affected, ensure_ascii=False))
        return record
    entry = matches[0]
    source_id = str(entry.get("source_id") or "")
    stored_range = str(entry.get("range"))
    record["evidence_location"] = f"intel.sqlite → events[{event_id}].doc.affected[]" + (
        f"（source_id={source_id}）" if source_id else "")
    record["evidence_fragment"] = _clip(json.dumps(entry, ensure_ascii=False))
    if stored_range == str(value.get("range")):
        record["evidence_status"] = "direct"
    else:
        record["evidence_status"] = "conflict"
        record["conflicts"].append(
            f"事件保存的 range={stored_range} 与候选 range={value.get('range')} 不一致。")
    if source_id.startswith("osv:"):
        osv_entry = _osv_index().get(event_id)
        if osv_entry:
            ranges = []
            for item in (osv_entry[1].get("affected") or []):
                if str((item.get("package") or {}).get("name")) == str(value.get("package")):
                    ranges.extend(item.get("ranges") or [])
            derived = _derive_range_from_ranges(ranges)
            record["evidence_fragment"] += (
                f" ｜ snapshots/osv/{osv_entry[0]} → affected[].ranges[].events："
                f"{json.dumps(ranges, ensure_ascii=False)}（推导区间={derived}）")
            if derived and derived != str(value.get("range")):
                record["conflicts"].append(
                    f"由 OSV 结构化事件推导的区间={derived} 与候选={value.get('range')} 不一致。")
    elif source_id.startswith("msrc:"):
        msrc_entry = _msrc_index().get(event_id)
        if msrc_entry:
            vuln = msrc_entry[2]
            record["evidence_fragment"] += (
                f" ｜ snapshots/msrc/{msrc_entry[0]} → Vulnerability[CVE={event_id}]："
                f"标题={((vuln.get('Title') or {}).get('Value'))}、"
                f"ProductStatuses={json.dumps(vuln.get('ProductStatuses'), ensure_ascii=False)}"
                "（无版本区间字段）")
        record["gaps"].append(
            "MSRC CVRF 记录不含版本区间字段（ProductStatuses 只给产品 ID 与状态类型、"
            "无版本号），候选 range=unknown 与来源一致，但不构成对具体受影响区间的证据。")
    elif source_id.startswith("kev:"):
        kev_entry = _kev_index().get(event_id)
        if kev_entry:
            item = kev_entry["record"]
            record["evidence_fragment"] += (
                f" ｜ snapshots/cisa_kev/{kev_entry['file']} → "
                f"vulnerabilities[cveID={event_id}]："
                f"vendor={item.get('vendorProject')}、product={item.get('product')}、"
                f"dateAdded={item.get('dateAdded')}、dueDate={item.get('dueDate')}、"
                f"requiredAction={_clip(str(item.get('requiredAction') or ''), 200)}"
                "（无版本区间字段）")
        record["gaps"].append(
            "CISA KEV 目录只给厂商/产品与处置要求，不含版本区间；候选 range=unknown 与来源一致，"
            "但不构成对具体受影响区间的证据。")
    elif source_id.startswith("mitre:"):
        mitre = _mitre_index().get(event_id)
        if mitre:
            versions = (mitre["affected"][0] or {}).get("versions") or []
            derived = _derive_range_from_versions(versions)
            record["evidence_fragment"] += (
                f" ｜ snapshots/mitre_cve/{mitre['file']} → containers.cna.affected[].versions："
                f"{json.dumps(versions, ensure_ascii=False)}（推导区间={derived}）")
            if derived and derived != str(value.get("range")):
                record["conflicts"].append(
                    f"由 MITRE 记录推导的区间={derived} 与候选={value.get('range')} 不一致。")
    return record


def build_fixed_version(case: dict, review: dict, osv: dict) -> dict:
    value = case["candidate_value"]
    entry = osv.get(case["subject"])
    record = {
        "item_id": case["relation_id"],
        "item_type": "relation",
        "category": "fixed_version",
        "subject": case["subject"],
        "relation": case["relation"],
        "object": case["object"],
        "candidate_value": value,
        "auto_judgment": review.get("auto_judgment"),
        "auto_reason": review.get("auto_reason"),
        "auto_confidence": review.get("auto_confidence"),
        "rules": [f"{r['rule']}={r['result']}: {r['detail']}"
                  for r in review.get("auto_rules") or []],
        "verification_method": case.get("verification_method"),
        "evidence_status": "missing",
        "evidence_location": None,
        "evidence_fragment": None,
        "conflicts": [],
        "questions_for_human": [],
    }
    if not entry:
        record["questions_for_human"].append(
            "本地没有该事件的 OSV 结构化快照：无法核对修复版本，请人工到上游来源确认。")
        return record
    filename, payload = entry
    record["evidence_location"] = f"snapshots/osv/{filename} → affected[].ranges[].events[].fixed"
    fixed_values: list[str] = []
    fragments: list[str] = []
    for affected in payload.get("affected") or []:
        package = (affected.get("package") or {}).get("name")
        if str(package or "").casefold() != str(value.get("package") or "").casefold():
            continue
        for rng in affected.get("ranges") or []:
            events = rng.get("events") or []
            fragments.append(json.dumps({"package": package, "ranges": {"type": rng.get("type"),
                                                                        "events": events}},
                                        ensure_ascii=False))
            fixed_values.extend(str(e["fixed"]) for e in events if "fixed" in e)
    if fragments:
        record["evidence_status"] = "direct"
        record["evidence_fragment"] = _clip(" ｜ ".join(fragments))
    if len(set(fixed_values)) > 1:
        record["conflicts"].append(
            f"同一记录内存在多个 fixed 值：{sorted(set(fixed_values))}，需确认哪一个是最终修复版本。")
    record["questions_for_human"] = [
        f"OSV 声明的 fixed 是否为 {value.get('fixed_version')}？",
        "受影响区间的下界是否为 0（即所有早期版本都受影响）？",
        "该修复版本与候选的 package/ecosystem 是否对应同一产品？",
    ]
    return record


def build_cvss(case: dict, review: dict, msrc: dict) -> dict:
    value = case["candidate_value"]
    entry = msrc.get(case["subject"])
    record = {
        "item_id": case["relation_id"],
        "item_type": "relation",
        "category": "cvss",
        "subject": case["subject"],
        "relation": case["relation"],
        "object": case["object"],
        "candidate_value": value,
        "auto_judgment": review.get("auto_judgment"),
        "auto_reason": review.get("auto_reason"),
        "auto_confidence": review.get("auto_confidence"),
        "rules": [f"{r['rule']}={r['result']}: {r['detail']}"
                  for r in review.get("auto_rules") or []],
        "verification_method": case.get("verification_method"),
        "evidence_status": "missing",
        "evidence_location": None,
        "evidence_fragment": None,
        "conflicts": [],
        "questions_for_human": [],
    }
    if not entry:
        return _build_cvss_from_osv(case, record) or _build_cvss_from_nvd(case, record)
    filename, doc_title, vuln = entry
    sets = vuln.get("CVSSScoreSets") or []
    record["evidence_location"] = (
        f"snapshots/msrc/{filename} → Vulnerability[CVE={vuln.get('CVE')}].CVSSScoreSets")
    if sets:
        record["evidence_status"] = "direct"
        record["evidence_fragment"] = _clip(
            f"文档：{doc_title}｜标题：{(vuln.get('Title') or {}).get('Value')}"
            f"｜CVSSScoreSets={json.dumps(sets, ensure_ascii=False)}")
    scores = [s.get("BaseScore") for s in sets if s.get("BaseScore") is not None]
    vectors = [str(s.get("Vector") or "") for s in sets if s.get("Vector")]
    if len(set(scores)) > 1:
        record["conflicts"].append(f"同一 CVE 有多个 BaseScore：{sorted(set(scores))}")
    if len(set(vectors)) > 1:
        record["conflicts"].append("同一 CVE 有多个不同的 CVSS 向量")
    _check_vector_match(record, vectors, source="MSRC")
    if sets and sets[0].get("TemporalScore"):
        record["conflicts"].append(
            f"该记录带 TemporalScore={sets[0]['TemporalScore']}；候选只保存 BaseScore，"
            "需确认口径是基础分还是时序分。")
    record["questions_for_human"] = [
        f"候选 score={value.get('score')} 是否等于 MSRC 的 BaseScore？",
        "候选 vector 与 MSRC 的 Vector 是否逐字一致（含 E/RL/RC 时序分量）？",
        "候选 version 与向量前缀（如 CVSS:3.1）是否一致？",
    ]
    return record


def _check_vector_match(record: dict, vectors: list[str], source: str) -> None:
    """把候选向量与证据向量逐字比对，不一致时写入冲突提示（不做主观裁定）。"""
    candidate = str((record.get("candidate_value") or {}).get("vector") or "")
    if not candidate or not vectors:
        return
    if candidate not in vectors:
        record["conflicts"].append(
            f"候选 vector 与 {source} 记录不一致：候选={candidate}；证据={vectors}")


def _build_cvss_from_osv(case: dict, record: dict) -> dict:
    entry = _osv_index().get(case["subject"])
    if not entry:
        return {}
    filename, payload = entry
    severity = payload.get("severity") or []
    record["evidence_location"] = f"snapshots/osv/{filename} → severity[].score"
    if severity:
        record["evidence_status"] = "direct"
        summary = _clip(str(payload.get("summary") or payload.get("details") or ""), 320)
        record["evidence_fragment"] = _clip(
            f"OSV id={payload.get('id')}｜severity={json.dumps(severity, ensure_ascii=False)}"
            f"｜summary/details={summary}")
        vectors = [str(s.get("score") or "") for s in severity if s.get("score")]
        _check_vector_match(record, vectors, source="OSV")
        if len({str(s.get("type") or "") for s in severity}) > 1:
            record["conflicts"].append("OSV 记录了多种 CVSS 类型，需确认以哪一条为准。")
    if (record.get("candidate_value") or {}).get("score") is None:
        record["conflicts"].append("候选只保存了向量、未保存基础分（score=null），无法核对分数。")
    record["questions_for_human"] = [
        f"OSV severity 中的向量是否为 {str((case['candidate_value'] or {}).get('vector'))[:48]}…？",
        "候选 score=null 是「上游未提供基础分」还是「采集遗漏」？",
        "候选 version 与 OSV severity type（CVSS_V3 / CVSS_V4）是否对应？",
    ]
    return record


def _build_cvss_from_nvd(case: dict, record: dict) -> dict:
    entry = _nvd_index().get(case["subject"])
    if not entry:
        record["questions_for_human"].append(
            "本地 MSRC / OSV / NVD 快照中都没有该 CVE：无法核对分数与向量。")
        return record
    filename, cve = entry
    metrics = cve.get("metrics") or {}
    vectors: list[str] = []
    scores: list[float] = []
    fragments: list[dict] = []
    for key in sorted(metrics):
        for metric in metrics[key] or []:
            data = metric.get("cvssData") or {}
            if data.get("vectorString"):
                vectors.append(str(data["vectorString"]))
            if data.get("baseScore") is not None:
                scores.append(data["baseScore"])
            fragments.append({
                "metric": key, "source": metric.get("source"), "type": metric.get("type"),
                "cvssData": data, "baseSeverity": metric.get("baseSeverity"),
            })
    record["evidence_location"] = (
        f"snapshots/nvd/{filename} → cve[{cve.get('id')}].metrics.*[].cvssData")
    if fragments:
        description = ""
        for item in cve.get("descriptions") or []:
            if item.get("lang") == "en":
                description = str(item.get("value") or "")
                break
        record["evidence_status"] = "direct"
        record["evidence_fragment"] = _clip(
            f"NVD cve={cve.get('id')}｜描述：{description}｜"
            f"metrics={json.dumps(fragments, ensure_ascii=False)}")
        _check_vector_match(record, vectors, source="NVD")
        if len(set(scores)) > 1:
            record["conflicts"].append(f"NVD 记录了多个 baseScore：{sorted(set(scores))}")
        if any(m.get("type") == "Secondary" for m in
               [f for k in metrics for f in (metrics[k] or [])]):
            record["conflicts"].append("NVD 该条仅由 Secondary 来源（非 NVD 自评）提供 CVSS。")
    record["questions_for_human"] = [
        f"候选 score={record['candidate_value'].get('score')} 是否等于 NVD 的 baseScore？",
        "候选 vector 与 NVD vectorString 是否逐字一致？",
        "该 CVSS 记录来自 Primary 还是 Secondary 来源，是否可接受？",
    ]
    return record


def _qa_priority(case: dict) -> tuple:
    """问答核验优先级：指定的拒答题 > 应拒答 > 多轮追问 > 带推理步骤 > 其余。"""
    return (
        0 if case["question_id"] in PRIORITY_QA else 1,
        0 if case.get("should_refuse") else 1,
        0 if case.get("history") else 1,
        0 if case.get("expected_reasoning_steps") else 1,
        case["question_id"],
    )


def build_qa(case: dict, record: dict, review: dict) -> dict:
    citations = record.get("citations_detail") or []
    return {
        "item_id": case["question_id"],
        "item_type": "qa",
        "category": case["category"],
        "subject": case["question"],
        "should_refuse": case["should_refuse"],
        "actually_refused": record.get("refused"),
        "expected_answer_terms": case["expected_answer_terms"],
        "expected_document_keys": case["expected_document_keys"],
        "system_answer": record.get("answer_full") or record.get("answer_head") or "",
        "signals": {
            "document_hit": record.get("document_hit"),
            "term_hit": record.get("term_hit"),
            "citations_retrievable": record.get("citations_retrievable"),
            "document_citation_count": record.get("document_citation_count"),
            "error": record.get("error"),
            "timeout": record.get("timeout"),
        },
        "corpus_probe": _corpus_probe(case),
        "auto_judgment": review.get("auto_judgment"),
        "auto_reason": review.get("auto_reason"),
        "auto_confidence": review.get("auto_confidence"),
        "rules": [f"{r['rule']}={r['result']}: {r['detail']}"
                  for r in review.get("auto_rules") or []],
        "evidence_status": "direct" if citations else "none",
        "citations": [{
            "chunk_id": c.get("chunk_id"),
            "document_key": c.get("document_key"),
            "char_start": c.get("char_start"),
            "char_end": c.get("char_end"),
            "quote": c.get("quote") or "",
        } for c in citations],
        "questions_for_human": [
            "系统答案是否为问题所问（而非答非所问或过度概括）？",
            "每条引用片段是否真的支持答案中的对应结论？",
            "是否遗漏关键条件（版本、暴露面、触发条件）？",
            "若应拒答：当前回答是否属于用摘录冒充结论？",
        ] + ([] if citations else [
            "该题系统未返回任何引用：请确认语料中是否本就缺少所需证据，拒答是否正当。"]),
    }


def _render_relation(packet: dict) -> str:
    lines = [
        f"### {packet['item_id']} · {packet['category']}",
        "",
        f"- **主体 / 关系 / 客体**：`{packet['subject']}` / `{packet['relation']}` / `{packet['object']}`",
        f"- **候选值**：`{json.dumps(packet['candidate_value'], ensure_ascii=False)}`",
        f"- **自动核验**：`{packet['auto_judgment']}`（{packet['auto_confidence']}）",
        f"- **自动理由**：{packet['auto_reason']}",
        f"- **证据状态**：**{packet['evidence_status']}**",
        f"- **证据定位**：`{packet['evidence_location'] or '（缺失）'}`",
    ]
    if packet["evidence_fragment"]:
        lines += ["", "**证据片段（原文）**：", "", "```", packet["evidence_fragment"], "```"]
    else:
        lines += ["", "**证据片段**：⚠️ 本地无可读取的直接证据，已标注为缺失。"]
    if packet["rules"]:
        lines += ["", "**自动规则明细**："] + [f"- `{r}`" for r in packet["rules"]]
    if packet["conflicts"]:
        lines += ["", "**⚠️ 冲突提示**："] + [f"- {c}" for c in packet["conflicts"]]
    lines += ["", "**需要人工确认的问题**："] + [f"1. {q}" for q in packet["questions_for_human"]]
    lines += [
        "",
        f"**判定规则**：{packet['verification_method']}",
        "",
        "**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _render_qa(packet: dict) -> str:
    lines = [
        f"### {packet['item_id']} · {packet['category']}",
        "",
        f"- **问题**：{packet['subject']}",
        f"- **预期**：{'应拒答' if packet['should_refuse'] else '应回答'}"
        f"｜**实际**：{'拒答' if packet['actually_refused'] else '作答'}",
        f"- **预期答案要点**：`{' / '.join(packet['expected_answer_terms']) or '（无）'}`",
        f"- **预期文档**：`{' / '.join(packet['expected_document_keys']) or '（无）'}`",
        f"- **自动评审**：`{packet['auto_judgment']}`（{packet['auto_confidence']}）｜{packet['auto_reason']}",
        f"- **证据状态**：**{packet['evidence_status']}**（{len(packet['citations'])} 条引用）",
        f"- **自动信号（非人工结论）**：文档命中={packet['signals']['document_hit']}"
        f"｜词命中={packet['signals']['term_hit']}"
        f"｜引用可取出={packet['signals']['citations_retrievable']}"
        f"｜异常={packet['signals']['error']}｜超时={packet['signals']['timeout']}",
        "",
        "**系统实际回答**：",
        "",
        "```",
        _clip(packet["system_answer"], 700),
        "```",
    ]
    if packet["citations"]:
        lines += ["", "**引用证据（逐条）**：", ""]
        for citation in packet["citations"]:
            lines += [
                f"- `{citation['chunk_id']}` ｜ 文档 `{citation['document_key']}` "
                f"｜ 字符 {citation['char_start']}–{citation['char_end']}",
                f"  > {_clip(citation['quote'], 260).replace(chr(10), ' ')}",
            ]
    else:
        lines += ["", "**引用证据**：无（系统未返回任何文档引用）。"]
    probe = packet.get("corpus_probe")
    if probe:
        docs = "、".join(f"{k}={v}" for k, v in probe["document_existence"].items()) or "（无）"
        terms = "、".join(f"{k}={v}" for k, v in probe["term_chunk_hits"].items()) or "（无）"
        lines += ["",
                  "**语料只读探测（词法信号，非结论）**：",
                  f"- 预期文档在库中条数：{docs}",
                  f"- 预期词在分块中出现次数：{terms}"]
    if packet["rules"]:
        lines += ["", "**自动规则明细**："] + [f"- `{r}`" for r in packet["rules"]]
    lines += ["", "**需要人工确认的问题**："] + [f"1. {q}" for q in packet["questions_for_human"]]
    lines += [
        "",
        "**人工填写**：最终判定 = ______ ｜ 引用支持性 = ______ ｜ 核验人 = ______ "
        "｜ 核验时间 = ______ ｜ 备注 = ______",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def _render_remaining(packet: dict) -> str:
    lines = [
        f"### {packet['item_id']} · {packet['category']}",
        "",
        f"- **主体 / 关系 / 客体**：`{packet['subject']}` / `{packet['relation']}` / `{packet['object']}`",
        f"- **候选值**：`{json.dumps(packet['candidate_value'], ensure_ascii=False)}`",
        f"- **自动核验**：`{packet['auto_judgment']}`（{packet['auto_confidence']}）",
        f"- **证据状态**：**{packet['evidence_status']}**",
        f"- **证据定位**：`{packet['evidence_location'] or '（缺失）'}`",
    ]
    if packet["evidence_fragment"]:
        lines += ["", "**证据片段（原文）**：", "", "```", packet["evidence_fragment"], "```"]
    else:
        lines += ["", "**证据片段**：⚠️ 本地无可读取的直接证据，已标注为缺失。"]
    if packet["rules"]:
        lines += ["", "**自动规则明细**："] + [f"- `{r}`" for r in packet["rules"]]
    if packet["conflicts"]:
        lines += ["", "**⚠️ 冲突提示**："] + [f"- {c}" for c in packet["conflicts"]]
    if packet["gaps"]:
        lines += ["", "**主要缺口**："] + [f"- {g}" for g in packet["gaps"]]
    lines += ["", "**需要人工确认的问题**："] + [f"1. {q}" for q in packet["questions_for_human"]]
    lines += [
        "",
        f"**判定规则**：{packet['verification_method']}",
        "",
        "**人工填写**：最终标签 = ______ ｜ 核验人 = ______ ｜ 核验时间 = ______ ｜ 备注 = ______",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def build_qa_gold_row(packet: dict, case: dict, record: dict) -> dict:
    """把一条问答证据包摊平成人工金标准工作表的一行（人工列全部留空）。"""
    citations = packet.get("citations") or []
    probe = packet.get("corpus_probe") or {}
    docs = "；".join(f"{k}={v}" for k, v in (probe.get("document_existence") or {}).items())
    terms = "；".join(f"{k}={v}" for k, v in (probe.get("term_chunk_hits") or {}).items())
    excerpt = " ｜ ".join(
        f"[{c['chunk_id']}] {_clip(c.get('quote') or '', 200)}" for c in citations[:5])
    row = {
        "question_id": case["question_id"],
        "category": case["category"],
        "difficulty": case.get("difficulty"),
        "question": case["question"],
        "has_history": bool(case.get("history")),
        "expected_action": "应拒答" if case["should_refuse"] else "应回答",
        "should_refuse": str(bool(case["should_refuse"])),
        "expected_answer_terms": "；".join(case.get("expected_answer_terms") or []),
        "expected_document_keys": "；".join(case.get("expected_document_keys") or []),
        "expected_event_ids": "；".join(case.get("expected_event_ids") or []),
        "expected_reasoning_steps": " → ".join(case.get("expected_reasoning_steps") or []),
        "system_answer": _clip(packet.get("system_answer") or "", 1200),
        "system_refused": str(bool(record.get("refused"))),
        "cited_document_keys": "；".join(
            sorted({str(c.get("document_key")) for c in citations if c.get("document_key")})),
        "cited_chunk_ids": "；".join(
            str(c.get("chunk_id")) for c in citations if c.get("chunk_id")),
        "citations_retrievable": str(record.get("citations_retrievable")),
        "answer_from_event_path": str(bool(record.get("related_event_ids"))),
        "auto_judgment": packet.get("auto_judgment"),
        "auto_confidence": packet.get("auto_confidence"),
        "auto_reason": packet.get("auto_reason"),
        "corpus_probe_summary": f"预期文档条数：{docs or '（无）'}；预期词命中块数：{terms or '（无）'}",
        "evidence_excerpt": excerpt,
        "evidence_location": "；".join(
            f"{c.get('chunk_id')}@{c.get('document_key')}（{c.get('char_start')}–{c.get('char_end')}）"
            for c in citations),
        "latency_ms": record.get("latency_ms"),
        "timeout": record.get("timeout"),
        "error": record.get("error"),
    }
    for column in QA_GOLD_HUMAN_COLUMNS:
        row[column] = ""
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="生成带真实证据的人工核验工作包")
    parser.add_argument("--outdir", type=Path, default=ARTIFACTS)
    parser.add_argument("--source-data-dir", type=Path, default=SOURCE_DATA_DIR)
    args = parser.parse_args()

    if not (args.source_data_dir / "intel.sqlite").is_file():
        print("找不到数据库:", args.source_data_dir / "intel.sqlite")
        return 2
    config.DATA_DIR = args.source_data_dir
    config.SNAPSHOT_DIR = args.source_data_dir / "snapshots"
    config.DB_PATH = args.source_data_dir / "intel.sqlite"

    candidates = {c["relation_id"]: c for c in json.loads(
        (ROOT / "evaluation" / "b_relation_candidates.json").read_text(encoding="utf-8"))["cases"]}
    rel_review = {c["item_id"] if "item_id" in c else c["relation_id"]: c for c in json.loads(
        (ARTIFACTS / "relation_auto_review.json").read_text(encoding="utf-8"))["cases"]}
    osv = _osv_index()
    msrc = _msrc_index()

    fixed = [build_fixed_version(candidates[r], rel_review[r], osv)
             for r in sorted(candidates) if candidates[r]["dimension"] == "fixed_version"]
    cvss = [build_cvss(candidates[r], rel_review[r], msrc)
            for r in sorted(candidates) if candidates[r]["dimension"] == "cvss"]

    relation_md = ["# 关系证据核验工作包", "",
                   f"生成自本地快照与自动核验结果；共 {len(fixed) + len(cvss)} 条。"
                   "**标签列一律留空，等待人工填写。**", "", "---", "",
                   f"## 一、fixed_version（{len(fixed)} 条）", ""]
    relation_md += [_render_relation(p) for p in fixed]
    relation_md += [f"## 二、CVSS（{len(cvss)} 条）", ""]
    relation_md += [_render_relation(p) for p in cvss]
    (args.outdir / "evidence_packet_relations.md").write_text(
        "\n".join(relation_md), encoding="utf-8")

    # 剩余 87 条：paper_link 37 + version_range 50（独立文件，互不覆盖）
    paper = [build_paper_link(candidates[r], rel_review[r])
             for r in sorted(candidates) if candidates[r]["dimension"] == "paper_link"]
    version = [build_version_range(candidates[r], rel_review[r])
               for r in sorted(candidates) if candidates[r]["dimension"] == "version_range"]
    remaining_md = ["# 剩余关系证据工作包（paper_link / version_range）", "",
                    f"共 {len(paper) + len(version)} 条 = paper_link {len(paper)} + "
                    f"version_range {len(version)}。**标签列一律留空，等待人工填写。**",
                    "", "---", "", f"## 一、paper_link（{len(paper)} 条）", ""]
    remaining_md += [_render_remaining(p) for p in paper]
    remaining_md += [f"## 二、version_range（{len(version)} 条）", ""]
    remaining_md += [_render_remaining(p) for p in version]
    (args.outdir / "evidence_packet_remaining.md").write_text(
        "\n".join(remaining_md), encoding="utf-8")

    dataset = json.loads(QA_DATASET.read_text(encoding="utf-8"))
    qa_results = {r["question_id"]: r for r in json.loads(
        (ARTIFACTS / "formal_qa_results.json").read_text(encoding="utf-8"))["records"]}
    qa_review = {r["question_id"]: r for r in json.loads(
        (ARTIFACTS / "qa_auto_review.json").read_text(encoding="utf-8"))["cases"]}
    # 优先级：指定的 6 道拒答重点题 > 应拒答 > 多轮追问 > 带推理步骤 > 其余
    ordered = sorted(dataset["cases"], key=_qa_priority)[:36]
    qa_packets = [build_qa(c, qa_results.get(c["question_id"], {}),
                           qa_review.get(c["question_id"], {})) for c in ordered]
    qa_md = ["# 问答证据核验工作包", "",
             f"共 {len(qa_packets)} 道高优先级题目；前 6 道为拒答相关重点题。"
             "**判定列一律留空，等待人工填写。**", "", "---", ""]
    qa_md += [_render_qa(p) for p in qa_packets]
    (args.outdir / "evidence_packet_qa.md").write_text("\n".join(qa_md), encoding="utf-8")

    # 全量 50 题：人工金标准工作表 + 证据包（独立文件，不覆盖上面的 36 题产物）
    gold_records = {r["question_id"]: r for r in json.loads(
        (ARTIFACTS / "formal_qa_results.json").read_text(encoding="utf-8"))["records"]}
    gold_packets = [build_qa(c, gold_records.get(c["question_id"], {}),
                             qa_review.get(c["question_id"], {}))
                    for c in dataset["cases"]]
    gold_md = ["# 问答人工金标准证据包（全部 50 题）", "",
               "每题的「标准答案」需要人工填写；本文件只提供系统实际输出、引用原文、"
               "语料只读探测与自动评审判定，**不含任何人工结论**。", "", "---", ""]
    gold_md += [_render_qa(p) for p in gold_packets]
    (args.outdir / "qa_gold_evidence_packet.md").write_text(
        "\n".join(gold_md), encoding="utf-8")
    gold_rows = [build_qa_gold_row(p, c, gold_records.get(c["question_id"], {}))
                 for p, c in zip(gold_packets, dataset["cases"])]
    gold_sheet = args.outdir / "qa_gold_standard_worksheet.csv"
    if _sheet_has_labels(gold_sheet, "人工最终标签"):
        print("⚠️ 已存在人工标签，跳过写入以保护人工核验结果:", gold_sheet)
    else:
        with gold_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=QA_GOLD_SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(gold_rows)

    relation_rows = [{
        "relation_id": p["item_id"], "dimension": p["category"],
        "subject": p["subject"], "relation": p["relation"], "object": p["object"],
        "candidate_value": json.dumps(p["candidate_value"], ensure_ascii=False),
        "auto_judgment": p["auto_judgment"], "auto_confidence": p["auto_confidence"],
        "auto_reason": p["auto_reason"],
        "evidence_status": p["evidence_status"],
        "evidence_location": p["evidence_location"] or "",
        RELATION_LABEL_COLUMN: "", "人工核验人": "", "人工核验时间": "", "人工备注": "",
    } for p in fixed + cvss]
    qa_rows = [{
        "question_id": p["item_id"], "category": p["category"],
        "subject_or_question": p["subject"],
        "auto_judgment": p["auto_judgment"], "auto_confidence": p["auto_confidence"],
        "evidence_status": p["evidence_status"],
        "evidence_location": "；".join(
            f"{c['chunk_id']}@{c['document_key']}" for c in p["citations"]) or "",
        LABEL_COLUMN: "", "人工核验人": "", "人工核验时间": "", "人工备注": "",
    } for p in qa_packets]
    relation_sheet = args.outdir / "evidence_relation_label_sheet.csv"
    if _sheet_has_labels(relation_sheet, RELATION_LABEL_COLUMN):
        print("⚠️ 已存在人工标签，跳过写入以保护人工核验结果:", relation_sheet)
    else:
        with relation_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RELATION_SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(relation_rows)
    qa_sheet = args.outdir / "evidence_qa_label_sheet.csv"
    if _sheet_has_labels(qa_sheet, LABEL_COLUMN):
        print("⚠️ 已存在人工判定，跳过写入以保护人工核验结果:", qa_sheet)
    else:
        with qa_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=QA_SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(qa_rows)

    remaining_rows = [{
        "relation_id": p["item_id"], "dimension": p["category"],
        "subject": p["subject"], "relation": p["relation"], "object": p["object"],
        "candidate_value": json.dumps(p["candidate_value"], ensure_ascii=False),
        "auto_judgment": p["auto_judgment"], "auto_confidence": p["auto_confidence"],
        "evidence_status": p["evidence_status"],
        "evidence_location": p["evidence_location"] or "",
        "证据说明": "；".join(p["conflicts"]) or "本地有可读取证据，见工作包正文",
        "主要缺口": "；".join(p["gaps"]),
        RELATION_LABEL_COLUMN: "", "人工核验人": "", "人工核验时间": "", "人工备注": "",
    } for p in paper + version]
    remaining_sheet = args.outdir / "evidence_remaining_label_sheet.csv"
    if _sheet_has_labels(remaining_sheet, RELATION_LABEL_COLUMN):
        print("⚠️ 已存在人工标签，跳过写入以保护人工核验结果:", remaining_sheet)
    else:
        with remaining_sheet.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REMAINING_SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(remaining_rows)

    all_packets = fixed + cvss + qa_packets
    coverage = {
        "schema_version": "b-evidence-packet-coverage-1.0",
        "artifacts": {
            "relations_markdown": "artifacts/b_eval/evidence_packet_relations.md",
            "qa_markdown": "artifacts/b_eval/evidence_packet_qa.md",
            "relation_label_sheet": "artifacts/b_eval/evidence_relation_label_sheet.csv",
            "qa_label_sheet": "artifacts/b_eval/evidence_qa_label_sheet.csv",
        },
        "counts": {
            "relations_fixed_version": len(fixed),
            "relations_cvss": len(cvss),
            "qa_high_priority": len(qa_packets),
            "total_items": len(all_packets),
            "relations_paper_link": len(paper),
            "relations_version_range": len(version),
            "remaining_total": len(paper) + len(version),
            "qa_gold_questions": len(gold_packets),
        },
        "evidence": {
            "direct": sum(1 for p in all_packets if p["evidence_status"] == "direct"),
            "missing": sum(1 for p in all_packets if p["evidence_status"] == "missing"),
            "none": sum(1 for p in all_packets if p["evidence_status"] == "none"),
            "by_group": {
                "fixed_version": {
                    "direct": sum(1 for p in fixed if p["evidence_status"] == "direct"),
                    "missing": sum(1 for p in fixed if p["evidence_status"] == "missing")},
                "cvss": {
                    "direct": sum(1 for p in cvss if p["evidence_status"] == "direct"),
                    "missing": sum(1 for p in cvss if p["evidence_status"] == "missing")},
                "qa": {
                    "direct": sum(1 for p in qa_packets if p["evidence_status"] == "direct"),
                    "none": sum(1 for p in qa_packets if p["evidence_status"] == "none")},
            },
        },
        "conflicts": {
            "fixed_version": sum(1 for p in fixed if p["conflicts"]),
            "cvss": sum(1 for p in cvss if p["conflicts"]),
            "items": [p["item_id"] for p in fixed + cvss if p["conflicts"]],
        },
        "missing_evidence_items": [p["item_id"] for p in all_packets
                                   if p["evidence_status"] == "missing"],
        "remaining": {
            "paper_link_direct": sum(1 for p in paper if p["evidence_status"] == "direct"),
            "paper_link_other": sum(1 for p in paper if p["evidence_status"] != "direct"),
            "version_range_direct": sum(1 for p in version
                                        if p["evidence_status"] == "direct"),
            "version_range_other": sum(1 for p in version
                                       if p["evidence_status"] != "direct"),
            "with_conflicts": [p["item_id"] for p in paper + version if p["conflicts"]],
            "with_gaps": [p["item_id"] for p in paper + version if p["gaps"]],
        },
        "note": "证据状态：direct=本地有可直接读取的原文；missing=本地读不到，"
                "已在工作包中明确标注；none=问答未返回任何引用。"
                "所有标签列均为空，等待人工填写。",
    }
    (args.outdir / "evidence_packet_coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=1), encoding="utf-8")

    print("关系工作包:", len(fixed), "fixed_version +", len(cvss), "CVSS")
    print("问答工作包:", len(qa_packets), "道")
    print("证据状态:", json.dumps(coverage["evidence"], ensure_ascii=False)[:200])
    print("缺失证据条目:", coverage["missing_evidence_items"][:10])
    print("冲突条目:", coverage["conflicts"]["items"][:10])
    print("剩余工作包:", len(paper), "paper_link +", len(version), "version_range")
    print("剩余证据状态:", json.dumps(coverage["remaining"], ensure_ascii=False)[:240])
    return 0


def review_confidence(packet: dict, reviews: dict) -> str:
    review = reviews.get(packet["item_id"]) or {}
    return review.get("auto_confidence", "")


if __name__ == "__main__":
    raise SystemExit(main())
