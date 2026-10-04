"""B 任务阶段 D：从现有事件与文档生成**关系标注候选**（六个维度）。

这个工具只做一件事：把数据库里**已经存在的字段**拉平成一条条可逐条审核的关系候选。
它不会推断缺失的事实，也不会把候选标成已核验——`annotation.status` 一律
`pending_human_review`，`annotation.label` 一律为 null，等待人工填写。

六个维度：paper_link / version_range / fixed_version / cvss / poc / asset_assessment。
其中 POC 与资产关联在当前语料中没有数据来源，工具会如实产出 0 条并说明原因。

用法::

    python tools/build_b_relation_candidates.py --out evaluation/b_relation_candidates.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import storage  # noqa: E402

DIMENSIONS = ("paper_link", "version_range", "fixed_version", "cvss", "poc", "asset_assessment")

VERIFICATION_METHOD = {
    "paper_link": "核对事件保存的 PDF/落地页链接与对应 RAG 文档的标题、正文主题是否一致。",
    "version_range": "对照来源公告原文，确认 package/ecosystem/range 三元组与受影响区间一致。",
    "fixed_version": "对照来源公告原文，确认修复版本号与受影响区间不矛盾。",
    "cvss": "对照来源公告原文，确认 score 与 vector 逐字一致，且确实来自该来源。",
    "poc": "对照来源公告或公开仓库，确认 POC 链接真实存在且指向该漏洞（不执行任何代码）。",
    "asset_assessment": "核对资产清单中的组件/版本/暴露面/触发条件与事件受影响范围是否匹配。",
}


def _candidate(dim: str, index: int, *, subject: str, relation: str, obj: str,
               value, evidence: dict, uncertainty: str) -> dict:
    return {
        "relation_id": f"BREL-{dim[:2].upper()}-{index:04d}",
        "dimension": dim,
        "subject": subject,
        "relation": relation,
        "object": obj,
        "candidate_value": value,
        "evidence": evidence,
        "verification_method": VERIFICATION_METHOD[dim],
        "annotation": {
            "status": "pending_human_review",
            "label": None,          # positive / negative / unknown / not_applicable
            "verified_by": None,
            "verified_at": None,
            "note": None,
        },
        "uncertainty": uncertainty,
    }


def build() -> dict:
    events, total = storage.list_events(limit=500)
    with storage.connect() as conn:
        doc_keys = {
            row["document_key"]
            for row in conn.execute("SELECT document_key FROM rag_documents").fetchall()
        }

    cases: list[dict] = []
    counters = {dim: 0 for dim in DIMENSIONS}

    for event in events:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue

        # --- paper_link ----------------------------------------------------
        paper = event.get("paper") or {}
        pdf_url = paper.get("pdf_url")
        if pdf_url:
            counters["paper_link"] += 1
            ident = paper.get("arxiv_id") or ""
            doc_key = f"paper:{ident}" if ident else ""
            cases.append(_candidate(
                "paper_link", counters["paper_link"], subject=event_id,
                relation="has_paper", obj=pdf_url,
                value={"pdf_url": pdf_url, "arxiv_id": ident or None,
                       "linked_document_key": doc_key if doc_key in doc_keys else None},
                evidence={"type": "event_field", "event_id": event_id,
                          "field": "paper.pdf_url"},
                uncertainty=("尚未确认该论文与事件主题是否同一工作；"
                             + ("" if doc_key in doc_keys else "本地 RAG 中没有对应全文文档（非 arXiv 链接未抓取）。")),
            ))

        # --- version_range / fixed_version / cvss ---------------------------
        for item in event.get("affected") or []:
            rng = item.get("range")
            if rng:
                counters["version_range"] += 1
                cases.append(_candidate(
                    "version_range", counters["version_range"], subject=event_id,
                    relation="affects", obj=f"{item.get('package')}@{rng}",
                    value={"package": item.get("package"), "ecosystem": item.get("ecosystem"),
                           "range": rng},
                    evidence={"type": "event_field", "event_id": event_id,
                              "field": "affected[].range",
                              "source_id": item.get("source_id")},
                    uncertainty="区间来自单一来源；不同来源之间可能存在冲突，未做交叉核验。",
                ))
            fixed = item.get("fixed_version")
            if fixed:
                counters["fixed_version"] += 1
                cases.append(_candidate(
                    "fixed_version", counters["fixed_version"], subject=event_id,
                    relation="fixed_by", obj=f"{item.get('package')}@{fixed}",
                    value={"package": item.get("package"), "fixed_version": fixed},
                    evidence={"type": "event_field", "event_id": event_id,
                              "field": "affected[].fixed_version",
                              "source_id": item.get("source_id")},
                    uncertainty="修复版本可能表示为区间下界（如 '>= 0.24.0'），需人工确认语义。",
                ))

        for cvss in event.get("cvss") or []:
            counters["cvss"] += 1
            cases.append(_candidate(
                "cvss", counters["cvss"], subject=event_id,
                relation="has_cvss", obj=str(cvss.get("vector") or cvss.get("version") or ""),
                value={"version": cvss.get("version"), "score": cvss.get("score"),
                       "vector": cvss.get("vector")},
                evidence={"type": "event_field", "event_id": event_id, "field": "cvss[]",
                          "source_id": cvss.get("source_id")},
                uncertainty="部分来源只给向量不给分数；此类样本分数为 null，不得当作 0。",
            ))

        # --- poc ------------------------------------------------------------
        for poc in event.get("poc") or []:
            counters["poc"] += 1
            cases.append(_candidate(
                "poc", counters["poc"], subject=event_id, relation="has_poc",
                obj=str(poc.get("url") or ""),
                value={"url": poc.get("url"), "status": poc.get("status")},
                evidence={"type": "event_field", "event_id": event_id, "field": "poc[]",
                          "source_id": poc.get("source_id")},
                uncertainty="系统只记录 POC 的存在与出处，从不执行；未收录不代表不存在。",
            ))

    assets = storage.list_assets()
    asset_by_id = {str(item.get("id")): item for item in assets}
    assessments = storage.list_assessments(limit=2000)
    for assessment in assessments:
        asset = asset_by_id.get(str(assessment.get("asset_id"))) or {}
        is_demo = bool(asset.get("is_demo"))
        counters["asset_assessment"] += 1
        cases.append(_candidate(
            "asset_assessment", counters["asset_assessment"],
            subject=str(assessment.get("event_id")), relation="assessed_against",
            obj=str(assessment.get("asset_id")),
            value={"status": assessment.get("status"),
                   "priority": assessment.get("priority"),
                   "asset_is_demo": is_demo,
                   "asset_authorized": asset.get("authorized"),
                   "asset_component": asset.get("component"),
                   "asset_version": asset.get("version"),
                   "asset_exposure": asset.get("exposure")},
            evidence={"type": "persisted_assessment",
                      "event_id": assessment.get("event_id"),
                      "asset_id": assessment.get("asset_id"),
                      "evidence_ids": assessment.get("evidence_ids") or [],
                      "asset_is_demo": is_demo,
                      "synthetic": is_demo},
            uncertainty=("**合成资产**：该候选基于演示用合成资产清单（is_demo=true），"
                         "不代表企业真实资产关联，只用于验证评测通道与处置建议逻辑。"
                         if is_demo else
                         "判定依赖资产清单的组件/版本/条件；资产数据缺失时结论不可用。"),
        ))

    synthetic_asset_candidates = sum(
        1 for case in cases if case["dimension"] == "asset_assessment"
        and (case.get("evidence") or {}).get("synthetic"))

    coverage = {dim: counters[dim] for dim in DIMENSIONS}
    gaps = []
    if counters["poc"] == 0:
        gaps.append({
            "dimension": "poc",
            "reason": "当前 14 个登记来源中没有任何专门的 POC 采集逻辑，"
                      "事件里 poc 字段全部为空。",
            "impact": "该维度的准确率/召回率在现有数据下无法评测。",
        })
    if counters["asset_assessment"] == 0:
        gaps.append({
            "dimension": "asset_assessment",
            "reason": f"资产表当前有 {len(assets)} 条记录，没有可匹配的资产，"
                      "因此没有任何资产研判记录。",
            "impact": "该维度在现有数据下无法评测。",
        })

    return {
        "schema_version": "b-relation-candidates-1.0",
        "description": "B 任务关系富化标注候选（六个维度），由现有事件/研判字段拉平而成。",
        "annotation_policy": "所有候选的 annotation.status 均为 pending_human_review，"
                             "label 为 null。未标注的候选**不得**计入 TP/FP/FN。",
        "event_sample_size": len(events),
        "events_total": total,
        "asset_count": len(assets),
        "synthetic_asset_candidates": synthetic_asset_candidates,
        "asset_data_source": (
            "合成资产清单（config/assets.example.json，is_demo=true）"
            if synthetic_asset_candidates else
            "无资产数据来源"
        ),
        "dimension_coverage": coverage,
        "coverage_gaps": gaps,
        "counts": {"candidates": len(cases)},
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 B 任务关系标注候选")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "evaluation" / "b_relation_candidates.json")
    args = parser.parse_args()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("候选总数:", payload["counts"]["candidates"])
    print("维度覆盖:", payload["dimension_coverage"])
    print("覆盖缺口:", [g["dimension"] for g in payload["coverage_gaps"]])
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
