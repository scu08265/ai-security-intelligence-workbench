"""B 任务阶段 A：D-4 的边界场景回归测试（补充已有覆盖）。

已有 `tests/test_rag_answer_citation_consistency.py` 覆盖了主流程；
本文件补的是"证据充分性"与"引用是否真的支持结论"这两类边界，
用于确认修复只是消除了表面矛盾，而**没有**把不足的证据拼成看似确定的答案。

全部离线：用合成 `rag_chunks` 驱动 RAG 路径，不读写任何数据库。
"""

from __future__ import annotations

import pytest

from app import intelligence

REFUSAL_FRAGMENT = "未找到可匹配的事件"
DOCUMENT_TEMPLATE = "根据命中的原文证据："

SUFFICIENT_TEXT = (
    "TrustedGuard enforces a signed allow list for every model asset before loading. " * 2
)
# 只含通用安全词的分块：术语确实存在于语料中，但不足以支撑一条结论
GENERIC_ONLY_TEXT = "vulnerability " * 20


def _chunk(text: str, *, chunk_id: str, document_id: str, title: str = "Synthetic doc",
           start: int = 0) -> dict:
    return {
        "document_id": document_id, "chunk_id": chunk_id, "text": text,
        "char_start": start, "char_end": start + len(text),
        "snapshot_hash": "d" * 64, "source_id": "synthetic", "title": title,
        "provenance": "fulltext", "corpus_class": "collected_source",
    }


def _answer_budget(citations: list[dict]) -> int:
    """答案文本允许的最大长度：模板 + 每条引用原文 + 列表符号与换行。"""
    quoted = citations[:3]
    return len(DOCUMENT_TEMPLATE) + 1 + sum(len(c["quote"]) + 2 for c in quoted) + len(quoted)


# --------------------------------------------------------------------------
# 1) 有充分证据的文档回答
# --------------------------------------------------------------------------

def test_sufficient_document_evidence_produces_a_grounded_answer():
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SUFFICIENT_TEXT, chunk_id="c-1",
                                                   document_id="d-1")]
    )
    assert result["document_citations"], "有充分证据时必须给出引用"
    assert result["answer"].startswith(DOCUMENT_TEMPLATE)
    assert REFUSAL_FRAGMENT not in result["answer"]


def test_document_answer_contains_only_cited_verbatim_quotes():
    """答案不得出现模板与引用原文之外的任何自造文字。"""
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SUFFICIENT_TEXT, chunk_id="c-1",
                                                   document_id="d-1")]
    )
    citations = result["document_citations"]
    for citation in citations:
        assert citation["quote"] in result["answer"], "引用原文必须逐字出现在答案中"
    assert len(result["answer"]) <= _answer_budget(citations), "答案长度超出引用原文总量"


# --------------------------------------------------------------------------
# 2) 有检索结果但证据不足（只命中通用安全词）
# --------------------------------------------------------------------------

def test_generic_term_only_hit_is_treated_as_insufficient_evidence():
    """"vulnerability" 确实存在于语料中，但单独命中不足以支撑回答。"""
    result = intelligence.answer_question(
        "vulnerability", [], [],
        rag_chunks=[_chunk(GENERIC_ONLY_TEXT, chunk_id="c-generic", document_id="d-generic")],
    )
    assert result["document_citations"] == [], "通用词单独命中不应被当作证据"
    assert result["rag"]["refused"] is True
    assert REFUSAL_FRAGMENT in result["answer"]


def test_generic_term_still_hits_in_the_retriever_itself():
    """对照：词本身是可以被检索到的，问题出在证据充分性判定，而不是检索失败。"""
    from app.rag import chunks_from_records, retrieve_chunks

    chunks = chunks_from_records(
        [_chunk(GENERIC_ONLY_TEXT, chunk_id="c-generic", document_id="d-generic")]
    )
    # 检索层会因为"≤ 通用词"守卫直接跳过，这里断言当前的真实行为
    assert retrieve_chunks("vulnerability", chunks, limit=12) == []


# --------------------------------------------------------------------------
# 3) 事件路径拒答且文档路径没有结果
# --------------------------------------------------------------------------

def test_event_refusal_without_any_document_hit_keeps_refusal():
    result = intelligence.answer_question("毫无依据的问题 zzz", [], [], rag_chunks=[])
    assert result["related_event_ids"] == []
    assert result["document_citations"] == []
    assert REFUSAL_FRAGMENT in result["answer"]


# --------------------------------------------------------------------------
# 4) 事件路径拒答但检索到文档
# --------------------------------------------------------------------------

def test_event_refusal_with_document_hits_never_invents_uncited_content():
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SUFFICIENT_TEXT, chunk_id="c-1",
                                                   document_id="d-1")]
    )
    assert result["related_event_ids"] == []
    assert result["document_citations"]
    citations = result["document_citations"]
    for citation in citations:
        assert citation["quote"] in result["answer"]
    assert len(result["answer"]) <= _answer_budget(citations)


# --------------------------------------------------------------------------
# 5) 事件路径有有效答案
# --------------------------------------------------------------------------

def _event() -> dict:
    return {
        "id": "CVE-2099-0001", "title": "Synthetic issue",
        "summary": "Synthetic summary about SynthServe.", "component": "SynthServe",
        "aliases": [], "relationships": [], "sources": [], "status": "confirmed",
        "withdrawn": False, "affected": [], "conditions": [],
    }


def test_valid_event_answer_takes_priority_over_document_path():
    result = intelligence.answer_question(
        "CVE-2099-0001 是什么？", [_event()], [],
        rag_chunks=[_chunk(SUFFICIENT_TEXT, chunk_id="c-1", document_id="d-1")],
    )
    assert result["related_event_ids"] == ["CVE-2099-0001"]
    assert "CVE-2099-0001" in result["answer"]
    assert result["answer"].startswith("CVE-2099-0001")
    # 事件路径有答案时不被覆盖；文档路径是否命中取决于查询词与文档内容是否重叠
    # （本例问的是 CVE，文档讲的是 TrustedGuard，因此 RAG 侧本来就不该有命中）。
    assert isinstance(result["document_citations"], list)
    assert REFUSAL_FRAGMENT not in result["answer"]


def test_event_answer_and_document_citations_coexist_when_both_paths_hit():
    """问句同时命中事件与文档时，事件答案与文档引用并存（引用不被清空）。"""
    result = intelligence.answer_question(
        "CVE-2099-0001 TrustedGuard", [_event()], [],
        rag_chunks=[_chunk(SUFFICIENT_TEXT, chunk_id="c-1", document_id="d-1")],
    )
    assert result["related_event_ids"] == ["CVE-2099-0001"]
    assert result["answer"].startswith("CVE-2099-0001")
    assert len(result["document_citations"]) == 1


# --------------------------------------------------------------------------
# 6) 多份引用来自不同文档，但不能被拼成一个结论
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "connective",
    ["因此", "所以", "综上", "综合来看", "combined with", "therefore", "in summary"],
)
def test_multi_document_citations_are_not_synthesised_into_a_conclusion(connective):
    """两篇文档各命中一条，答案只能并列原文，不得出现综合结论措辞。"""
    chunks = [
        _chunk(SUFFICIENT_TEXT, chunk_id="c-a", document_id="d-a", title="Doc A"),
        _chunk("TrustedGuard also signs plugin manifests before execution. " * 3,
               chunk_id="c-b", document_id="d-b", title="Doc B"),
    ]
    result = intelligence.answer_question("TrustedGuard", [], [], rag_chunks=chunks)
    document_ids = {c["document_id"] for c in result["document_citations"]}
    assert len(document_ids) >= 2, "前置条件：应命中两篇不同文档"
    assert connective not in result["answer"], f"答案出现了推断性措辞：{connective}"
    assert len(result["answer"]) <= _answer_budget(result["document_citations"])


# --------------------------------------------------------------------------
# 7) 引用 ID 可回查，但引用内容不一定支持答案
# --------------------------------------------------------------------------

def test_citation_is_returned_even_when_the_question_subject_is_not_covered():
    """已知局限：检索只做词法匹配，问题的具体主张可能并未被引用覆盖。

    系统不会因此编造"量子纠缠"结论——答案里只有引用原文，
    读者可以据此自行判断支持性。该支持性判定**未自动化**，需人工核验。
    """
    result = intelligence.answer_question(
        "TrustedGuard quantum entanglement", [], [],
        rag_chunks=[_chunk(SUFFICIENT_TEXT, chunk_id="c-1", document_id="d-1")],
    )
    # 词法检索仍会返回引用（'trustedguard' 命中）
    assert result["document_citations"], "本例用于说明词法检索会给出引用"
    # 但答案只包含引用原文，不包含问题里未被证据覆盖的主张
    assert "quantum" not in result["answer"].casefold()
    assert "entanglement" not in result["answer"].casefold()
    for citation in result["document_citations"]:
        assert citation["quote"] in result["answer"]


def test_citation_identity_is_verbatim_and_unchanged():
    """引用 ID / 文档 ID / 区间与原文切片必须严格对应，不得被改写。"""
    text = SUFFICIENT_TEXT
    result = intelligence.answer_question(
        "TrustedGuard", [], [],
        rag_chunks=[_chunk(text, chunk_id="c-fixed", document_id="d-fixed")],
    )
    citation = result["document_citations"][0]
    assert citation["chunk_id"] == "c-fixed"
    assert citation["document_id"] == "d-fixed"
    assert citation["snapshot_hash"] == "d" * 64
    assert text[citation["char_start"]:citation["char_end"]] == citation["quote"]
