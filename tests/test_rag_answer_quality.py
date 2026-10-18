"""答案层回归：标题走元数据、参考文献块不进证据。

两条问题都来自 B 的 10-18 人工复核：问"标题是什么"却回摘要片段，
以及"补充依据"里出现 `ArXiv, vol.` 这类参考文献残句。
"""

from __future__ import annotations

from app import rag


def _chunk(text: str, *, chunk_id: str, document_id: str = "doc-1",
           title: str = "Synthetic doc", start: int = 0) -> dict:
    return {
        "document_id": document_id, "chunk_id": chunk_id, "text": text,
        "char_start": start, "char_end": start + len(text),
        "snapshot_hash": "a" * 64, "source_id": "synthetic", "title": title,
        "provenance": "fulltext", "corpus_class": "collected_source",
    }


def test_title_question_is_answered_from_metadata():
    chunks = [
        _chunk(
            "This paper presents DistillGuard, a novel NPM malicious package detector. "
            "The detector combines static graph analysis with LLM distillation.",
            chunk_id="chunk-title",
            title="DistillGuard: Malicious NPM Package Detection and API Attack Chain Analysis",
        )
    ]
    result = rag.answer_with_rag("DistillGuard 这篇论文的标题是什么？", chunks=chunks)
    assert result["answer"].startswith("《DistillGuard: Malicious NPM Package Detection")
    assert result["citations"], "标题答案也要绑定引用"
    assert result["claims"][0]["evidence_ids"] == ["chunk-title"]


def test_reference_list_chunks_do_not_become_evidence():
    references = "\n".join([
        "[12] A. Author et al., Some Paper, in Proceedings of ACL, 2023.",
        "[13] B. Author et al., Prompt Injection Attacks, arXiv preprint arXiv:2310.18512, 2023.",
        "[14] C. Author, Prompt Injection Defense, vol. 12, pp. 33-45, 2022.",
        "[15] D. Author, Fourth Paper, doi:10.1000/xyz, 2021.",
    ])
    chunks = [
        _chunk(references, chunk_id="chunk-refs", document_id="doc-refs",
               title="Reference list sample"),
        _chunk(
            "Prompt injection bends the instruction boundary of a language model. "
            "It is a leading risk for agents that consume untrusted text.",
            chunk_id="chunk-prose", document_id="doc-prose",
            title="Prompt injection primer",
        ),
    ]
    result = rag.answer_with_rag("什么是提示词注入？", chunks=chunks)
    cited = {item["chunk_id"] for item in result["citations"]}
    assert "chunk-refs" not in cited
    assert result["retrieval"]["bibliographic_filtered"] >= 1


def test_body_paragraph_with_a_volume_marker_is_not_dropped():
    body = (
        "The measurement study reports the attack volume in table 12. "
        "It covers exposed LLM APIs and shows how probes escalate over time."
    )
    assert rag._looks_bibliographic(body) is False
