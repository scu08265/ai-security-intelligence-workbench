"""A1：论文关联的 DOI 逐字比对与标题+年份双匹配。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_paper_links as links  # noqa: E402


def test_doi_normalisation_strips_the_pdf_suffix():
    assert links.normalize_doi(
        "https://link.springer.com/content/pdf/10.1186/s43556-026-00600-7.pdf"
    ) == "10.1186/s43556-026-00600-7"
    assert links.normalize_doi("https://doi.org/10.1000/xyz.123") == "10.1000/xyz.123"
    assert links.normalize_doi("https://example.com/article/12345") is None


def _case(pdf_url: str) -> dict:
    return {
        "relation_id": "BREL-PA-T",
        "subject": "OPENALEX-T",
        "candidate_value": {"pdf_url": pdf_url, "arxiv_id": None, "linked_document_key": None},
    }


def _event(doi: str | None, title: str = "Override Theatre: Governing the Human Override",
           year: str = "2026") -> dict:
    return {
        "title": title,
        "published_at": f"{year}-01-01T00:00:00Z",
        "references": [f"https://doi.org/{doi}"] if doi else [],
    }


def test_a_matching_doi_is_resolved_without_any_fuzzy_matching():
    row = links.classify(
        _case("https://link.springer.com/content/pdf/10.1186/s43556-026-00600-7.pdf"),
        _event("10.1186/s43556-026-00600-7"),
    )
    assert row["status"] == "doi_match"
    assert row["missing"] is None


def test_a_conflicting_doi_is_not_rounded_up():
    row = links.classify(
        _case("https://example.org/10.1000/aaa.pdf"), _event("10.1000/bbb"),
    )
    assert row["status"] == "doi_mismatch"
    assert "不一致" in row["missing"]


def test_a_title_without_a_year_stays_unknown_and_says_why():
    row = links.classify(
        _case("https://example.org/override-theatre-governing-the-human-override.pdf"),
        _event("10.1000/bbb"),
    )
    assert row["title_match"] is True
    assert row["status"] == "unknown"
    assert "没有年份" in row["missing"]


def test_a_title_with_a_conflicting_year_stays_unknown():
    row = links.classify(
        _case("https://example.org/2025/override-theatre-governing-the-human-override.pdf"),
        _event("10.1000/bbb", year="2026"),
    )
    assert row["status"] == "unknown"
    assert "2025" in row["missing"] and "2026" in row["missing"]


def test_a_record_without_a_doi_names_the_missing_field():
    row = links.classify(
        _case("https://example.org/download/12345"),
        _event(None),
    )
    assert row["status"] == "unknown"
    assert "OpenAlex 记录缺 DOI" in row["missing"]
