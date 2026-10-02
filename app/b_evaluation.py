"""Read the frozen B-task evaluation artifacts without rewriting their meaning.

The B evaluator keeps machine metrics, human labels and non-computable values in
separate files.  This module projects those files into one read-only API shape
for the competition scorecard.  Missing files or unavailable metrics remain
``None``/``available=False``; nothing is inferred from filenames or filled with
zero.
"""

from __future__ import annotations

import json
from typing import Any

from . import config


ARTIFACT_DIR = config.BASE_DIR / "artifacts" / "b_eval"


def _read_json(name: str) -> dict[str, Any] | None:
    path = ARTIFACT_DIR / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _number(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) else None


def _qa_quality(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False}
    answer = payload.get("answer") or {}
    citation = payload.get("citation") or {}
    refusal = payload.get("refusal") or {}
    should_refuse = refusal.get("should_refuse") or {}
    return {
        "available": True,
        "computable": bool(payload.get("computable")),
        "cases_total": _number(payload.get("cases_total")),
        "human_judged_cases": _number(payload.get("human_judged_cases")),
        "pending_human_cases": _number(payload.get("pending_human_cases")),
        "answer_accuracy": _number(answer.get("rate")),
        "answer_numerator": _number(answer.get("numerator")),
        "answer_denominator": _number(answer.get("denominator")),
        "citation_support": _number(citation.get("rate")),
        "citation_numerator": _number(citation.get("numerator")),
        "citation_denominator": _number(citation.get("denominator")),
        "refusal_recall": _number(should_refuse.get("refused_recall")),
        "refusal_numerator": _number(should_refuse.get("correctly_refused")),
        "refusal_denominator": _number(should_refuse.get("n")),
        "refusal_precision": _number(refusal.get("refused_precision")),
        "refusal_accuracy": _number(refusal.get("refusal_accuracy")),
        "target_comparison": payload.get("target_comparison") or {},
        "basis": "B 任务 2026-09-30 冻结人工基线；本次问答链路修改后尚未重新人工标注。",
        "source": "artifacts/b_eval/qa_human_score.json",
    }


def _qa_performance(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False, "batches": []}
    batches: list[dict[str, Any]] = []
    total_timeouts = 0
    total_errors = 0
    for item in payload.get("batches") or []:
        if not isinstance(item, dict):
            continue
        latency = item.get("latency_ms") or {}
        outcomes = item.get("outcomes") or {}
        timeouts = int(outcomes.get("timeouts") or 0)
        errors = int(outcomes.get("errors") or 0)
        total_timeouts += timeouts
        total_errors += errors
        batches.append({
            "label": item.get("label"),
            "cases": item.get("cases"),
            "p50_ms": latency.get("p50"),
            "p95_ms": latency.get("p95"),
            "max_ms": latency.get("max"),
            "answered": outcomes.get("answered"),
            "refused": outcomes.get("refused"),
            "errors": errors,
            "timeouts": timeouts,
        })
    return {
        "available": bool(batches),
        "batches": batches,
        "timeouts": total_timeouts,
        "errors": total_errors,
        "comparison": payload.get("comparison") or {},
        "source": "artifacts/b_eval/qa_performance_stats.json",
    }


def _relation(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False}
    micro = payload.get("micro") or {}
    fn_source = payload.get("fn_source") or {}
    per_dimension = payload.get("per_dimension") or {}
    return {
        "available": True,
        "computable": bool(payload.get("computable")),
        "precision": micro.get("precision"),
        "recall": micro.get("recall"),
        "f1": micro.get("f1"),
        "tp": micro.get("tp"),
        "fp": micro.get("fp"),
        "fn": micro.get("fn"),
        "evaluable_samples": micro.get("evaluable_samples"),
        "fn_source_available": bool(fn_source.get("available")),
        "fn_source_reason": fn_source.get("reason"),
        "dimensions": {
            name: {
                "total": item.get("total"),
                "tp": item.get("tp"),
                "fp": item.get("fp"),
                "undetermined": item.get("undetermined"),
                "precision": item.get("precision"),
                "recall": item.get("recall"),
                "f1": item.get("f1"),
            }
            for name, item in per_dimension.items() if isinstance(item, dict)
        },
        "source": "artifacts/b_eval/relation_score_all.json",
    }


def _multihop(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False}
    counts = payload.get("counts") or {}
    by_type = counts.get("by_chain_type") or {}
    cross = by_type.get("cross_document") or {}
    two_hop = by_type.get("two_hop") or {}
    return {
        "available": True,
        "candidates": counts.get("candidates"),
        "path_found": counts.get("path_found"),
        "no_path": counts.get("no_path"),
        "two_hop_found": two_hop.get("path_found"),
        "two_hop_total": two_hop.get("total"),
        "cross_document_found": cross.get("path_found", 0),
        "cross_document_total": cross.get("total"),
        "missing_edge_kinds": payload.get("missing_edge_kinds") or {},
        "limitations": payload.get("limitations") or [],
        "source": "artifacts/b_eval/multihop_path_validation.json",
    }


def _demo(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {"available": False}
    shots = payload.get("shots") or []
    cited = [item for item in shots if isinstance(item, dict) and item.get("citations")]
    return {
        "available": True,
        "scenarios": len([item for item in shots if item.get("scenario") != "工作台首页"]),
        "screenshots": len(shots),
        "citations": sum(len(item.get("citations") or []) for item in cited),
        "source": "artifacts/b_eval/b_demo_screenshots.json",
    }


def summary() -> dict[str, Any]:
    """Return the current frozen B evidence projection."""

    qa_quality = _qa_quality(_read_json("qa_human_score.json"))
    qa_performance = _qa_performance(_read_json("qa_performance_stats.json"))
    relation = _relation(_read_json("relation_score_all.json"))
    multihop = _multihop(_read_json("multihop_path_validation.json"))
    demo = _demo(_read_json("b_demo_screenshots.json"))
    available = all(item.get("available") for item in (
        qa_quality, qa_performance, relation, multihop,
    ))
    return {
        "available": available,
        "artifact_dir": "artifacts/b_eval",
        "qa_quality": qa_quality,
        "qa_performance": qa_performance,
        "relation": relation,
        "multihop": multihop,
        "demo": demo,
        "evaluation_basis": "冻结基线；新实现必须重新运行机器评测并由人工重新核验后才能更新这些数字。",
        "limitations": [
            "人工指标按人工标签口径计算，partial 或 unknown 不回填为正确。",
            "关系 Recall/F1 只有在存在“应抽取但未抽取”的金标准全集时才会计算。",
            "跨文档题目前验证的是检索连通性，不等于系统已经完成跨文档综合推理。",
            "合成资产和用户名录不会自动升级为真实生产资产证据。",
        ],
    }
