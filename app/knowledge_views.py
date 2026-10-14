"""Read-only projections for the knowledge and agent-workbench UI.

The functions in this module do not infer links.  Graph edges are emitted only
when the stored event names the source/evidence, carries an evidence-bound
relationship, or has a persisted asset assessment.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from . import agents, intelligence, sources, storage, streaming, task_dag, term_dictionary


def _events(limit: int = 500) -> tuple[list[dict], int]:
    return storage.list_events(limit=max(1, min(limit, 500)))


def _source_prefix(evidence_id: str) -> str:
    return str(evidence_id or "").split(":", 1)[0]


def _document(source: dict, event: dict) -> dict:
    evidence_id = str(source.get("id") or "")
    registered_id = _source_prefix(evidence_id)
    spec = sources.get(registered_id)
    return {
        "id": evidence_id,
        "event_id": str(event.get("id") or ""),
        "event_title": event.get("title"),
        "title": source.get("title") or event.get("title") or evidence_id,
        "publisher": source.get("publisher"),
        "source_type": source.get("source_type"),
        "registered_source_id": registered_id if spec else None,
        "category": sources.event_group(event),
        "url": source.get("url"),
        "published_at": source.get("published_at"),
        "collected_at": source.get("collected_at"),
        "trust": source.get("trust"),
        "excerpt": source.get("excerpt"),
        "content_hash": source.get("content_hash"),
        "provenance": "stored_event_source",
    }


def documents(*, category: str = "", source_id: str = "", limit: int = 200) -> dict:
    events, event_total = _events()
    items = [_document(source, event) for event in events
             for source in (event.get("sources") or []) if source.get("id")]
    if category:
        items = [item for item in items if item["category"] == category]
    if source_id:
        items = [item for item in items if item["registered_source_id"] == source_id]
    items.sort(key=lambda item: (str(item.get("published_at") or ""), item["id"]), reverse=True)
    total = len(items)
    return {
        "items": items[:limit],
        "total": total,
        "event_total": event_total,
        "filters": {"category": category or None, "source_id": source_id or None},
        "classification": {
            "categories": dict(Counter(item["category"] for item in items)),
            "source_types": dict(Counter(item["source_type"] or "unknown" for item in items)),
            "publishers": dict(Counter(item["publisher"] or "unknown" for item in items)),
        },
        "note": "每项均来自事件中实际保存的 sources[]；未保存的正文或来源不会补写。",
    }


def overview() -> dict:
    events, event_total = _events()
    docs = [_document(source, event) for event in events
            for source in (event.get("sources") or []) if source.get("id")]
    relationships = [rel for event in events for rel in (event.get("relationships") or [])
                     if rel.get("evidence_ids")]
    gaps = Counter()
    complete = 0
    for event in events:
        enrichment = intelligence.enrich_event(event).get("enrichment") or {}
        event_gaps = enrichment.get("gaps") or []
        gaps.update(event_gaps)
        complete += not bool(event_gaps)
    source_summary = agents.monitoring_summary()
    return {
        "counts": {
            "events": event_total,
            "documents": len(docs),
            "registered_sources": len(sources.SOURCES),
            "producing_sources": source_summary["coverage"]["endpoints_with_data"],
            "evidence_bound_relationships": len(relationships),
            "assets": storage.count_assets(),
            "assessments": storage.count_assessments(),
            "evidence_complete_events": complete,
            "events_with_gaps": len(events) - complete,
        },
        "categories": dict(Counter(sources.event_group(event) for event in events)),
        "kinds": dict(Counter(event.get("kind") or "unknown" for event in events)),
        "statuses": dict(Counter(event.get("status") or "unknown" for event in events)),
        "top_gaps": [{"name": name, "count": count} for name, count in gaps.most_common(10)],
        "group_order": list(sources.GROUP_ORDER),
        "note": "统计只覆盖当前已持久化数据；关系数仅包含带 evidence_ids 的显式关系。",
    }


def graph(*, event_limit: int = 200) -> dict:
    events, total = _events(event_limit)
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}

    def add_node(node: dict) -> None:
        nodes.setdefault(node["id"], node)

    def add_edge(edge: dict) -> None:
        edges.setdefault(edge["id"], edge)

    for event in events:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        event_node = f"event:{event_id}"
        add_node({"id": event_node, "type": "event", "ref_id": event_id,
                  "label": event.get("title") or event_id,
                  "category": sources.event_group(event), "status": event.get("status")})
        valid_evidence = {str(item.get("id")) for item in event.get("sources") or [] if item.get("id")}
        for source in event.get("sources") or []:
            evidence_id = str(source.get("id") or "")
            if not evidence_id:
                continue
            source_node = f"document:{evidence_id}"
            add_node({"id": source_node, "type": "document", "ref_id": evidence_id,
                      "label": source.get("title") or source.get("publisher") or evidence_id,
                      "source_id": _source_prefix(evidence_id), "url": source.get("url")})
            add_edge({"id": f"documents:{event_id}:{evidence_id}", "source": event_node,
                      "target": source_node, "type": "documented_by",
                      "label": "由文档支撑", "evidence_ids": [evidence_id],
                      "basis": "event.sources"})
        for index, relation in enumerate(event.get("relationships") or []):
            evidence_ids = [str(item) for item in relation.get("evidence_ids") or []
                            if str(item) in valid_evidence]
            if not evidence_ids:
                continue
            relation_node = f"relation:{event_id}:{index}"
            label = " ".join(str(relation.get(key) or "")
                             for key in ("subject", "predicate", "object")).strip()
            add_node({"id": relation_node, "type": "claim", "ref_id": f"{event_id}:{index}",
                      "label": label or "有证据关系", "subject": relation.get("subject"),
                      "predicate": relation.get("predicate"), "object": relation.get("object")})
            add_edge({"id": f"claims:{event_id}:{index}", "source": event_node,
                      "target": relation_node, "type": "has_claim", "label": "包含关系声明",
                      "evidence_ids": evidence_ids, "basis": "event.relationships"})

    visible_events = {node["ref_id"] for node in nodes.values() if node["type"] == "event"}
    assets = {str(item.get("id")): item for item in storage.list_assets() if item.get("id")}
    for assessment in storage.list_assessments(limit=2000):
        event_id, asset_id = str(assessment.get("event_id") or ""), str(assessment.get("asset_id") or "")
        if event_id not in visible_events or asset_id not in assets:
            continue
        asset = assets[asset_id]
        asset_node = f"asset:{asset_id}"
        add_node({"id": asset_node, "type": "asset", "ref_id": asset_id,
                  "label": asset.get("name") or asset_id, "component": asset.get("component"),
                  "is_demo": bool(asset.get("is_demo"))})
        add_edge({"id": f"assessment:{event_id}:{asset_id}", "source": f"event:{event_id}",
                  "target": asset_node, "type": "assessed_against",
                  "label": assessment.get("status") or "unknown",
                  "evidence_ids": list(assessment.get("evidence_ids") or []),
                  "basis": "persisted_assessment", "priority": assessment.get("priority")})
    # 术语 → 文档：术语字典已经把这层两跳算好了，这里把它并进图谱返回，让图谱视图
    # 第一次能看到术语节点。只并入**有文档命中的**术语——未覆盖的术语放进图里会变成
    # 孤点、看起来像渲染错误，它们在 /api/knowledge/terms 里已经如实标为"语料未覆盖"。
    #
    # 边界（必须与跨文档指标分开表述）：这只是术语 → 文档的两跳，不是文档之间的
    # 跨文档推理；跨文档路径仍按 10/21 报，不因为多了这一层就上调。
    term_edge_count = 0
    covered_terms = 0
    for card in term_dictionary.entries():
        documents = card.get("related_documents") or []
        if not documents:
            continue
        covered_terms += 1
        term_node = f"term:{card.get('key')}"
        add_node({
            "id": term_node, "type": "term", "ref_id": card.get("key"),
            "label": card.get("label") or card.get("term") or card.get("key"),
            "term": card.get("term"), "category": card.get("category"),
            "document_count": len(documents),
            "definition_chunk_id": (card.get("definition") or {}).get("chunk_id"),
        })
        definition_chunk = (card.get("definition") or {}).get("chunk_id")
        for item in documents:
            document_key = str(item.get("document_key") or "")
            if not document_key:
                continue
            # 术语字典的"文档"是两类东西：事件的标题摘要（document_key 就是事件 ID），
            # 以及 RAG 分块文档（document_key 形如 paper:…）。节点类型必须跟着真实身份走，
            # 否则会出现 document:CVE-… 这种把事件当文档的错标。
            event_record = storage.get_event(document_key)
            if event_record is not None:
                target = f"event:{document_key}"
                add_node({
                    "id": target, "type": "event", "ref_id": document_key,
                    "label": event_record.get("title") or document_key,
                    "category": sources.event_group(event_record),
                    "status": event_record.get("status"),
                    # 这个事件节点是术语层带进来的，没有加载它的 sources / relationships，
                    # 标出来避免被读成"事件节点没有证据"。
                    "term_only": True,
                })
            else:
                target = f"document:{document_key}"
                add_node({
                    "id": target, "type": "document", "ref_id": document_key,
                    "label": document_key, "source_id": _source_prefix(document_key),
                    "corpus_document": True,
                })
            add_edge({
                "id": f"term_documents:{card.get('key')}:{document_key}",
                "source": term_node, "target": target, "type": "term_in_document",
                "label": "术语出现在文档", "chunks": item.get("chunks"),
                "evidence_ids": [definition_chunk] if definition_chunk else [],
                "basis": "term_dictionary.entries",
            })
            term_edge_count += 1

    return {"nodes": list(nodes.values()), "edges": list(edges.values()),
            "event_total": total, "event_limit": event_limit, "truncated": total > len(events),
            "term_summary": {
                "covered_terms": covered_terms,
                "term_document_edges": term_edge_count,
                "note": ("术语 → 文档的两跳；不等于跨文档推理，跨文档指标另按抽样穷尽金标准报。"),
            },
            "policy": ("不推断边：仅展示 event.sources、带有效 evidence_ids 的 relationships、"
                       "已保存 assessments，以及术语字典算出的术语 → 文档两跳。"
                       "术语 → 文档不等于跨文档推理，跨文档指标另按抽样穷尽金标准报。")}


def agent_workbench() -> dict:
    states = storage.all_source_states()
    tools = []
    for spec in sources.SOURCES:
        state = states.get(spec.id, {})
        tools.append({
            "id": spec.id, "name": spec.name, "layer": "tool", "category": spec.category_label,
            "mode": spec.mode, "status": state.get("status", "idle"),
            "last_run": state.get("last_run"), "last_success": state.get("last_success"),
            "last_error": state.get("last_error"), "events_count": int(state.get("events_count") or 0),
            "requires_token": bool(spec.requires_token_env),
        })
    runs = storage.list_runs(limit=20)
    tasks = task_dag.list_tasks(limit=20)
    return {
        "layers": [
            {"id": "input", "label": "输入层", "items": [
                {"id": "source_registry", "label": "登记来源选择", "constraint": "只接受已登记 source_id"},
                {"id": "question", "label": "用户问题", "constraint": "最多 2000 字；检索本地证据"},
                {"id": "assets", "label": "授权资产", "constraint": "仅对已保存资产执行影响研判"},
            ]},
            {"id": "orchestration", "label": "编排层", "runtime": "single_process_sequential",
             "items": [{"id": phase, "label": label} for phase, label in streaming.PHASE_LABELS.items()]},
            {"id": "tool", "label": "工具层", "items": tools},
        ],
        "roles": [{"id": role, "label": label} for role, label in streaming.ROLE_LABELS.items()],
        "scheduling": {"max_rounds": agents.MAX_ROUNDS, "tool_budget": agents.TOOL_BUDGET},
        "recent_runs": [{"id": run.get("id"), "kind": run.get("kind"),
                         "status": run.get("status"), "started_at": run.get("started_at"),
                         "finished_at": run.get("finished_at"), "summary": run.get("summary")}
                        for run in runs],
        # The workbench receives a compact task-card projection.  The full
        # DAG, checkpoints and handoffs remain available via /api/agent/tasks/{id}.
        "task_dag": [{
            "id": task["id"], "objective": task["objective"], "status": task["status"],
            "success_criteria": task["success_criteria"], "tool_candidates": task["tool_candidates"],
            "budget": task["budget"], "updated_at": task["updated_at"],
        } for task in tasks],
        "runtime_note": "角色是单进程中的逻辑职责；运行记录为空时不表示步骤已经执行。",
    }
