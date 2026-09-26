"""Live streaming of what the agents actually do.

This module exists so the console can show the pipeline *while it runs* rather
than replacing a spinner with a finished result.  Two rules shape every line:

1. **Nothing is replayed for effect.**  ``docs/CONTRACT.md`` forbids 伪造延迟, so
   there is no typewriter layer and no artificial pause.  A frame is yielded at
   the instant a real unit of work finishes, and every ``duration_ms`` is
   measured with ``time.monotonic()`` around the call that produced it.  When
   the work is instant the frames arrive instantly and the UI will say so.

2. **Every frame answers four questions in plain language** so the console can
   render them without inventing anything: 拿到什么 (``obtained``),
   做了什么 (``action``), 产出什么 (``output``), 有什么影响 (``effect``).

Text frames come in two flavours and the UI must never blur them:

* ``source="local"`` -- one sentence the local engine assembled from stored
  evidence.  ``answer_question`` joins its sentences with a newline, and this
  module emits exactly one frame per sentence, so **the frame boundary is the
  newline**: rendering each local frame as its own paragraph reproduces the
  recorded answer byte for byte.
* ``source="model"`` -- a genuine token stream from the configured model,
  used only to *restate* the evidence-bound sentences, never to add facts.
  These frames carry no evidence ids, because they are not evidence.

The functions here are generators of ``(event_name, payload)`` pairs.  ``api``
wraps them in SSE framing; the tests consume them directly without HTTP.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from . import agent_orchestration, agents, config, intelligence, rag_corpus, sources, storage

Frame = tuple[str, dict[str, Any]]

# Roles rendered in plain Chinese.  The console shows `label` next to the
# technical `role` so a non-specialist reader can follow what each step is.
ROLE_LABELS: dict[str, str] = {
    "collector": "采集员",
    "normalizer": "标准化员",
    "deduplicator": "查重员",
    "planner": "规划员",
    "retriever": "查证员",
    "evidence_auditor": "证据审核员",
    "assessor": "影响分析员",
    "scheduler": "调度员",
}

PHASE_LABELS: dict[str, str] = {
    "collect": "第一步 · 抓取（从官网取回原始材料）",
    "normalize": "第二步 · 整理（统一成同一种格式）",
    "enrich": "第三步 · 补证（缺什么就去权威库查什么）",
    "assess": "第四步 · 判断影响（对每条自有资产下结论）",
    "summary": "汇总",
    "answer": "问答",
}


class _Seq:
    """Monotonic frame counter so the console can order frames deterministically."""

    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


def _stage(
    seq: _Seq,
    *,
    phase: str,
    role: str,
    title: str,
    action: str,
    obtained: str = "",
    output: str = "",
    effect: str = "",
    status: str = "done",
    duration_ms: int | None = None,
    refs: list[str] | None = None,
    note: str | None = None,
) -> Frame:
    payload: dict[str, Any] = {
        "seq": seq.next(),
        "phase": phase,
        "phase_label": PHASE_LABELS.get(phase, phase),
        "role": role,
        "role_label": ROLE_LABELS.get(role, role),
        "title": title,
        "action": action,
        "obtained": obtained,
        "output": output,
        "effect": effect,
        "status": status,
        "refs": refs or [],
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if note:
        payload["note"] = note
    return ("stage", payload)


def _text_frame(seq: _Seq, delta: str, *, source: str, evidence_ids: list[str]) -> Frame:
    return ("text", {
        "seq": seq.next(),
        "delta": delta,
        "source": source,
        "evidence_ids": evidence_ids,
    })


# --------------------------------------------------------------------------
# full pipeline
# --------------------------------------------------------------------------

def stream_pipeline(
    source_ids: list[str] | None = None,
    *,
    close_gaps: bool = True,
    enrich_limit: int = 6,
) -> Iterator[Frame]:
    """Run the pipeline, narrating every real step, and always leave a record.

    A run that is stopped halfway still advances the cursors of the sources it
    already finished, so it *must* leave a trace -- otherwise the store would
    show sources that moved with nothing explaining why.  The wrapper writes
    that record on the way out, including for an abandoned client.
    """
    seq = _Seq()
    started_at = storage.utcnow()
    run_id = storage.new_id("run")
    run_state: dict[str, Any] = {
        "completed": False, "selected": [], "added": 0, "updated": 0,
        "enriched": 0, "tool_calls": 0, "assessments": 0, "unknown": [],
    }
    try:
        yield from _pipeline_body(seq, run_id, started_at, run_state,
                                  source_ids, close_gaps, enrich_limit)
    finally:
        if not run_state["completed"]:
            storage.save_run({
                "id": run_id, "kind": "collect", "status": "aborted",
                "started_at": started_at, "finished_at": storage.utcnow(),
                "summary": (
                    f"【已中断】流式全流程在 {len(run_state['selected'])} 个来源上被中止："
                    f"新增 {run_state['added']}，更新 {run_state['updated']}，"
                    f"补证 {run_state['enriched']} 条，生成 {run_state['assessments']} 条结论"
                ),
                "detail": {
                    "streamed": True, "aborted": True,
                    "completed_sources": sum(
                        1 for s in run_state["selected"] if s.get("status") != "idle"),
                    "sources": run_state["selected"],
                    "events_added": run_state["added"], "events_updated": run_state["updated"],
                    "enriched": run_state["enriched"], "tool_calls": run_state["tool_calls"],
                    "assessments": run_state["assessments"],
                    "unknown_source_ids": run_state["unknown"],
                    "note": "客户端中途断开或用户点击停止；已完成的来源进度已保留。",
                },
            })


def _pipeline_body(
    seq: _Seq,
    run_id: str,
    started_at: str,
    run_state: dict[str, Any],
    source_ids: list[str] | None,
    close_gaps: bool,
    enrich_limit: int,
) -> Iterator[Frame]:
    """The pipeline itself.

    The work is done by the same functions the non-streaming endpoints call
    (`agents.process_and_store`, `agents.close_evidence_gaps`), so streaming
    cannot drift from the recorded behaviour.
    """
    wall_start = time.monotonic()

    selected = source_ids or [s.id for s in sources.SOURCES]
    unknown = [s for s in selected if sources.get(s) is None]
    selected = [s for s in selected if sources.get(s) is not None]
    collection_plan = agent_orchestration.collection_plan(
        selected, config.model_config() or None,
    )
    collection_tool_calls: list[dict] = []

    yield ("start", {
        "seq": seq.next(),
        "run_id": run_id,
        "phase_label": PHASE_LABELS["collect"],
        "planned_sources": len(selected),
        "unknown_source_ids": unknown,
        "started_at": started_at,
        "close_gaps": close_gaps,
    })

    run_state["unknown"] = unknown
    if unknown:
        yield _stage(
            seq, phase="collect", role="collector", status="skipped",
            title="跳过未登记的数据源",
            action="拒绝抓取后端未登记的名字",
            obtained=", ".join(unknown),
            output="不产生任何抓取结果",
            effect="为防止被诱导去访问任意网址，只允许抓取后端登记过的来源。",
            note="前端无法提交任意 URL，这是刻意的安全限制。",
        )

    # -- 1. collect ---------------------------------------------------------
    collected: list[dict] = []
    per_source: list[dict] = []
    added = updated = 0

    for source_id in selected:
        spec = sources.get(source_id)
        assert spec is not None
        state = storage.source_state(source_id)

        yield _stage(
            seq, phase="collect", role="collector", status="running",
            title=f"正在抓取：{spec.name}",
            action=f"访问登记的官方地址（{spec.mode} 方式）",
            obtained=f"上次抓取位置：{state.get('cursor') or '无（首次全量）'}",
            output="等待返回…",
            effect="成功则原始响应按内容哈希存档、游标前移；失败则原样记录错误，不写入任何占位数据。",
            refs=[source_id],
        )

        outcome = agents.collectors.collect(source_id, since=state.get("cursor"))
        collection_tool_calls.append(agent_orchestration.audit(
            "collect_registered_source", status=outcome.status,
            result=f"{source_id}: 获取 {outcome.fetched}，保留 {len(outcome.events)}",
            count=len(outcome.events),
        ))

        # What the source actually returned, stated in counts rather than adjectives.
        if outcome.status == "skipped":
            obtained = outcome.error or "该来源需要额外凭据，本次未配置"
            effect = "本次没有取到数据。这会在监测页如实记为“已跳过”，不会用空数据冒充成功。"
        elif outcome.ok:
            obtained = (f"取回 {outcome.fetched} 条原始记录"
                        + (f"，其中 {outcome.filtered} 条与 AI 安全无关被剔除" if outcome.filtered else "")
                        + (f"；保留 {len(outcome.events)} 条"))
            effect = "保留的记录会进入第二步整理。"
        else:
            obtained = outcome.error or "抓取失败，原因未提供"
            effect = "失败原因原文已记录，不会生成占位数据。"

        duration = outcome.duration_ms
        yield _stage(
            seq, phase="collect", role="collector",
            status="skipped" if outcome.status == "skipped" else ("failed" if not outcome.ok else "done"),
            title=f"抓取完成：{spec.name}",
            action=f"访问登记的官方地址（{spec.mode} 方式）",
            obtained=obtained,
            output=f"原始文件快照：{outcome.snapshot_hash[:16] + '…' if outcome.snapshot_hash else '未落盘'}",
            effect=effect,
            duration_ms=duration,
            refs=[source_id],
            note=(outcome.notes[0] if outcome.notes else None),
        )

        for event in outcome.events:
            result = agents.process_and_store(event, close_gaps=False)
            if result["action"] == "new":
                added += 1
            elif result["action"] in {"updated", "merged"}:
                updated += 1
            run_state["added"], run_state["updated"] = added, updated
            collected.append(result["event"])

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

        if outcome.snapshot_hash:
            yield _stage(
                seq, phase="normalize", role="normalizer",
                title=f"整理：{spec.name} 的 {len(outcome.events)} 条记录",
                action="把各家不同的字段名，统一成本系统的一种格式",
                obtained=f"原始快照 {outcome.snapshot_hash[:16]}… 已存盘，可随时按哈希核对",
                output="统一格式：编号、组件、受影响版本范围、来源、发布时间",
                effect="无法可靠解析的版本范围写 unknown，绝不猜测。",
                # No duration_ms: normalising happens inside process_and_store
                # below and is not timed separately.  Reporting a hardcoded 0
                # would render as "0 ms" and read as a measurement.
                refs=[source_id],
            )

        per_source.append({
            "source_id": source_id, "name": spec.name, "status": outcome.status,
            "fetched": outcome.fetched, "kept": len(outcome.events),
            "filtered": outcome.filtered, "duration_ms": outcome.duration_ms,
            "error": outcome.error, "snapshot_hash": outcome.snapshot_hash,
        })
        # Mirrored so the abort path can report how far it actually got.
        run_state["selected"] = per_source

    yield _stage(
        seq, phase="summary", role="collector",
        title="抓取阶段结束",
        action="汇总本阶段结果",
        obtained=f"共处理 {len(selected)} 个来源",
        output=f"新增 {added} 条，更新 {updated} 条",
        effect="下一步只对“还没补过证”或“仍有缺口”的条目做补证，避免重复外网调用。",
        duration_ms=int((time.monotonic() - wall_start) * 1000),
    )

    # -- 2. enrich ----------------------------------------------------------
    pending = [
        e for e in collected
        if not e.get("withdrawn") and (
            not e.get("enrichment") or (e.get("enrichment") or {}).get("gaps")
        )
    ][:enrich_limit]

    if not pending:
        if enrich_limit == 0:
            # `[:0]` empties the list regardless of the real gaps, so claiming
            # "no gaps" here would be asserting something never looked at.
            yield _stage(
                seq, phase="enrich", role="planner", status="skipped",
                title="按设置跳过了补证",
                action="本次设置为不补证，直接进入下一步",
                obtained=f"本轮入库 {len(collected)} 条，其证据缺口尚未检查",
                output="不产生补证计划",
                effect="这些条目的缺口状态仍是「未检查」，不等于没有缺口；可在「情报条目」页单独补证。",
            )
        else:
            yield _stage(
                seq, phase="enrich", role="planner", status="skipped",
                title="没有需要补证的条目",
                action="检查哪些事件还缺关键信息",
                obtained=f"本轮入库 {len(collected)} 条，其中没有待补条目",
                output="不产生补证计划",
                effect="跳过补证，不产生外网调用。",
            )

    total_calls = 0
    for event in pending:
        label = event.get("id") or event.get("title") or "未命名事件"
        before = set(((intelligence.enrich_event(event).get("enrichment") or {}).get("gaps")) or [])

        yield _stage(
            seq, phase="enrich", role="planner", status="running",
            title=f"规划补证：{label}",
            action="看这条记录缺什么，再决定去哪个权威库查",
            obtained=("当前缺口：" + "、".join(sorted(before))) if before else "无缺口",
            output="生成补证计划",
            effect="只查缺口，不做无目的的遍历。",
            refs=[str(event.get("id") or "")],
        )

        result = agents.close_evidence_gaps(event)
        total_calls += result["tool_calls"]
        run_state["tool_calls"], run_state["enriched"] = total_calls, run_state["enriched"] + 1
        after = set((result["event"].get("enrichment") or {}).get("gaps") or [])

        # One frame per tool call, carrying the real returned note.
        for call in result["trace"]:
            yield _stage(
                seq, phase="enrich", role="retriever",
                title=f"查证：{call.get('action')}",
                action=f"第 {call.get('round')} 轮 · 调用工具 {call.get('tool')}",
                obtained=call.get("result") or "工具未返回说明",
                output=f"带回 {call.get('found', 0)} 条可用记录",
                effect="带回的记录会与本地记录合并；同一事实保留多个来源，不互相覆盖。",
                duration_ms=call.get("duration_ms"),
                refs=[str(event.get("id") or "")],
            )

        yield _stage(
            seq, phase="enrich", role="scheduler",
            status="done" if not after else "warn",
            title=f"补证结束：{label}",
            action="判断是否可以停止",
            obtained=f"停止原因：{result['stop_reason']}",
            output=(f"剩余 {len(after)} 个缺口：" + "、".join(sorted(after))) if after
                   else "证据已齐备，可用于对外结论",
            effect=("仍有缺口，该条只作为参考，不作为确定结论。"
                    if after else "该条可以进入正式结论。"),
            refs=[str(event.get("id") or "")],
        )

        updated_event = result["event"]
        updated_event["pipeline"] = {
            "state": agents.STATE_PUBLISHED if not after else agents.STATE_PENDING_REVIEW,
            "history": [{
                "state": agents.STATE_PENDING_ENRICHMENT, "role": "planner",
                "note": f"补证调度：{result['stop_reason']}", "at": storage.utcnow(),
            }],
            "scheduler_trace": result["trace"],
            "stop_reason": result["stop_reason"],
            "tool_calls": result["tool_calls"],
        }
        storage.upsert_event(updated_event)

    # -- 3. assess ----------------------------------------------------------
    assets = storage.list_assets()
    stored_events, _ = storage.list_events(limit=500)

    yield _stage(
        seq, phase="assess", role="assessor", status="running",
        title="开始影响判断",
        action="把每条情报与每条自有资产逐一对上",
        obtained=f"待判断事件 {len(stored_events)} 条，自有资产 {len(assets)} 条",
        output="等待判断…",
        effect="组件名对不上的组合会被跳过，不做无依据的关联。",
    )

    stored = 0
    not_applicable = 0
    affected = 0
    for event in stored_events:
        for asset in assets:
            if not agents._component_matches(event, asset):
                continue
            assessment = intelligence.assess_asset(event, asset)
            storage.save_assessment(assessment)
            stored += 1
            run_state["assessments"] = stored
            if assessment.get("status") == "not_applicable":
                not_applicable += 1
            if assessment.get("status") == "affected":
                affected += 1
            yield _stage(
                seq, phase="assess", role="assessor",
                status="warn" if assessment.get("status") in {"affected", "needs_confirmation"} else "done",
                title=f"判断：{asset.get('name') or asset.get('id')} × {event.get('id')}",
                action="比对组件名，再比对版本范围与前置条件",
                obtained=f"资产组件：{asset.get('component')}；事件组件：{event.get('component')}",
                output=f"结论：{assessment.get('status')}（优先级 {assessment.get('priority')}）",
                effect="；".join(assessment.get("reasons") or []) or "无补充说明",
                refs=[str(asset.get("id") or ""), str(event.get("id") or "")],
            )

    yield _stage(
        seq, phase="summary", role="assessor",
        title="全部完成",
        action="汇总本次全流程",
        obtained=f"共 {total_calls} 次权威库查证",
        output=(f"生成 {stored} 条影响结论（受影响 {affected} 条，"
                f"范围外未判断 {not_applicable} 条 —— 含未授权与组件不匹配两种原因）"),
        effect="结论、证据与缺口都已写入运行日志，可随时复查。",
        duration_ms=int((time.monotonic() - wall_start) * 1000),
    )

    # Flag completion *before* writing the finished record.  If it were set
    # after, a client that vanished while the generator sat suspended on the
    # final yield would let the wrapper write an "aborted" record with the same
    # run_id, and save_run upserts by id -- overwriting a good record.
    run_state["completed"] = True

    # A run where every source failed is not a completed run.
    failed = [s for s in per_source if s["status"] == "failed"]
    status = ("completed" if not failed
              else ("partial" if len(failed) < len(per_source) else "failed"))

    storage.save_run({
        "id": run_id, "kind": "collect",
        "status": status,
        "started_at": started_at, "finished_at": storage.utcnow(),
        "summary": (f"流式全流程：抓取 {len(selected)} 个来源，新增 {added}，更新 {updated}，"
                    f"补证 {len(pending)} 条 / {total_calls} 次查证，生成 {stored} 条结论"
                    + (f"；{len(failed)} 个来源失败" if failed else "")),
        "detail": {
            "streamed": True, "sources": per_source, "events_added": added,
            "events_updated": updated, "enriched": len(pending),
            "tool_calls": total_calls, "assessments": stored,
            "unknown_source_ids": unknown,
            "agent_plan": collection_plan,
            "agent_tool_calls": collection_tool_calls,
        },
    })

    yield ("final", {
        "seq": seq.next(),
        "run_id": run_id,
        "events_added": added,
        "events_updated": updated,
        "enriched": len(pending),
        "tool_calls": total_calls,
        "assessments": stored,
        "affected": affected,
        "not_applicable": not_applicable,
        "duration_ms": int((time.monotonic() - wall_start) * 1000),
        "sources": per_source,
        "agent_plan": collection_plan,
        "agent_tool_calls": collection_tool_calls,
    })


# --------------------------------------------------------------------------
# question answering
# --------------------------------------------------------------------------

# Mirrors `intelligence.answer_question`.  `test_streaming` asserts the streamed
# text equals the engine's recorded answer for identical inputs, so the two
# cannot drift apart without a test failing.
_ATTACK_RE = re.compile(r"攻击链|attack\s*(chain|path)|利用链")
_ASSET_RE = re.compile(r"资产|影响我|受影响|asset|affected")


# Delegated rather than copied.  A hand-copied `_norm` collapsed "/" as well,
# so an event component of "apache/airflow" matched an asset of "apache-airflow"
# here but not in the engine -- the stream then emitted an asset sentence the
# recorded answer did not contain, silently breaking the byte-identity
# guarantee.  Calling through makes that class of drift impossible.
_norm = intelligence._norm


def _evidence_ids(event: dict) -> list[str]:
    return intelligence._evidence_ids(event)


def stream_answer(
    question: str,
    history: list[dict] | None = None,
    *,
    use_model: bool = False,
    context_snapshot: dict | None = None,
    thread_id: str | None = None,
) -> Iterator[Frame]:
    """Answer one question, narrating retrieval and emitting text as it is built.

    ``use_model`` asks the configured model to *restate* the finished local
    answer as a token stream.  It can only rephrase: the authoritative answer is
    the local one, and it is sent in the ``final`` frame beside the model text.
    """
    seq = _Seq()
    started_at = storage.utcnow()
    run_id = storage.new_id("run")
    wall_start = time.monotonic()
    model_config = config.model_config() or None
    plan = agent_orchestration.answer_plan(
        question, has_assets=bool(storage.list_assets()), model=model_config,
    )
    tool_calls: list[dict] = []

    yield ("start", {
        "seq": seq.next(),
        "run_id": run_id,
        "question": question,
        "phase_label": PHASE_LABELS["answer"],
        "started_at": started_at,
        "model_requested": bool(use_model),
        "model_available": config.model_configured(),
    })

    # -- 1. understand ------------------------------------------------------
    yield _stage(
        seq, phase="answer", role="planner",
        title="理解问题",
        action="从问题里找出事件编号、组件名和想知道的类型",
        obtained=f"原始问题：{question}",
        output=("问的是攻击链；" if _ATTACK_RE.search(question.casefold()) else "")
               + ("问的是自有资产是否受影响；" if _ASSET_RE.search(question.casefold()) else "")
               + ("一般性询问。" if not (_ATTACK_RE.search(question.casefold()) or _ASSET_RE.search(question.casefold())) else ""),
        effect="只有问题里明确问到的内容才会展开，不会主动补充没问的结论。",
    )

    # -- 2. retrieve --------------------------------------------------------
    retrieve_start = time.monotonic()
    events, total = storage.list_events(limit=500)
    assets = storage.list_assets()
    chunks = rag_corpus.list_chunk_records(current_only=True)
    tool_calls.extend([
        agent_orchestration.audit("load_event_evidence", status="completed",
                                 result="已读取本地事件证据快照", count=total),
        agent_orchestration.audit("load_knowledge_evidence", status="completed",
                                 result="已读取版本化知识分块", count=len(chunks)),
        agent_orchestration.audit("load_authorized_assets", status="completed",
                                 result="已读取资产范围快照",
                                 count=sum(1 for asset in assets if asset.get("authorized"))),
    ])
    retrieve_ms = int((time.monotonic() - retrieve_start) * 1000)

    yield _stage(
        seq, phase="answer", role="retriever",
        title="翻本地已存的证据",
        action="在本地数据库里找匹配的事件和资产",
        obtained=f"库中现有 {total} 条事件、{len(assets)} 条自有资产",
        output="下一帧给出命中结果",
        effect="只读本地已存证据；这一步不会去外网现查。",
        duration_ms=retrieve_ms,
    )

    result = intelligence.answer_question(
        question, events, assets, history=history, model_config=model_config,
        rag_chunks=chunks,
        context_snapshot=context_snapshot,
    )
    tool_calls.append(agent_orchestration.audit(
        "answer_from_evidence", status="completed", result="已按本轮证据快照生成结论",
        count=len(result.get("related_event_ids") or []),
    ))
    result["agent_plan"] = plan
    result["tool_calls"] = tool_calls
    selected_ids = set(result.get("related_event_ids") or [])
    selected = [e for e in events if e.get("id") in selected_ids]

    if not selected:
        yield _stage(
            seq, phase="answer", role="scheduler", status="warn",
            title="没有找到匹配的事件",
            action="停止并如实说明原因",
            obtained=f"库中 {total} 条事件均未命中",
            output="不作答",
            effect="没有证据就不给结论，避免编造。请换成 CVE 编号或组件名再问。",
        )
        yield _text_frame(seq, result["answer"], source="local", evidence_ids=[])
        agents._persist_answer_context(question, result, thread_id=thread_id)
        yield ("final", {**result, "seq": seq.next(), "run_id": run_id,
                         "duration_ms": int((time.monotonic() - wall_start) * 1000)})
        _record_answer_run(run_id, started_at, question, result, selected)
        return

    yield _stage(
        seq, phase="answer", role="retriever",
        title=f"命中 {len(selected)} 条相关事件",
        action="列出命中的事件",
        obtained="、".join(str(e.get("id")) for e in selected[:8]),
        output=f"共 {len(selected)} 条",
        effect="下面逐条读它们的证据，一条读完就输出一条结论。",
        refs=[str(e.get("id")) for e in selected],
    )

    # -- 3. per-evidence generation ----------------------------------------
    asks_attack = bool(_ATTACK_RE.search(question.casefold()))
    asks_asset = bool(_ASSET_RE.search(question.casefold()))
    limitations = list(result.get("limitations") or [])
    assessments_seen = 0

    for event in selected:
        evidence = _evidence_ids(event)
        label = event.get("id") or event.get("title") or "该事件"
        withdrawn = bool(event.get("withdrawn") or event.get("status") == "withdrawn")

        yield _stage(
            seq, phase="answer", role="retriever",
            title=f"读取证据：{label}",
            action="取出这条事件的来源、受影响范围和已有结论",
            obtained=f"{len(event.get('sources') or [])} 个来源，证据编号 "
                     + ("、".join(evidence[:4]) if evidence else "（无）"),
            output="下面输出这条事件的结论句",
            effect=("该事件已撤回，只能说明它失效。" if withdrawn
                    else "该事件仍在有效期内。"),
            refs=[str(event.get("id"))],
        )

        # The sentence is produced here, then pushed immediately.  It is the
        # same string the engine puts into its recorded answer.
        if withdrawn:
            sentence = f"{label} 已标记撤回，不能继续作为当前有效影响结论。"
        else:
            sentence = (f"{label}：{event.get('summary') or event.get('title') or '已有事件记录，但缺少摘要。'}")
        yield _text_frame(seq, sentence, source="local", evidence_ids=evidence)

        if asks_attack:
            rels = [r for r in event.get("relationships", []) if r.get("evidence_ids")]
            if rels:
                chain = "；".join(
                    f"{r.get('subject')} → {r.get('predicate')} → {r.get('object')}" for r in rels
                )
                yield _text_frame(seq, f"有证据关系：{chain}。", source="local",
                                  evidence_ids=list(dict.fromkeys(
                                      i for r in rels for i in r.get("evidence_ids", []))))
            else:
                yield _stage(
                    seq, phase="answer", role="evidence_auditor", status="warn",
                    title=f"攻击链缺证据：{label}",
                    action="检查能否拼出完整攻击链",
                    obtained="现有资料没有足以组成攻击链的有来源关系",
                    output="拒绝补写缺失环节",
                    effect="缺的那一环不会被推测填上，这是刻意设计。",
                    refs=[str(event.get("id"))],
                )
                yield _text_frame(seq, "现有资料没有足以组成攻击链的有来源关系，系统拒绝补写缺失环节。",
                                  source="local", evidence_ids=[])

        if asks_asset:
            for asset in [a for a in assets if _norm(a.get("component")) == _norm(event.get("component"))]:
                assessment = intelligence.assess_asset(event, asset)
                assessments_seen += 1
                yield _stage(
                    seq, phase="answer", role="assessor",
                    status="warn" if assessment.get("status") in {"affected", "needs_confirmation"} else "done",
                    title=f"判断自有资产：{asset.get('name') or asset.get('id')}",
                    action="比对版本范围与前置条件",
                    obtained=f"资产版本 {asset.get('version') or '未填'}；组件 {asset.get('component')}",
                    output=f"结论：{assessment.get('status')}（优先级 {assessment.get('priority')}）",
                    effect="；".join(assessment.get("reasons") or []),
                    refs=[str(asset.get("id") or "")],
                )
                yield _text_frame(
                    seq,
                    f"资产 {asset.get('name') or asset.get('id')}：{assessment['status']}"
                    f"（{'；'.join(assessment['reasons'])}）。",
                    source="local",
                    evidence_ids=_evidence_ids(event),
                )

    # -- 4. optional model restatement --------------------------------------
    model_text = ""
    if use_model:
        yield _stage(
            seq, phase="answer", role="planner",
            title="让大模型转述（可选步骤）",
            action="把上面已生成的结论交给模型，请它换一种更口语的说法",
            obtained=f"输入是本地已生成的 {len(result.get('answer') or '')} 字结论，不含新资料",
            output="下面实时逐字输出模型返回的内容",
            effect="模型只能改写措辞，不能新增事实。它与本地结论不一致时，一律以本地结论为准。",
        )
        got_any = False
        for chunk, failure in _stream_model_restatement(question, result.get("answer") or "", limitations):
            if failure:
                yield _stage(
                    seq, phase="answer", role="planner", status="failed",
                    title="模型转述失败",
                    action="调用远端模型",
                    obtained=failure,
                    output="已放弃模型转述",
                    effect="下面的结论仍然完整可用，它本来就不依赖模型。",
                )
                break
            got_any = True
            model_text += chunk
            yield _text_frame(seq, chunk, source="model", evidence_ids=[])
        if got_any:
            yield _stage(
                seq, phase="answer", role="evidence_auditor",
                title="模型转述完成",
                action="记录模型输出以便复查",
                obtained=f"模型共返回 {len(model_text)} 字",
                output="已与本地权威结论并列展示",
                effect="复查时请以本地结论为准；模型输出不进入引用与证据链。",
            )

    yield _stage(
        seq, phase="summary", role="scheduler",
        title="回答结束",
        action="收尾并记录",
        obtained=f"引用 {len(result.get('citations') or [])} 个来源，"
                 f"结论 {assessments_seen or len(result.get('assessments') or [])} 条",
        output="缺证据的部分已明确拒答，并在下方列出局限",
        effect="整个过程写入运行日志，可复查。",
    )

    agents._persist_answer_context(question, result, thread_id=thread_id)
    final = {**result, "seq": seq.next(), "run_id": run_id,
             "duration_ms": int((time.monotonic() - wall_start) * 1000)}
    if model_text:
        final["model_restatement"] = model_text
        final["model_restatement_notice"] = (
            "以上模型转述仅供阅读，事实以本地证据结论为准；模型输出未进入引用与证据链。"
        )
    yield ("final", final)
    _record_answer_run(run_id, started_at, question, result, selected)


def _record_answer_run(run_id: str, started_at: str, question: str,
                       result: dict, selected: list[dict]) -> None:
    for assessment in result.get("assessments") or []:
        storage.save_assessment(assessment)
    storage.save_run({
        "id": run_id, "kind": "chat", "status": "completed",
        "started_at": started_at, "finished_at": storage.utcnow(),
        "summary": f"问答（{result.get('mode')}）：{question[:60]}",
        "detail": {
            "question": question, "mode": result.get("mode"),
            "streamed": True,
            "related_event_ids": result.get("related_event_ids"),
            "citations": len(result.get("citations") or []),
            "matched_events": len(selected),
            "agent_plan": result.get("agent_plan"),
            "tool_calls": result.get("tool_calls"),
        },
    })


# --------------------------------------------------------------------------
# optional model restatement
# --------------------------------------------------------------------------

RESTATE_SYSTEM_PROMPT = (
    "你是情报系统的朗读员。用户会给你一段已经由规则引擎生成的结论。"
    "你的唯一任务是把这段话改写得更容易读。"
    "严禁新增、推测或补充任何事实、编号、版本号、结论；"
    "严禁改变任何结论的含义；不得使用原文没有的信息。"
    "如果原文某处说“缺少证据”或“拒绝回答”，你必须保留这个意思。"
    "只输出改写后的正文，不要任何解释、前言或 Markdown 标题。"
)


def _stream_model_restatement(question: str, answer: str,
                              limitations: list[str]) -> Iterator[tuple[str, str | None]]:
    """Yield ``(chunk, failure)`` from a real streaming model call.

    The local answer is the only material supplied; the model is told it may
    only rephrase.  Output is never stored as evidence.
    """
    cfg = config.model_config()
    if not cfg:
        yield "", "未配置模型密钥，或模型开关已关闭"
        return

    key = os.getenv(cfg.get("api_key_env") or "")
    if not key or not cfg.get("base_url") or not cfg.get("model"):
        yield "", "模型配置不完整"
        return

    body = json.dumps({
        "model": cfg["model"],
        "temperature": 0,
        "stream": True,
        "messages": [
            {"role": "system", "content": RESTATE_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({
                "question": question,
                "engine_answer": answer,
                "engine_limitations": limitations,
            }, ensure_ascii=False)},
        ],
    }).encode("utf-8")
    url = str(cfg["base_url"]).rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Accept": "text/event-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(10.0, float(cfg.get("timeout", 8)) * 4)) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                # `delta` may be a list or string on a malformed/proxied
                # response, so it is type-checked rather than assumed to be a
                # dict: `.get` on a non-dict raises AttributeError, which used
                # to escape the handler entirely and abort an answer that had
                # already been fully computed from local evidence.
                try:
                    delta = json.loads(payload)["choices"][0]["delta"]
                except (ValueError, KeyError, IndexError, TypeError):
                    continue
                chunk = delta.get("content") if isinstance(delta, dict) else None
                if isinstance(chunk, str) and chunk:
                    yield chunk, None
    except urllib.error.HTTPError as exc:
        yield "", f"模型接口返回 HTTP {exc.code}"
    except (OSError, urllib.error.URLError) as exc:
        yield "", f"模型接口不可达（{type(exc).__name__}）"
    except Exception as exc:  # noqa: BLE001
        # The local answer never depends on this stream, so no failure here is
        # allowed to take the answer down with it.
        yield "", f"模型转述中断（{type(exc).__name__}）"


def encode_sse(frame: Frame) -> str:
    """Serialise one frame as an SSE message."""
    name, payload = frame
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
