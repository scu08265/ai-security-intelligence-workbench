"""Local regression evaluation against a gold standard.

This runs the real engine -- `assess_asset`, `enrich_event`, `answer_question`
-- over the verified research cases plus clearly-labelled synthetic fixtures,
and reports what passed and what failed.

It is a small local regression, not a blind benchmark.  Every response says so,
because a passing score here is evidence that the code behaves as specified and
nothing more.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from packaging.version import InvalidVersion, Version

from . import config, intelligence, storage
from .eval_dataset import run_labelled_evaluation

FIXTURE_NOTICE = (
    "本题集为本地回归用的小样本集，其中合成夹具均标注 synthetic；"
    "它不是盲测，没有第三方独立标注，不能代表正式比赛成绩。"
)


@dataclass
class EvalCase:
    id: str
    category: str
    description: str
    check: Callable[[], tuple[bool, str]]
    synthetic: bool = False
    source: str = ""


@dataclass
class EvalResult:
    id: str
    category: str
    description: str
    passed: bool
    detail: str
    synthetic: bool
    source: str
    duration_ms: int = 0
    error: str | None = None


def _bump(version: str, delta: int) -> str | None:
    """Step a version's last release component up or down."""
    try:
        parsed = Version(version)
    except InvalidVersion:
        return None
    release = list(parsed.release)
    if not release:
        return None
    release[-1] = max(0, release[-1] + delta)
    return ".".join(str(p) for p in release)


def _probe_versions(entry: dict) -> tuple[str | None, str | None]:
    """Return (inside, outside) sample versions for a range, if derivable."""
    spec = str(entry.get("range") or "").strip()
    fixed = str(entry.get("fixed_version") or "").strip()
    fixed_version = fixed if fixed and fixed[0].isdigit() and "," not in fixed else None

    if spec.startswith(">=") and ", <" in spec:
        upper = spec.split(", <")[1].strip()
        return _bump(upper, -1), upper
    if spec.startswith("< "):
        upper = spec[2:].strip()
        return _bump(upper, -1), upper
    if spec.startswith("<= "):
        upper = spec[3:].strip()
        return upper, _bump(upper, 1)
    if spec.startswith("= "):
        exact = spec[2:].strip()
        return exact, _bump(exact, 1)
    if fixed_version:
        below = _bump(fixed_version, -1)
        return (below, fixed_version) if below else (None, None)
    return None, None


def _conditions_for(event: dict) -> dict:
    return {c.get("name"): True for c in event.get("conditions") or [] if c.get("name")}


def _asset_for(event: dict, version: str | None, **overrides: Any) -> dict:
    base = {
        "id": f"eval-{event.get('id')}",
        "name": f"评测资产 {event.get('id')}",
        "component": event.get("component"),
        "ecosystem": event.get("ecosystem"),
        "version": version,
        "exposure": "public",
        "business_criticality": "high",
        "conditions": _conditions_for(event),
        "is_demo": True,
        "authorized": True,
    }
    base.update(overrides)
    return base


def _make_cases() -> list[EvalCase]:
    cases: list[EvalCase] = []
    events, _ = storage.list_events(limit=500)
    research = [e for e in events if "verified_research" in (e.get("tags") or [])]

    for event in research:
        event_id = str(event.get("id"))
        entry = (event.get("affected") or [None])[0]
        if not entry:
            continue
        inside, outside = _probe_versions(entry)
        source = f"research/cases.json · {event_id}"

        if inside and outside:
            def version_inside(event=event, inside=inside):
                result = intelligence.assess_asset(event, _asset_for(event, inside))
                ok = result["status"] == "affected"
                return ok, f"版本 {inside} 期望 affected，实际 {result['status']}（{'；'.join(result['reasons'][:2])}）"

            def version_outside(event=event, outside=outside):
                result = intelligence.assess_asset(event, _asset_for(event, outside))
                ok = result["status"] == "not_affected"
                return ok, f"版本 {outside} 期望 not_affected，实际 {result['status']}（{'；'.join(result['reasons'][:2])}）"

            cases.append(EvalCase(
                id=f"{event_id}::version-inside", category="版本边界",
                description=f"{event_id} 版本落在受影响区间内应判定为受影响",
                check=version_inside, source=source))
            cases.append(EvalCase(
                id=f"{event_id}::version-outside", category="版本边界",
                description=f"{event_id} 版本等于修复版本应判定为不受影响",
                check=version_outside, source=source))

        def unknown_version(event=event):
            result = intelligence.assess_asset(event, _asset_for(event, None))
            ok = result["status"] == "needs_confirmation"
            return ok, f"版本未知时期望 needs_confirmation，实际 {result['status']}"

        def missing_condition(event=event):
            asset = _asset_for(event, None)
            asset["version"] = inside or "1.0.0"
            asset["conditions"] = {}
            result = intelligence.assess_asset(event, asset)
            ok = result["status"] == "needs_confirmation"
            return ok, f"关键配置未知时期望 needs_confirmation，实际 {result['status']}"

        def out_of_scope(event=event):
            asset = _asset_for(event, inside or "1.0.0", authorized=False)
            result = intelligence.assess_asset(event, asset)
            ok = result["status"] == "not_applicable"
            return ok, f"未授权资产期望 not_applicable，实际 {result['status']}"

        def withdrawn(event=event):
            withdrawn_event = dict(event)
            withdrawn_event["withdrawn"] = True
            withdrawn_event["status"] = "withdrawn"
            result = intelligence.assess_asset(withdrawn_event, _asset_for(event, inside or "1.0.0"))
            ok = result["status"] == "needs_confirmation"
            return ok, f"撤回事件期望 needs_confirmation，实际 {result['status']}"

        def attack_chain(event=event, event_id=event_id):
            # `event_id` must be bound per-iteration; a late-bound closure here
            # would query the last event of the loop for every case.
            answer = intelligence.answer_question(
                f"{event_id} 的攻击链是什么？", [event], [], model_config=None)
            has_sourced = any(r.get("evidence_ids") for r in event.get("relationships") or [])
            ok = has_sourced or "拒绝补写" in answer["answer"]
            return ok, "有来源关系时展示攻击链，缺证据时明确拒答"

        def enrichment_gaps(event=event):
            enriched = intelligence.enrich_event(event)
            gaps = (enriched.get("enrichment") or {}).get("gaps") or []
            trace = (enriched.get("enrichment") or {}).get("trace") or []
            ok = bool(gaps) and bool(trace) and bool(trace[-1].get("stop_reason"))
            return ok, f"报告 {len(gaps)} 个证据缺口，调度轨迹含停止原因"

        cases.append(EvalCase(id=f"{event_id}::unknown-version", category="未知处理",
                              description=f"{event_id} 资产版本未知时不得判为不受影响",
                              check=unknown_version, source=source))
        cases.append(EvalCase(id=f"{event_id}::missing-condition", category="未知处理",
                              description=f"{event_id} 关键配置未知时不得判为不受影响",
                              check=missing_condition, source=source))
        cases.append(EvalCase(id=f"{event_id}::out-of-scope", category="授权边界",
                              description=f"{event_id} 未授权资产不作影响判断",
                              check=out_of_scope, source=source))
        cases.append(EvalCase(id=f"{event_id}::withdrawn", category="撤回处理",
                              description=f"{event_id} 事件撤回后结论失效，不得视为安全",
                              check=withdrawn, source=source))
        cases.append(EvalCase(id=f"{event_id}::attack-chain", category="拒答策略",
                              description=f"{event_id} 攻击链缺少来源关系时必须拒答",
                              check=attack_chain, source=source))
        cases.append(EvalCase(id=f"{event_id}::enrichment", category="证据缺口",
                              description=f"{event_id} 富化应报告证据缺口与停止原因",
                              check=enrichment_gaps, source=source))

    cases.extend(_synthetic_cases(research))
    return cases


def _synthetic_cases(research: list[dict]) -> list[EvalCase]:
    """Fixtures written by hand.  Every one is flagged synthetic."""
    fixture_event = {
        "id": "SYNTHETIC-0001",
        "aliases": ["SYNTHETIC-GHSA-0001"],
        "title": "Synthetic AI inference component issue (fixture)",
        "summary": "Synthetic fixture used only for local regression.",
        "component": "SyntheticAI",
        "ecosystem": "PyPI",
        "published_at": "2026-01-01T00:00:00Z",
        "modified_at": None,
        "collected_at": "2026-01-01T00:00:00Z",
        "withdrawn": False,
        "status": "confirmed",
        "affected": [{"package": "SyntheticAI", "ecosystem": "PyPI", "range": ">=1.2.0, <1.10.0",
                      "fixed_version": "1.10.0", "source_id": "synthetic-src-1"}],
        "conditions": [{"name": "remote_api", "value": True, "description": "synthetic",
                        "source_id": "synthetic-src-1"}],
        "severity": "high",
        "cvss": [{"version": "3.1", "score": 8.1, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                  "source_id": "synthetic-src-1"}],
        "cwes": ["CWE-125"],
        "sources": [{"id": "synthetic-src-1", "url": "https://example.invalid/synthetic",
                     "title": "Synthetic fixture", "publisher": "Fixture", "source_type": "synthetic",
                     "excerpt": "Synthetic fixture only.", "published_at": None,
                     "collected_at": "2026-01-01T00:00:00Z", "content_hash": "synthetic",
                     "trust": "fixture"}],
        "references": [],
        "poc": [],
        "ai_relevance": {"included": True, "reason": "synthetic fixture"},
        "tags": ["synthetic"],
        "relationships": [],
        "content_hash": "synthetic",
    }

    def case(name, description, check):
        return EvalCase(id=f"SYNTHETIC-0001::{name}", category="合成夹具",
                        description=description, check=check, synthetic=True,
                        source="tests fixture (synthetic)")

    def semantic_versioning():
        low = intelligence.assess_asset(fixture_event, _asset_for(fixture_event, "1.9.0"))
        high = intelligence.assess_asset(fixture_event, _asset_for(fixture_event, "1.10.0"))
        ok = low["status"] == "affected" and high["status"] == "not_affected"
        return ok, f"1.9.0 → {low['status']}（期望 affected）；1.10.0 → {high['status']}（期望 not_affected）"

    def condition_blocks():
        asset = _asset_for(fixture_event, "1.5.0")
        asset["conditions"] = {"remote_api": False}
        result = intelligence.assess_asset(fixture_event, asset)
        ok = result["status"] == "not_affected"
        return ok, f"配置不满足触发条件时期望 not_affected，实际 {result['status']}"

    def unparseable_range_is_conservative():
        broken = dict(fixture_event)
        broken["affected"] = [{"package": "SyntheticAI", "ecosystem": "PyPI",
                               "range": "before the spring release", "fixed_version": None,
                               "source_id": "synthetic-src-1"}]
        result = intelligence.assess_asset(broken, _asset_for(broken, "1.5.0"))
        ok = result["status"] == "needs_confirmation"
        return ok, f"无法解析的区间期望 needs_confirmation，实际 {result['status']}"

    def unsourced_poc_not_invented():
        enriched = intelligence.enrich_event(fixture_event)
        dimension = next(d for d in enriched["enrichment"]["dimensions"] if d["name"] == "poc")
        ok = dimension["status"] == "missing" and "不等同于不存在" in dimension["detail"]
        return ok, f"未收录 POC 时标记为缺口且不推断其不存在：{dimension['detail'][:40]}"

    def no_match_has_no_claims():
        answer = intelligence.answer_question("完全无关的合成问题", [fixture_event], [])
        ok = answer["claims"] == [] and answer["citations"] == []
        return ok, "无匹配事件时不产生任何无证据陈述"

    def component_mismatch_not_applicable():
        asset = _asset_for(fixture_event, "1.5.0", component="UnrelatedComponent")
        result = intelligence.assess_asset(fixture_event, asset)
        ok = result["status"] == "not_applicable"
        return ok, f"组件不匹配期望 not_applicable，实际 {result['status']}"

    return [
        case("semantic-versioning", "版本比较按语义而非字符串（合成夹具）", semantic_versioning),
        case("condition-blocks", "配置条件不满足时判为不受影响（合成夹具）", condition_blocks),
        case("unparseable-range", "无法解析的版本区间不作安全推断（合成夹具）", unparseable_range_is_conservative),
        case("poc-absence", "未收录 POC 不等同于不存在（合成夹具）", unsourced_poc_not_invented),
        case("no-match", "无匹配事件时不编造结论（合成夹具）", no_match_has_no_claims),
        case("component-mismatch", "组件不匹配时不作影响判断（合成夹具）", component_mismatch_not_applicable),
    ]


def run_evaluation() -> dict:
    """Execute the gold-standard regression and return honest metrics."""
    started_at = storage.utcnow()
    started = time.monotonic()
    cases = _make_cases()

    results: list[EvalResult] = []
    for case in cases:
        began = time.monotonic()
        try:
            passed, detail = case.check()
            error = None
        except Exception as exc:  # noqa: BLE001 - a crashing case is a failure, not a crash
            passed, detail = False, "用例执行异常"
            error = f"{type(exc).__name__}: {exc}"
        results.append(EvalResult(
            id=case.id, category=case.category, description=case.description,
            passed=passed, detail=detail, synthetic=case.synthetic, source=case.source,
            duration_ms=int((time.monotonic() - began) * 1000), error=error,
        ))

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = by_category.setdefault(result.category, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        bucket["passed" if result.passed else "failed"] += 1

    real = [r for r in results if not r.synthetic]
    synthetic = [r for r in results if r.synthetic]
    metrics = {
        "cases_total": total,
        "cases_passed": passed,
        "cases_failed": total - passed,
        "accuracy": round(passed / total, 4) if total else None,
        "real_case_count": len(real),
        "real_case_passed": sum(1 for r in real if r.passed),
        "synthetic_case_count": len(synthetic),
        "synthetic_case_passed": sum(1 for r in synthetic if r.passed),
        "by_category": by_category,
    }
    stored_events, _ = storage.list_events(limit=500)
    labelled_metrics = run_labelled_evaluation(stored_events, storage.list_assets())
    for key in ("retrieval_precision", "retrieval_recall", "answer_accuracy",
                "citation_accuracy", "refusal_accuracy"):
        metrics[key] = labelled_metrics[key]
    metrics["labelled_counts"] = labelled_metrics["counts"]
    metrics["qa_response_duration_ms"] = labelled_metrics["response_duration_ms"]

    limitations = [
        FIXTURE_NOTICE,
        f"本次共 {total} 条用例，其中真实核验案例导出 {len(real)} 条、合成夹具 {len(synthetic)} 条，样本量小，置信区间宽。",
        "未做盲测：用例与系统均由同一团队编写，存在共同偏差；正式成绩需冻结样本后由第三方独立标注。",
        "评测只覆盖版本边界、条件判定、授权边界、撤回处理与拒答策略，未覆盖全部生产场景。",
        "未对模型辅助路径评分：模型调用结果具有随机性，需单独设计重复实验。",
        "检索、问答、引用与拒答指标来自 evaluation/gold_cases.json；real_verified 与 synthetic_regression 分开标注，但均非第三方盲测。",
    ]

    payload = {
        "status": "completed",
        "scope": "本地金标准回归：research/cases.json 中已核验的 AI 基础设施漏洞案例 + 标注 synthetic 的合成夹具",
        "started_at": started_at,
        "finished_at": storage.utcnow(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "mode": config.mode_label(),
        "metrics": metrics,
        "results": [
            {
                "id": r.id, "category": r.category, "description": r.description,
                "passed": r.passed, "detail": r.detail, "synthetic": r.synthetic,
                "source": r.source, "duration_ms": r.duration_ms, "error": r.error,
            }
            for r in results
        ],
        "limitations": limitations,
        "note": "分数仅在真实执行后产生；小样本结果不代表正式盲测成绩。",
    }
    storage.save_run({
        "id": storage.new_id("run"), "kind": "evaluation", "status": "completed",
        "started_at": started_at, "finished_at": payload["finished_at"],
        "summary": f"本地回归评测：{passed}/{total} 通过（准确率 {metrics['accuracy']}）",
        "detail": {"metrics": metrics, "limitations": limitations,
                   "duration_ms": payload["duration_ms"]},
    })
    return payload


def latest_evaluation() -> dict:
    """Return the most recent evaluation, or an explicit not-run status."""
    run = storage.latest_run("evaluation")
    if not run:
        return {
            "status": "not_run",
            "metrics": {},
            "results": [],
            "limitations": ["尚未执行评测；未执行时不提供任何分数。"],
            "detail": None,
        }
    detail = run.get("detail") or {}
    return {
        "status": "completed",
        "executed_at": run.get("finished_at"),
        "summary": run.get("summary"),
        "metrics": detail.get("metrics") or {},
        "results": [],
        "limitations": detail.get("limitations") or [FIXTURE_NOTICE],
        "note": "以上为最近一次执行摘要；重新执行可获取完整逐条结果。",
    }
