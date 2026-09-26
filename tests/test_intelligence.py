from app.intelligence import answer_question, assess_asset, enrich_event, hybrid_search_events


def event(**updates):
    value = {
        "id": "CVE-2026-12345", "aliases": ["GHSA-abcd-efgh-ijkl"], "title": "Synthetic Widget issue",
        "summary": "Synthetic parser issue for regression testing.", "component": "Widget-AI", "ecosystem": "PyPI",
        "withdrawn": False, "status": "confirmed", "severity": "high", "cvss": [], "cwes": [], "references": [], "tags": [],
        "affected": [{"package": "Widget-AI", "ecosystem": "PyPI", "range": ">=1.2, <1.10", "fixed_version": "1.10", "source_id": "src-1"}],
        "conditions": [{"name": "remote_api", "value": True, "description": "synthetic", "source_id": "src-1"}],
        "sources": [{"id": "src-1", "url": "https://example.invalid/advisory", "title": "Synthetic advisory", "publisher": "Fixture", "source_type": "vendor", "excerpt": "Synthetic fixture only", "published_at": None, "collected_at": "2026-01-01T00:00:00Z", "content_hash": "synthetic", "trust": "fixture"}],
        "poc": [], "relationships": [], "ai_relevance": {"included": True, "reason": "synthetic"},
    }
    value.update(updates)
    return value


def asset(version="1.9", **updates):
    value = {"id": "asset-synthetic", "name": "Synthetic asset", "component": "widget_ai", "ecosystem": "PyPI", "version": version, "exposure": "public", "business_criticality": "high", "conditions": {"remote_api": True}, "is_demo": True, "authorized": True, "updated_at": "2026-01-01T00:00:00Z"}
    value.update(updates)
    return value


def test_versions_are_semantic_not_lexicographic():
    assert assess_asset(event(), asset("1.9"))["status"] == "affected"
    assert assess_asset(event(), asset("1.10"))["status"] == "not_affected"


def test_unknown_version_or_condition_never_becomes_safe():
    assert assess_asset(event(), asset(None))["status"] == "needs_confirmation"
    assert assess_asset(event(), asset(conditions={}))["status"] == "needs_confirmation"


def test_unparseable_range_and_withdrawal_are_conservative():
    bad = event(affected=[{"package": "Widget-AI", "ecosystem": "PyPI", "range": "before spring release", "fixed_version": None, "source_id": "src-1"}])
    assert assess_asset(bad, asset())["status"] == "needs_confirmation"
    assert assess_asset(event(withdrawn=True, status="withdrawn"), asset())["status"] == "needs_confirmation"


def test_unauthorized_asset_is_not_assessed():
    result = assess_asset(event(), asset(authorized=False))
    assert result["status"] == "not_applicable"


def test_version_outside_range_does_not_require_trigger_conditions():
    """A trigger cannot make an explicitly unaffected version uncertain."""
    value = event()
    value["affected"] = [{
        "package": "widget_ai", "ecosystem": "PyPI", "range": "<=0.8.5",
        "fixed_version": "0.8.6", "source_id": "src-1",
    }]
    value["conditions"] = [{
        "name": "remote_api", "value": True, "description": "required",
        "source_id": "src-1",
    }]
    result = assess_asset(value, asset(version="0.10.0", conditions={}))
    assert result["status"] == "not_affected"
    assert any("不在已知受影响区间" in reason for reason in result["reasons"])
    assert not any("关键配置" in reason for reason in result["reasons"])


def test_enrichment_reports_gaps_and_does_not_invent_poc():
    result = enrich_event(event())
    assert "POC资料与验证状态" in result["enrichment"]["gaps"]
    poc = next(x for x in result["enrichment"]["dimensions"] if x["name"] == "poc")
    assert "不等同于不存在" in poc["detail"]
    assert result["enrichment"]["poc_status"] == {
        "status": "not_collected", "records": 0, "executed": False,
        "meaning": "当前接入证据未收录POC；不能据此推断POC不存在",
    }
    assert result["enrichment"]["trace"][-1]["stop_reason"]


def test_attack_chain_is_refused_without_sourced_relationships():
    result = answer_question("CVE-2026-12345 的攻击链是什么？", [event()], [asset()])
    assert "拒绝补写" in result["answer"]
    assert result["mode"] == "local_evidence_extraction"
    assert result["citations"][0]["id"] == "src-1"


def test_generic_vulnerability_words_do_not_match_an_unknown_subject():
    result = answer_question("量子奶酪漏洞怎么修复？", [event()], [asset()])
    assert result["related_event_ids"] == []
    assert "无法可靠回答" in result["answer"]


def test_asset_question_returns_auditable_assessment():
    result = answer_question("CVE-2026-12345 是否影响我的资产？", [event()], [asset()])
    assert result["assessments"][0]["status"] == "affected"
    assert result["trace"][-1]["stop_reason"]


def test_follow_up_uses_history_and_remote_failure_degrades(monkeypatch):
    history = [{"role": "assistant", "content": "此前讨论 CVE-2026-12345"}]
    result = answer_question("它影响资产吗？", [event()], [asset()], history=history,
                             model_config={"planner": True, "base_url": "http://127.0.0.1:1/v1", "model": "x", "api_key_env": "TEST_MODEL_KEY", "timeout": .1})
    assert result["related_event_ids"] == ["CVE-2026-12345"]
    assert result["mode"] == "local_evidence_extraction"
    assert any("降级" in x or "密钥" in x for x in result["limitations"])


def test_no_match_has_no_fabricated_claims():
    result = answer_question("完全无关的问题", [event()], [])
    assert result["claims"] == []
    assert result["citations"] == []


def test_hybrid_search_handles_paraphrase_and_cross_document_results():
    first = event(id="CVE-2026-10001", component="VideoServe",
                  title="Remote video decoder memory corruption",
                  summary="A crafted movie reaches the decoder and may execute commands.")
    second = event(id="CVE-2026-10002", component="VideoServe",
                   title="Video URL validation bypass",
                   summary="Remote multimedia input bypasses URL validation.")
    ranked = hybrid_search_events("remote video multimedia decoder risk", [first, second], limit=5)
    assert {x["id"] for x in ranked} == {"CVE-2026-10001", "CVE-2026-10002"}
    answer = answer_question("VideoServe 有哪些视频风险？", [first, second], [])
    assert set(answer["related_event_ids"]) == {"CVE-2026-10001", "CVE-2026-10002"}
    assert len(answer["citations"]) == 1  # both documents share the same fixture evidence id


def test_multiturn_pronoun_can_request_fix_version():
    history = [{"role": "assistant", "content": "此前讨论 CVE-2026-12345"}]
    result = answer_question("它的修复版本是什么？", [event()], [], history=history)
    assert result["related_event_ids"] == ["CVE-2026-12345"]
    assert "1.10" in result["answer"]
    fix_claim = next(x for x in result["claims"] if "修复版本" in x["text"])
    assert fix_claim["evidence_ids"] == ["src-1"]


def test_asset_remediation_is_bound_to_fix_evidence():
    result = answer_question("CVE-2026-12345 影响我的资产时如何修复？", [event()], [asset()])
    assert result["assessments"][0]["status"] == "affected"
    assert "升级到 1.10" in result["answer"]
    advice = next(x for x in result["claims"] if "建议资产" in x["text"])
    assert advice["evidence_ids"] == ["src-1"]


def test_pronoun_history_never_matches_events_with_empty_component():
    empty_component = event(id="KNOWLEDGE-EMPTY", component="", title="Unrelated knowledge")
    history = [{"role": "assistant", "content": "Previously discussed CVE-2026-12345"}]
    result = answer_question("it affects assets?", [event(), empty_component], [asset()], history=history)
    assert result["related_event_ids"] == ["CVE-2026-12345"]


def test_singular_component_question_ranks_one_but_plural_keeps_many():
    video = event(id="CVE-2026-20001", component="vLLM",
                  title="vLLM video processing remote code execution",
                  summary="A crafted video reaches a vulnerable decoder.")
    temperature = event(id="CVE-2026-20002", component="vLLM",
                        title="vLLM temperature validation denial of service",
                        summary="NaN temperature crashes a GPU worker.")
    singular = answer_question("which vLLM video processing vulnerability allows code execution?",
                               [temperature, video], [])
    plural = answer_question("vLLM has which vulnerabilities?", [temperature, video], [])
    assert singular["related_event_ids"] == ["CVE-2026-20001"]
    assert set(plural["related_event_ids"]) == {"CVE-2026-20001", "CVE-2026-20002"}
