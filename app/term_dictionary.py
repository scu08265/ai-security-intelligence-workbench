"""Business semantic dictionary for the AI-security terms used in the corpus.

The dictionary is a *seed list* plus a grounding pass.  The seed decides which
terms matter for this domain; everything shown about a term -- how many
documents carry it, which ones, and the sentence that introduces it -- is read
back from the corpus.  A term that the corpus does not contain is reported as
not covered instead of being given an invented definition.

This is the piece that turns a bare term into a first-class object: a term card
can name the documents it appears in, which is the two-hop link (term →
document) the graph did not have before.
"""

from __future__ import annotations

import re
from typing import Any

from . import rag_corpus

# Curated seed.  ``label`` is the Chinese name used in the UI, ``aliases`` are
# the spellings actually searched for, and ``why`` says why the term matters for
# this competition rather than being a generic glossary entry.
SEED_TERMS: tuple[dict[str, Any], ...] = (
    {"key": "prompt_injection", "term": "prompt injection", "label": "提示词注入",
     "category": "模型与数据层风险",
     "aliases": ("prompt injection", "prompt-injection", "提示词注入"),
     "why": "赛题点名的模型层风险，也是语料里出现频率最高的攻击面之一。"},
    {"key": "jailbreak", "term": "jailbreak", "label": "越狱绕过",
     "category": "模型与数据层风险",
     "aliases": ("jailbreak", "jailbreaking", "越狱"),
     "why": "与提示词注入同属绕过模型安全约束的一类手法，常与提示词注入同时出现。"},
    {"key": "data_poisoning", "term": "data poisoning", "label": "数据投毒",
     "category": "模型与数据层风险",
     "aliases": ("data poisoning", "poisoning", "投毒"),
     "why": "赛题点名的训练/检索数据层风险。"},
    {"key": "prompt_leakage", "term": "prompt leakage", "label": "系统提示词泄漏",
     "category": "模型与数据层风险",
     "aliases": ("prompt leakage", "system prompt", "提示词泄漏"),
     "why": "赛题点名的风险类型，也决定回答能否引用到原始系统提示。"},
    {"key": "multi_agent", "term": "multi-agent", "label": "多智能体",
     "category": "AI 应用与智能体风险",
     "aliases": ("multi-agent", "multiagent", "多智能体"),
     "why": "本系统自身的架构形态；语料里有专门讨论多智能体合谋与检测的论文。"},
    {"key": "tool_calling", "term": "tool calling", "label": "工具调用",
     "category": "AI 应用与智能体风险",
     "aliases": ("tool calling", "tool-calling", "function calling", "工具调用"),
     "why": "智能体能力的核心，也是本赛题优化指标里明确点名的能力。"},
    {"key": "supply_chain", "term": "supply chain", "label": "供应链风险",
     "category": "供应链风险",
     "aliases": ("supply chain", "supply-chain", "供应链"),
     "why": "赛题参考分类的第四类，本系统的监测范围按它组织。"},
    {"key": "mcp", "term": "MCP", "label": "模型上下文协议",
     "category": "AI 基础设施",
     "aliases": ("mcp", "model context protocol"),
     "why": "AI 工具接入的事实标准，语料中的 Langflow 漏洞正是 MCP 配置引发的命令注入。"},
    {"key": "rag", "term": "RAG", "label": "检索增强生成",
     "category": "技术方案",
     "aliases": ("rag", "retrieval augmented", "检索增强"),
     "why": "本系统问答模块的实现方式，决定了引用与拒答的口径。"},
    {"key": "graphrag", "term": "GraphRAG", "label": "图谱增强检索",
     "category": "技术方案",
     "aliases": ("graphrag", "graph rag", "图谱增强"),
     "why": "跨文档推理的候选路线；本系统目前只做到检索层，未建图。"},
    {"key": "auroc", "term": "AUROC", "label": "受试者曲线下面积",
     "category": "评测方法",
     "aliases": ("auroc", "auc-roc"),
     "why": "论文里衡量检测器效果的常用指标；评测集里有跨文档题专门问它出现在哪些论文中。"},
    {"key": "false_positive", "term": "false positive", "label": "误报",
     "category": "评测方法",
     "aliases": ("false positive", "false-positive", "误报"),
     "why": "富化与检测类指标都绕不开的分母口径，和 precision 直接对应。"},
    {"key": "cvss", "term": "CVSS", "label": "通用漏洞评分系统",
     "category": "情报标准",
     "aliases": ("cvss",),
     "why": "赛题点名的富化维度之一，本系统按事件保存向量与评分。"},
    {"key": "poc", "term": "POC", "label": "概念验证代码",
     "category": "情报标准",
     "aliases": ("poc", "proof of concept", "概念验证"),
     "why": "赛题点名的富化维度之一；评测语料里没有该维度数据，因此报告写无数据。"},
    # 2026-10-14 领域复核新增（对照赛题四类风险补齐；只加种子，匹配机制未改）。
    # 每条都实测过"语料里是否真的出现"，命中数为 0 的一律没有加入，
    # 依据与覆盖数见 docs/B_TERM_SEED_REVIEW.md。
    {"key": "indirect_prompt_injection", "term": "indirect prompt injection", "label": "间接提示词注入",
     "category": "模型与数据层风险",
     "aliases": ("indirect prompt injection", "间接提示词注入"),
     "why": "提示词注入的关键变体：注入指令来自被检索或被访问的外部内容，而不是用户输入，"
            "与直接注入是两个不同的攻击面。"},
    {"key": "data_leakage", "term": "data leakage", "label": "数据泄漏与外泄",
     "category": "模型与数据层风险",
     "aliases": ("data leakage", "data exfiltration", "数据泄漏", "数据外泄"),
     "why": "训练与推理数据被带出模型边界的一类风险，与“提示词泄漏”（只泄漏系统提示）不是同一件事。"},
    {"key": "membership_inference", "term": "membership inference", "label": "成员推断攻击",
     "category": "模型与数据层风险",
     "aliases": ("membership inference", "成员推断"),
     "why": "判断某条样本是否在训练集中的经典模型隐私攻击，是模型与数据层风险里此前没有覆盖的一类。"},
    {"key": "model_inversion", "term": "model inversion", "label": "模型反演",
     "category": "模型与数据层风险",
     "aliases": ("model inversion", "模型反演"),
     "why": "通过查询重建训练样本特征；与成员推断同属隐私攻击，但机制不同（重建 vs 判定）。"},
    {"key": "multi_agent_collusion", "term": "multi-agent collusion", "label": "多智能体合谋",
     "category": "AI 应用与智能体风险",
     "aliases": ("collusion", "合谋"),
     "why": "多智能体系统的特有风险：多个智能体互相配合绕过各自的约束；语料里有专门讨论该问题的论文。"},
    {"key": "tool_poisoning", "term": "tool poisoning", "label": "工具投毒",
     "category": "AI 应用与智能体风险",
     "aliases": ("tool poisoning", "工具投毒"),
     "why": "智能体被被污染的工具描述或返回值操纵，与提示词注入同源但发生在工具层。"},
    {"key": "excessive_agency", "term": "excessive agency", "label": "过度代理",
     "category": "AI 应用与智能体风险",
     "aliases": ("excessive agency", "过度代理"),
     "why": "智能体被授予超出任务所需的权限与动作空间，是应用层最容易被忽视的一类风险。"},
    {"key": "sandbox_escape", "term": "sandbox escape", "label": "沙箱逃逸",
     "category": "AI 基础设施",
     "aliases": ("sandbox escape", "沙箱逃逸"),
     "why": "执行智能体代码或工具的环境被突破；AI 基础设施这一类此前只有 MCP 一条种子。"},
    {"key": "vllm", "term": "vLLM", "label": "vLLM 推理框架",
     "category": "AI 基础设施",
     "aliases": ("vllm",),
     "why": "语料里命中文档数最多的推理框架，本系统关系评测的多数生态事件也落在它的版本区间上。"},
    {"key": "ollama", "term": "Ollama", "label": "Ollama 本地运行时",
     "category": "AI 基础设施",
     "aliases": ("ollama",),
     "why": "语料覆盖面很广的本地模型运行时，也是模型链“没有本地模型层”这条设计说明的对照面。"},
    {"key": "hugging_face", "term": "Hugging Face", "label": "Hugging Face 模型分发",
     "category": "供应链风险",
     "aliases": ("hugging face", "huggingface"),
     "why": "模型与数据集的集中分发节点，供应链风险里语料命中最多的一条。"},
    {"key": "malicious_package", "term": "malicious package", "label": "恶意包",
     "category": "供应链风险",
     "aliases": ("malicious package", "恶意包", "恶意依赖"),
     "why": "供应链攻击最常见的落地形态；与“投毒”不同，它发生在分发环节而不是训练数据。"},
)

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？；\.\!\?;])\s*")
_DOCUMENT_LIMIT = 8
_QUOTE_LIMIT = 220
_ASCII_ALIAS = re.compile(r"[a-z0-9][a-z0-9 ._\-]*")
_QUOTE_MIN_CHARS = 25

# Some seeded terms are stored as structured fields rather than as prose, so
# searching the text would report them as uncovered while the data is plainly
# there.  These are reported as an event-level count instead of a quote.
STRUCTURED_FIELDS = {"cvss": "cvss", "poc": "poc"}


def _alias_pattern(alias: str) -> re.Pattern:
    """Match an ASCII term as a whole word, a CJK term as a substring.

    Substring matching alone made "rag" hit "fragmenta" and reported the wrong
    document and a nonsense definition sentence, so ASCII aliases require a
    word boundary on both sides.
    """
    escaped = re.escape(alias)
    if _ASCII_ALIAS.fullmatch(alias):
        # Case-insensitive so a definition sentence in title case still matches,
        # and searched against the original text so the offset stays correct.
        return re.compile(r"(?<![a-z0-9])" + escaped + r"(?![a-z0-9])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _event_records() -> list[dict]:
    """Events as searchable documents.

    Most of what this system knows arrives as events, not as full-text
    documents, so a dictionary that only looked at RAG chunks would report
    almost every term as uncovered while the corpus plainly contains it.
    """
    from . import storage

    records: list[dict] = []
    events, _ = storage.list_events(limit=None)
    for event in events:
        text = " ".join(
            str(event.get(field) or "")
            for field in ("title", "summary", "component", "ecosystem")
        ).strip()
        if not text:
            continue
        identifier = str(event.get("id"))
        records.append({
            "document_id": f"event:{identifier}",
            "document_key": identifier,
            "chunk_id": f"event:{identifier}#0",
            "text": text,
            "char_start": 0,
        })
    return records


def _records() -> tuple[list[dict], dict[str, str]]:
    """(searchable records, document_key lookup) over chunks plus events."""
    keys = _document_keys()
    chunks: list[dict] = []
    for record in rag_corpus.list_chunk_records(current_only=True):
        document_id = str(record.get("document_id") or "")
        chunks.append({
            **record,
            "document_key": keys.get(document_id, document_id),
        })
    return chunks + _event_records(), keys


def _document_keys() -> dict[str, str]:
    # document_id -> document_key, so a term card can name documents the way the
    # rest of the system does (paper:..., official:..., source:...).
    from . import storage

    with storage.connect() as conn:
        return {
            row["id"]: row["document_key"]
            for row in conn.execute("SELECT id, document_key FROM rag_documents").fetchall()
        }


def _sentence_with(text: str, pattern: re.Pattern) -> tuple[str, int] | None:
    """The most useful sentence containing the term, plus its offset in `text`."""
    for match in pattern.finditer(text or ""):
        window = text[max(0, match.start() - 400):match.end() + 400]
        for candidate in _SENTENCE_SPLIT.split(window):
            if not pattern.search(candidate):
                continue
            cleaned = " ".join(candidate.split())
            if len(cleaned) < _QUOTE_MIN_CHARS:
                continue
            snippet = cleaned[:_QUOTE_LIMIT] + ("…" if len(cleaned) > _QUOTE_LIMIT else "")
            return snippet, max(0, match.start())
    return None


def _structured_coverage(field: str) -> dict[str, Any]:
    from . import storage

    events, _ = storage.list_events(limit=None)
    present = sum(1 for event in events if event.get(field))
    return {"field": field, "present_events": present, "total_events": len(events)}


def entries(*, limit: int | None = None) -> list[dict[str, Any]]:
    """One card per seeded term, grounded in the persisted corpus."""
    records, keys = _records()
    cards: list[dict[str, Any]] = []
    for seed in SEED_TERMS:
        patterns = [_alias_pattern(alias.casefold()) for alias in seed["aliases"]]
        documents: dict[str, dict] = {}
        quote = None
        quote_chunk = None
        quote_offset = None
        matched_chunks = 0
        for record in records:
            text = str(record.get("text") or "")
            pattern = next((item for item in patterns if item.search(text)), None)
            if pattern is None:
                continue
            matched_chunks += 1
            document_key = str(record.get("document_key") or record.get("document_id") or "")
            documents.setdefault(document_key, {
                "document_key": document_key,
                "chunks": 0,
            })["chunks"] += 1
            if quote is None:
                found = _sentence_with(text, pattern)
                if found:
                    quote, offset = found
                    quote_chunk = record.get("chunk_id")
                    quote_offset = int(record.get("char_start") or 0) + offset
        related = sorted(
            documents.values(), key=lambda item: (-item["chunks"], item["document_key"])
        )
        cards.append({
            "key": seed["key"],
            "term": seed["term"],
            "label": seed["label"],
            "category": seed["category"],
            "why": seed["why"],
            "aliases": list(seed["aliases"]),
            "covered": bool(documents),
            "document_count": len(documents),
            "chunk_count": matched_chunks,
            "structured": (
                _structured_coverage(STRUCTURED_FIELDS[seed["key"]])
                if seed["key"] in STRUCTURED_FIELDS else None
            ),
            "related_documents": related[:_DOCUMENT_LIMIT],
            "definition": {
                "quote": quote,
                "chunk_id": quote_chunk,
                "char_offset": quote_offset,
                "source": "corpus" if quote else None,
            },
            "note": (
                "定义句取自语料原文并可回读；本系统不提供模型生成的术语释义。"
                if quote else "该术语在当前语料中没有出现，因此不给释义。"
            ),
        })
    cards.sort(key=lambda card: (-int(card["covered"]), -card["document_count"], card["key"]))
    return cards[:limit] if limit else cards


def coverage() -> dict[str, Any]:
    cards = entries()
    covered = [card for card in cards if card["covered"]]
    categories: dict[str, int] = {}
    for card in cards:
        categories[card["category"]] = categories.get(card["category"], 0) + 1
    return {
        "terms": len(cards),
        "covered_terms": len(covered),
        "uncovered_terms": [card["key"] for card in cards if not card["covered"]],
        "documents_referenced": len({
            item["document_key"] for card in covered for item in card["related_documents"]
        }),
        "categories": categories,
        "note": "术语节点 → 文档的两跳关系由 related_documents 给出；未覆盖的术语如实列出，不补写释义。",
    }


def term_edges() -> list[dict[str, Any]]:
    """Term → document edges, for callers that want them as graph edges."""
    edges: list[dict[str, Any]] = []
    for card in entries():
        for item in card["related_documents"]:
            edges.append({
                "term": card["key"],
                "document_key": item["document_key"],
                "chunks": item["chunks"],
                "evidence_chunk_id": card["definition"]["chunk_id"],
            })
    return edges
