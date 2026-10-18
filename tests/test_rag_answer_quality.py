"""答案层回归：标题走元数据、参考文献块不进证据。

两条问题都来自 B 的 10-18 人工复核：问"标题是什么"却回摘要片段，
以及"补充依据"里出现 `ArXiv, vol.` 这类参考文献残句。
"""

from __future__ import annotations

from app import answer_generator, rag


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


def _prose_chunks():
    return [
        _chunk(
            "OllamaDrama deploys a dedicated honeypot that mimics an LLM API "
            "and measures attacks against exposed inference services.",
            chunk_id="chunk-honeypot",
            title="OllamaDrama: Designing and Deploying a Honeypot",
        )
    ]


def test_generated_answer_must_cite_a_retrieved_chunk():
    def generator(question, context, citations):
        return "OllamaDrama 部署了一个模仿 LLM API 的蜜罐 [chunk-honeypot]。"

    result = rag.answer_with_rag(
        "OllamaDrama 中的 honeypot 部署在哪里？",
        chunks=_prose_chunks(), generator=generator,
    )
    assert result["answer"].startswith("OllamaDrama 部署了一个模仿")
    assert result["retrieval"]["generator_used"] is True


def test_generated_answer_without_a_citation_falls_back_to_local_evidence():
    def generator(question, context, citations):
        return "部署在一个蜜罐服务里，但没有给出任何引用。"

    result = rag.answer_with_rag(
        "OllamaDrama 中的 honeypot 部署在哪里？",
        chunks=_prose_chunks(), generator=generator,
    )
    assert result["retrieval"]["generator_used"] is False
    assert result["retrieval"]["generator_error"] == "missing_citation"
    assert "chunk-honeypot" in result["answer"]


def test_generator_failure_degrades_to_local_evidence():
    def generator(question, context, citations):
        raise answer_generator.GeneratorError("upstream_timeout")

    result = rag.answer_with_rag(
        "OllamaDrama 中的 honeypot 部署在哪里？",
        chunks=_prose_chunks(), generator=generator,
    )
    assert result["retrieval"]["generator_used"] is False
    assert result["retrieval"]["generator_error"] == "GeneratorError"
    assert result["citations"], "失败时仍必须返回可核对的原文本地答案"


def test_model_refusal_is_kept_instead_of_replaced_by_a_fragment():
    def generator(question, context, citations):
        return "证据不足，无法回答。"

    result = rag.answer_with_rag(
        "OllamaDrama 中的 honeypot 部署在哪里？", chunks=_prose_chunks(), generator=generator,
    )
    assert result["answer"] == "证据不足，无法回答。"
    assert result["refused"] is True
    assert result["refusal_reason"] == "model_insufficient_evidence"
    assert result["retrieval"]["generator_used"] is True


def test_build_generator_passes_evidence_and_question_to_the_model(monkeypatch):
    captured = {}

    def fake_chat(model_config, messages):
        captured["messages"] = messages
        return "答案 [chunk-honeypot]。"

    monkeypatch.setattr(answer_generator, "_chat", fake_chat)
    generator = answer_generator.build_generator({
        "base_url": "https://example.invalid/v1",
        "model": "synthetic",
        "api_key_env": "SYNTHETIC_KEY",
    })
    citations = [{"chunk_id": "chunk-honeypot", "title": "T", "quote": "Q"}]
    assert generator("问题", "ctx", citations) == "答案 [chunk-honeypot]。"
    joined = " ".join(item["content"] for item in captured["messages"])
    assert "chunk-honeypot" in joined and "问题" in joined
