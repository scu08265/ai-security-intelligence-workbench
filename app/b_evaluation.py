"""Read the frozen B-task evaluation artifacts without rewriting their meaning.

The B evaluator keeps machine metrics, human labels and non-computable values in
separate files.  This module projects those files into one read-only API shape
for the competition scorecard.  Missing files or unavailable metrics remain
``None``/``available=False``; nothing is inferred from filenames or filled with
zero.
"""

from __future__ import annotations

import json
import re
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


def _qa_quality(payload: dict[str, Any] | None, batch: dict[str, Any] | None = None, *, source: str | None = None) -> dict[str, Any]:
    if not payload:
        return {"available": False}
    answer = payload.get("answer") or {}
    citation = payload.get("citation") or {}
    refusal = payload.get("refusal") or {}
    should_refuse = refusal.get("should_refuse") or {}
    return {
        "available": True,
        "computable": bool(payload.get("computable")),
        "batch_id": (batch or {}).get("batch_id"),
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
        "strict_answer_rate": _number(answer.get("strict_rate")),
        "strict_answer_denominator": _number(answer.get("strict_denominator")),
        "answer_partial_count": _number(answer.get("partial_counted_not_correct")),
        "answer_undecided": _number(answer.get("undecided")),
        "citation_not_applicable": _number(citation.get("not_applicable")),
        "citation_undecided": _number(citation.get("undecided")),
        "target_comparison": payload.get("target_comparison") or {},
        "basis": ("B 任务 2026-10-02 重评测批次；人工复核完成，当前作为活动批次展示。" if batch else "B 任务 2026-09-30 冻结人工基线；本次问答链路修改后尚未重新人工标注。"),
        "source": source or "artifacts/b_eval/qa_human_score.json",
    }


def _qa_performance(payload: dict[str, Any] | None, batch: dict[str, Any] | None = None, *, source: str | None = None) -> dict[str, Any]:
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
        "batch_id": (batch or {}).get("batch_id"),
        "batches": batches,
        "timeouts": total_timeouts,
        "errors": total_errors,
        "comparison": payload.get("comparison") or {},
        "notes": payload.get("notes") or {},
        "source": source or "artifacts/b_eval/qa_performance_stats.json",
    }


def _relation(payload: dict[str, Any] | None, *, source: str | None = None) -> dict[str, Any]:
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
        "expected_relation_ids": fn_source.get("expected_relation_ids"),
        "missing_relation_ids": len(fn_source.get("missing_relation_ids") or []),
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
        "source": source or "artifacts/b_eval/relation_score_all.json",
    }


def _multihop(payload: dict[str, Any] | None, *, source: str | None = None,
              missing_edges: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "term_reachable": counts.get("term_reachable"),
        "term_not_reachable": counts.get("term_not_reachable"),
        "missing_edge_kinds": (missing_edges or (payload.get("missing_edge_summary") or {}).get("missing_edge_kinds") or payload.get("missing_edge_kinds") or {}),
        "limitations": payload.get("limitations") or [],
        "source": source or "artifacts/b_eval/multihop_path_validation.json",
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


_BATCH_FILE_RE = re.compile(r"^(qa_human_score|qa_performance)_(\d{8})\.json$")
_MULTIHOP_FILE_RE = re.compile(r"^multihop_path_validation_(\d{8})(_v2)?\.json$")
_RELATION_GOLD_RE = re.compile(r"^relation_score_gold_(\d{8})\.json$")
_CONTRAST_RELATION_RE = re.compile(r"^relation_score_gold_frozen(\d{8})_(\d{8})\.json$")


def _active_relation() -> str | None:
    """Newest gold-scored relation file, where recall/F1 become computable."""
    found: list[str] = []
    for path in ARTIFACT_DIR.glob("relation_score_gold_*.json"):
        match = _RELATION_GOLD_RE.match(path.name)
        if match:
            found.append(match.group(1))
    if not found:
        return None
    return f"relation_score_gold_{max(found)}.json"


def _contrast_relation() -> str | None:
    """Newest score computed against a *frozen* earlier gold.

    Kept separate from the active projection on purpose: the active line says
    how good the system is now, the contrast line says what the same run
    scores against the older ground truth.  Publishing only one of them
    invites the wrong conclusion, so both are exposed.
    """
    found: list[tuple[str, str]] = []
    for path in ARTIFACT_DIR.glob("relation_score_gold_frozen*.json"):
        match = _CONTRAST_RELATION_RE.match(path.name)
        if match:
            found.append((match.group(2), match.group(1)))
    if not found:
        return None
    newest = max(found)
    return f"relation_score_gold_frozen{newest[1]}_{newest[0]}.json"


def _active_multihop() -> str | None:
    """Newest versioned multihop validation file, preferring the v2 revision."""
    found: list[tuple[str, int]] = []
    for path in ARTIFACT_DIR.glob("multihop_path_validation_*.json"):
        match = _MULTIHOP_FILE_RE.match(path.name)
        if match:
            found.append((match.group(1), 1 if match.group(2) else 0))
    if not found:
        return None
    batch_id, _version = max(found, key=lambda item: (item[0], item[1]))
    return f"multihop_path_validation_{batch_id}_v2.json"


def _active_batch() -> dict[str, Any] | None:
    """Return the newest complete B batch, without touching frozen files."""
    batches: dict[str, set[str]] = {}
    for path in ARTIFACT_DIR.glob("qa_*_*.json"):
        match = _BATCH_FILE_RE.match(path.name)
        if not match:
            continue
        prefix, batch_id = match.groups()
        batches.setdefault(batch_id, set()).add(prefix)
    complete = [
        batch_id for batch_id, kinds in batches.items()
        if {"qa_human_score", "qa_performance"} <= kinds
    ]
    if not complete:
        return None
    batch_id = sorted(complete)[-1]
    return {
        "batch_id": batch_id,
        "qa_human_score_file": f"qa_human_score_{batch_id}.json",
        "qa_performance_file": f"qa_performance_{batch_id}.json",
        "label": f"{batch_id[:4]}-{batch_id[4:6]}-{batch_id[6:]}",
    }


def summary() -> dict[str, Any]:
    """Return the current frozen B evidence projection."""

    qa_quality = _qa_quality(_read_json("qa_human_score.json"))
    qa_performance = _qa_performance(_read_json("qa_performance_stats.json"))
    active_batch = _active_batch()
    active_qa_quality = _qa_quality(
        _read_json(active_batch["qa_human_score_file"]) if active_batch else None,
        active_batch,
        source=("artifacts/b_eval/" + active_batch["qa_human_score_file"]) if active_batch else None,
    )
    active_qa_performance = _qa_performance(
        _read_json(active_batch["qa_performance_file"]) if active_batch else None,
        active_batch,
        source=("artifacts/b_eval/" + active_batch["qa_performance_file"]) if active_batch else None,
    )
    relation = _relation(_read_json("relation_score_all.json"))
    active_relation_file = _active_relation()
    contrast_relation_file = _contrast_relation()
    contrast_relation = _relation(
        _read_json(contrast_relation_file) if contrast_relation_file else None,
        source=("artifacts/b_eval/" + contrast_relation_file) if contrast_relation_file else None,
    )
    active_relation = _relation(
        _read_json(active_relation_file) if active_relation_file else None,
        source=("artifacts/b_eval/" + active_relation_file) if active_relation_file else None,
    )
    active_multihop_file = _active_multihop()
    active_multihop = _multihop(
        _read_json(active_multihop_file) if active_multihop_file else None,
        source=("artifacts/b_eval/" + active_multihop_file) if active_multihop_file else None,
    )
    multihop = _multihop(_read_json("multihop_path_validation.json"))
    demo = _demo(_read_json("b_demo_screenshots.json"))
    available = all(item.get("available") for item in (
        qa_quality, qa_performance, relation, multihop,
    ))
    active_available = bool(active_batch) and all(item.get("available") for item in (
        active_qa_quality, active_qa_performance, active_relation, active_multihop,
    ))
    return {
        "available": available,
        "active_available": active_available,
        "active_batch": active_batch,
        "artifact_dir": "artifacts/b_eval",
        "qa_quality": qa_quality,
        "qa_performance": qa_performance,
        "active_qa_quality": active_qa_quality,
        "active_qa_performance": active_qa_performance,
        "relation": relation,
        "active_relation": active_relation,
        "contrast_relation": contrast_relation,
        "multihop": multihop,
        "active_multihop": active_multihop,
        "demo": demo,
        "evaluation_basis": ("旧冻结基线保留；qa_quality / qa_performance 指向改造前基线，active_qa_quality / active_qa_performance 指向最新完整批次。" if active_batch else "冻结基线；新实现必须重新运行机器评测并由人工重新核验后才能更新这些数字。"),
        "limitations": [
            "人工指标按人工标签口径计算，partial 或 unknown 不回填为正确。",
            "关系 Recall/F1 只有在存在“应抽取但未抽取”的金标准全集时才会计算。",
            "跨文档题目前验证的是检索连通性，不等于系统已经完成跨文档综合推理。",
            "合成资产和用户名录不会自动升级为真实生产资产证据。",
        ],
    }
