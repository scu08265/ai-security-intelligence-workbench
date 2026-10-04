"""B 任务：补真实跨文档关系边（新增来源 → 目标文档 / 术语 → 文档）。

队长要求（选项 A）：

1. 新增 5–8 篇与现有 22 篇产生**明确引用或链接关系**的论文/安全博客；
2. 登记 ≥5 条 ``verified=true`` 的文档间边（subject/predicate/object/chunk_id/
   char_start/char_end/可回读 quote）；
3. 为 ≥5 个题目的起始术语建立"术语 → 文档"的有证据第一跳。

做法（全程只写库副本，真实库只读）：

* ``--stage fetch``：按主题从 arXiv 检索候选论文，下载 PDF 到工作目录（限速 3s/请求）；
* ``--stage screen``：用项目自己的 PDF 解析器抽文本，筛出"命中目标文档标题/官方编号"
  或"含候选题起始术语"的论文；
* ``--stage ingest``：把入选论文按 ``app.paper_fulltext`` 的方式入库到**副本**
  （document_key = ``paper:<arxiv id>``）；
* ``--stage edges``：在入库后的 chunk 里定位命中位置，做**回读校验**
  （``text[char_start:char_end] == quote``），写出边文件。

边界：

* 不修改 ``app/``；不写真实库；不执行任何下载内容里的代码；
* 只认标题/官方编号/arXiv 号级别的匹配，**通用词共现一律丢弃**；
* 未命中的题目不会出现在边文件里，也不改写 ``no_path``。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_PDF = "https://arxiv.org/pdf/{identifier}"
USER_AGENT = "ai-security-workbench-b-eval/1.0 (+evaluation; read-only arXiv fetch)"
RATE_LIMIT_SECONDS = 3.0

# 目标文档（21 道跨文档题的终点）与判定用的标题/官方编号
GOAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "official:eu_ai_act": (
        "Regulation (EU) 2024/1689", "EU AI Act", "European Commission AI Act",
        "Artificial Intelligence Act",
    ),
    "source:owasp_genai": (
        "OWASP Top 10 for LLM Applications", "OWASP Top 10 for Large Language Model",
        "OWASP LLM Top 10", "OWASP GenAI", "OWASP Top 10",
    ),
    "source:nist_ai_rmf": (
        "NIST AI Risk Management Framework", "AI Risk Management Framework",
        "NIST AI RMF",
    ),
    "paper:2609.28915": (
        "On the Effectiveness of Kernel-Level Evidence for Agent Security",
        "Kernel-Level Evidence for Agent Security",
    ),
    "paper:2606.15617": (
        "NeRD: Neuro-Symbolic Rule Distillation",
        "Neuro-Symbolic Rule Distillation for Efficient Ontology-Grounded",
    ),
}

# 候选题的起始术语（对应 evaluation/b_multihop_candidates.json 的 reasoning_path[0]）
START_TERMS = (
    "AUROC", "kernel-level", "multi-agent", "reinforcement learning", "prompt injection",
    "supply chain", "risk management", "Qwen3", "adversarial", "benchmark", "jailbreak",
    "model poisoning", "agent security", "chain-of-thought", "backdoor", "privacy",
    "fine-tuning", "vulnerability", "detector", "alignment", "hallucination",
)

SEARCH_QUERIES = (
    'all:"prompt injection"',
    'all:"AI governance"',
    'all:"agent security"',
    'all:"large language model" AND all:"jailbreak"',
    'all:"LLM security"',
)


def _request(url: str, *, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _arxiv_identifier(entry_id: str) -> str | None:
    match = re.search(r"abs/([0-9]{4}\.[0-9]{4,5})(v[0-9]+)?", entry_id or "")
    return match.group(1) if match else None


def search(query: str, limit: int) -> list[dict]:
    url = f"{ARXIV_API}?search_query={urllib.parse.quote(query)}&max_results={limit}" \
          "&sortBy=submittedDate&sortOrder=descending"
    payload = _request(url)
    namespace = {"a": "http://www.w3.org/2005/Atom"}
    feed = ET.fromstring(payload)
    results = []
    for entry in feed.findall("a:entry", namespace):
        identifier = _arxiv_identifier(entry.findtext("a:id", default="", namespaces=namespace))
        if not identifier:
            continue
        results.append({
            "arxiv_id": identifier,
            "title": " ".join((entry.findtext("a:title", default="", namespaces=namespace) or "").split()),
            "published": entry.findtext("a:published", default="", namespaces=namespace),
            "abstract": " ".join((entry.findtext("a:summary", default="", namespaces=namespace) or "").split()),
            "query": query,
        })
    return results


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def stage_fetch(workdir: Path, per_query: int, queries: tuple[str, ...] | None = None) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    pdf_dir = workdir / "pdf"
    pdf_dir.mkdir(exist_ok=True)
    seen: dict[str, dict] = {}
    for index, query in enumerate(queries or SEARCH_QUERIES):
        if index:
            time.sleep(RATE_LIMIT_SECONDS)
        for item in search(query, per_query):
            seen.setdefault(item["arxiv_id"], item)
    print(f"检索到候选论文：{len(seen)} 篇")

    manifest = []
    for index, (identifier, item) in enumerate(sorted(seen.items())):
        target = pdf_dir / f"{identifier}.pdf"
        if target.is_file():
            raw = target.read_bytes()
        else:
            time.sleep(RATE_LIMIT_SECONDS)
            try:
                raw = _request(ARXIV_PDF.format(identifier=identifier))
            except Exception as exc:                     # noqa: BLE001 - 记录失败即可
                print(f"  下载失败 {identifier}: {type(exc).__name__}: {exc}")
                continue
            if not raw.startswith(b"%PDF-"):
                print(f"  非 PDF，跳过 {identifier}")
                continue
            target.write_bytes(raw)
        manifest.append({**item, "pdf": str(target), "pdf_sha256": _sha256(raw),
                         "pdf_bytes": len(raw)})
    (workdir / "fetched.json").write_text(
        json.dumps({"papers": manifest}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已下载：{len(manifest)} 篇 → {workdir / 'fetched.json'}")
    return {"papers": manifest}


def _extract_text(path: Path) -> str:
    from app import rag_corpus
    sections, _ = rag_corpus.parse_document(path.read_bytes(), "application/pdf")
    return "\n".join(section.text for section in sections if getattr(section, "text", ""))


def _find_matches(text: str) -> tuple[dict[str, str], dict[str, str]]:
    lowered = text.casefold()
    goals: dict[str, str] = {}
    for goal, patterns in GOAL_PATTERNS.items():
        for pattern in patterns:
            if len(pattern) >= 12 and pattern.casefold() in lowered:
                goals[goal] = pattern
                break
    terms = {}
    for term in START_TERMS:
        if term.casefold() in lowered:
            terms[term] = term
    return goals, terms


def stage_screen(workdir: Path) -> dict:
    fetched = json.loads((workdir / "fetched.json").read_text(encoding="utf-8"))["papers"]
    screened = []
    for item in fetched:
        path = Path(item["pdf"])
        try:
            text = _extract_text(path)
        except Exception as exc:                          # noqa: BLE001
            print(f"  解析失败 {item['arxiv_id']}: {type(exc).__name__}")
            continue
        goals, terms = _find_matches(text)
        screened.append({**item, "chars": len(text), "goal_hits": sorted(goals),
                         "goal_patterns": goals, "term_hits": sorted(terms)})
    screened.sort(key=lambda x: (-len(x["goal_hits"]), -len(x["term_hits"])))
    (workdir / "screened.json").write_text(
        json.dumps({"papers": screened}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"可解析：{len(screened)} 篇；命中目标文档的：" 
          f"{sum(1 for x in screened if x['goal_hits'])} 篇")
    for item in screened[:12]:
        print(f"  {item['arxiv_id']} goals={item['goal_hits']} terms={len(item['term_hits'])} "
              f"| {item['title'][:60]}")
    return {"papers": screened}


def stage_ingest(workdir: Path, db_dir: Path, top: int) -> dict:
    os.environ["INTEL_DATA_DIR"] = str(db_dir)
    from app import paper_fulltext

    screened = json.loads((workdir / "screened.json").read_text(encoding="utf-8"))["papers"]
    selected = [item for item in screened if item["goal_hits"]][:top]
    print(f"入库 {len(selected)} 篇到副本：{db_dir}")
    results = []
    for item in selected:
        event = {"id": f"arxiv-{item['arxiv_id']}", "title": item["title"],
                 "paper": {"arxiv_id": item["arxiv_id"]},
                 "sources": [{"url": f"https://arxiv.org/abs/{item['arxiv_id']}"}]}
        result = paper_fulltext.ingest_arxiv_paper(event)
        results.append({"arxiv_id": item["arxiv_id"], "title": item["title"],
                        "goal_hits": item["goal_hits"], "term_hits": item["term_hits"],
                        "pdf_sha256": item["pdf_sha256"],
                        "status": result.get("status"),
                        "snapshot_hash": result.get("snapshot_hash"),
                        "document_key": f"paper:{item['arxiv_id']}"})
        print(f"  {item['arxiv_id']} → {result.get('status')} "
              f"doc={result.get('document_key') or 'paper:' + item['arxiv_id']}")
    (workdir / "ingested.json").write_text(
        json.dumps({"papers": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"papers": results}


def stage_edges(workdir: Path, db_dir: Path, edges_out: Path, docs_out: Path) -> dict:
    os.environ["INTEL_DATA_DIR"] = str(db_dir)
    import sqlite3

    ingested = json.loads((workdir / "ingested.json").read_text(encoding="utf-8"))["papers"]
    connection = sqlite3.connect(f"file:{db_dir / 'intel.sqlite'}?mode=ro", uri=True)
    known_docs = {row[0] for row in connection.execute("select document_key from rag_documents")}
    edges: list[dict] = []
    documents: list[dict] = []

    for item in ingested:
        if item["status"] != "fulltext":
            continue
        document_key = item["document_key"]
        rows = connection.execute(
            """SELECT c.id, c.text FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
               WHERE d.document_key = ? AND d.current_version_id = c.version_id""",
            (document_key,)).fetchall()
        doc_edges = []
        for goal in item["goal_hits"]:
            patterns = sorted(GOAL_PATTERNS.get(goal, ()), key=len, reverse=True)
            best: dict | None = None
            for chunk_id, text in rows:
                for pattern in patterns:
                    position = (text or "").casefold().find(pattern.casefold())
                    if position < 0:
                        continue
                    quote = text[position:position + len(pattern)]
                    if quote.casefold() != pattern.casefold():
                        continue
                    # 取最具体（最长）的匹配作为证据，避免用弱串凑边
                    if best is None or len(quote) > len(best["evidence"]["quote"]):
                        best = {
                            "subject": document_key, "predicate": "cites", "object": goal,
                            "match_basis": f"正文/参考文献中出现 {pattern!r}",
                            "evidence": {"chunk_id": chunk_id, "char_start": position,
                                         "char_end": position + len(pattern), "quote": quote,
                                         "context": " ".join(
                                             (text or "")[max(0, position - 90):
                                                          position + len(pattern) + 90].split())},
                            "verified": True,
                        }
            if best and goal in known_docs:
                doc_edges.append(best)
        for term in item["term_hits"]:
            for chunk_id, text in rows:
                position = (text or "").casefold().find(term.casefold())
                if position < 0:
                    continue
                quote = text[position:position + len(term)]
                doc_edges.append({
                    "subject": f"term:{term}", "predicate": "mentioned_in",
                    "object": f"doc:{document_key}",
                    "match_basis": f"文档正文出现术语 {term!r}",
                    "evidence": {"chunk_id": chunk_id, "char_start": position,
                                 "char_end": position + len(term), "quote": quote,
                                 "context": " ".join(
                                     (text or "")[max(0, position - 60):
                                                  position + len(term) + 60].split())},
                    "verified": True,
                })
                break
        edges.extend(doc_edges)
        documents.append({"arxiv_id": item["arxiv_id"], "title": item["title"],
                          "document_key": document_key, "status": item["status"],
                          "pdf_sha256": item["pdf_sha256"],
                          "snapshot_hash": item["snapshot_hash"],
                          "goal_edges": sum(1 for e in doc_edges if e["predicate"] == "cites"),
                          "term_edges": sum(1 for e in doc_edges
                                            if e["predicate"] == "mentioned_in"),
                          "goals": item["goal_hits"]})

    previous = ROOT / "evaluation" / "b_cross_document_edges_20261002.json"
    payload = {
        "schema_version": "b-cross-document-edges-2.0",
        "scope": "B 任务跨文档/多跳：新增来源后登记的真实文档间边与术语第一跳",
        "method": "arXiv 检索 → 项目自带 PDF 解析 → 只在标题/官方编号级别匹配 → "
                  "记录 chunk_id 与字符偏移并回读校验 text[char_start:char_end] == quote",
        "never_string_cooccurrence": "通用词共现（如 Agents/Adversarial）一律不作边；"
                                     "术语边只在候选题声明的起始术语上建立",
        "edges": edges,
        "documents": documents,
        "counts": {
            "new_documents": len(documents),
            "document_edges": sum(1 for e in edges if e["predicate"] == "cites"),
            "term_edges": sum(1 for e in edges if e["predicate"] == "mentioned_in"),
        },
        "previous_edge_file": str(previous.relative_to(ROOT)) if previous.is_file() else None,
    }
    edges_out.parent.mkdir(parents=True, exist_ok=True)
    edges_out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    docs_out.parent.mkdir(parents=True, exist_ok=True)
    docs_out.write_text(json.dumps({"papers": documents}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print("新增文档:", payload["counts"]["new_documents"],
          "| 文档间边:", payload["counts"]["document_edges"],
          "| 术语边:", payload["counts"]["term_edges"])
    print("边文件:", edges_out)
    print("文档清单:", docs_out)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="补真实跨文档关系边（新增来源）")
    parser.add_argument("--stage", required=True,
                        choices=("fetch", "screen", "ingest", "edges", "packet"))
    parser.add_argument("--workdir", type=Path, default=Path(r"D:\ICT\b_crossdoc_work"))
    parser.add_argument("--db-dir", type=Path, default=Path(r"D:\ICT\intel-data-b-poc-20261002"))
    parser.add_argument("--per-query", type=int, default=10)
    parser.add_argument("--query", action="append", default=None,
                        help="自定义 arXiv 检索式（可重复；不传则用内置主题）")
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--edges-out", type=Path,
                        default=ROOT / "evaluation" / "b_cross_document_edges_20261002_v2.json")
    parser.add_argument("--docs-out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "new_documents_20261002.json")
    args = parser.parse_args()

    if args.stage == "fetch":
        stage_fetch(args.workdir, args.per_query,
                    tuple(args.query) if args.query else None)
    elif args.stage == "screen":
        stage_screen(args.workdir)
    elif args.stage == "ingest":
        stage_ingest(args.workdir, args.db_dir, args.top)
    elif args.stage == "packet":
        stage_packet(args.edges_out, args.db_dir, args.docs_out,
                     ROOT / "artifacts" / "b_eval" / "cross_document_paths_20261002.md")
    else:
        stage_edges(args.workdir, args.db_dir, args.edges_out, args.docs_out)
    return 0


def stage_packet(edges_path: Path, db_dir: Path, docs_path: Path, out_path: Path) -> dict:
    """把连通路径与未连通原因整理成可复核的 markdown（只读，不产生指标）。"""
    import sqlite3

    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    documents = json.loads(docs_path.read_text(encoding="utf-8"))["papers"]
    validation = json.loads(
        (ROOT / "artifacts" / "b_eval" / "multihop_path_validation_20261002_v2.json")
        .read_text(encoding="utf-8"))
    candidates = {c["question_id"]: c for c in json.loads(
        (ROOT / "evaluation" / "b_multihop_candidates.json").read_text(encoding="utf-8"))["cases"]}
    texts: dict[str, str] = {}
    if (db_dir / "intel.sqlite").is_file():
        with sqlite3.connect(f"file:{db_dir / 'intel.sqlite'}?mode=ro", uri=True) as conn:
            texts = {row[0]: row[1] for row in conn.execute("select id, text from rag_chunks")}
    def _node(value: str) -> str:
        text = str(value or "")
        return text if text.startswith(("doc:", "term:", "event:", "component:")) else f"doc:{text}"

    # 证据必须按"边"对应，不能只按 chunk 反查（同一 chunk 可能承载多条边）
    edge_index: dict[tuple[str, str], dict] = {}
    for edge in edges["edges"]:
        edge_index[(_node(edge["subject"]), _node(edge["object"]))] = edge

    lines = [
        "# 跨文档多跳路径复核材料（2026-10-02 批次）",
        "",
        "来源：`artifacts/b_eval/multihop_path_validation_20261002_v2.json`（"
        f"跨文档 {validation['counts']['by_chain_type']['cross_document'].get('path_found', 0)}"
        f"/{validation['counts']['by_chain_type']['cross_document'].get('total', 0)} 连通）。",
        "每条路径都列出**节点 / 边 / evidence ID / 可回读 quote**；未连通的题保留原样。",
        "",
        "## 一、新增来源（{} 篇）".format(len(documents)),
        "",
        "| arXiv ID | 标题 | 命中目标文档 | 文档间边 | 术语边 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for doc in documents:
        lines.append(f"| {doc['arxiv_id']} | {doc['title'][:70]} | "
                     f"{', '.join(doc['goals']) or '—'} | {doc['goal_edges']} | {doc['term_edges']} |")

    connected = [c for c in validation["cases"]
                 if c["chain_type"] == "cross_document" and c["path_found"]]
    lines += ["", f"## 二、已连通路径（{len(connected)} 条）", ""]
    for case in connected:
        question = candidates.get(case["question_id"], {}).get("question", "")
        lines.append(f"### {case['question_id']}｜{question}")
        lines.append("")
        lines.append(f"- 节点：{' → '.join(case['path_nodes'])}")
        for edge in case["path_edges"]:
            lines.append(f"- 边：`{edge['from']}` --{edge['relation']}--> `{edge['to']}`")
        for edge in case["path_edges"]:
            record = edge_index.get((edge["from"], edge["to"]))
            if not record:
                lines.append(f"- evidence: 该边来自图内建边（无外部边文件记录）："
                             f"`{edge['from']}` → `{edge['to']}`")
                continue
            ev = record["evidence"]
            evidence_id = ev["chunk_id"]
            text = texts.get(evidence_id, "")
            readback = text[ev["char_start"]:ev["char_end"]] == ev["quote"]
            lines.append(f"- evidence `{evidence_id}` [{ev['char_start']}:{ev['char_end']}] "
                         f"quote={ev['quote']!r} 回读={'OK' if readback else '失败'} "
                         f"（{record['subject']} → {record['object']}）")
            if ev.get("context"):
                lines.append(f"    - 上下文：…{ev['context']}…")
        lines.append(f"- 与候选声明链路一致：{case['matches_declared_path']}")
        lines.append("")

    unresolved = [c for c in validation["cases"]
                  if c["chain_type"] == "cross_document" and not c["path_found"]]
    lines += [f"## 三、未连通（{len(unresolved)} 条，保留 no_path）", ""]
    lines += ["| 题号 | 起始术语 | 目标文档 | 术语是否可达 | 失败原因 |",
              "| --- | --- | --- | --- | --- |"]
    for case in unresolved:
        diag = case.get("term_diagnostics") or {}
        reason = (case.get("failure_reason") or "").replace("|", "/")
        lines.append(f"| {case['question_id']} | {diag.get('term')} | {case['declared_path'][-1]} "
                     f"| {diag.get('term_reachable')} | {reason[:90]} |")
    lines += ["",
              "## 四、复现命令",
              "",
              "```",
              ".venv\\Scripts\\python.exe tools\\multihop_path_retriever.py "
              "--candidates evaluation\\b_multihop_candidates.json "
              "--edges evaluation\\b_cross_document_edges_20261002_v2.json "
              "--out artifacts\\b_eval\\multihop_path_validation_20261002_v2.json",
              "```"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("复核材料:", out_path, "| 连通", len(connected), "| 未连通", len(unresolved))
    return {"connected": len(connected), "unresolved": len(unresolved)}


if __name__ == "__main__":
    raise SystemExit(main())
