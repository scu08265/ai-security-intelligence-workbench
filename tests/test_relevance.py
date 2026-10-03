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


# --------------------------------------------------------------------------
# 中文与标点：社区/博客源以中文为主，若只认 ASCII 术语会整源被过滤成 0 条
# --------------------------------------------------------------------------

def test_chinese_ai_terms_qualify_on_their_own():
    verdict = relevance.classify("AI智能体提示词注入攻击复现")
    assert verdict.included is True
    assert verdict.confidence == "high"


def test_chinese_ai_component_plus_security_intent_is_admitted():
    verdict = relevance.classify("大模型越权调用工具链导致数据泄露")
    assert verdict.included is True
    # "大模型" 是无歧义的 AI 术语，因此判为高置信度而非弱信号待复核
    assert verdict.confidence == "high"


def test_chinese_non_ai_vulnerability_is_still_rejected():
    verdict = relevance.classify("PostgreSQL pgcrypto 堆缓冲区溢出漏洞深度分析")
    assert verdict.included is False


def test_non_breaking_hyphen_does_not_hide_the_ai_signal():
    """Feeds emit 'AI-powered' with U+2011; the token regex keeps it whole."""
    verdict = relevance.classify(
        "GitHub expands application security coverage with AI‑powered scanning"
    )
    assert verdict.included is True
    assert verdict.confidence == "medium"


def test_component_named_in_a_headline_qualifies_without_a_package_argument():
    """Blog titles name the component but never pass `package`."""
    for headline in ("CVE-2026-1234: LiteLLM 密钥泄露漏洞分析",
                     "Ollama 未授权访问漏洞利用分析"):
        assert relevance.classify(headline).included is True


def test_short_component_names_do_not_match_ordinary_prose():
    """'ray', 'jan', 'jax' would otherwise fire on unrelated headlines."""
    for headline in ("Ray 分布式框架任务调度异常",
                     "Jan 5 incident report on phishing"):
        assert relevance.classify(headline).included is False


def test_plain_security_headlines_are_not_admitted_by_the_widened_rules():
    for headline in (
        "Spring Framework UriComponentsBuilder SSRF 漏洞",
        "Group Policy hijacked: PAYLOAD ransomware weaponizes Active Directory",
        "Heap overflow in libpng image parser",
    ):
        assert relevance.classify(headline).included is False

