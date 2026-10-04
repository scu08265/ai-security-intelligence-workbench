"""B 任务：最小结构化多跳路径检索器与验证器。

**能力范围（说在前面）**：这不是语义推理引擎。它只做一件事——
把本地**真实存在**的关系边组成一张有向图，然后在图上做受限 BFS，
看候选题声明的推理路径是否真的连通，并给出每条边的证据 ID。

图里只有两类边，全部有据可查：

* `事件 --component_is--> 组件`：证据是事件的 `component` 字段与来源 ID；
* `组件或术语 --mentioned_in--> 文档`：证据是一个真实的 `chunk_id` 与字符区间。

**图里没有文档到文档的边**，因此"跨文档题"声明的 `term -> 文档A -> 文档B` 路径
在图上是**不连通**的，验证器会如实报告这一点，而不会补一条虚构的边。

用法::

    python tools/multihop_path_retriever.py --out artifacts/b_eval/multihop_path_validation.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, storage  # noqa: E402

CANDIDATES = ROOT / "evaluation" / "b_multihop_candidates.json"
SOURCE_DATA_DIR = Path(r"D:\ICT\intel-data-b")
MAX_HOPS = 4


def _norm(value: str) -> str:
    return "".join(ch for ch in (value or "").casefold() if ch.isalnum())


class Graph:
    """有向多重图：邻接表存 (目标节点, 关系, 证据) 三元组。"""

    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.adj: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)
        self.edges: list[dict] = []

    def add_node(self, node_id: str, kind: str, label: str = "") -> None:
        self.nodes.setdefault(node_id, {"id": node_id, "kind": kind, "label": label or node_id})

    def add_edge(self, source: str, target: str, relation: str, evidence: dict) -> None:
        key = (source, target, relation, json.dumps(evidence, sort_keys=True, ensure_ascii=False))
        if any(record["_key"] == key for _target, _relation, record in self.adj.get(source, [])):
            return  # 去重：同一条边不重复加入
        record = {"from": source, "to": target, "relation": relation, "evidence": evidence,
                  "_key": key}
        self.adj[source].append((target, relation, record))
        self.edges.append(record)

    def find_path(self, start: str, goal: str, max_hops: int = MAX_HOPS) -> list[dict] | None:
        """受限 BFS；返回边序列，找不到返回 None。"""
        if start not in self.nodes or goal not in self.nodes:
            return None
        queue = deque([(start, [])])
        seen = {start}
        while queue:
            node, path = queue.popleft()
            if len(path) > max_hops:
                continue
            if node == goal and path:
                return path
            for target, _relation, record in self.adj.get(node, []):
                if target in seen:
                    continue
                seen.add(target)
                queue.append((target, path + [record]))
        return None


def build_graph() -> Graph:
    graph = Graph()
    events, _ = storage.list_events(limit=500)
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.document_id, c.text, d.document_key
               FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id
               WHERE c.version_id=d.current_version_id"""
        ).fetchall()

    # 组件 -> 文档（证据：真实分块）
    component_to_docs: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for row in rows:
        graph.add_node(f"doc:{row['document_key']}", "document", row["document_key"])
        text = (row["text"] or "").casefold()
        for event in events:
            component = str(event.get("component") or "").strip()
            if not component or len(component) < 3:
                continue
            if component.casefold() in text:
                node = f"component:{_norm(component)}"
                graph.add_node(node, "component", component)
                component_to_docs[node].append((f"doc:{row['document_key']}",
                                                {"type": "chunk", "chunk_id": row["id"],
                                                 "document_key": row["document_key"]}))

    for node, targets in component_to_docs.items():
        for target, evidence in targets:
            graph.add_edge(node, target, "mentioned_in", evidence)

    # 事件 -> 组件（证据：事件字段）
    for event in events:
        component = str(event.get("component") or "").strip()
        if not component:
            continue
        event_node = f"event:{event['id']}"
        component_node = f"component:{_norm(component)}"
        graph.add_node(event_node, "event", event["id"])
        graph.add_node(component_node, "component", component)
        graph.add_edge(event_node, component_node, "component_is", {
            "type": "event_field", "event_id": event["id"], "field": "component",
            "source_id": (event.get("sources") or [{}])[0].get("id"),
        })
    return graph


def _resolve(node: str) -> list[str]:
    """把候选里的写法（事件 ID / 组件名 / document_key / 术语）映射到图节点。"""
    if node.startswith(("event:", "component:", "doc:", "term:")):
        return [node]
    candidates = [f"event:{node}", f"doc:{node}", f"component:{_norm(node)}", f"term:{node}"]
    return candidates


def _as_node(value: str) -> str:
    """边文件里的端点：已带前缀的按原样使用，否则视为文档节点。"""
    text = str(value or "")
    if text.startswith(("doc:", "term:", "event:", "component:")):
        return text
    return f"doc:{text}"


def term_diagnostics(case: dict, graph: Graph) -> dict:
    """术语可达性：单独诊断，不参与 path_found 判定。"""
    declared = case.get("reasoning_path") or []
    if not declared:
        return {"term": None, "term_nodes": [], "term_reachable": False,
                "term_first_hop_documents": 0}
    term = declared[0]
    nodes = [node for node in _resolve(term) if node in graph.nodes]
    first_hop = {edge["to"] for edge in graph.edges if edge["from"] in nodes}
    return {
        "term": term,
        "term_nodes": nodes,
        "term_reachable": bool(nodes and first_hop),
        "term_first_hop_documents": len(first_hop),
    }


def validate(case: dict, graph: Graph) -> dict:
    declared = case["reasoning_path"]
    start_options = _resolve(declared[0])
    goal_options = _resolve(declared[-1])
    start = next((n for n in start_options if n in graph.nodes), None)
    goal = next((n for n in goal_options if n in graph.nodes), None)

    result = {
        "question_id": case["question_id"],
        "chain_type": case["chain_type"],
        "declared_path": declared,
        "start_node": start,
        "goal_node": goal,
        "path_found": False,
        "hops": None,
        "path_nodes": [],
        "path_edges": [],
        "evidence_ids": [],
        "matches_declared_path": False,
        "failure_reason": None,
    }
    if start is None or goal is None:
        result["failure_reason"] = (
            f"图中找不到端点（起始={start or declared[0]!r}，目标={goal or declared[-1]!r}）")
        # 逐跳说明：端点是否已在图中，缺的是什么
        missing = []
        for index in range(len(declared) - 1):
            left, right = declared[index], declared[index + 1]
            left_known = any(node in graph.nodes for node in _resolve(left))
            right_known = any(node in graph.nodes for node in _resolve(right))
            if left_known and right_known:
                required, why = "document_to_document", "两个端点都在图中，但当前图没有边连接它们"
            elif not left_known:
                required, why = "term_node_with_evidence", (
                    f"节点 {left!r} 不在图中：它既不是已登记来源、事件或组件，"
                    "也没有作为带证据的实体被登记")
            else:
                required, why = "term_node_with_evidence", f"节点 {right!r} 不在图中"
            missing.append({
                "from": left, "to": right, "required_relation": required, "why": why,
                "evidence_needed": "一条可追溯到真实证据的关系边",
            })
        result["missing_edges"] = missing
        return result
    path = graph.find_path(start, goal)
    if path is None:
        result["failure_reason"] = (
            f"图中 {start} 到 {goal} 不连通：当前图只有"
            "事件→组件、组件/术语→文档 两类边，没有文档到文档的边")
        # 逐跳列出缺失的边，不猜测、不补造
        missing = []
        for index in range(len(declared) - 1):
            missing.append({
                "from": declared[index],
                "to": declared[index + 1],
                "required_relation": ("document_to_document"
                                      if declared[index].startswith(("paper:", "source:", "official:"))
                                      else "unspecified"),
                "why": "当前图没有这类边：只有 事件→组件 与 组件/术语→文档",
                "evidence_needed": "一条可追溯到真实证据的关系边"
                                   "（例如两篇文档引用同一实体，或同一 CVE 同时出现在两篇文档中）",
            })
        result["missing_edges"] = missing
        return result
    nodes = [path[0]["from"]] + [edge["to"] for edge in path]
    result.update({
        "missing_edges": [],
        "path_found": True,
        "hops": len(path),
        "path_nodes": nodes,
        "path_edges": [{"from": e["from"], "to": e["to"], "relation": e["relation"]}
                       for e in path],
        "evidence_ids": [e["evidence"].get("chunk_id") or e["evidence"].get("event_id")
                         for e in path],
        "matches_declared_path": all(node in _resolve(declared[i]) or node == declared[i]
                                     for i, node in enumerate(nodes)
                                     if i < len(declared)) if nodes else False,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="多跳候选路径验证")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "multihop_path_validation.json")
    parser.add_argument("--source-data-dir", type=Path, default=SOURCE_DATA_DIR)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES,
                        help="多跳/跨文档候选集（默认冻结基线；重评测批次显式指定）")
    parser.add_argument("--edges", type=Path, default=None,
                        help="已人工核验的文档间关系边 JSON（subject/predicate/object/"
                             "evidence{chunk_id,char_start,char_end}/verified）。"
                             "只加载 verified=true 的边；不加载即维持原行为")
    args = parser.parse_args()
    if not (args.source_data_dir / "intel.sqlite").is_file():
        print("找不到数据库:", args.source_data_dir / "intel.sqlite")
        return 2
    config.DATA_DIR = args.source_data_dir
    config.SNAPSHOT_DIR = args.source_data_dir / "snapshots"
    config.DB_PATH = args.source_data_dir / "intel.sqlite"

    graph = build_graph()
    loaded_edges: list[dict] = []
    if args.edges:
        if not args.edges.is_file():
            print("找不到关系边文件:", args.edges)
            return 2
        edge_payload = json.loads(args.edges.read_text(encoding="utf-8"))
        for edge in edge_payload.get("edges") or []:
            if not edge.get("verified"):
                continue          # 未核验的边不进入图
            evidence = edge.get("evidence") or {}
            if not evidence.get("chunk_id"):
                continue          # 没有真实 chunk 证据的边不进入图
            subject, obj = edge.get("subject"), edge.get("object")
            subject_node, object_node = _as_node(subject), _as_node(obj)
            graph.add_node(subject_node, "term" if subject_node.startswith("term:") else "document",
                           subject)
            graph.add_node(object_node, "document", obj)
            graph.add_edge(subject_node, object_node,
                           edge.get("predicate") or "document_to_document", evidence)
            loaded_edges.append(edge)
    payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    results = [validate(case, graph) for case in payload["cases"]]
    for case, result in zip(payload["cases"], results):
        result["term_diagnostics"] = term_diagnostics(case, graph)

    by_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    missing_kinds: dict[str, int] = {}
    for item in results:
        by_type[item["chain_type"]]["total"] += 1
        by_type[item["chain_type"]]["path_found" if item["path_found"] else "no_path"] += 1
        for edge in item.get("missing_edges") or []:
            key = edge["required_relation"]
            missing_kinds[key] = missing_kinds.get(key, 0) + 1

    out = {
        "schema_version": "b-multihop-path-validation-1.0",
        "graph": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "edge_kinds": sorted({e["relation"] for e in graph.edges}),
            "verified_document_edges_loaded": len(loaded_edges),
            "note": "只含可追溯到真实证据的边；文档到文档的边只有人工核验且带 chunk 证据的才会加载。",
        },
        "counts": {
            "candidates": len(results),
            "path_found": sum(1 for r in results if r["path_found"]),
            "no_path": sum(1 for r in results if not r["path_found"]),
            "by_chain_type": {k: dict(v) for k, v in by_type.items()},
            "missing_edge_kinds": missing_kinds,
            "term_reachable": sum(1 for r in results
                                  if r["term_diagnostics"]["term_reachable"]),
            "term_not_reachable": sum(1 for r in results
                                      if not r["term_diagnostics"]["term_reachable"]),
        },
        "missing_edge_summary": {
            "cases_with_missing_edges": sum(1 for r in results if r.get("missing_edges")),
            "missing_edge_kinds": missing_kinds,
            "note": "缺失清单只说明'缺哪类边、需要什么证据'，不包含任何补造的关系。",
        },
        "limitations": [
            "本工具是受限 BFS，不是语义推理；找不到路径时不会创造新边。",
            "跨文档题声明的 文档A→文档B 在图中不存在，因此必然不连通——"
            "这是数据缺口，不是工具缺陷。",
        ],
        "cases": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("图规模: 节点 %d / 边 %d / 边类型 %s" % (
        len(graph.nodes), len(graph.edges), sorted({e["relation"] for e in graph.edges})))
    print("候选题:", out["counts"]["candidates"],
          "| 找到路径:", out["counts"]["path_found"],
          "| 不连通:", out["counts"]["no_path"])
    print("按类型:", json.dumps(out["counts"]["by_chain_type"], ensure_ascii=False))
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
