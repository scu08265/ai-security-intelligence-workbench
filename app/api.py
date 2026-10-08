"""HTTP interface.

Implements the endpoints fixed in docs/CONTRACT.md.  Three properties are enforced
here rather than left to callers:

* the client cannot choose a URL -- only registered `source_ids` are accepted;
* write requests must come from a local origin, and CORS is not opened up;
* no response ever contains a credential, because keys are read from the
  environment inside the engine and never stored.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import (agent_context, agents, b_evaluation, competition_scorecard, config, cyclonedx_assets,
                 disposition,
               evaluation, intelligence, knowledge_views, observability, rag_corpus,
               reliability, self_healing, sources, storage, streaming,
               multi_agent_runtime)
from . import dag_executor, task_dag

MAX_QUESTION = 2000
MAX_QUERY = 200
LOCAL_ORIGIN_PREFIXES = ("http://127.0.0.1", "http://localhost", "http://[::1]")

# Upper bound on how many rows the events endpoint will read to compute the
# type counts.  If the matching set is larger than this we return no counts at
# all rather than counts that quietly describe only the first N rows.
CORPUS_LIMIT = 500

app = FastAPI(title="AI 安全知识情报系统", version=config.APP_VERSION)
storage.init_db()
agents.refresh_source_event_counts()


# --------------------------------------------------------------------------
# request models
# --------------------------------------------------------------------------

class CollectRequest(BaseModel):
    source_ids: list[str] | None = Field(default=None, max_length=50)


class AssetRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    component: str = Field(min_length=1, max_length=200)
    # A CycloneDX import keeps its context under ``deployment_context`` and
    # leaves these top-level keys null.  Accepting None here is what lets an
    # imported asset be read back and updated through this same endpoint;
    # without it the round-trip fails with HTTP 422 and the asset's version
    # can never be changed.
    ecosystem: str | None = Field(default=None, max_length=120)
    version: str | None = Field(default=None, max_length=120)
    exposure: str | None = Field(default=None, pattern="^(public|internal|unknown)$")
    business_criticality: str | None = Field(default=None, pattern="^(critical|high|medium|low|unknown)$")
    conditions: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    is_demo: bool = False
    authorized: bool = True


class AssetImportRequest(BaseModel):
    items: list[AssetRequest] = Field(min_length=1, max_length=200)


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(max_length=MAX_QUESTION)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    thread_id: str | None = Field(default=None, max_length=160)
    # This contains only explicit focus/conditions from the previous answer,
    # never free-form model reasoning.
    context_snapshot: dict[str, Any] | None = None


class StreamAnswerRequest(ChatRequest):
    # Opt-in: asks the configured model to restate the finished local answer.
    # Refused (with a stated reason) when no key is configured, rather than
    # silently ignored.
    use_model: bool = False


class StreamPipelineRequest(BaseModel):
    source_ids: list[str] | None = Field(default=None, max_length=50)
    close_gaps: bool = True
    enrich_limit: int = Field(default=6, ge=0, le=20)


class CycloneDXRequest(BaseModel):
    bom: dict[str, Any]


class CycloneDXImportRequest(CycloneDXRequest):
    authorized: bool
    is_demo: bool = True
    policies: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RAGSnapshotRequest(BaseModel):
    source_id: str = Field(min_length=1, max_length=100)
    snapshot_hash: str = Field(min_length=64, max_length=64)
    suffix: str | None = Field(default=None, max_length=12)
    document_key: str | None = Field(default=None, max_length=500)
    title: str = Field(default="", max_length=500)
    canonical_url: str = Field(default="", max_length=2000)


class RAGFileRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4000)
    source_id: str = Field(default="local", min_length=1, max_length=100)
    document_key: str | None = Field(default=None, max_length=500)
    title: str = Field(default="", max_length=500)
    canonical_url: str = Field(default="", max_length=2000)
    authorized: bool


class RAGLatestRequest(BaseModel):
    source_ids: list[str] | None = Field(default=None, max_length=20)
    limit: int = Field(default=3, ge=1, le=20)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentThreadRequest(StrictRequest):
    thread_id: str | None = Field(default=None, max_length=160)
    objective: str = Field(min_length=1, max_length=2000)
    base_constraints: list[str] = Field(default_factory=list, max_length=50)


class ResolvedReferenceRequest(StrictRequest):
    mention: str = Field(min_length=1, max_length=500)
    kind: str = Field(pattern="^(event|asset|document|chunk|source_version)$")
    resolved_id: str = Field(min_length=1, max_length=200)
    method: str = Field(default="explicit", max_length=80)


class AgentTurnRequest(StrictRequest):
    visible_user_input: str = Field(default="", max_length=10000)
    visible_assistant_output: str = Field(default="", max_length=30000)
    objective: str | None = Field(default=None, max_length=2000)
    focus_event_id: str | None = Field(default=None, max_length=200)
    focus_asset_id: str | None = Field(default=None, max_length=200)
    focus_document_id: str | None = Field(default=None, max_length=200)
    inherit_focus: bool = True
    constraints: list[str] = Field(default_factory=list, max_length=50)
    resolved_references: list[ResolvedReferenceRequest] = Field(default_factory=list, max_length=100)
    chunk_ids: list[str] = Field(default_factory=list, max_length=200)
    source_version_ids: list[str] = Field(default_factory=list, max_length=100)


class DispositionUpdateRequest(StrictRequest):
    event_id: str = Field(min_length=1, max_length=200)
    asset_id: str = Field(min_length=1, max_length=200)
    status: str = Field(pattern="^(open|in_progress|fixed|verified|accepted)$")
    assignee: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    version_before: str | None = Field(default=None, max_length=200)
    version_after: str | None = Field(default=None, max_length=200)
    operator: str | None = Field(default=None, max_length=200)
    run_verification: bool = True


class AgentTaskRequest(StrictRequest):
    task_id: str | None = Field(default=None, max_length=160)
    objective: str = Field(min_length=1, max_length=2000)
    success_criteria: list[str] = Field(default_factory=list, max_length=50)
    tool_candidates: list[Any] = Field(default_factory=list, max_length=50)
    budget: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list, max_length=50)


class AgentPlanRequest(StrictRequest):
    plan_id: str | None = Field(default=None, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=4000)


class AgentTaskNodeRequest(StrictRequest):
    node_id: str | None = Field(default=None, max_length=160)
    plan_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(default_factory=list, max_length=100)
    success_criteria: list[str] = Field(default_factory=list, max_length=50)
    tool_candidates: list[Any] = Field(default_factory=list, max_length=50)
    budget: dict[str, Any] = Field(default_factory=dict)


class AgentCheckpointRequest(StrictRequest):
    label: str = Field(min_length=1, max_length=500)
    status: str = Field(default="recorded", pattern="^(recorded|passed|failed)$")
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    note: str = Field(default="", max_length=4000)


class AgentNodeStatusRequest(StrictRequest):
    status: str = Field(pattern="^(planned|running|blocked|completed|skipped)$")
    checkpoint_note: str = Field(default="", max_length=4000)
    result: dict[str, Any] = Field(default_factory=dict)


class AgentTaskStatusRequest(StrictRequest):
    status: str = Field(pattern="^(planned|running|blocked|completed|cancelled)$")


class AgentHandoffRequest(StrictRequest):
    handoff_id: str | None = Field(default=None, max_length=160)
    from_node_id: str = Field(min_length=1, max_length=160)
    to_node_id: str = Field(min_length=1, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentHandoffDecisionRequest(StrictRequest):
    decision: str = Field(pattern="^(accepted|rejected)$")
    decision_note: str = Field(default="", max_length=4000)


class BoundedPlanRequest(StrictRequest):
    objective: str = Field(default="安全情报任务", max_length=2000)
    source_ids: list[str] | None = Field(default=None, max_length=20)
    collect: bool = True
    assess_assets: bool = True
    enrich_limit: int = Field(default=6, ge=0, le=20)
    question: str = Field(default="", max_length=2000)
    thread_id: str | None = Field(default=None, max_length=160)


class MultiAgentRunRequest(StrictRequest):
    objective: str = Field(min_length=1, max_length=2000)
    actions: list[str] = Field(default_factory=list, min_length=1, max_length=20)
    run_id: str | None = Field(default=None, max_length=160)


class SelfHealingRunRequest(StrictRequest):
    source_ids: list[str] | None = Field(default=None, max_length=20)


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------

@app.middleware("http")
async def local_origin_guard(request: Request, call_next):
    """Reject cross-origin writes.

    Browsers always attach `Origin` to non-GET requests, so a missing header
    means a non-browser client such as curl, which is allowed for local use.
    """
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and not origin.startswith(LOCAL_ORIGIN_PREFIXES):
            return JSONResponse(
                status_code=403,
                content={"detail": "拒绝跨源写请求：本服务仅接受来自本机前端的操作"},
            )
    started = time.monotonic()
    response = await call_next(request)
    observability.log_event(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path in {"/", "/index.html", "/app.js", "/styles.css"}:
        # Local UI updates must not leave PyCharm/browser sessions on stale code.
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def _bad(message: str, status: int = 400) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


# --------------------------------------------------------------------------
# health and dashboard
# --------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    source_states = storage.all_source_states()
    failed_sources = [
        source_id for source_id, state in source_states.items()
        if state.get("status") == "failed"
    ]
    skipped_sources = [
        source_id for source_id, state in source_states.items()
        if state.get("status") == "skipped"
    ]
    return {
        "status": "ok",
        "version": config.APP_VERSION,
        "mode": config.mode_label(),
        "model_configured": config.model_configured(),
        "data_dir": str(config.DATA_DIR),
        "checks": {
            "database": "ok",
            "events": storage.count_events()["events"],
            "failed_sources": failed_sources,
            "skipped_sources": skipped_sources,
        },
    }


@app.get("/api/ai-participation")
def ai_participation() -> dict:
    """Describe, from the running code, exactly where the model is used.

    The prompts are read from the module constants that the real calls send,
    not retyped here, so this endpoint cannot drift away from the behaviour it
    documents.  Anything not listed under `participations` is deterministic
    Python -- that boundary is the honest answer to "what did the AI do?".
    """
    return {
        "mode": config.mode_label(),
        "model_configured": config.model_configured(),
        "model_name": (config.model_config() or {}).get("model"),
        "participations": [
            {
                "id": "select",
                "name": "从候选里挑事件",
                "when": "每次提问，且已配置模型时",
                "where": "app/intelligence.py",
                "prompt": intelligence.SELECT_SYSTEM_PROMPT,
                "input": "用户的问题 + 允许挑选的事件编号清单",
                "output": "一个事件编号数组；编号不在清单里的会被丢弃",
                "bound": "temperature=0，只能从给定清单里选，选不出就降级回本地检索",
            },
            {
                "id": "restate",
                "name": "把已有结论换个说法",
                "when": "仅当在「证据问答」页手动打开开关",
                "where": "app/streaming.py",
                "prompt": streaming.RESTATE_SYSTEM_PROMPT,
                "input": "已经由本地规则拼好的结论 + 该结论的局限性说明",
                "output": "改写后的正文，逐字流式返回",
                "bound": "只改措辞；输出不进入引用与证据链，界面上单独标注「仅供阅读」",
            },
        ],
        "not_ai": [
            {"name": "采集", "detail": "抓哪个源、抓多少、窗口多大，全部由后端登记表与游标决定"},
            {"name": "归一与去重", "detail": "纯 Python 规则：别名归并、内容哈希、版本区间解析"},
            {"name": "富化", "detail": "只盘点证据缺不缺，不抓取、不推断，没有模型参与"},
            {"name": "影响研判", "detail": "版本区间比对 + 条件判断，四档结论全部由本地规则给出"},
            {"name": "检索与拒答", "detail": "本地混合检索；证据不足时拒答由规则触发，不是模型决定"},
            {"name": "评测", "detail": "在冻结题目上跑本地引擎计分，模型不参与打分"},
        ],
    }


@app.get("/api/orchestration")
def orchestration() -> dict:
    """How the pipeline is wired -- read from the same tables the run uses.

    `runtime` states the honest boundary: the roles are logical duties executed
    in order inside one process, not independent agents negotiating with each
    other.  Reporting that plainly is worth more than an inflated diagram.
    """
    return {
        "runtime": "单进程串行执行；下列角色是同一程序里的逻辑职责，不是互相通信的独立智能体",
        "phases": [{"id": key, "label": label}
                   for key, label in streaming.PHASE_LABELS.items()],
        "roles": [{"id": key, "label": label}
                  for key, label in streaming.ROLE_LABELS.items()],
        "tools": [
            {
                "id": spec.id,
                "name": spec.name,
                "category_label": spec.category_label,
                "mode": spec.mode,
                "group": sources.display_group(spec.id),
                "requires_token": spec.requires_token_env,
            }
            for spec in sources.SOURCES
        ],
        "scheduling": {
            "max_rounds": agents.MAX_ROUNDS,
            "tool_budget": agents.TOOL_BUDGET,
            "stop_conditions": [
                "证据已齐备",
                "没有可用工具能补充剩余缺口",
                f"达到工具调用预算上限（{agents.TOOL_BUDGET} 次）",
                "本轮未取得新证据",
            ],
        },
    }


@app.get("/api/dashboard")
def dashboard() -> dict:
    counts = storage.count_events()
    monitoring = agents.monitoring_summary()
    latest = storage.latest_run("collect")
    return {
        "counts": {
            "events": counts["events"],
            "sources": len(sources.SOURCES),
            "assets": storage.count_assets(),
            "needs_review": counts["needs_review"],
            "knowledge": counts.get("knowledge", 0),
            "vulnerability": counts.get("vulnerability", 0),
            "withdrawn": counts.get("withdrawn", 0),
            "assessments": storage.count_assessments(),
        },
        "latest_collection": {
            "id": latest.get("id"),
            "status": latest.get("status"),
            "finished_at": latest.get("finished_at"),
            "summary": latest.get("summary"),
        } if latest else None,
        "mode": config.mode_label(),
        "model_configured": config.model_configured(),
        "monitoring": {
            "coverage": monitoring["coverage"],
            "sources": [
                {k: v for k, v in item.items() if k != "cursor"}
                for item in monitoring["items"]
            ],
        },
        "evaluation": evaluation.latest_evaluation(),
    }


@app.get("/api/sources")
def list_sources() -> dict:
    return {"items": agents.monitoring_summary()["items"]}


@app.get("/api/monitoring/evidence")
def monitoring_evidence(days: int = Query(default=7, ge=1, le=31)) -> dict:
    return agents.monitoring_evidence(days=days)


@app.get("/api/knowledge/overview")
def knowledge_overview() -> dict:
    return knowledge_views.overview()


@app.get("/api/knowledge/documents")
def knowledge_documents(
    category: str = Query(default="", max_length=40),
    source_id: str = Query(default="", max_length=80),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    if source_id and sources.get(source_id) is None:
        raise _bad(f"未登记的数据源：{source_id}")
    return knowledge_views.documents(category=category, source_id=source_id, limit=limit)


@app.get("/api/knowledge/graph")
def knowledge_graph(event_limit: int = Query(default=200, ge=1, le=500)) -> dict:
    return knowledge_views.graph(event_limit=event_limit)


@app.get("/api/agent/workbench")
def agent_workbench() -> dict:
    return knowledge_views.agent_workbench()


@app.get("/api/competition/scorecard")
def competition_metrics_scorecard() -> dict:
    return competition_scorecard.scorecard()


@app.get("/api/system/reliability")
def system_reliability(days: int = Query(default=7, ge=1, le=31)) -> dict:
    return reliability.build_reliability_report(days=days)


@app.get("/api/system/alerts")
def system_alerts(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    return observability.recent_alerts(limit=limit)


@app.get("/api/system/logs")
def system_logs(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    return observability.recent_logs(limit=limit)


@app.post("/api/collect")
def collect(payload: CollectRequest | None = None) -> dict:
    requested = (payload.source_ids if payload else None) or None
    if requested:
        unknown = [s for s in requested if sources.get(s) is None]
        if unknown:
            raise _bad(f"未登记的数据源：{', '.join(unknown)}")
    return agents.run_collection(requested, trigger="manual")


@app.post("/api/seed")
def seed() -> dict:
    """Load the verified research cases and the synthetic demo assets."""
    return {
        "research": agents.seed_research_cases(),
        "demo_assets": agents.seed_demo_assets(),
        "notice": "演示资产为合成数据（is_demo=true）；核验案例来自 research/cases.json。",
    }


@app.post("/api/enrichment/run")
def run_enrichment(limit: int = Query(default=10, ge=1, le=50)) -> dict:
    return agents.run_enrichment(limit=limit)


@app.post("/api/assessments/run")
def run_assessments() -> dict:
    return agents.run_assessment()


@app.get("/api/dispositions")
def list_dispositions(limit: int = Query(default=1000, ge=1, le=2000)) -> dict:
    return disposition.list_dispositions(limit=limit)


@app.get("/api/dispositions/metrics")
def disposition_metrics() -> dict:
    return disposition.metrics()


@app.get("/api/dispositions/{event_id}/{asset_id}/advice")
def disposition_advice(event_id: str, asset_id: str) -> dict:
    return disposition.advice(event_id, asset_id)


@app.get("/api/dispositions/{event_id}/{asset_id}")
def get_disposition(event_id: str, asset_id: str) -> dict:
    return disposition.get_disposition(event_id, asset_id)


@app.put("/api/dispositions/{event_id}/{asset_id}")
def update_disposition(event_id: str, asset_id: str, payload: DispositionUpdateRequest) -> dict:
    try:
        return disposition.update_disposition(
            event_id,
            asset_id,
            status=payload.status,
            assignee=payload.assignee,
            note=payload.note,
            evidence_ids=payload.evidence_ids,
            version_before=payload.version_before,
            version_after=payload.version_after,
            operator=payload.operator,
            run_verification=payload.run_verification,
        )
    except disposition.DispositionError as exc:
        raise _bad(str(exc)) from exc


# --------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------

@app.get("/api/events")
def list_events(
    q: str = Query(default="", max_length=MAX_QUERY),
    status: str = Query(default="", max_length=40),
    kind: str = Query(default="", max_length=40),
    category: str = Query(default="", max_length=40),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    # `category` is the user-facing type (漏洞 / 论文 / 标准与框架 / 政策法规),
    # derived from the collector that produced each event -- see
    # `sources.event_group`.  It is not a stored column, so filter and count it
    # here rather than in SQL.
    events, total = storage.list_events(
        query=q, status=status, kind=kind, limit=max(limit, CORPUS_LIMIT))

    counts: dict[str, int] | None = None
    if total <= CORPUS_LIMIT:
        counts = {}
        for event in events:
            group = sources.event_group(event)
            counts[group] = counts.get(group, 0) + 1

    if category:
        events = [e for e in events if sources.event_group(e) == category]
        total = len(events)

    items = []
    for event in events[:limit]:
        enriched = dict(event)
        enriched["category"] = sources.event_group(event)
        enriched.setdefault("enrichment", intelligence.enrich_event(event).get("enrichment"))
        items.append(enriched)
    return {"items": items, "total": total, "categories": counts,
            "group_order": list(sources.GROUP_ORDER)}


@app.get("/api/events/{event_id}")
def get_event(event_id: str) -> dict:
    event = storage.find_event_by_identifier(event_id)
    if event is None:
        raise _bad("事件不存在", status=404)
    result = dict(event)
    result["category"] = sources.event_group(event)
    result["enrichment"] = intelligence.enrich_event(event).get("enrichment")
    result["assessments"] = storage.assessments_for_event(str(event.get("id")))
    return result


# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------

def _asset_payload(model: AssetRequest) -> dict:
    data = model.model_dump()
    data["component"] = data["component"].strip()
    data["name"] = data["name"].strip()
    # Coerce the nullable context fields back to their documented defaults so
    # the stored record always matches the shape the wider app expects.
    data["ecosystem"] = data.get("ecosystem") or ""
    data["exposure"] = data.get("exposure") or "unknown"
    data["business_criticality"] = data.get("business_criticality") or "medium"
    data["conditions"] = data.get("conditions") or {}
    return data


@app.get("/api/assets")
def list_assets() -> dict:
    return {"items": storage.list_assets()}


@app.post("/api/assets")
def create_asset(payload: AssetRequest) -> dict:
    return storage.upsert_asset(_asset_payload(payload))


@app.post("/api/assets/import")
def import_assets(payload: AssetImportRequest) -> dict:
    items = [storage.upsert_asset(_asset_payload(item)) for item in payload.items]
    return {"imported": len(items), "items": items}


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str) -> dict:
    return {"deleted": storage.delete_asset(asset_id)}


@app.post("/api/assets/demo")
def create_demo_assets() -> dict:
    return agents.seed_demo_assets()


@app.post("/api/assets/cyclonedx/dry-run")
def dry_run_cyclonedx(payload: CycloneDXRequest) -> dict:
    try:
        return cyclonedx_assets.preview(payload.bom)
    except cyclonedx_assets.CycloneDXError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/assets/cyclonedx/import")
def import_cyclonedx(payload: CycloneDXImportRequest) -> dict:
    try:
        return cyclonedx_assets.import_bom(
            payload.bom, authorized=payload.authorized,
            is_demo=payload.is_demo, policies=payload.policies,
        )
    except cyclonedx_assets.CycloneDXError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/assets/cyclonedx/{batch_id}/assess")
def assess_cyclonedx_batch(batch_id: str) -> dict:
    try:
        return cyclonedx_assets.assess_batch(batch_id)
    except cyclonedx_assets.CycloneDXError as exc:
        raise _bad(str(exc), status=404) from exc


# --------------------------------------------------------------------------
# assessments and chat
# --------------------------------------------------------------------------

@app.get("/api/assessments")
def list_assessments(limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    return {"items": storage.list_assessments(limit=limit)}


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    return agents.answer(
        payload.question, history=history, thread_id=payload.thread_id,
        context_snapshot=payload.context_snapshot,
    )


# --------------------------------------------------------------------------
# streaming
# --------------------------------------------------------------------------

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _sse(frames) -> StreamingResponse:
    """Wrap a frame generator as SSE.

    A failure after the first byte cannot change the HTTP status any more, so
    it is reported as an `error` frame instead of being swallowed -- the client
    always learns that the run stopped and why.
    """
    def generator():
        try:
            for frame in frames:
                yield streaming.encode_sse(frame)
        except Exception as exc:  # noqa: BLE001 - surfaced to the client verbatim
            yield streaming.encode_sse(("error", {
                "message": f"运行中断：{type(exc).__name__}: {exc}",
            }))

    return StreamingResponse(generator(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/api/stream/pipeline")
def stream_pipeline(payload: StreamPipelineRequest | None = None) -> StreamingResponse:
    """Run the whole pipeline, narrating every real step as it completes."""
    request = payload or StreamPipelineRequest()
    if request.source_ids:
        unknown = [s for s in request.source_ids if sources.get(s) is None]
        if unknown:
            raise _bad(f"未登记的数据源：{', '.join(unknown)}")
    return _sse(streaming.stream_pipeline(
        request.source_ids,
        close_gaps=request.close_gaps,
        enrich_limit=request.enrich_limit,
    ))


@app.post("/api/stream/answer")
def stream_answer(payload: StreamAnswerRequest) -> StreamingResponse:
    """Answer a question, emitting each evidence-bound sentence as it is built."""
    if payload.use_model and not config.model_configured():
        raise _bad("未配置模型密钥，无法使用模型转述；本地证据结论不受影响，可取消该选项后重试")
    history = [{"role": m.role, "content": m.content} for m in payload.history]
    return _sse(streaming.stream_answer(
        payload.question, history=history, use_model=payload.use_model,
        thread_id=payload.thread_id, context_snapshot=payload.context_snapshot,
    ))


# --------------------------------------------------------------------------
# runs, evaluation, export
# --------------------------------------------------------------------------

@app.get("/api/runs")
def list_runs(limit: int = Query(default=30, ge=1, le=200)) -> dict:
    return {"items": storage.list_runs(limit=limit)}


@app.get("/api/evaluation")
def get_evaluation() -> dict:
    return evaluation.latest_evaluation()


@app.get("/api/evaluation/b")
def get_b_evaluation() -> dict:
    """Return the frozen human/machine B evidence used by the scorecard."""
    return b_evaluation.summary()


@app.post("/api/evaluation/run")
def run_evaluation() -> dict:
    return evaluation.run_evaluation()


@app.get("/api/export")
def export() -> dict:
    return storage.export_snapshot()


# --------------------------------------------------------------------------
# versioned full-text corpus (RAG data layer)
# --------------------------------------------------------------------------

@app.post("/api/rag/ingest/snapshot")
def rag_ingest_snapshot(payload: RAGSnapshotRequest) -> dict:
    try:
        return rag_corpus.ingest_snapshot(
            source_id=payload.source_id, snapshot_hash=payload.snapshot_hash,
            suffix=payload.suffix, document_key=payload.document_key,
            title=payload.title, canonical_url=payload.canonical_url,
        )
    except FileNotFoundError as exc:
        raise _bad(str(exc), 404) from exc
    except (OSError, ValueError) as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/rag/ingest/file")
def rag_ingest_file(payload: RAGFileRequest) -> dict:
    if not payload.authorized:
        raise _bad("必须明确授权读取该本地文件")
    try:
        return rag_corpus.ingest_local_file(
            payload.path, source_id=payload.source_id,
            document_key=payload.document_key, title=payload.title,
            canonical_url=payload.canonical_url,
        )
    except FileNotFoundError as exc:
        raise _bad("本地文件不存在", 404) from exc
    except (OSError, ValueError) as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/rag/ingest/latest")
def rag_ingest_latest(payload: RAGLatestRequest | None = None) -> dict:
    request = payload or RAGLatestRequest()
    try:
        return rag_corpus.ingest_latest_snapshots(
            source_ids=request.source_ids, limit=request.limit,
        )
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.get("/api/rag/documents")
def rag_documents(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = rag_corpus.list_documents(limit=limit)
    return {"items": items, "total": len(items)}


@app.get("/api/rag/documents/{document_id}")
def rag_document(document_id: str) -> dict:
    result = rag_corpus.get_document(document_id)
    if result is None:
        raise _bad("文档不存在", 404)
    return result


@app.get("/api/rag/chunks/{chunk_id}")
def rag_chunk(chunk_id: str) -> dict:
    result = rag_corpus.get_chunk(chunk_id)
    if result is None:
        raise _bad("文本块不存在", 404)
    return result


@app.get("/api/rag/search")
def rag_search(
    q: str = Query(min_length=1, max_length=MAX_QUERY),
    limit: int = Query(default=10, ge=1, le=50),
    current_only: bool = True,
) -> dict:
    items = rag_corpus.search(q, limit=limit, current_only=current_only)
    return {"query": q, "items": items, "total": len(items), "index": "keyword-v1"}


# --------------------------------------------------------------------------
# immutable structured Agent context
# --------------------------------------------------------------------------

@app.post("/api/agent/threads")
def create_agent_thread(payload: AgentThreadRequest) -> dict:
    try:
        return agent_context.create_thread(
            payload.objective, thread_id=payload.thread_id,
            base_constraints=payload.base_constraints,
        )
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/threads/{thread_id}/turns")
def append_agent_turn(thread_id: str, payload: AgentTurnRequest) -> dict:
    try:
        return agent_context.append_turn(
            thread_id, visible_user_input=payload.visible_user_input,
            visible_assistant_output=payload.visible_assistant_output,
            objective=payload.objective, focus_event_id=payload.focus_event_id,
            focus_asset_id=payload.focus_asset_id,
            focus_document_id=payload.focus_document_id,
            inherit_focus=payload.inherit_focus, constraints=payload.constraints,
            resolved_references=[item.model_dump() for item in payload.resolved_references],
            chunk_ids=payload.chunk_ids,
            source_version_ids=payload.source_version_ids,
        )
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.get("/api/agent/threads/{thread_id}")
def get_agent_thread(thread_id: str) -> dict:
    result = agent_context.get_thread(thread_id)
    if result is None:
        raise _bad("thread不存在", 404)
    return result


@app.get("/api/agent/threads/{thread_id}/context-snapshots")
def get_agent_thread_snapshots(thread_id: str) -> dict:
    if agent_context.get_thread(thread_id) is None:
        raise _bad("thread不存在", 404)
    items = agent_context.snapshots_for_thread(thread_id)
    return {"thread_id": thread_id, "items": items, "total": len(items)}


@app.get("/api/agent/context-snapshots/{snapshot_id}")
def get_agent_context_snapshot(snapshot_id: str) -> dict:
    result = agent_context.get_snapshot(snapshot_id)
    if result is None:
        raise _bad("context snapshot不存在", 404)
    return result


# --------------------------------------------------------------------------
# task DAG: explicit plan, dependencies, checkpoints and handoffs
# --------------------------------------------------------------------------

@app.post("/api/agent/plans/preview")
def preview_bounded_plan(payload: BoundedPlanRequest) -> dict:
    try:
        return dag_executor.build_plan(payload.model_dump())
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/plans/execute")
def execute_bounded_plan(payload: BoundedPlanRequest) -> dict:
    try:
        return dag_executor.execute_plan(dag_executor.build_plan(payload.model_dump()))
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/multi/execute")
def execute_multi_agent_task(payload: MultiAgentRunRequest) -> dict:
    allowed = set(payload.actions)
    registry = {
        "count_events": lambda: {
            "status": "ok",
            "evidence_ids": ["storage.events"],
            "count": storage.list_events(limit=1)[1],
        },
        "read_cached_snapshot": lambda: {
            "status": "ok",
            "snapshot_hash": "cached-snapshot",
            "evidence_ids": ["cached-snapshot"],
        },
        "run_assessment": lambda: {
            "status": "ok",
            "evidence_ids": ["assessment.run"],
            **agents.run_assessment(),
        },
    }
    actions = [action for action in payload.actions if action in registry]
    if not actions:
        raise _bad("未提供任何可执行的受限工具名称")
    return multi_agent_runtime.run_multi_agent_task(
        payload.objective, actions, registry, run_id=payload.run_id,
    )


@app.post("/api/self-healing/run")
def run_self_healing_endpoint(payload: SelfHealingRunRequest | None = None) -> dict:
    source_ids = payload.source_ids if payload else None
    if source_ids:
        unknown = [item for item in source_ids if sources.get(item) is None]
        if unknown:
            raise _bad(f"未登记的数据源：{', '.join(unknown)}")
    return self_healing.run_self_healing(source_ids)

@app.post("/api/agent/tasks")
def create_agent_task(payload: AgentTaskRequest) -> dict:
    try:
        return task_dag.create_task(
            payload.objective, task_id=payload.task_id,
            success_criteria=payload.success_criteria,
            tool_candidates=payload.tool_candidates, budget=payload.budget,
            constraints=payload.constraints,
        )
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.get("/api/agent/tasks")
def list_agent_tasks(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = task_dag.list_tasks(limit=limit)
    return {"items": items, "total": len(items)}


@app.get("/api/agent/tasks/{task_id}")
def get_agent_task(task_id: str) -> dict:
    result = task_dag.get_task(task_id)
    if result is None:
        raise _bad("task不存在", 404)
    return result


@app.patch("/api/agent/tasks/{task_id}/status")
def update_agent_task_status(task_id: str, payload: AgentTaskStatusRequest) -> dict:
    try:
        return task_dag.set_task_status(task_id, payload.status)
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/plans")
def create_agent_task_plan(task_id: str, payload: AgentPlanRequest) -> dict:
    try:
        return task_dag.create_plan(task_id, payload.title, summary=payload.summary, plan_id=payload.plan_id)
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/nodes")
def create_agent_task_node(task_id: str, payload: AgentTaskNodeRequest) -> dict:
    try:
        return task_dag.create_node(
            task_id, payload.plan_id, payload.title, node_id=payload.node_id,
            depends_on=payload.depends_on, success_criteria=payload.success_criteria,
            tool_candidates=payload.tool_candidates, budget=payload.budget,
        )
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.patch("/api/agent/tasks/{task_id}/nodes/{node_id}/status")
def update_agent_task_node_status(task_id: str, node_id: str, payload: AgentNodeStatusRequest) -> dict:
    try:
        return task_dag.set_node_status(
            task_id, node_id, payload.status,
            checkpoint_note=payload.checkpoint_note, result=payload.result,
        )
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/nodes/{node_id}/checkpoints")
def create_agent_task_checkpoint(task_id: str, node_id: str, payload: AgentCheckpointRequest) -> dict:
    try:
        return task_dag.add_checkpoint(
            task_id, node_id, payload.label, status=payload.status,
            evidence_refs=payload.evidence_refs, note=payload.note,
        )
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/handoffs")
def create_agent_task_handoff(task_id: str, payload: AgentHandoffRequest) -> dict:
    try:
        return task_dag.create_handoff(
            task_id, payload.from_node_id, payload.to_node_id,
            payload=payload.payload, handoff_id=payload.handoff_id,
        )
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


@app.post("/api/agent/tasks/{task_id}/handoffs/{handoff_id}/decision")
def decide_agent_task_handoff(task_id: str, handoff_id: str, payload: AgentHandoffDecisionRequest) -> dict:
    try:
        return task_dag.decide_handoff(
            task_id, handoff_id, payload.decision, decision_note=payload.decision_note,
        )
    except KeyError as exc:
        raise _bad(str(exc).strip("'"), 404) from exc
    except ValueError as exc:
        raise _bad(str(exc)) from exc


# --------------------------------------------------------------------------
# static UI
# --------------------------------------------------------------------------

if config.STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
