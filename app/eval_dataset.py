"""Reusable labelled-set format and metric computation, separate from engines."""

from __future__ import annotations

import json
import time
from pathlib import Path

DATASET_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "gold_cases.json"


def load_cases(path: Path = DATASET_PATH) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ValueError("unsupported evaluation dataset schema")
    cases = payload.get("cases") or []
    for case in cases:
        if case.get("provenance") not in {"real_verified", "synthetic_regression"}:
            raise ValueError(f"case {case.get('id')} lacks an explicit provenance")
    return cases


def score_records(gold: list[dict], predictions: dict[str, dict]) -> dict:
    """Score retrieval, answer, citation and refusal without hiding denominators."""
    tp = fp = fn = answer_ok = citation_ok = refusal_ok = 0
    answer_n = citation_n = refusal_n = 0
    details = []
    for case in gold:
        pred = predictions.get(case["id"], {})
        expected = set(case.get("expected_event_ids") or [])
        actual = set(pred.get("event_ids") or [])
        tp += len(expected & actual); fp += len(actual - expected); fn += len(expected - actual)
        required = [str(x).casefold() for x in case.get("required_answer_terms") or []]
        answer = str(pred.get("answer") or "").casefold()
        if required:
            answer_n += 1; answer_ok += int(all(term in answer for term in required))
        expected_citations = set(case.get("expected_evidence_ids") or [])
        if expected_citations:
            citation_n += 1
            citation_ok += int(expected_citations <= set(pred.get("evidence_ids") or []))
        if case.get("should_refuse") is not None:
            refusal_n += 1; refusal_ok += int(bool(pred.get("refused")) == bool(case["should_refuse"]))
        details.append({"id": case["id"], "provenance": case["provenance"], "retrieved": sorted(actual)})
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {
        "retrieval_precision": round(precision, 4) if precision is not None else None,
        "retrieval_recall": round(recall, 4) if recall is not None else None,
        "answer_accuracy": round(answer_ok / answer_n, 4) if answer_n else None,
        "citation_accuracy": round(citation_ok / citation_n, 4) if citation_n else None,
        "refusal_accuracy": round(refusal_ok / refusal_n, 4) if refusal_n else None,
        "counts": {"retrieval_tp": tp, "retrieval_fp": fp, "retrieval_fn": fn,
                   "answer_cases": answer_n, "citation_cases": citation_n, "refusal_cases": refusal_n},
        "details": details,
    }


def run_labelled_evaluation(events: list[dict], assets: list[dict], path: Path = DATASET_PATH) -> dict:
    """Run the labelled set through the public QA engine."""
    from . import intelligence

    cases = load_cases(path)
    synthetic = {
        "id": "SYNTHETIC-CVE-0001", "title": "Synthetic inference issue",
        "summary": "Synthetic regression fixture.", "component": "SyntheticServe",
        "ecosystem": "PyPI", "status": "confirmed", "withdrawn": False,
        "affected": [{"package": "SyntheticServe", "ecosystem": "PyPI",
                      "range": "<2.0.0", "fixed_version": "2.0.0", "source_id": "synthetic-src"}],
        "conditions": [], "relationships": [], "poc": [], "severity": "high", "cvss": [],
        "sources": [{"id": "synthetic-src", "url": "https://example.invalid/synthetic",
                     "title": "Synthetic fixture", "publisher": "Fixture", "source_type": "synthetic",
                     "excerpt": "Synthetic only.", "trust": "fixture"}],
        "tags": ["synthetic"], "aliases": []
    }
    corpus = list(events) + [synthetic]
    predictions = {}
    durations_ms: list[float] = []
    for case in cases:
        began = time.perf_counter()
        result = intelligence.answer_question(case["question"], corpus, assets,
                                              history=case.get("history") or [], model_config=None)
        durations_ms.append((time.perf_counter() - began) * 1000)
        evidence = {str(s.get("id")) for s in result.get("citations") or [] if s.get("id")}
        evidence.update(str(i) for c in result.get("claims") or [] for i in c.get("evidence_ids") or [])
        predictions[case["id"]] = {
            "event_ids": result.get("related_event_ids") or [], "answer": result.get("answer") or "",
            "evidence_ids": sorted(evidence), "refused": not bool(result.get("related_event_ids")),
        }
    scored = score_records(cases, predictions)
    scored["response_duration_ms"] = {
        "samples": len(durations_ms),
        "average": round(sum(durations_ms) / len(durations_ms), 3) if durations_ms else None,
        "maximum": round(max(durations_ms), 3) if durations_ms else None,
    }
    return scored
