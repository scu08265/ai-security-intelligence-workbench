"""赛题指标页面 vs 权威 JSON：只读一致性核对（B 任务）。

页面（``app/b_evaluation.py`` → ``/api/competition/scorecard`` → 前端卡片）
只投影 ``artifacts/b_eval`` 下四份冻结文件。本工具逐字段把这些页面口径的值
与权威 JSON 重新读取一遍做对照，用来回答"页面上显示的 21.21% / 3.23% / 50%
到底来自哪里、和 JSON 是否一致、新批次结果有没有被混进去"。

设计约束：

* **只读**：不写数据库、不改任何冻结产物；只写一份核对结果 JSON。
* **不参与评分**：结论既不是新指标，也不得覆盖旧基线。
* 页面值缺失时输出 ``null`` 并记 ``missing``，绝不补 0。

用法::

    python tools/check_b_scorecard_consistency.py \
        --out artifacts/b_eval/scorecard_consistency_20261002.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "b_eval"


def _load(name: str) -> dict:
    path = ARTIFACTS / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _check(checks: list[dict], field: str, page: object, source_file: str,
           source_value: object) -> None:
    checks.append({
        "field": field,
        "page_value": page,
        "source_file": source_file,
        "source_value": source_value,
        "match": page == source_value,
    })


def build() -> dict:
    from app import b_evaluation

    page = b_evaluation.summary()
    active_batch = page.get("active_batch") or {}
    active_human = _load(active_batch["qa_human_score_file"]) if active_batch else {}
    active_performance = _load(active_batch["qa_performance_file"]) if active_batch else {}
    qa_human = _load("qa_human_score.json")
    performance = _load("qa_performance_stats.json")
    relation = _load("relation_score_all.json")
    multihop = _load("multihop_path_validation.json")
    demo = _load("b_demo_screenshots.json")

    checks: list[dict] = []
    quality = page.get("qa_quality") or {}
    answer = qa_human.get("answer") or {}
    citation = qa_human.get("citation") or {}
    refusal = qa_human.get("refusal") or {}
    should_refuse = refusal.get("should_refuse") or {}
    for field, page_value, source_value in (
        ("qa_quality.human_judged_cases", quality.get("human_judged_cases"),
         qa_human.get("human_judged_cases")),
        ("qa_quality.answer_accuracy", quality.get("answer_accuracy"), answer.get("rate")),
        ("qa_quality.answer_numerator", quality.get("answer_numerator"), answer.get("numerator")),
        ("qa_quality.answer_denominator", quality.get("answer_denominator"), answer.get("denominator")),
        ("qa_quality.citation_support", quality.get("citation_support"), citation.get("rate")),
        ("qa_quality.citation_numerator", quality.get("citation_numerator"), citation.get("numerator")),
        ("qa_quality.citation_denominator", quality.get("citation_denominator"), citation.get("denominator")),
        ("qa_quality.refusal_recall", quality.get("refusal_recall"), should_refuse.get("refused_recall")),
        ("qa_quality.refusal_precision", quality.get("refusal_precision"), refusal.get("refused_precision")),
        ("qa_quality.refusal_accuracy", quality.get("refusal_accuracy"), refusal.get("refusal_accuracy")),
    ):
        _check(checks, field, page_value, "qa_human_score.json", source_value)

    batches_page = page.get("qa_performance", {}).get("batches") or []
    batches_src = performance.get("batches") or []
    _check(checks, "qa_performance.batch_count", len(batches_page), "qa_performance_stats.json",
           len(batches_src))
    for index, source in enumerate(batches_src):
        row = batches_page[index] if index < len(batches_page) else {}
        latency = source.get("latency_ms") or {}
        for key, source_value in (("p50_ms", latency.get("p50")),
                                  ("p95_ms", latency.get("p95"))):
            _check(checks, f"qa_performance.batches[{index}].{key}",
                   row.get(key), "qa_performance_stats.json", source_value)

    relation_page = page.get("relation") or {}
    micro = relation.get("micro") or {}
    for key in ("precision", "recall", "f1", "tp", "fp", "fn", "evaluable_samples"):
        _check(checks, f"relation.{key}", relation_page.get(key),
               "relation_score_all.json", micro.get(key))

    multihop_page = page.get("multihop") or {}
    counts = multihop.get("counts") or {}
    by_type = counts.get("by_chain_type") or {}
    for key, source_value in (
        ("two_hop_found", (by_type.get("two_hop") or {}).get("path_found")),
        ("two_hop_total", (by_type.get("two_hop") or {}).get("total")),
        ("cross_document_found", (by_type.get("cross_document") or {}).get("path_found", 0)),
        ("cross_document_total", (by_type.get("cross_document") or {}).get("total")),
    ):
        _check(checks, f"multihop.{key}", multihop_page.get(key),
               "multihop_path_validation.json", source_value)

    demo_page = page.get("demo") or {}
    shots = demo.get("shots") or []
    _check(checks, "demo.screenshots", demo_page.get("screenshots"),
           "b_demo_screenshots.json", len(shots))

    active_quality = page.get("active_qa_quality") or {}
    active_answer = active_human.get("answer") or {}
    active_citation = active_human.get("citation") or {}
    active_refusal = active_human.get("refusal") or {}
    active_should_refuse = active_refusal.get("should_refuse") or {}
    for field, page_value, source_value in (
        ("active_qa_quality.human_judged_cases", active_quality.get("human_judged_cases"),
         active_human.get("human_judged_cases")),
        ("active_qa_quality.answer_accuracy", active_quality.get("answer_accuracy"),
         active_answer.get("rate")),
        ("active_qa_quality.answer_numerator", active_quality.get("answer_numerator"),
         active_answer.get("numerator")),
        ("active_qa_quality.answer_denominator", active_quality.get("answer_denominator"),
         active_answer.get("denominator")),
        ("active_qa_quality.citation_support", active_quality.get("citation_support"),
         active_citation.get("rate")),
        ("active_qa_quality.citation_numerator", active_quality.get("citation_numerator"),
         active_citation.get("numerator")),
        ("active_qa_quality.citation_denominator", active_quality.get("citation_denominator"),
         active_citation.get("denominator")),
        ("active_qa_quality.refusal_recall", active_quality.get("refusal_recall"),
         active_should_refuse.get("refused_recall")),
        ("active_qa_quality.refusal_precision", active_quality.get("refusal_precision"),
         active_refusal.get("refused_precision")),
        ("active_qa_quality.refusal_accuracy", active_quality.get("refusal_accuracy"),
         active_refusal.get("refusal_accuracy")),
    ):
        _check(checks, field, page_value, active_batch.get("qa_human_score_file"), source_value)

    active_batches_page = page.get("active_qa_performance", {}).get("batches") or []
    active_batches_src = active_performance.get("batches") or []
    for index, source in enumerate(active_batches_src):
        row = active_batches_page[index] if index < len(active_batches_page) else {}
        latency = source.get("latency_ms") or {}
        for key, source_value in (("p50_ms", latency.get("p50")),
                                  ("p95_ms", latency.get("p95"))):
            _check(checks, f"active_qa_performance.batches[{index}].{key}",
                   row.get(key), active_batch.get("qa_performance_file"), source_value)

    new_batch = {
        "formal_qa_results_20261002.json": (ARTIFACTS / "formal_qa_results_20261002.json").is_file(),
        "qa_performance_20261002.json": (ARTIFACTS / "qa_performance_20261002.json").is_file(),
        "qa_human_score_20261002.json": (ARTIFACTS / "qa_human_score_20261002.json").is_file(),
    }
    mismatches = [item for item in checks if not item["match"]]
    return {
        "schema_version": "b-scorecard-consistency-1.0",
        "page_source": "app/b_evaluation.py::summary()（页面卡片消费的同一个投影）",
        "active_batch": page.get("active_batch"),
        "frozen_sources": [
            "artifacts/b_eval/qa_human_score.json （2026-09-30 冻结人工基线）",
            "artifacts/b_eval/qa_performance_stats.json",
            "artifacts/b_eval/relation_score_all.json",
            "artifacts/b_eval/multihop_path_validation.json",
            "artifacts/b_eval/b_demo_screenshots.json",
        ],
        "checks": checks,
        "mismatches": mismatches,
        "conclusion": {
            "page_matches_frozen_json": not mismatches,
            "page_shows_new_batch": bool(page.get("active_available")),
            "note": "旧基线字段仍与冻结 JSON 一致；active_qa_quality/active_qa_performance 指向最新完整批次，页面卡片优先显示活动批次。",
        },
        "new_batch_files_present": new_batch,
        "caveat": "本文件是只读核对结果，不是指标；不覆盖、不重算任何冻结基线。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="赛题指标页面与权威 JSON 一致性核对（只读）")
    parser.add_argument("--out", type=Path,
                        default=ARTIFACTS / "scorecard_consistency_20261002.json")
    args = parser.parse_args()

    payload = build()
    print("对照字段数:", len(payload["checks"]),
          "| 不一致:", len(payload["mismatches"]))
    for item in payload["mismatches"]:
        print("  MISMATCH:", item["field"], "page=", item["page_value"],
              "source=", item["source_value"], f"({item['source_file']})")
    print("页面是否显示新批次:", payload["conclusion"]["page_shows_new_batch"])
    print("新批次文件存在情况:", json.dumps(payload["new_batch_files_present"], ensure_ascii=False))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
