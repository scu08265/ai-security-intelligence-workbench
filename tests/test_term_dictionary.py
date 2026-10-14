"""The semantic dictionary must be grounded, not written by hand."""

from __future__ import annotations

from app import knowledge_views, storage, term_dictionary


def test_ascii_aliases_match_whole_words_only():
    """Substring matching made "rag" hit "fragmenta" and quoted the wrong text."""
    pattern = term_dictionary._alias_pattern("rag")
    assert pattern.search("a rag pipeline over documents")
    assert not pattern.search("the fragmenta of national rules")
    assert not pattern.search("storage engine")


def test_cjk_aliases_still_match_as_substrings():
    pattern = term_dictionary._alias_pattern("提示词注入")
    assert pattern.search("攻击者通过提示词注入控制智能体")


def test_every_seed_term_gets_a_card_and_unknowns_stay_unknown():
    cards = term_dictionary.entries()
    assert len(cards) == len(term_dictionary.SEED_TERMS)
    for card in cards:
        assert card["key"] and card["term"] and card["label"]
        if not card["covered"]:
            # An uncovered term must not invent a definition or quote.
            assert card["definition"]["quote"] is None
            assert card["definition"]["source"] is None
            assert card["document_count"] == 0


def test_a_grounded_term_names_the_documents_it_appears_in():
    storage.upsert_event({
        "id": "CVE-2099-DICT-1", "kind": "vulnerability", "status": "confirmed",
        "title": "Prompt injection in a local agent", "summary": "Prompt injection allows control.",
        "component": "vllm", "ecosystem": "PyPI",
        "published_at": "2099-01-01T00:00:00Z", "collected_at": storage.utcnow(),
        "withdrawn": False, "aliases": [], "ai_relevance": {"included": True, "reason": "test"},
        "content_hash": "dict-hash-1",
    })
    card = next(item for item in term_dictionary.entries() if item["key"] == "prompt_injection")
    assert card["covered"] is True
    assert "CVE-2099-DICT-1" in {item["document_key"] for item in card["related_documents"]}
    assert card["definition"]["source"] == "corpus"


def test_coverage_reports_what_is_missing_rather_than_filling_it_in():
    coverage = term_dictionary.coverage()
    assert coverage["terms"] == len(term_dictionary.SEED_TERMS)
    assert coverage["covered_terms"] + len(coverage["uncovered_terms"]) == coverage["terms"]


def test_term_edges_land_in_the_knowledge_graph_as_term_nodes():
    """A4：术语 → 文档两跳必须出现在图谱返回里，且术语节点与文档节点分型。"""
    storage.upsert_event({
        "id": "CVE-2099-DICT-2", "kind": "vulnerability", "status": "confirmed",
        "title": "RAG poisoning against a retrieval pipeline",
        "summary": "Data poisoning of the retrieval index.",
        "component": "vllm", "ecosystem": "PyPI",
        "published_at": "2099-01-02T00:00:00Z", "collected_at": storage.utcnow(),
        "withdrawn": False, "aliases": [], "ai_relevance": {"included": True, "reason": "test"},
        "content_hash": "dict-hash-2",
    })
    graph = knowledge_views.graph(event_limit=50)
    terms = [node for node in graph["nodes"] if node["type"] == "term"]
    assert terms, "图谱里应当出现术语节点"
    assert "rag" in {node["ref_id"] for node in terms}

    term_ids = {node["id"] for node in terms}
    node_ids = {node["id"] for node in graph["nodes"]}
    edges = [edge for edge in graph["edges"] if edge["type"] == "term_in_document"]
    assert edges
    for edge in edges:
        assert edge["source"] in term_ids
        assert edge["target"] in node_ids
        # 术语边不能指向术语节点自己，否则"两跳"就退化成自环。
        assert edge["target"] not in term_ids

    # 术语字典把事件标题摘要也当作可检索文档；那些 document_key 就是事件 ID，
    # 图里必须落成事件节点，不能出现 document:CVE-… 这种错标。
    document_refs = {node["ref_id"] for node in graph["nodes"] if node["type"] == "document"}
    assert "CVE-2099-DICT-2" not in document_refs
    assert "event:CVE-2099-DICT-2" in node_ids

    # 边界必须写在返回里，避免被读成跨文档推理。
    assert "跨文档" in graph["term_summary"]["note"]
    assert "跨文档" in graph["policy"]


def test_uncovered_terms_do_not_become_isolated_graph_nodes():
    """未覆盖的术语放进图里会变成孤点，容易读成渲染错误；只在字典里如实标注。"""
    graph = knowledge_views.graph(event_limit=50)
    term_refs = {node["ref_id"] for node in graph["nodes"] if node["type"] == "term"}
    covered = {card["key"] for card in term_dictionary.entries() if card["covered"]}
    assert term_refs <= covered
