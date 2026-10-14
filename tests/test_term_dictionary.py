"""The semantic dictionary must be grounded, not written by hand."""

from __future__ import annotations

from app import storage, term_dictionary


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
