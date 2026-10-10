"""B 任务：产出关系抽取的"抽样穷尽"金标准，暴露真实漏检（FN），让 Recall/F1 可算。

为什么需要它：`evaluation/b_relation_candidates_*.json` 本身就是**系统输出**，
拿它当金标准只能算 Precision，永远得不到 FN，Recall/F1 是空的。

本工具的做法（与"标候选"相反）：

1. **圈定抽样范围**：8–12 个对象，覆盖论文 / 漏洞事件 / 官方标准文档三类；
2. **以源头为全集逐条枚举**：事件字段（`cvss[]`、`affected[]`、`paper`、`poc[]`）
   ＋ 副本里的 NVD 快照（`metrics`）；**不从候选集反推**；
3. **逐条与系统候选比对**：源头声明但候选集里没有的 = 真实 FN，单独输出并说明原因；
4. **gold 只收两类 id**：
   * 已人工判 positive 的候选 id（构成 TP）；
   * 确认漏检的新 id（构成 FN）。
   候选里标签为 unknown 的一律放进 `uncertain`，**不进任何分母**
   （否则会被 FN 逻辑重复计数）。

复核批次（`--former-missed`）额外做一件事：把上一批次的漏检条目**按关系内容**
对应到本批次的候选，写进 gold 的 `resolved_former_ids`（旧合成 id → 新候选 id），
于是"上一批的 FN 现在被哪条真实候选解释掉了"是显式、可机检的；
只有当该候选已被人工判为 `human_verified` / `positive` 时才允许记入，否则直接报错。

边界：

* 只读数据库/快照与既有产物；只写本任务的新文件；不改 `app/`、不动旧冻结产物；
* 抽样之外的关系一条都不写进 gold（避免用不完整标注抬高 Recall）；
* 不猜测：无法确认的关系进 `uncertain`。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import b_relation_sources as sources  # 同目录模块：库外快照里的版本/修复关系

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DB_DIR = Path(r"D:\ICT\intel-data-b-poc-20261002")

# 默认批次（2026-10-04，冻结产物）用的输入。新批次一律用命令行显式指定
# --system-output / --labeled-input，绝不复用旧批次的 relation_id，避免张冠李戴。
SYSTEM_OUTPUT_DEFAULT = ROOT / "evaluation" / "b_relation_candidates_20261002_full.json"
LABELED_DEFAULT = ROOT / "artifacts" / "b_eval" / "relation_candidates_labeled_all.json"

GOLD_OUT = ROOT / "evaluation" / "b_relation_gold_20261004.json"
MISSED_OUT = ROOT / "artifacts" / "b_eval" / "relation_missed_relations_20261004.json"
SCOPE_INPUT_OUT = ROOT / "artifacts" / "b_eval" / "relation_candidates_labeled_gold_scope_20261004.json"

# 复核批次用：上一批次的漏检清单（含 subject/dimension/object 与证据定位）。
# 默认不传 —— 只有"复核上一批漏检"时才需要，避免把别的批次的内容混进来。
FORMER_MISSED_DEFAULT: Path | None = None

# 抽样范围（用户已确认）：论文 3 篇 + CVE 事件 3 个 + 生态漏洞事件 2 个 + 官方/标准文档 3 个
SCOPE_EVENTS = (
    "CVE-2026-64849", "CVE-2025-62593", "CVE-2026-33017",
    "PYSEC-2026-4000", "GHSA-8pw2-6jv3-mj5j",
)
SCOPE_PAPERS = ("paper:2609.28996", "paper:2609.29757", "paper:2609.28900")
SCOPE_OFFICIAL = ("official:eu_ai_act", "source:nist_ai_rmf", "source:owasp_genai")

# 两种枚举口径：
#   legacy —— 10-04 / 10-06 用过的 11 个对象（5 事件 + 3 论文 + 3 官方文档）；
#   full   —— 2026-10-10 起：论文全量、生态事件全量、CVE 全量盘点，
#             CVE 再按"证据覆盖"分层（见 resolve_scope），证据不足的不进任何分母。
# 用 ``--scope`` 选择，默认 full。
SCOPE_MODE_LEGACY = "legacy"
SCOPE_MODE_FULL = "full"
SCOPE_MODE_DEFAULT = SCOPE_MODE_FULL
CVE_PREFIX = "CVE-"
ECOSYSTEM_PREFIXES = ("GHSA-", "PYSEC-")

DIMENSION_PREFIX = {
    "paper_link": "PA", "version_range": "VE", "fixed_version": "FI",
    "cvss": "CV", "poc": "PO", "asset_assessment": "AS",
}


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


def _count_by_dimension(relations: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for relation in relations:
        counts[relation["dimension"]] = counts.get(relation["dimension"], 0) + 1
    return counts


def _former_gold_ref(former_missed_path: Path) -> str:
    """上一批次的漏检清单 → 上一批次 gold 的仓库内相对路径。"""
    name = former_missed_path.name.replace("relation_missed_relations_",
                                          "b_relation_gold_")
    return f"evaluation/{name}"


def _repo_rel(path: Path) -> str:
    """仓库内相对路径（命令行可能给绝对或相对路径）。"""
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_docs(db_dir: Path) -> dict[str, dict]:
    connection = sqlite3.connect(f"file:{db_dir / 'intel.sqlite'}?mode=ro", uri=True)
    with connection:
        return {ident: json.loads(doc)
                for ident, doc in connection.execute("select id, doc from events")}


def _doc_keys(db_dir: Path) -> set[str]:
    """本地 RAG 文档键（``paper:*`` / ``official:*`` / ``source:*``）。"""
    connection = sqlite3.connect(f"file:{db_dir / 'intel.sqlite'}?mode=ro", uri=True)
    with connection:
        return {row[0] for row in connection.execute("select document_key from rag_documents")}


def _nvd_record(db_dir: Path, cve: str) -> tuple[dict | None, str | None]:
    path = db_dir / "snapshots" / "nvd" / f"{cve}.json"
    if not path.is_file():
        return None, None
    payload = _load(path)
    vulnerabilities = payload.get("vulnerabilities") or []
    if not vulnerabilities:
        return None, None
    return vulnerabilities[0].get("cve") or {}, str(path)


def _nvd_cvss(nvd: dict, source: str) -> list[dict]:
    """从 NVD 记录里抽出 CVSS 关系（每个 metric 一条）。"""
    results = []
    metrics = nvd.get("metrics") or {}
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for index, item in enumerate(metrics.get(key) or []):
            data = item.get("cvssData") or {}
            vector = str(data.get("vectorString") or "").strip()
            if not vector:
                continue
            results.append({
                "dimension": "cvss",
                "subject": nvd.get("id"),
                "relation": "has_cvss",
                "object": vector,
                "source": "nvd_snapshot",
                "source_path": source,
                "source_locator": f"metrics.{key}[{index}]",
                "detail": {"base_score": data.get("baseScore"),
                           "base_severity": data.get("baseSeverity"),
                           "metric": key},
            })
    return results


def _scope_targets(scope: dict | None):
    """把 scope 归一化成 (事件, 论文, 查 NVD/MITRE 的 CVE, 查 OSV 的生态事件, 是否用快照)。"""
    if scope is None:
        return (
            list(SCOPE_EVENTS),
            list(SCOPE_PAPERS),
            {e for e in SCOPE_EVENTS if e.startswith(CVE_PREFIX)},
            {e for e in SCOPE_EVENTS if not e.startswith(CVE_PREFIX)},
            False,
        )
    targets = scope.get("snapshot_targets") or {}
    # legacy 口径必须走 10-06 的 NVD 定向回读，否则它就不能用来复现旧 gold。
    use_snapshots = scope.get("mode") != SCOPE_MODE_LEGACY
    return (
        list(scope.get("events") or ()),
        list(scope.get("papers") or ()),
        set(targets.get("cve") or ()),
        set(targets.get("ecosystem") or ()),
        use_snapshots,
    )


def enumerate_source_relations(db_dir: Path, events: dict[str, dict],
                               scope: dict | None = None,
                               *, skipped: list | None = None) -> list[dict]:
    """按源头逐条枚举"应抽取关系"（gold 覆盖的四个维度）。

    ``scope`` 省略时用 10-04/10-06 批次的 11 个对象（legacy）；给出
    ``resolve_scope()`` 的结果时按"全量盘点 + CVE 分层"口径枚举。

    ``skipped``（可选）用于收集"源头没有可比事实、因而不构成应抽取关系"的条目，
    例如只声明了 ``unknown`` 区间的 KEV 事件。这些必须如实排除，
    否则会把"无法核验"算成漏检。
    """
    relations: list[dict] = []
    event_ids, papers, cve_targets, ecosystem_targets, use_snapshots = _scope_targets(scope)

    def _skip(kind: str, **payload) -> None:
        if skipped is not None:
            skipped.append({"kind": kind, **payload})

    for event_id in event_ids:
        event = events.get(event_id)
        if not event:
            continue
        for index, item in enumerate(event.get("cvss") or []):
            vector = str(item.get("vector") or "").strip()
            if not vector:
                continue
            relations.append({
                "dimension": "cvss", "subject": event_id, "relation": "has_cvss",
                "object": vector, "source": "event_field",
                "source_path": f"events[{event_id}].cvss[{index}]",
                "source_locator": item.get("source_id"),
                "detail": {"score": item.get("score"), "version": item.get("version")},
            })
        for index, item in enumerate(event.get("affected") or []):
            package, ecosystem = item.get("package"), item.get("ecosystem")
            version_range = item.get("range")
            if package and version_range:
                if version_range == sources.UNKNOWN_RANGE:
                    _skip("range_unknown", dimension="version_range", subject=event_id,
                          reason="事件只有 unknown 区间（KEV/MSRC 等来源不给版本边界），"
                                 "源头没有可比版本，不作为应抽取关系",
                          source_path=f"events[{event_id}].affected[{index}].range")
                else:
                    relations.append({
                        "dimension": "version_range", "subject": event_id,
                        "relation": "affects",
                        "object": f"{package}@{version_range}", "source": "event_field",
                        "source_path": f"events[{event_id}].affected[{index}].range",
                        "source_locator": item.get("source_id"),
                        "detail": {"package": package, "ecosystem": ecosystem,
                                   "range": version_range},
                    })
            fixed_version = item.get("fixed_version")
            if package and fixed_version:
                relations.append({
                    "dimension": "fixed_version", "subject": event_id,
                    "relation": "fixed_by", "object": f"{package}@{fixed_version}",
                    "source": "event_field",
                    "source_path": f"events[{event_id}].affected[{index}].fixed_version",
                    "source_locator": item.get("source_id"),
                    "detail": {"package": package, "fixed_version": fixed_version},
                })
        paper = event.get("paper") or {}
        pdf_url = str(paper.get("pdf_url") or paper.get("url") or "").strip()
        if pdf_url:
            relations.append({
                "dimension": "paper_link", "subject": event_id, "relation": "has_paper",
                "object": pdf_url, "source": "event_field",
                "source_path": f"events[{event_id}].paper.pdf_url",
                "source_locator": paper.get("arxiv_id"),
                "detail": {"arxiv_id": paper.get("arxiv_id")},
            })

    # 论文范围：扫描全部事件，凡是 paper 字段指向抽样论文的，都应有一条 paper_link
    for event_id, event in sorted(events.items()):
        paper = event.get("paper") or {}
        arxiv_id = str(paper.get("arxiv_id") or "").strip()
        pdf_url = str(paper.get("pdf_url") or paper.get("url") or "").strip()
        for key in papers:
            if arxiv_id and arxiv_id == key.split(":", 1)[1]:
                relations.append({
                    "dimension": "paper_link", "subject": event_id,
                    "relation": "has_paper",
                    "object": pdf_url or f"https://arxiv.org/abs/{arxiv_id}",
                    "source": "event_field",
                    "source_path": f"events[{event_id}].paper.arxiv_id",
                    "source_locator": pdf_url or None,
                    "detail": {"document_key": key, "arxiv_id": arxiv_id,
                               "matched_by": "sampled_paper"},
                })

    if use_snapshots:
        # 库外快照：OSV 的 ranges[].events.fixed、NVD 的 metrics + configurations、
        # MITRE CVE 记录的 lessThan。三条来源都在 tools/b_relation_sources.py 里
        # 逐字翻译，不推断、不补全。
        for payload in (
            sources.nvd_snapshot_relations(db_dir / "snapshots" / "nvd", cve_targets),
            sources.mitre_snapshot_relations(db_dir / "snapshots" / "mitre_cve", cve_targets),
            sources.osv_snapshot_relations(db_dir / "snapshots" / "osv", ecosystem_targets),
        ):
            relations.extend(payload["relations"])
            for item in payload["coverage"].get("ranges_skipped") or []:
                _skip("osv_range_skipped", dimension="not_enumerable", subject=None, **item)
    else:
        # legacy：沿用 10-06 的 NVD 定向回读（snapshots/nvd/<CVE>.json 的 metrics）
        for event_id in event_ids:
            if not event_id.startswith(CVE_PREFIX):
                continue
            nvd, path = _nvd_record(db_dir, event_id)
            if not nvd or not path:
                continue
            for item in _nvd_cvss(nvd, path):
                item["subject"] = event_id
                relations.append(item)

    # CVSS 回填后，同一条向量会同时出现在事件字段与 NVD 快照里；计分上它们是
    # 同一条关系，按 (维度, 主体, 归一化向量) 去重，避免把分母算大。
    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for relation in relations:
        key = (relation["dimension"], relation["subject"], _norm(relation["object"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return deduped


def match_candidate(relation: dict, index: dict) -> dict | None:
    key = (relation["dimension"], relation["subject"], _norm(relation["object"]))
    return index.get(key)


def resolve_former_missed(former_missed_path: Path, index: dict,
                          label_by_id: dict) -> dict[str, dict]:
    """把上一批漏检条目按内容对应到本批候选，返回 {旧 id: 映射记录}。

    任何一条对不上、或对应的候选不是人工核验过的 positive，都直接报错——
    不允许把"修复后仍未确认"的东西写成"已解析"。
    """
    former = json.loads(former_missed_path.read_text(encoding="utf-8"))
    resolved: dict[str, dict] = {}
    problems: list[str] = []
    for entry in former.get("missed_relations") or []:
        gold_id = entry["gold_relation_id"]
        key = (entry["dimension"], entry["subject"], _norm(entry["object"]))
        candidate = index.get(key)
        if candidate is None:
            problems.append(f"{gold_id}：本批次候选集里找不到内容相同的候选")
            continue
        annotation = label_by_id.get(candidate["relation_id"]) or {}
        if annotation.get("status") != "human_verified" or annotation.get("label") != "positive":
            problems.append(
                f"{gold_id} → {candidate['relation_id']}："
                f"候选尚未人工核验为 positive（status={annotation.get('status')}）")
            continue
        resolved[gold_id] = {
            "new_relation_id": candidate["relation_id"],
            "dimension": candidate["dimension"],
            "subject": candidate["subject"],
            "object": candidate["object"],
            "system_evidence_source_id": (candidate.get("evidence") or {}).get("source_id"),
            "human_label": annotation.get("label"),
            "verified_by": annotation.get("verified_by"),
            "verified_at": annotation.get("verified_at"),
        }
    if problems:
        raise ValueError("复核上一批漏检失败：\n  - " + "\n  - ".join(problems))
    return resolved


def resolve_scope(db_dir: Path, events: dict[str, dict], doc_keys: set[str],
                  mode: str = SCOPE_MODE_DEFAULT) -> dict:
    """算出本批次的**盘点范围**、**可核验范围**与证据覆盖量（不产出关系）。

    规则（2026-10-10 确认）：

    * 论文、生态事件"全量纳入"；
    * CVE 全量盘点，但按**证据覆盖**分层：有权威快照（NVD / MITRE）或事件自身带
      可核验事实（CVSS 向量 / 非 ``unknown`` 区间）的进"可核验"层；
      其余进"证据不足"层，只统计数量与原因，**不进任何分母**——
      避免把"无法核验"误算成漏检。

    16 篇论文 / 12 个生态事件 / 37 个 CVE 是**盘点**范围，不代表全部进同一个分母。
    """
    papers = sorted(key for key in doc_keys if key.startswith("paper:"))
    ecosystem = sorted(ident for ident in events
                       if ident.startswith(ECOSYSTEM_PREFIXES))
    cves = sorted(ident for ident in events if ident.startswith(CVE_PREFIX))

    if mode == SCOPE_MODE_LEGACY:
        return {
            "mode": mode,
            "kind": "sample_exhaustive",
            "note": "10-04/10-06 口径：5 个事件 + 3 篇论文 + 3 个官方/标准文档。",
            "events": list(SCOPE_EVENTS),
            "papers": list(SCOPE_PAPERS),
            "official_documents": list(SCOPE_OFFICIAL),
            "snapshot_targets": {
                "cve": [e for e in SCOPE_EVENTS if e.startswith(CVE_PREFIX)],
                "ecosystem": [e for e in SCOPE_EVENTS if not e.startswith(CVE_PREFIX)],
            },
            "inventory": {"papers": len(SCOPE_PAPERS), "ecosystem_events": 2,
                          "cve_events": 3},
            "tiers": {},
        }

    nvd = sources.nvd_snapshot_relations(db_dir / "snapshots" / "nvd", set(cves))
    mitre = sources.mitre_snapshot_relations(db_dir / "snapshots" / "mitre_cve", set(cves))
    nvd_ids = set(nvd["coverage"]["in_scope_ids"])
    mitre_ids = set(mitre["coverage"]["in_scope_ids"])

    verifiable: list[dict] = []
    insufficient: list[dict] = []
    for cve_id in cves:
        event = events.get(cve_id) or {}
        vectors = [v.get("vector") for v in (event.get("cvss") or []) if v.get("vector")]
        declared = [a.get("range") for a in (event.get("affected") or [])
                    if a.get("range") and a.get("range") != sources.UNKNOWN_RANGE]
        evidence: list[str] = []
        if cve_id in nvd_ids:
            evidence.append("副本内有 NVD 快照（metrics / configurations 可回读）")
        if cve_id in mitre_ids:
            evidence.append("副本内有 MITRE CVE 记录（versions 可回读）")
        if vectors:
            evidence.append(f"事件自带 CVSS 向量 ×{len(vectors)}")
        if declared:
            evidence.append("事件已声明可比区间")
        if evidence:
            verifiable.append({"event": cve_id, "evidence": evidence})
        else:
            insufficient.append({
                "event": cve_id,
                "reason": "事件只有一个 unknown 区间（KEV 类来源不给版本边界），"
                          "副本内没有 NVD / MITRE 快照可回读，没有可核验的版本事实",
            })

    verifiable_ids = [item["event"] for item in verifiable]
    osv = sources.osv_snapshot_relations(db_dir / "snapshots" / "osv", set(ecosystem))
    return {
        "mode": SCOPE_MODE_FULL,
        "kind": "sample_exhaustive",
        "note": "抽样穷尽，不是全语料穷尽：这里列出的是本批次**盘点**的全部对象；"
                "CVE 按证据覆盖分层，只有'可核验'层进入评分分母。",
        "events": [*ecosystem, *cves],
        "papers": papers,
        "official_documents": list(SCOPE_OFFICIAL),
        "snapshot_targets": {"cve": verifiable_ids, "ecosystem": ecosystem},
        "inventory": {
            "papers": len(papers),
            "ecosystem_events": len(ecosystem),
            "cve_events": len(cves),
        },
        "tiers": {
            "cve_verifiable": {"count": len(verifiable), "items": verifiable,
                               "note": "有权威快照或事件自带可核验事实，进评分分母"},
            "cve_insufficient_evidence": {
                "count": len(insufficient), "items": insufficient,
                "note": "只统计数量与原因，不进任何分母（避免把'无法核验'算成漏检）"},
            "ecosystem_events_verifiable": {
                "count": len(ecosystem),
                "note": "每个生态事件都有 OSV 快照声明区间与修复版本，可逐字回读"},
            "papers_full": {"count": len(papers), "note": "16 篇论文全量纳入 paper_link 维度"},
            "official_documents": {
                "count": len(SCOPE_OFFICIAL),
                "note": "官方/标准文档不参与六维度关系，预期 0 条并已核对"},
        },
        "snapshot_coverage": {
            "osv": osv["coverage"],
            "nvd": {k: v for k, v in nvd["coverage"].items() if k != "records_without_event"},
            "nvd_records_without_event": len(nvd["coverage"]["records_without_event"]),
            "mitre": mitre["coverage"],
        },
    }


def build(db_dir: Path, system_path: Path = SYSTEM_OUTPUT_DEFAULT,
          labeled_path: Path = LABELED_DEFAULT,
          former_missed_path: Path | None = FORMER_MISSED_DEFAULT,
          scope_mode: str = SCOPE_MODE_DEFAULT) -> dict:
    labeled = _load(labeled_path)["cases"]
    system = _load(system_path)["cases"]
    events = _event_docs(db_dir)
    scope = resolve_scope(db_dir, events, _doc_keys(db_dir), scope_mode)

    label_by_id = {c["relation_id"]: (c.get("annotation") or {}) for c in labeled}
    index = {(c["dimension"], c["subject"], _norm(c["object"])): c for c in system}

    skipped: list[dict] = []
    relations = enumerate_source_relations(db_dir, events, scope, skipped=skipped)
    extracted_positive: list[dict] = []
    extracted_undecided: list[dict] = []
    missed: list[dict] = []
    uncertain: list[dict] = []
    fn_counter: dict[str, int] = defaultdict(int)

    for relation in relations:
        candidate = match_candidate(relation, index)
        if candidate is not None:
            annotation = label_by_id.get(candidate["relation_id"]) or {}
            label = annotation.get("label")
            record = {**relation, "system_relation_id": candidate["relation_id"],
                      "system_object": candidate["object"]}
            if label == "positive":
                extracted_positive.append(record)
            else:
                record["human_label"] = label
                record["uncertain_reason"] = (
                    "候选已存在但人工判为 unknown/未确认，无法确认系统是否漏检" if label else "候选缺少人工标签")
                extracted_undecided.append(record)
                uncertain.append({"kind": "candidate_undecided",
                                  "relation_id": candidate["relation_id"],
                                  "dimension": candidate["dimension"],
                                  "reason": record["uncertain_reason"]})
            continue

        prefix = DIMENSION_PREFIX.get(relation["dimension"], "XX")
        fn_counter[prefix] += 1
        gold_id = f"BREL-GOLD-FN-{prefix}-{fn_counter[prefix]:04d}"
        missed.append({
            "gold_relation_id": gold_id,
            "dimension": relation["dimension"],
            "subject": relation["subject"],
            "relation": relation["relation"],
            "object": relation["object"],
            "evidence": {
                "type": relation["source"],
                "source_path": relation["source_path"],
                "source_locator": relation.get("source_locator"),
                "detail": relation.get("detail") or {},
            },
            "why_expected": why_expected(relation),
            "why_missed": why_missed(relation),
        })

    resolved_former_ids = (
        resolve_former_missed(former_missed_path, index, label_by_id)
        if former_missed_path else {}
    )

    expected = {item["system_relation_id"]: item["dimension"]
                for item in extracted_positive}
    expected.update({item["gold_relation_id"]: item["dimension"] for item in missed})

    gold = {
        "schema_version": "b-relation-gold-1.0",
        "expected_relation_ids": expected,
        "scope": {
            **scope,
            "dimensions_in_scope": ["paper_link", "version_range", "fixed_version", "cvss"],
            "dimensions_excluded": {
                "poc": "已由 POC 签核单独核验（16 yes / 16 no），本次不并入 gold，避免与本轮四维口径混算",
                "asset_assessment": "资产为合成资产（synthetic=true），不作为真实金标准",
            },
            "enumerated": {
                "declared_relations": len(relations),
                "by_dimension": _count_by_dimension(relations),
                "note": "枚举量 = 盘点范围内源头明确声明的关系条数（去重后）；"
                        "不等于评分分母，分母只由'人工核验 positive'与'真实漏检'组成。",
            },
            "excluded_not_enumerable": {
                "count": len(skipped),
                "items": skipped,
                "note": "源头没有可比事实（unknown 区间 / GIT 区间 / 批量响应缺正文），"
                        "如实排除，不计入任何分母。",
            },
        },
        "completeness": {
            "source_of_truth": [
                "事件字段 cvss[]/affected[]/paper",
                "副本内 NVD 快照 metrics + configurations[].nodes[].cpeMatch[]",
                "副本内 OSV 快照 affected[].ranges[].events[]（introduced / fixed / last_affected）",
                "副本内 MITRE CVE 记录 containers.cna.affected[].versions[]（lessThan）",
            ],
            "sources_not_covered": [
                f"OSV 批量查询响应里只有 id/modified，没有 affected，离线枚举不出区间"
                f"（本次响应命中 {scope.get('snapshot_coverage', {}).get('osv', {}).get('batch_advisory_ids', 0)} 条公告，"
                f"采集侧按预算只取回 "
                f"{scope.get('snapshot_coverage', {}).get('osv', {}).get('detail_records', 0)} 条详情）",
                "NVD 快照只覆盖副本里已抓取的文件（其余 CVE 无快照可回读）",
                "官方/标准文档（NIST/OWASP/EU AI Act）不参与六维度关系，预期 0 条并已核对",
            ],
            "sampled_relations_declared_by_sources": len(relations),
            "system_extracted_and_positive": len(extracted_positive),
            "system_extracted_but_undecided": len(extracted_undecided),
            "missed": len(missed),
            "not_enumerable": len(skipped),
        },
        "uncertain": uncertain,
        "protocol_ref": "docs/B_RELATION_GOLD_PROTOCOL.md",
    }
    if former_missed_path:
        former = json.loads(former_missed_path.read_text(encoding="utf-8"))
        former_total = len(former.get("missed_relations") or [])
        gold["former_gold_ref"] = _former_gold_ref(former_missed_path)
        gold["former_missed_ref"] = _repo_rel(former_missed_path)
        gold["resolved_former_ids"] = resolved_former_ids
        gold["completeness"]["former_missed_total"] = former_total
        gold["completeness"]["former_missed_resolved"] = len(resolved_former_ids)
    return {"gold": gold, "missed": missed, "relations": relations,
            "extracted_positive": extracted_positive, "labeled": labeled}


def why_expected(relation: dict) -> str:
    if relation["source"] == "nvd_snapshot":
        return ("该 CVE 的 NVD 记录声明了 CVSS 指标（metrics 字段），属于 cvss 维度应抽取的关系；"
                "本系统以 NVD 为权威来源之一，因此该关系应当出现在候选集里")
    if relation["source"] == "nvd_configuration":
        return ("该 CVE 的 NVD 记录在 configurations[].nodes[].cpeMatch[] 里声明了受影响产品与"
                "版本边界（versionStartIncluding / versionEndExcluding），属于 version_range / "
                "fixed_version 维度应抽取的关系；versionEndExcluding 即首个修复版本")
    if relation["source"] == "osv_snapshot":
        return ("该生态漏洞的 OSV 快照在 affected[].ranges[].events[] 里声明了受影响区间与"
                "修复版本，属于 version_range / fixed_version 维度应抽取的关系")
    if relation["source"] == "mitre_snapshot":
        return ("该 CVE 的 MITRE 记录在 affected[].versions[].lessThan 里声明了受影响上界，"
                "``< X`` 即修复于 X，属于 version_range / fixed_version 维度应抽取的关系")
    return ("源头（事件字段/%s）明确声明了该关系，属于六维度定义下应抽取的对象"
            % relation["source"])


def why_missed(relation: dict) -> str:
    if relation["dimension"] == "cvss" and relation["source"] == "nvd_snapshot":
        return ("该事件的 CVSS 只存在于 NVD 快照；采集链路只把 NVD 的 Exploit 引用回填到 "
                "poc[]（见 tools/backfill_nvd_poc.py），没有合并 NVD 的 metrics，"
                "因此候选集里该事件没有 cvss 记录")
    if relation["source"] == "nvd_configuration":
        return ("NVD 的 configurations（CPE 产品与版本边界）从未被采集链路合并："
                "事件 affected[] 只带来源自己给的区间（KEV 类来源为 unknown），"
                "因此候选集里没有该产品/版本的关系记录")
    if relation["source"] == "osv_snapshot":
        return ("OSV 快照的 ranges[].events[] 此前未被解析进枚举，候选集里没有对应记录；"
                "本批次把该来源接入枚举后，这类关系才第一次被要求抽取")
    if relation["source"] == "mitre_snapshot":
        return ("MITRE 记录的 lessThan 上界没有被转换成 fixed_version："
                "app/normalize.mitre_to_event 只把区间写进 affected[].range，"
                "fixed_version 一律留空，因此候选集里没有这条修复版本关系")
    if relation["dimension"] == "paper_link":
        return "事件声明了论文链接，但候选集里没有对应的 paper_link 记录"
    return "源头声明了该关系，但候选集里没有匹配记录（字段未合并或未进入抽取路径）"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成关系抽取的抽样穷尽金标准")
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--system-output", type=Path, default=SYSTEM_OUTPUT_DEFAULT,
                        help="系统候选集（新批次显式指定，不要与旧批次混用）")
    parser.add_argument("--labeled-input", type=Path, default=LABELED_DEFAULT,
                        help="带人工标注的候选集（按关系内容与本批次 system-output 对齐）")
    parser.add_argument("--gold-out", type=Path, default=GOLD_OUT)
    parser.add_argument("--missed-out", type=Path, default=MISSED_OUT)
    parser.add_argument("--scope-input-out", type=Path, default=SCOPE_INPUT_OUT)
    parser.add_argument("--former-missed", type=Path, default=FORMER_MISSED_DEFAULT,
                        help="上一批次的漏检清单；给出时 gold 会带 resolved_former_ids 映射")
    parser.add_argument("--scope", choices=(SCOPE_MODE_FULL, SCOPE_MODE_LEGACY),
                        default=SCOPE_MODE_DEFAULT,
                        help="枚举口径：full=全量盘点（论文全量/生态全量/CVE 盘点后按证据分层）；"
                             "legacy=10-04、10-06 用过的 11 个对象")
    args = parser.parse_args()

    result = build(args.db_dir, args.system_output, args.labeled_input, args.former_missed,
                   args.scope)
    gold, missed = result["gold"], result["missed"]
    scope = gold["scope"]
    if scope.get("tiers"):
        print("盘点范围: 论文 %d 篇 / 生态事件 %d 个 / CVE %d 个" % (
            scope["inventory"]["papers"], scope["inventory"]["ecosystem_events"],
            scope["inventory"]["cve_events"]))
        print("CVE 分层: 可核验 %d｜证据不足 %d（不进分母）" % (
            scope["tiers"]["cve_verifiable"]["count"],
            scope["tiers"]["cve_insufficient_evidence"]["count"]))
    if gold.get("resolved_former_ids"):
        print("已解析上一批漏检:", len(gold["resolved_former_ids"]),
              "/", gold["completeness"]["former_missed_total"])
    if not missed:
        print("说明：抽样范围内没有发现漏检关系（missed=0）。"
              "这在‘修复后复核’批次里是预期结果（原 FN 已转为命中），"
              "此时 gold 的 FN 来源为空，Recall 由‘命中/抽样全集’给出。")

    args.gold_out.parent.mkdir(parents=True, exist_ok=True)
    args.gold_out.write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
    args.missed_out.write_text(
        json.dumps({"schema_version": "b-relation-missed-1.0",
                    "scope": gold["scope"],
                    "counts": {"missed": len(missed)},
                    "missed_relations": missed},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    # 供"口径一致"评分使用的输入：只保留盘点范围内的已标注候选
    scope_keys = (set(scope["events"]) | set(scope["papers"])
                  | set(scope["official_documents"]))
    kept = [c for c in result["labeled"]
            if c["subject"] in scope_keys
            or (c.get("candidate_value") or {}).get("linked_document_key") in scope_keys]
    args.scope_input_out.write_text(
        json.dumps({"schema_version": "b-relation-candidates-labeled-scope-1.0",
                    "scope": gold["scope"],
                    "counts": {"cases": len(kept)},
                    "cases": kept}, ensure_ascii=False, indent=1), encoding="utf-8")

    print("抽样范围声明关系数:", gold["completeness"]["sampled_relations_declared_by_sources"],
          gold["scope"]["enumerated"]["by_dimension"])
    print("不可枚举（源头无版本事实，已排除）:", gold["completeness"]["not_enumerable"])
    print("已抽取且人工 positive:", len(result["extracted_positive"]))
    print("已抽取但待定（进 uncertain）:", gold["completeness"]["system_extracted_but_undecided"])
    print("真实漏检（FN）:", len(missed))
    for item in missed:
        print(f"   {item['gold_relation_id']} {item['dimension']} {item['subject']} → "
              f"{str(item['object'])[:60]}")
    print("gold:", args.gold_out)
    print("missed:", args.missed_out)
    print("scope input:", args.scope_input_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
