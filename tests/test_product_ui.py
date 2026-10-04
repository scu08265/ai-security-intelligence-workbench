"""Structural checks on the console.

These read the static files rather than driving a browser, so they catch a
navigation or labelling change cheaply.  The browser behaviour itself is
covered by `tools/browser_check.py`.
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import app


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "app/static/app.js").read_text(encoding="utf-8")


def test_rail_has_exactly_three_user_task_entries():
    tabs = re.findall(r'class="tab[^"]*"[^>]*data-tab="([a-z]+)"', HTML)
    assert tabs == ["overview", "knowledge", "scorecard"]


def test_primary_navigation_follows_risk_to_action_workflow():
    labels = ["任务工作台", "知识图谱", "赛题指标"]
    positions = [HTML.index(label) for label in labels]
    assert positions == sorted(positions)
    assert 'id="tab-overview"' in HTML
    assert 'aria-selected="true"' in HTML[HTML.index('id="tab-overview"'):HTML.index('id="tab-overview"') + 180]


def test_old_windows_are_merged_but_their_functional_hosts_survive():
    for gone in ("tab-live", "tab-assessments", "tab-events", "tab-assets", "tab-chat", "tab-manual"):
        assert 'id="' + gone + '"' not in HTML, gone + " should have no rail button"
    for body in ("body-live", "body-assessments", "body-chat", "body-assets", "body-collect",
                 "body-tools", "body-events", "body-runs", "body-evaluation", "body-labels"):
        assert 'id="' + body + '"' in HTML, body + " must still exist"


def test_advanced_functions_use_progressive_disclosure():
    modules = re.findall(r'<details class="workspace-module[^"]*" data-module="([a-z-]+)"', HTML)
    assert modules == ["assessments", "chat", "assets", "sources", "events", "quality", "agent-evidence"]
    assert "wireInlineModules" in SCRIPT


def test_workbench_contains_input_stream_tools_and_conclusion():
    for label in ("从这里开始", "流式生成与工具调用", "最终结论与处置清单"):
        assert label in HTML
    for label in ("做了什么", "得到什么", "产出什么", "有什么影响"):
        assert label in HTML or label in SCRIPT


def test_workbench_has_dynamic_first_run_guide():
    assert 'id="body-onboarding"' in HTML
    for label in ("第一次使用 · 先看这里", "一键体验完整流程", "四个结论怎么读？",
                  "告诉系统我有什么", "获取外面发生了什么", "判断影响并告诉我先做什么"):
        assert label in SCRIPT or label in HTML
    for function in ("initOnboarding", "renderOnboarding", "runGuidedDemo"):
        assert f"function {function}" in SCRIPT
    assert "现在还不能判断你的资产风险" in SCRIPT
    assert "只表示今天没有新增" in SCRIPT


def test_workbench_has_compact_agent_handoff_map_without_a_new_navigation_entry():
    assert 'id="body-orchestration-map"' in HTML
    for label in ("任务如何交接", "输入层", "工具层", "角色交接顺序"):
        assert label in HTML or label in SCRIPT
    for function in ("initOrchestrationMap", "renderOrchestrationMap", "loadOrchestrationMap"):
        assert f"function {function}" in SCRIPT
    assert "'/api/agent/workbench'" in SCRIPT
    assert 'data-tab="orchestration"' not in HTML


def test_standard_asset_simulation_is_a_complete_workbench_flow():
    assert 'id="body-simulation"' in HTML
    for label in ("选择 CycloneDX JSON", "使用内置标准样例", "核对来源与仿真假设",
                  "Agent 执行计划", "匹配结论", "来源事实", "资产输入", "系统推导", "未知与假设"):
        assert label in SCRIPT or label in HTML
    assert "'/api/assets/cyclonedx/dry-run'" in SCRIPT
    assert "'/api/assets/cyclonedx/import'" in SCRIPT
    assert "'/assess'" in SCRIPT
    assert "affectedIds = new Set" in SCRIPT
    assert "风险—资产匹配项" in SCRIPT


def test_simulation_keeps_synthetic_data_and_unknowns_explicit():
    assert "SIMULATION_SAMPLE_BOM" in SCRIPT
    assert "合成仿真数据" in SCRIPT
    assert "不代表任何真实系统" in SCRIPT
    assert "不会判定为安全" in SCRIPT
    assert "不使用 ALL_TRUE 假设" in SCRIPT


def test_knowledge_graph_is_visual_drillable_and_uses_existing_apis():
    assert 'id="panel-knowledge"' in HTML
    assert "function renderKnowledge" in SCRIPT
    assert "'/api/knowledge/documents?limit=200'" in SCRIPT
    assert "'/api/sources'" in SCRIPT
    for label in ("全文文档", "摘要/摘录", "可检索块", "已索引章节", "知识关系与覆盖"):
        assert label in SCRIPT
    assert "openKnowledgeEvent" in SCRIPT


def test_rag_ui_does_not_claim_excerpt_is_fulltext_and_supports_chunk_drilldown():
    for contract_field in ("content_scope", "section_count", "chunk_count", "context_chunks"):
        assert contract_field in SCRIPT
    for honest_label in ("全文尚未入库", "没有可下钻的正文块", "不能用于论文正文级多跳问答"):
        assert honest_label in SCRIPT
    for drilldown_label in ("Agent 本轮上下文块", "个具体块", "无法下钻到具体块"):
        assert drilldown_label in SCRIPT
    assert "function ragDocument" in SCRIPT
    assert "function answerContextChunks" in SCRIPT


def test_agent_context_snapshot_and_confirmation_stay_inside_workbench():
    for label in ("当前 Agent 上下文", "焦点事件", "焦点资产", "焦点文档", "本轮实际使用块", "继承约束"):
        assert label in SCRIPT
    for function in ("renderChatContext", "questionContextWarning", "updateChatContext", "resetChatContextSegment"):
        assert f"function {function}" in SCRIPT
    assert "检测到话题切换" in SCRIPT
    assert "指代可能有歧义" in SCRIPT
    assert "新建上下文段并发送" in SCRIPT
    assert "state.chat.history = []" in SCRIPT
    # Context is hosted by the existing inline chat module, not a fourth rail tab.
    assert 'data-module="chat"' in HTML
    assert 'data-tab="context"' not in HTML


def test_scorecard_consumes_current_evidence_and_reserves_unified_api():
    assert 'id="mode-sub"' in HTML
    assert 'id="mode-link"' in HTML
    assert "'/api/competition/scorecard'" in SCRIPT
    assert "'/api/monitoring/evidence?days=7'" in SCRIPT
    for label in ("持续监测", "知识富化", "证据问答", "时效与性能", "Agent 编排证据"):
        assert label in SCRIPT


def test_scorecard_reads_active_multihop_fields():
    for token in (
        "active_multihop",
        "term_reachable",
        "missing_edge_kinds",
        "缺文档间边",
    ):
        assert token in SCRIPT


def test_scorecard_reads_canonical_monitoring_and_active_batch_fields():
    for token in (
        "monitoring_7d.within_24h_rate.value",
        "monitoring_7d.cumulative_actual_run_days.value",
        "monitoring_7d.cumulative_scheduled_run_days.value",
        "active_qa_quality",
        "active_qa_performance",
        "累计有采集日期",
        "当前批次",
    ):
        assert token in SCRIPT


def test_static_assets_are_cache_busted_and_no_store():
    assert '/app.js?v=' in HTML
    assert '/styles.css?v=' in HTML
    client = TestClient(app)
    for path in ("/", "/index.html", "/app.js", "/styles.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert "no-store" in response.headers.get("cache-control", "")
    assert "'/api/ai-participation'" in SCRIPT


def test_prompts_are_rendered_from_the_backend_not_retyped():
    """A prompt copied into the frontend would drift from the one actually sent."""
    assert "item.prompt" in SCRIPT
    assert "prompt-block" in SCRIPT


def test_papers_are_a_first_class_type():
    """39 arXiv papers were filed under the word 知识 and could not be found."""
    for name in ("论文", "标准与框架", "政策法规"):
        assert "'" + name + "'" in SCRIPT, name + " must be a selectable type"
    assert "CATEGORY_ORDER" in SCRIPT
    assert "renderCategoryOptions" in SCRIPT
    # The old coarse label must not survive anywhere user-facing.
    assert "knowledge: '知识'" not in SCRIPT


def test_dashboard_has_operational_metrics_and_story():
    for label in ["今日新增风险", "受影响资产", "待补信息", "优先处置"]:
        assert f"tile('{label}'" in SCRIPT
    for step in ["公开披露", "系统发现", "证据确认", "关联资产", "给出处置", "留痕验证"]:
        assert step in SCRIPT


def test_technical_detail_is_progressively_disclosed():
    assert "高级信息：来源覆盖、最近运行与质量验证" in SCRIPT
    assert "高级信息：处理轨迹与调度明细" in SCRIPT
    assert "humanizeReason" in SCRIPT
