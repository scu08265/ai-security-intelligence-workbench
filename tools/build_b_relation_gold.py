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

DIMENSION_PREFIX = {
    "paper_link": "PA", "version_range": "VE", "fixed_version": "FI",
    "cvss": "CV", "poc": "PO", "asset_assessment": "AS",
}


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


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


def enumerate_source_relations(db_dir: Path, events: dict[str, dict]) -> list[dict]:
    """按源头逐条枚举"应抽取关系"（本次 gold 覆盖的四个维度）。"""
    relations: list[dict] = []

    for event_id in SCOPE_EVENTS:
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
                relations.append({
                    "dimension": "version_range", "subject": event_id, "relation": "affects",
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
        for key in SCOPE_PAPERS:
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

    # NVD 快照：为抽样事件补齐 CVSS（本次已实证 KEV 事件缺 CVSS）
    for event_id in SCOPE_EVENTS:
        if not event_id.startswith("CVE-"):
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


def build(db_dir: Path, system_path: Path = SYSTEM_OUTPUT_DEFAULT,
          labeled_path: Path = LABELED_DEFAULT,
          former_missed_path: Path | None = FORMER_MISSED_DEFAULT) -> dict:
    labeled = _load(labeled_path)["cases"]
    system = _load(system_path)["cases"]
    events = _event_docs(db_dir)

    label_by_id = {c["relation_id"]: (c.get("annotation") or {}) for c in labeled}
    index = {(c["dimension"], c["subject"], _norm(c["object"])): c for c in system}

    relations = enumerate_source_relations(db_dir, events)
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
            "kind": "sample_exhaustive",
            "note": "抽样穷尽，不是全语料穷尽：只声明以下对象的应抽取关系全集；其余文档与旧产物不动。",
            "events": list(SCOPE_EVENTS),
            "papers": list(SCOPE_PAPERS),
            "official_documents": list(SCOPE_OFFICIAL),
            "dimensions_in_scope": ["paper_link", "version_range", "fixed_version", "cvss"],
            "dimensions_excluded": {
                "poc": "已由 POC 签核单独核验（16 yes / 16 no），本次不并入 gold，避免与本轮四维口径混算",
                "asset_assessment": "资产为合成资产（synthetic=true），不作为真实金标准",
            },
        },
        "completeness": {
            "source_of_truth": ["事件字段 cvss[]/affected[]/paper", "副本内 NVD 快照 metrics"],
            "sources_not_covered": [
                "OSV 快照结构未解析成功，未用于本次枚举",
                "NVD 只覆盖已抓取的 37 个 CVE",
                "官方/标准文档（NIST/OWASP/EU AI Act）不参与六维度关系，预期 0 条并已核对",
            ],
            "sampled_relations_declared_by_sources": len(relations),
            "system_extracted_and_positive": len(extracted_positive),
            "system_extracted_but_undecided": len(extracted_undecided),
            "missed": len(missed),
        },
        "uncertain": uncertain,
        "protocol_ref": "docs/B_RELATION_GOLD_PROTOCOL.md",
    }
    if former_missed_path:
        former = json.loads(former_missed_path.read_text(encoding="utf-8"))
        former_total = len(former.get("missed_relations") or [])
        gold["former_gold_ref"] = "evaluation/b_relation_gold_20261004.json"
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
    return ("源头（事件字段/%s）明确声明了该关系，属于六维度定义下应抽取的对象"
            % relation["source"])


def why_missed(relation: dict) -> str:
    if relation["dimension"] == "cvss" and relation["source"] == "nvd_snapshot":
        return ("该事件的 CVSS 只存在于 NVD 快照；采集链路只把 NVD 的 Exploit 引用回填到 "
                "poc[]（见 tools/backfill_nvd_poc.py），没有合并 NVD 的 metrics，"
                "因此候选集里该事件没有 cvss 记录")
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
    args = parser.parse_args()

    result = build(args.db_dir, args.system_output, args.labeled_input, args.former_missed)
    gold, missed = result["gold"], result["missed"]
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

    # 供"口径一致"评分使用的输入：只保留抽样范围内的已标注候选
    scope_keys = set(SCOPE_EVENTS) | set(SCOPE_PAPERS) | set(SCOPE_OFFICIAL)
    kept = [c for c in result["labeled"]
            if c["subject"] in scope_keys
            or (c.get("candidate_value") or {}).get("linked_document_key") in scope_keys]
    args.scope_input_out.write_text(
        json.dumps({"schema_version": "b-relation-candidates-labeled-scope-1.0",
                    "scope": gold["scope"],
                    "counts": {"cases": len(kept)},
                    "cases": kept}, ensure_ascii=False, indent=1), encoding="utf-8")

    print("抽样范围声明关系数:", gold["completeness"]["sampled_relations_declared_by_sources"])
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
