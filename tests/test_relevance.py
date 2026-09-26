"""The AI-relevance filter decides what enters the corpus.

These tests pin down the two failure modes that matter: letting unrelated
vulnerabilities flood the store, and discarding genuine AI findings.
"""

from __future__ import annotations

import pytest

from app import relevance


def test_known_ai_packages_match_on_the_package_name_alone():
    for package in ("vllm", "ollama", "langchain", "transformers", "mlflow", "gradio"):
        verdict = relevance.classify(package=package)
        assert verdict.included and verdict.confidence == "high", package


def test_go_module_paths_match_on_their_trailing_segment():
    verdict = relevance.classify(package="github.com/ollama/ollama")
    assert verdict.included and verdict.confidence == "high"


def test_unrelated_package_is_excluded():
    verdict = relevance.classify("Some Office Suite remote code execution", package="office-suite")
    assert verdict.included is False


def test_a_single_generic_word_never_qualifies():
    """Otherwise the whole CVE feed would qualify."""
    verdict = relevance.classify("A vulnerability was found in the parser")
    assert verdict.included is False


def test_generic_words_inside_a_long_description_do_not_qualify():
    """Long descriptions contain 'model', 'training', 'vector' by accident."""
    body = (
        "A vulnerability in the Linux kernel allows an attacker to cause a denial of "
        "service. The model of the training data pipeline uses a vector of attack "
        "vectors. Multiple unrelated words such as inference and embedding appear here "
        "purely as filler to simulate a long advisory text."
    )
    verdict = relevance.classify("Linux Kernel Race Condition Vulnerability", body=body)
    assert verdict.included is False


def test_weak_signal_in_the_headline_goes_to_review_not_confirmed():
    verdict = relevance.classify("Model parsing vulnerability", package="some-product")
    assert verdict.included is True
    assert verdict.confidence == "medium"
    assert verdict.needs_review is True
    assert "复核" in verdict.reason


def test_unambiguous_terms_in_the_headline_are_high_confidence():
    verdict = relevance.classify("Prompt injection in an LLM agent")
    assert verdict.included and verdict.confidence == "high"


def test_reason_always_explains_the_decision():
    for kwargs in (
        {"package": "vllm"},
        {},
        {"package": "nginx"},
    ):
        verdict = relevance.classify(**kwargs)
        assert verdict.reason.strip()


def test_norm_handles_empty_input_without_crashing():
    verdict = relevance.classify(None, "", package=None)
    assert verdict.included is False


@pytest.mark.parametrize("package", ["vllm", "torch", "langchain"])
def test_ai_packages_are_matched_case_insensitively(package):
    assert relevance.classify(package=package.upper()).included is True
