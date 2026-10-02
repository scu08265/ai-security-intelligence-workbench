"""B 任务阶段 C：从真实语料生成跨文档 / 多跳**候选**题集。

生成规则（全部以数据为依据，不写入任何推断出来的事实）：

* `two_hop`：`事件 --component--> 组件名 --mentioned_in--> 文档分块`。
  两条边的证据分别是事件的 `component` 字段（含其 `sources[].id`）与一个**真实存在**的 `chunk_id`。
* `cross_document`：同一术语在 **>= 2 篇不同文档**中出现，每篇各取一个真实 `chunk_id` 作为证据。
  这类题目只是"跨文档检索"，**不是**多跳推理，`chain_type` 会如实标注。

输出文件是候选集，`verification_status` 一律为 `pending_human_review`；
其中没有任何人工核验的关系。

用法::

    python tools/build_b_multihop_candidates.py --out evaluation/b_multihop_candidates.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import storage  # noqa: E402

# 用于跨文档题的真实术语（均已确认在 >=2 篇文档中出现）
CROSS_DOCUMENT_TOPICS: tuple[tuple[str, str], ...] = (
    ("AUROC", "AUROC 在哪些文档中被讨论？"),
    ("kernel-level", "kernel-level 出现在哪些文档中？"),
    ("multi-agent", "multi-agent 出现在哪些文档中？"),
    ("reinforcement learning", "reinforcement learning 出现在哪些论文中？"),
    ("prompt injection", "prompt injection 出现在哪些文档中？"),
    ("supply chain", "supply chain 出现在哪些文档中？"),
    ("membership inference", "membership inference 出现在哪些文档中？"),
    ("risk management", "risk management 出现在哪些文档中？"),
    ("transparency obligations", "transparency obligations 出现在哪些文档中？"),
    ("malicious package", "malicious package 出现在哪些文档中？"),
    ("Qwen3", "Qwen3 出现在哪些文档中？"),
    ("honeypot", "honeypot 出现在哪些文档中？"),
    ("adversarial", "adversarial 出现在哪些文档中？"),
    ("benchmark", "benchmark 出现在哪些文档中？"),
    ("jailbreak", "jailbreak 出现在哪些文档中？"),
    ("model poisoning", "model poisoning 出现在哪些文档中？"),
    ("agent security", "agent security 出现在哪些文档中？"),
    ("chain-of-thought", "chain-of-thought 出现在哪些文档中？"),
    ("backdoor", "backdoor 出现在哪些文档中？"),
    ("privacy", "privacy 出现在哪些文档中？"),
    ("fine-tuning", "fine-tuning 出现在哪些文档中？"),
    ("vulnerability", "vulnerability 出现在哪些文档中？"),
    ("detector", "detector 出现在哪些文档中？"),
    ("alignment", "alignment 出现在哪些文档中？"),
    ("hallucination", "hallucination 出现在哪些文档中？"),
)

# 用于 two_hop 的组件名（均为事件中真实出现的 component）
TWO_HOP_COMPONENTS: tuple[str, ...] = ("vllm", "ray")


def _corpus() -> tuple[dict[str, str], list[dict]]:
    with storage.connect() as conn:
        keys = {
            row["id"]: row["document_key"]
            for row in conn.execute("SELECT id, document_key FROM rag_documents").fetchall()
        }
        chunks = conn.execute(
            """SELECT c.id, c.document_id, c.ordinal, c.char_start, c.char_end, c.text
               FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id
               WHERE c.version_id=d.current_version_id
               ORDER BY d.updated_at DESC, c.ordinal"""
        ).fetchall()
    return keys, [dict(row) for row in chunks]


def _first_hit_per_document(chunks: list[dict], term: str) -> dict[str, dict]:
    hits: dict[str, dict] = {}
    folded = term.casefold()
    for chunk in chunks:
        if folded not in (chunk["text"] or "").casefold():
            continue
        hits.setdefault(chunk["document_id"], chunk)
    return hits


def build() -> dict:
    keys, chunks = _corpus()
    cases: list[dict] = []
    counter = 0

    # --- two_hop -----------------------------------------------------------
    events, _ = storage.list_events(limit=500)
    for component in TWO_HOP_COMPONENTS:
        related = [e for e in events
                   if str(e.get("component") or "").strip().casefold() == component.casefold()]
        hits = _first_hit_per_document(chunks, component)
        if not related or not hits:
            continue
        for event in related:
            source = (event.get("sources") or [{}])[0]
            # 一个事件只出一道题，把全部匹配文档放进同一道题里，避免复制凑数。
            pairs = list(hits.items())[:3]
            counter += 1
            edges = [{
                "from": event["id"], "relation": "component_is", "to": component,
                "evidence": {"type": "event_field", "event_id": event["id"],
                             "field": "component", "source_id": source.get("id")},
            }]
            for document_id, chunk in pairs:
                document_key = keys[document_id]
                quote_start = (chunk["text"] or "").casefold().index(component.casefold())
                quote = (chunk["text"] or "")[max(0, quote_start - 60):quote_start + 140]
                edges.append({
                    "from": component, "relation": "mentioned_in", "to": document_key,
                    "evidence": {"type": "chunk", "chunk_id": chunk["id"],
                                 "document_key": document_key,
                                 "char_start": chunk["char_start"],
                                 "char_end": chunk["char_end"], "quote": quote},
                })
            cases.append({
                "question_id": f"BMH-{counter:03d}",
                "chain_type": "two_hop",
                "question": f"{event['id']} 关联的组件 {component}，在我们采集的文档里被讨论到了哪些？",
                "answer_points": [
                    f"事件 {event['id']} 的组件为 {component}",
                    "下列文档正文中出现了该组件名：" + "、".join(keys[d] for d, _ in pairs),
                ],
                "documents": [keys[d] for d, _ in pairs],
                "entities": [event["id"], component],
                "edges": edges,
                "reasoning_path": [event["id"], component, *[keys[d] for d, _ in pairs]],
                "required_evidence": [source.get("id"), *[c["id"] for _, c in pairs]],
                "evidence_complete": True,
                "verification_status": "pending_human_review",
                "notes": "两条边的证据均可追溯：事件字段 + 真实分块坐标。"
                         "第二跳是字符串共现，不代表论文对事件本身作出论断；未经人工确认。",
            })

    # --- cross_document ----------------------------------------------------
    for term, question in CROSS_DOCUMENT_TOPICS:
        hits = _first_hit_per_document(chunks, term)
        if len(hits) < 2:
            continue
        counter += 1
        documents = [keys[doc_id] for doc_id in hits]
        edges = [{
            "from": term, "relation": "mentioned_in", "to": keys[doc_id],
            "evidence": {"type": "chunk", "chunk_id": chunk["id"],
                         "document_key": keys[doc_id],
                         "char_start": chunk["char_start"], "char_end": chunk["char_end"],
                         "quote": (chunk["text"] or "")[:180]},
        } for doc_id, chunk in hits.items()]
        cases.append({
            "question_id": f"BMH-{counter:03d}",
            "chain_type": "cross_document",
            "question": question,
            "answer_points": [f"术语 {term} 至少出现在 {len(documents)} 篇文档中"],
            "documents": documents,
            "entities": [term],
            "edges": edges,
            "reasoning_path": [term, *documents],
            "required_evidence": [edge["evidence"]["chunk_id"] for edge in edges],
            "evidence_complete": True,
            "verification_status": "pending_human_review",
            "notes": "这是跨文档**检索**证据，不构成多跳推理；每篇文档各有一个真实分块坐标。",
        })

    counts = {"two_hop": sum(1 for c in cases if c["chain_type"] == "two_hop"),
              "cross_document": sum(1 for c in cases if c["chain_type"] == "cross_document")}
    return {
        "schema_version": "b-multihop-candidates-1.0",
        "description": "B 任务跨文档/多跳候选题库（由真实证据生成）",
        "verification_policy": "所有条目均为候选，verification_status=pending_human_review；"
                               "两条边中至少一条来自字段匹配而非人工确认的关系。",
        "limitations": [
            "系统当前只有 known_exploited 一种显式关系谓词，没有实体/关系抽取，"
            "因此没有真正的多跳路径搜索能力。",
            "two_hop 链的第二跳是'组件名出现在文档文本中'，属于**字符串共现**，"
            "不等于论文对事件本身做出了论断。",
            "cross_document 链只是同一术语在多篇文档中出现，不是跨文档推理。",
        ],
        "counts": counts,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 B 任务跨文档/多跳候选题")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "evaluation" / "b_multihop_candidates.json")
    args = parser.parse_args()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("候选题总数:", len(payload["cases"]), payload["counts"])
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
