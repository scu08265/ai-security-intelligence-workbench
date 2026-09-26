"""Agent orchestration: a persistent state machine with traced handoffs.

Roles here are logical responsibilities (planner / retriever / auditor /
assessor), not separate processes -- adding deployment weight to make a
diagram look busier is not a feature.

The interesting part is the *bounded* scheduling loop.  Enrichment reports the
evidence gaps it found; a planner then chooses retrieval tools to close the
ones that are actually closeable, spending at most a small budget.  It stops
when the evidence is sufficient, when a round yields nothing new, or when the
budget runs out -- and it records which of those happened.  Absence of evidence
never becomes evidence of absence: "not in KEV" is recorded as a checked fact
that does NOT mean "not exploited".
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

from . import (agent_context, agent_orchestration, collectors, config, dedupe,
               intelligence, normalize, paper_fulltext, provenance, rag_corpus, storage, sources)

STATE_DISCOVERED = "discovered"
STATE_NORMALIZED = "normalized"
STATE_PENDING_ENRICHMENT = "pending_enrichment"
STATE_PENDING_REVIEW = "pending_review"
STATE_PUBLISHED = "published"
STATE_RETRY = "retry"
STATE_INVALIDATED = "invalidated"

MAX_ROUNDS = 2
TOOL_BUDGET = 3


# --------------------------------------------------------------------------
# retrieval tools (bounded, read-only, no code execution)
# --------------------------------------------------------------------------

def _tool_nvd(event: dict) -> tuple[list[dict], str]:
    cve_id = _cve_of(event)
    if not cve_id:
        return [], "事件没有 CVE 编号，无法查询 NVD"
    payload, raw = collectors.get_json(
        "https://services.nvd.nist.gov/rest/json/cves/2.0", params={"cveId": cve_id}
    )
    storage.save_snapshot("tool_nvd", raw)
    items = payload.get("vulnerabilities") or []
    if not items:
        return [], f"NVD 未收录 {cve_id}"
    other = normalize.nvd_to_event(items[0])
    return ([other] if other else []), f"取得 NVD 记录 {cve_id}"


def _tool_mitre(event: dict) -> tuple[list[dict], str]:
    cve_id = _cve_of(event)
    if not cve_id:
        return [], "事件没有 CVE 编号，无法查询 CVE Program 记录"
    payload, raw = collectors.get_json(f"https://cveawg.mitre.org/api/cve/{cve_id}")
    storage.save_snapshot("tool_mitre", raw)
    other = normalize.mitre_to_event(payload)
    return ([other] if other else []), f"取得 CVE Program 记录 {cve_id}"


def _tool_osv(event: dict) -> tuple[list[dict], str]:
    """Look the event up in OSV by its own identifier or a known alias."""
    for candidate in [event.get("id"), *(event.get("aliases") or [])]:
        if not candidate:
            continue
        try:
            payload, raw = collectors.get_json(f"https://api.osv.dev/v1/vulns/{candidate}")
        except collectors.FetchError:
            continue
        storage.save_snapshot("tool_osv", raw)
        other = normalize.osv_to_event(payload)
        if other:
            return [other], f"取得 OSV 记录 {candidate}"
    return [], "OSV 中没有该标识对应的记录"


def _tool_kev(event: dict) -> tuple[list[dict], str]:
    """Check the exploitation catalog.

    A miss is reported as a checked fact and explicitly NOT as proof the
    vulnerability is unexploited.
    """
    cve_id = _cve_of(event)
    if not cve_id:
        return [], "事件没有 CVE 编号，无法核对在野利用目录"
    payload, raw = collectors.get_json(sources.BY_ID["cisa_kev"].url)
    storage.save_snapshot("tool_kev", raw)
    for entry in payload.get("vulnerabilities") or []:
        if str(entry.get("cveID")) == cve_id:
            other = normalize.kev_to_event(entry)
            return ([other] if other else []), f"CISA KEV 已收录 {cve_id}（存在在野利用记录）"
    return [], f"CISA KEV 当前未收录 {cve_id}；未收录不等于未被利用"


# The third element is the gap label this tool can close.  Labels must match
# the strings `intelligence.enrich_event` actually emits, otherwise the planner
# finds nothing to do and silently stops.
TOOLS: dict[str, tuple[str, Callable[[dict], tuple[list[dict], str]], str]] = {
    "nvd_record": ("查询 NVD 权威记录", _tool_nvd, "受影响版本范围"),
    "mitre_record": ("查询 CVE Program 权威记录", _tool_mitre, "受影响版本范围"),
    "osv_record": ("查询 OSV 生态记录", _tool_osv, "修复版本或缓解措施"),
    "kev_status": ("核对 CISA 在野利用目录", _tool_kev, "在野利用状态"),
}


def _cve_of(event: dict) -> str | None:
    for candidate in [event.get("id"), *(event.get("aliases") or [])]:
        text = str(candidate or "")
        if text.startswith("CVE-"):
            return text
    return None


# --------------------------------------------------------------------------
# planner
# --------------------------------------------------------------------------

def plan_gap_closure(event: dict, gaps: list[str], already: set[str]) -> list[str]:
    """Choose tools for the reported gaps, skipping anything already tried.

    Matching is case-insensitive because gap labels mix Chinese and Latin text.
    """
    plan: list[str] = []
    for gap in gaps:
        needle = gap.casefold()
        if "poc" in needle and "kev_status" not in already and "kev_status" not in plan:
            plan.append("kev_status")
            continue
        for name, (_label, _fn, target) in TOOLS.items():
            if name in already or name in plan:
                continue
            if target.casefold() in needle or needle in target.casefold():
                plan.append(name)
                break
    return plan


def close_evidence_gaps(event: dict, *, max_rounds: int = MAX_ROUNDS,
                        budget: int = TOOL_BUDGET) -> dict:
    """Run the bounded enrichment loop.  Returns the event plus an audit trail."""
    trace: list[dict] = []
    used: set[str] = set()
    calls = 0
    stop_reason = "预算未使用"

    for round_index in range(1, max_rounds + 1):
        enriched = intelligence.enrich_event(event)
        gaps = list((enriched.get("enrichment") or {}).get("gaps") or [])
        if not gaps:
            stop_reason = "证据已齐备"
            break
        plan = plan_gap_closure(event, gaps, used)
        if not plan:
            stop_reason = "没有可用工具能补充剩余缺口"
            break

        progressed = False
        for tool_name in plan:
            if calls >= budget:
                stop_reason = f"达到工具调用预算上限（{budget} 次）"
                break
            label, tool, _target = TOOLS[tool_name]
            used.add(tool_name)
            calls += 1
            started = time.monotonic()
            try:
                found, note = tool(event)
            except collectors.FetchError as exc:
                found, note = [], f"工具执行失败，已如实记录：{exc}"
            elapsed = int((time.monotonic() - started) * 1000)
            trace.append({
                "round": round_index, "role": "retriever", "tool": tool_name,
                "action": label, "evidence_ids": [], "result": note,
                "duration_ms": elapsed, "found": len(found),
            })
            for other in found:
                merged = dedupe.merge_events(event, other)
                if merged.get("content_hash") != event.get("content_hash") or len(
                    merged.get("sources") or []
                ) > len(event.get("sources") or []):
                    progressed = True
                event = merged
        if stop_reason.startswith("达到工具调用预算"):
            break
        if not progressed:
            stop_reason = "本轮未取得新证据，停止调度"
            break

    final = intelligence.enrich_event(event)
    return {
        "event": final,
        "trace": trace,
        "tool_calls": calls,
        "stop_reason": stop_reason,
    }


# --------------------------------------------------------------------------
# per-event state machine
# --------------------------------------------------------------------------

def process_event(event: dict, *, close_gaps: bool = True) -> dict:
    """Advance one event through the pipeline, recording every transition."""
    history: list[dict] = []

    def move(state: str, role: str, note: str) -> None:
        history.append({"state": state, "role": role, "note": note, "at": storage.utcnow()})

    move(STATE_DISCOVERED, "collector", "从登记来源采集到原始记录")
    move(STATE_NORMALIZED, "normalizer", "已转换为规范事件文档")

    if event.get("withdrawn") or event.get("status") == "withdrawn":
        move(STATE_INVALIDATED, "auditor", "来源标注为撤回，相关结论进入失效标记")

    enrichment_trace: list[dict] = []
    stop_reason = None
    tool_calls = 0
    gaps: list[str] | None = None
    if close_gaps and not event.get("withdrawn"):
        move(STATE_PENDING_ENRICHMENT, "planner", "进入富化与证据缺口调度")
        outcome = close_evidence_gaps(event)
        event = outcome["event"]
        enrichment_trace = outcome["trace"]
        tool_calls = outcome["tool_calls"]
        stop_reason = outcome["stop_reason"]
        gaps = list((event.get("enrichment") or {}).get("gaps") or [])
        move(STATE_PENDING_ENRICHMENT, "scheduler", f"调度结束：{stop_reason}")

    withdrawn = bool(event.get("withdrawn") or event.get("status") == "withdrawn")
    if withdrawn:
        # A withdrawn advisory is not enriched and not published; anything
        # derived from it stays invalidated.
        pass
    elif gaps is None:
        # Enrichment was not run, so the evidence gaps are simply unknown.
        # Claiming they are closed would be an unverified statement.
        move(STATE_PENDING_ENRICHMENT, "scheduler",
             "本次未执行富化，证据完整性尚未评估（不等于无缺口）")
    elif gaps:
        move(STATE_PENDING_REVIEW, "evidence_auditor", f"仍有 {len(gaps)} 个证据缺口：{'、'.join(gaps[:4])}")
    else:
        move(STATE_PUBLISHED, "evidence_auditor", "证据齐备，可用于对外结论")

    event["pipeline"] = {
        "state": history[-1]["state"],
        "history": history,
        "scheduler_trace": enrichment_trace,
        "stop_reason": stop_reason,
        "tool_calls": tool_calls,
    }
    return event


def process_and_store(event: dict, *, close_gaps: bool = True) -> dict:
    processed = process_event(event, close_gaps=close_gaps)
    resolved = dedupe.resolve(processed)
    stored = provenance.mark_ingested(resolved.event, storage.utcnow())
    # Keep the pipeline record of the newest processing pass.
    stored["pipeline"] = processed["pipeline"]
    storage.upsert_event(stored)
    return {"action": resolved.action, "event": stored,
            "merged_ids": resolved.merged_ids, "candidate_ids": resolved.candidate_ids}


# `conditions: "ALL_TRUE"` means "this deployment satisfies every trigger
# precondition the advisories list", resolved against the stored events.
DEMO_ASSETS: tuple[dict, ...] = (
    {
        "id": "asset-demo-ollama-vulnerable",
        "name": "演示资产：推理服务 A（合成）",
        "component": "Ollama",
        "ecosystem": "Go",
        "version": "0.16.0",
        "exposure": "public",
        "business_criticality": "high",
        "conditions": "ALL_TRUE",
        "is_demo": True,
        "authorized": True,
    },
    {
        "id": "asset-demo-ollama-patched",
        "name": "演示资产：推理服务 B（合成，已升级）",
        "component": "Ollama",
        "ecosystem": "Go",
        "version": "0.17.1",
        "exposure": "internal",
        "business_criticality": "medium",
        "conditions": "ALL_TRUE",
        "is_demo": True,
        "authorized": True,
    },
    {
        "id": "asset-demo-vllm-unknown-config",
        "name": "演示资产：推理服务 C（合成，配置未知）",
        "component": "vLLM",
        "ecosystem": "PyPI",
        "version": "0.9.0",
        "exposure": "public",
        "business_criticality": "high",
        "conditions": {},
        "is_demo": True,
        "authorized": True,
    },
    {
        "id": "asset-demo-vllm-patched",
        "name": "演示资产：推理服务 D（合成，已升级）",
        "component": "vLLM",
        "ecosystem": "PyPI",
        "version": "0.24.0",
        "exposure": "internal",
        "business_criticality": "low",
        "conditions": "ALL_TRUE",
        "is_demo": True,
        "authorized": True,
    },
    {
        "id": "asset-demo-unauthorized",
        "name": "演示资产：未纳入授权范围的主机（合成）",
        "component": "vLLM",
        "ecosystem": "PyPI",
        "version": "0.9.0",
        "exposure": "unknown",
        "business_criticality": "medium",
        "conditions": {},
        "is_demo": True,
        "authorized": False,
    },
)


def seed_demo_assets() -> dict:
    """Insert the synthetic demo assets.

    Everything here is invented for demonstration and flagged `is_demo`.  No
    claim is made that these correspond to any real host on the internet.

    Condition names are read from the stored events rather than hard-coded, so
    the demo stays correct when the underlying advisories change.
    """
    events, _ = storage.list_events(limit=200)
    created = 0
    for template in DEMO_ASSETS:
        asset = dict(template)
        if asset["conditions"] == "ALL_TRUE":
            names: list[str] = []
            for event in events:
                if _component_matches(event, asset):
                    names.extend(c.get("name") for c in event.get("conditions") or [] if c.get("name"))
            asset["conditions"] = dict.fromkeys(names, True)
            if not asset["conditions"]:
                asset["conditions"] = {}
        storage.upsert_asset(asset)
        created += 1
    return {
        "created": created,
        "notice": "全部为合成演示资产（is_demo=true），不代表任何真实公网资产；"
                  "其中一条未标记授权，用于演示系统拒绝在授权范围外作影响判断。",
    }


def seed_research_cases(path=None) -> dict:
    """Load the verified case file into the store.

    These three cases were checked by hand against official sources, so they
    carry the strongest evidence grade in the corpus and seed the evaluation
    gold standard.
    """
    import json
    from pathlib import Path

    target = Path(path or (config.BASE_DIR / "research" / "cases.json"))
    if not target.exists():
        return {"seeded": 0, "error": f"未找到核验案例文件 {target}"}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"seeded": 0, "error": f"案例文件无法解析：{exc}"}

    seeded = 0
    for case in payload.get("cases") or []:
        event = normalize.research_case_to_event(case)
        process_and_store(event, close_gaps=False)
        seeded += 1
    return {
        "seeded": seeded,
        "accessed_at": payload.get("accessed_at"),
        "policy": payload.get("verification_policy"),
    }


# --------------------------------------------------------------------------
# collection run
# --------------------------------------------------------------------------

def _run_collection_deterministic(
    source_ids: list[str] | None = None, *, close_gaps: bool = False,
    agent_plan: dict | None = None,
) -> dict:
    """Execute a pre-validated collection plan against registered sources."""
    started_at = storage.utcnow()
    run_id = storage.new_id("run")
    selected = source_ids or [s.id for s in sources.SOURCES]
    unknown = [s for s in selected if sources.get(s) is None]
    selected = [s for s in selected if sources.get(s) is not None]

    results: list[dict] = []
    added = updated = merged_total = 0
    candidates = 0
    observed_events: list[dict] = []
    tool_audit: list[dict] = []
    for source_id in selected:
        spec = sources.get(source_id)
        assert spec is not None
        state = storage.source_state(source_id)
        outcome = collectors.collect(source_id, since=state.get("cursor"))
        tool_audit.append(agent_orchestration.audit(
            "collect_registered_source", status=outcome.status,
            result=f"{source_id}: 获取 {outcome.fetched}，保留 {len(outcome.events)}",
            count=len(outcome.events),
        ))
        observed_events.extend(outcome.events)

        per_source_new = 0
        per_source_updated = 0
        event_evidence: list[dict] = []
        paper_fetches = 0
        paper_ids: set[str] = set()
        for event in outcome.events:
            outcome_result = process_and_store(event, close_gaps=close_gaps)
            if outcome_result["action"] == "new":
                per_source_new += 1
            elif outcome_result["action"] in {"updated", "merged"}:
                per_source_updated += 1
            candidates += len(outcome_result["candidate_ids"])
            stored_event = outcome_result["event"]
            paper_result: dict[str, Any] | None = None
            if source_id == "arxiv":
                # The Agent may invoke this only as a registered action, with
                # a fixed arXiv-only URL resolver and a per-run budget.
                candidate_id = paper_fulltext.arxiv_identifier(
                    str((stored_event.get("paper") or {}).get("arxiv_id") or "")
                )
                if candidate_id and candidate_id not in paper_ids and paper_fetches < paper_fulltext.DEFAULT_MAX_PAPERS_PER_RUN:
                    paper_ids.add(candidate_id)
                    paper_fetches += 1
                    paper_result = paper_fulltext.ingest_arxiv_paper(stored_event)
                    stored_event = paper_fulltext.annotate_event(stored_event, paper_result)
                    storage.upsert_event(stored_event)
                    tool_audit.append(agent_orchestration.audit(
                        "ingest_arxiv_fulltext", status=str(paper_result.get("status") or "failed"),
                        result=(f"{candidate_id}: {paper_result.get('chunks', 0)} 个全文分块"
                                if paper_result.get("has_full_text") else
                                f"{candidate_id}: {paper_result.get('reason') or '未形成全文'}"),
                        count=int(paper_result.get("chunks") or 0),
                    ))
            timing = stored_event.get("monitoring") or {}
            delay_seconds = timing.get("publication_to_discovery_seconds")
            event_evidence.append({
                "event_id": stored_event.get("id"),
                "published_at": stored_event.get("published_at"),
                "discovered_at": timing.get("discovered_at"),
                "collected_at": stored_event.get("collected_at"),
                "ingested_at": timing.get("ingested_at"),
                "delay_hours": round(float(delay_seconds) / 3600, 3)
                if delay_seconds is not None else None,
                "within_24h": timing.get("within_24h"),
                "action": outcome_result["action"],
                "paper_fulltext": paper_result,
            })
        added += per_source_new
        updated += per_source_updated
        merged_total += sum(1 for e in outcome.events)

        fields: dict[str, Any] = {
            "status": outcome.status,
            "last_run": storage.utcnow(),
            "last_error": outcome.error,
            "events_count": (state.get("events_count") or 0) + len(outcome.events),
        }
        if outcome.ok:
            fields["last_success"] = storage.utcnow()
        if outcome.cursor and outcome.ok:
            fields["cursor"] = outcome.cursor
        if outcome.snapshot_hash:
            fields["last_hash"] = outcome.snapshot_hash
        storage.update_source_state(source_id, **fields)

        results.append({
            "source_id": source_id,
            "name": spec.name,
            "status": outcome.status,
            "fetched": outcome.fetched,
            "kept": len(outcome.events),
            "filtered": outcome.filtered,
            "events_added": per_source_new,
            "events_updated": per_source_updated,
            "duration_ms": outcome.duration_ms,
            "error": outcome.error,
            "snapshot_hash": outcome.snapshot_hash,
            "notes": outcome.notes,
            "timeliness": provenance.summarize(outcome.events),
            "events": event_evidence,
            "paper_fulltext_attempted": paper_fetches if source_id == "arxiv" else 0,
        })

    failed = [r for r in results if r["status"] == "failed"]
    status = "completed" if not failed else ("partial" if len(failed) < len(results) else "failed")
    detail = {
        "results": results,
        "unknown_source_ids": unknown,
        "duplicate_candidates": candidates,
        "timeliness": provenance.summarize(observed_events),
        "agent_plan": agent_plan or {"kind": "collection", "planner": "legacy"},
        "tool_calls": tool_audit,
    }
    if not close_gaps:
        detail["note"] = "采集阶段只做规范化与去重；富化在大批量任务中单独执行以控制外网调用开销"

    finished_at = storage.utcnow()
    storage.save_run({
        "id": run_id, "kind": "collect", "status": status,
        "started_at": started_at, "finished_at": finished_at,
        "summary": f"采集 {len(selected)} 个来源：新增 {added}，更新 {updated}，失败 {len(failed)}",
        "detail": detail,
    })
    return {
        "run_id": run_id, "status": status, "results": results,
        "events_added": added, "events_updated": updated,
        "duration_ms": _elapsed_ms(started_at),
        "started_at": started_at, "finished_at": finished_at,
        "agent_plan": detail["agent_plan"], "tool_calls": tool_audit,
    }


def run_collection(source_ids: list[str] | None = None, *, close_gaps: bool = False) -> dict:
    """Let the bounded Agent plan, then execute only registered collectors.

    The LLM, when configured, cannot add sources or network destinations.  Its
    plan is persisted with the observable per-source results; without a model,
    the same executor runs a deterministic plan.
    """
    requested = source_ids or [source.id for source in sources.SOURCES]
    valid = [source_id for source_id in requested if sources.get(source_id) is not None]
    plan = agent_orchestration.collection_plan(valid, config.model_config() or None)
    return _run_collection_deterministic(requested, close_gaps=close_gaps, agent_plan=plan)


def _elapsed_ms(started_at: str) -> int:
    from datetime import datetime

    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return 0
    now = datetime.fromisoformat(storage.utcnow().replace("Z", "+00:00"))
    return int((now - start).total_seconds() * 1000)


# --------------------------------------------------------------------------
# enrichment run
# --------------------------------------------------------------------------

def run_enrichment(limit: int = 20, *, only_pending: bool = True) -> dict:
    """Enrich stored events, running the gap-closing scheduler on each."""
    started_at = storage.utcnow()
    run_id = storage.new_id("run")
    events, _ = storage.list_events(limit=500)
    if only_pending:
        # "Pending" means either never enriched, or enriched with gaps left.
        events = [
            e for e in events
            if e.get("kind", "vulnerability") == "vulnerability"
            and not e.get("withdrawn") and (
                not e.get("enrichment") or (e.get("enrichment") or {}).get("gaps")
            )
        ]
    events = events[:limit]

    enriched = 0
    total_calls = 0
    closed = 0
    for event in events:
        before = set(((intelligence.enrich_event(event).get("enrichment") or {}).get("gaps")) or [])
        result = close_evidence_gaps(event)
        after = set((result["event"].get("enrichment") or {}).get("gaps") or [])
        updated = result["event"]
        updated["pipeline"] = {
            "state": STATE_PUBLISHED if not after else STATE_PENDING_REVIEW,
            "history": [{
                "state": STATE_PENDING_ENRICHMENT, "role": "planner",
                "note": f"补证调度：{result['stop_reason']}", "at": storage.utcnow(),
            }],
            "scheduler_trace": result["trace"],
            "stop_reason": result["stop_reason"],
            "tool_calls": result["tool_calls"],
        }
        storage.upsert_event(updated)
        enriched += 1
        total_calls += result["tool_calls"]
        if len(after) < len(before):
            closed += 1

    storage.save_run({
        "id": run_id, "kind": "enrich", "status": "completed",
        "started_at": started_at, "finished_at": storage.utcnow(),
        "summary": f"富化 {enriched} 条，{closed} 条缺口减少，共 {total_calls} 次工具调用",
        "detail": {"events": enriched, "gaps_closed": closed, "tool_calls": total_calls},
    })
    return {
        "run_id": run_id, "events": enriched, "gaps_closed": closed,
        "tool_calls": total_calls, "duration_ms": _elapsed_ms(started_at),
    }


# --------------------------------------------------------------------------
# assessment run
# --------------------------------------------------------------------------

def run_assessment() -> dict:
    """Assess every event against every authorised asset and store the results."""
    started_at = storage.utcnow()
    run_id = storage.new_id("run")
    assets = storage.list_assets()
    events, _ = storage.list_events(limit=500)

    stored = 0
    not_applicable = 0
    for event in events:
        for asset in assets:
            if not _component_matches(event, asset):
                continue
            # Out-of-scope assets are still assessed, so the record shows the
            # system declining to judge rather than silently skipping them.
            assessment = intelligence.assess_asset(event, asset)
            storage.save_assessment(assessment)
            stored += 1
            if assessment.get("status") == "not_applicable":
                not_applicable += 1

    storage.save_run({
        "id": run_id, "kind": "assess", "status": "completed",
        "started_at": started_at, "finished_at": storage.utcnow(),
        "summary": f"对 {len(events)} 个事件与 {len(assets)} 个资产执行影响判断，生成 {stored} 条结论"
                   f"（其中 {not_applicable} 条因不在授权范围而未作判断）",
        "detail": {"events": len(events), "assets": len(assets),
                   "assessments": stored, "not_applicable": not_applicable},
    })
    return {"run_id": run_id, "assessments": stored, "assets": len(assets),
            "events": len(events), "not_applicable": not_applicable,
            "duration_ms": _elapsed_ms(started_at)}


def _component_matches(event: dict, asset: dict) -> bool:
    def norm(value: str | None) -> str:
        import re

        return re.sub(r"[\s_.\-/]+", "", (value or "").casefold())

    target = norm(asset.get("component"))
    if not target:
        return False
    names = {norm(event.get("component")), *(norm(a) for a in event.get("aliases") or [])}
    if target in names:
        return True
    return any(norm(item.get("package")) == target for item in event.get("affected") or [])


# --------------------------------------------------------------------------
# question answering
# --------------------------------------------------------------------------

def _persist_answer_context(
    question: str, result: dict, *, thread_id: str | None = None,
) -> str | None:
    """Persist only visible, structured context after a completed answer.

    The Q&A engine owns conversational resolution; this adapter translates its
    result into the immutable, evidence-versioned thread ledger.  It never
    stores prompts, scratchpads or model reasoning.
    """
    try:
        thread = agent_context.get_thread(thread_id) if thread_id else None
        if not thread:
            thread = agent_context.create_thread(question, thread_id=thread_id)
        snapshot = result.get("context_snapshot") or {}
        references: list[dict[str, str]] = []
        for reference in snapshot.get("resolved_references") or []:
            kind = reference.get("type")
            expression = str(reference.get("expression") or "resolved")
            for identifier in reference.get("ids") or []:
                references.append({
                    "mention": expression, "kind": str(kind),
                    "resolved_id": str(identifier), "method": "conversation_resolution",
                })
        event_ids = list(snapshot.get("selected_event_ids") or [])
        asset_ids = list(snapshot.get("selected_asset_ids") or [])
        document_ids = list(snapshot.get("selected_document_ids") or [])
        chunks = ((result.get("rag") or {}).get("context_chunks") or [])
        chunk_ids = [str(chunk.get("id")) for chunk in chunks if chunk.get("id")]
        for citation in result.get("document_citations") or []:
            document_id = citation.get("document_id")
            if document_id and document_id not in document_ids:
                document_ids.append(str(document_id))
        constraints = snapshot.get("inherited_constraints") or {}
        constraint_items = (
            ["asset_overrides=" + json.dumps(constraints.get("asset_overrides"), ensure_ascii=False, sort_keys=True)]
            if isinstance(constraints, dict) and constraints.get("asset_overrides") else []
        )
        saved = agent_context.append_turn(
            thread["id"], visible_user_input=question,
            visible_assistant_output=str(result.get("answer") or ""),
            focus_event_id=str(event_ids[0]) if event_ids else None,
            focus_asset_id=str(asset_ids[0]) if asset_ids else None,
            focus_document_id=str(document_ids[0]) if document_ids else None,
            constraints=constraint_items, resolved_references=references,
            chunk_ids=chunk_ids,
        )
        result["thread_id"] = thread["id"]
        result["persisted_context_snapshot"] = saved["context_snapshot"]
        return thread["id"]
    except (KeyError, ValueError):
        # An answer remains useful if its optional audit record cannot be
        # written.  Surface the fact instead of fabricating a snapshot.
        result.setdefault("limitations", []).append("本轮上下文快照未能写入审计库；回答证据不受影响")
        return None


def answer(
    question: str, history: list[dict] | None = None, *,
    context_snapshot: dict | None = None, thread_id: str | None = None,
) -> dict:
    """Execute a bounded Agent evidence plan and record every visible action."""
    started_at = storage.utcnow()
    run_id = storage.new_id("run")
    started = time.monotonic()
    model = config.model_config() or None
    # The planner sees only a short question and action names.  It cannot see
    # credentials and has no route to invent a source/tool parameter.
    plan = agent_orchestration.answer_plan(question, has_assets=bool(storage.list_assets()), model=model)
    tool_calls: list[dict] = []
    events: list[dict] = []
    assets: list[dict] = []
    chunks: list[dict] = []
    for action in plan["actions"]:
        if action == "load_event_evidence":
            events, _ = storage.list_events(limit=500)
            tool_calls.append(agent_orchestration.audit(
                action, status="completed", result="已读取本地事件证据快照", count=len(events)))
        elif action == "load_knowledge_evidence":
            chunks = rag_corpus.list_chunk_records(current_only=True)
            tool_calls.append(agent_orchestration.audit(
                action, status="completed", result="已读取版本化知识分块", count=len(chunks)))
        elif action == "load_authorized_assets":
            assets = storage.list_assets()
            authorised = sum(1 for asset in assets if asset.get("authorized"))
            tool_calls.append(agent_orchestration.audit(
                action, status="completed", result="已读取资产范围快照", count=authorised))
        elif action == "answer_from_evidence":
            # Action order is validated by the planner wrapper.  A missing
            # read remains an empty snapshot, producing a grounded refusal
            # rather than an implicit external lookup.
            result = intelligence.answer_question(
                question, events, assets, history=history, model_config=model,
                rag_chunks=chunks, context_snapshot=context_snapshot,
            )
            tool_calls.append(agent_orchestration.audit(
                action, status="completed", result="已按本轮证据快照生成结论",
                count=len(result.get("related_event_ids") or [])))

    # A plan is never allowed to omit its evidence finalizer, but retain this
    # guard so a future catalogue change fails safely.
    if "result" not in locals():
        result = {
            "answer": "本轮计划缺少证据回答动作，系统未生成结论。",
            "mode": "planning_error", "citations": [], "related_event_ids": [],
            "assessments": [], "limitations": ["受限动作计划不完整"], "trace": [],
        }
        tool_calls.append(agent_orchestration.audit(
            "answer_from_evidence", status="blocked", result="计划不完整，安全停止"))

    result["agent_plan"] = plan
    result["tool_calls"] = tool_calls
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    result["run_id"] = run_id

    for assessment in result.get("assessments") or []:
        storage.save_assessment(assessment)

    _persist_answer_context(question, result, thread_id=thread_id)

    storage.save_run({
        "id": run_id, "kind": "chat", "status": "completed",
        "started_at": started_at, "finished_at": storage.utcnow(),
        "summary": f"问答（{result.get('mode')}）：{question[:60]}",
        "detail": {
            "question": question, "mode": result.get("mode"),
            "related_event_ids": result.get("related_event_ids"),
            "citations": len(result.get("citations") or []),
            "duration_ms": result["duration_ms"],
            "agent_plan": plan,
            "tool_calls": tool_calls,
        },
    })
    return result


# --------------------------------------------------------------------------
# dashboard support
# --------------------------------------------------------------------------

def monitoring_summary() -> dict:
    """Honest source coverage: registered vs. actually producing data."""
    states = storage.all_source_states()
    items = []
    producing = 0
    for spec in sources.SOURCES:
        state = states.get(spec.id, {})
        count = int(state.get("events_count") or 0)
        if count > 0:
            producing += 1
        items.append({
            "id": spec.id, "name": spec.name, "category": spec.category,
            "category_label": spec.category_label, "mode": spec.mode,
            "realtime": spec.realtime, "independent_origin": spec.independent_origin,
            "requires_token_env": spec.requires_token_env,
            "status": state.get("status") or "idle",
            "last_run": state.get("last_run"), "last_success": state.get("last_success"),
            "last_error": state.get("last_error"), "events_count": count,
            "cursor": state.get("cursor"),
        })
    coverage = sources.coverage()
    coverage.update({
        "endpoints_with_data": producing,
        "endpoints_without_data": len(sources.SOURCES) - producing,
        "note": "仅登记而未产生有效数据的端点不计为已接入",
    })
    return {"items": items, "coverage": coverage}


def monitoring_evidence(days: int = 7) -> dict:
    """Build an honest daily evidence ledger from persisted runs and observations.

    Missing days remain present with zero runs.  This makes the structure useful
    for a seven-day trial without manufacturing history before the trial exists.
    """
    from datetime import datetime, timedelta, timezone

    days = max(1, min(int(days), 31))
    today = datetime.now(timezone.utc).date()
    dates = [today - timedelta(days=offset) for offset in reversed(range(days))]
    buckets = {
        day.isoformat(): {
            "date": day.isoformat(), "collection_runs": 0, "successful_runs": 0,
            "partial_or_failed_runs": 0, "events_observed": 0,
            "events_with_publisher_time": 0, "within_24h": 0, "over_24h": 0,
            "sources": [],
        }
        for day in dates
    }
    for run in storage.list_runs(limit=200):
        if run.get("kind") != "collect" or not run.get("started_at"):
            continue
        day = str(run["started_at"])[:10]
        if day not in buckets:
            continue
        bucket = buckets[day]
        bucket["collection_runs"] += 1
        if run.get("status") == "completed":
            bucket["successful_runs"] += 1
        else:
            bucket["partial_or_failed_runs"] += 1
        for result in (run.get("detail") or {}).get("results") or []:
            if result.get("status") in {"ok", "partial"}:
                bucket["sources"].append(result.get("source_id"))

    events, _ = storage.list_events(limit=2000)
    for event in events:
        for observation in event.get("monitoring_observations") or []:
            day = str(observation.get("discovered_at") or "")[:10]
            if day not in buckets:
                continue
            bucket = buckets[day]
            bucket["events_observed"] += 1
            latency = observation.get("publication_to_discovery_seconds")
            if latency is not None:
                bucket["events_with_publisher_time"] += 1
                bucket["within_24h" if float(latency) <= 86400 else "over_24h"] += 1
    for bucket in buckets.values():
        bucket["sources"] = sorted(set(x for x in bucket["sources"] if x))
        measured = bucket["events_with_publisher_time"]
        bucket["within_24h_rate"] = (
            round(bucket["within_24h"] / measured, 4) if measured else None
        )
    return {
        "window_days": days,
        "generated_at": storage.utcnow(),
        "days": list(buckets.values()),
        "complete_days": sum(1 for bucket in buckets.values() if bucket["collection_runs"] > 0),
        "note": "零运行日期原样保留；该结构用于积累连续运行证据，不补写历史数据。",
    }
