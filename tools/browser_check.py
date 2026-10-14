"""End-to-end browser check for the console.

Drives the real UI in a real browser and asserts the things that only break in
a browser: that the pipeline narrates itself *incrementally* (rather than
dumping a finished list), that the streaming answer grows as it is built, and
that no console error or failed request occurs.

Playwright is **optional** -- the application does not need it. Install it only
to run this check:

    pip install playwright && playwright install chromium

Usage (start the server first):

    python -m uvicorn app.api:app --port 8020
    python tools/browser_check.py --base http://127.0.0.1:8020

Exit code 0 means every assertion held.  Screenshots land in
``artifacts/browser/`` for visual review.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

QUESTION = "CVE-2026-22778 会影响我的哪些资产？"
FAST_SOURCE = "cisa_kev"
SHOT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "browser"
# The two health panels are quoted in the technical report, so their screenshots
# belong next to the other report screenshots, not only in the scratch dir.
DOC_SHOT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {label}{(' -- ' + detail) if detail else ''}")
    if not condition:
        failures.append(label)


def wait_until(predicate, timeout_s: float = 60.0, what: str = "condition"):
    """Poll from Python.

    ``page.wait_for_function`` compiles its argument with ``eval``, which the
    page's own CSP (``script-src 'self'``, no ``unsafe-eval``) forbids.  That
    the CSP blocks the test harness is itself a good sign, so poll here instead.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            value = predicate()
        except Exception:  # noqa: BLE001 -- element not there yet
            value = None
        if value:
            return value
        time.sleep(0.25)
    raise TimeoutError(f"timed out after {timeout_s}s waiting for {what}")


def _launch(pw):
    """Launch the installed Edge when the Chromium bundle is absent.

    ``tools/capture_operations_screenshots.py`` already prefers the system Edge
    so no browser download is needed; this check should not require a 130 MB
    download just to look at the same page.
    """
    try:
        return pw.chromium.launch(channel="msedge")
    except Exception:
        try:
            return pw.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - reported to the operator
            raise SystemExit(
                "没有可用浏览器：装 Edge，或先跑 `playwright install chromium`。"
                f"（{type(exc).__name__}）"
            ) from None


def run(base: str) -> int:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    DOC_SHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as pw:
        browser = _launch(pw)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: failed_requests.append(f"{r.url} {r.failure}"))

        print("\n1. 启动与默认面板")
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(500)
        check("模式横幅已渲染", bool(page.inner_text("#mode-text").strip()))
        check("默认打开任务台", page.is_visible("#panel-overview"))
        check("首页渲染任务引导",
              bool(page.inner_text("#body-onboarding").strip()))

        print("\n2. 三入口结构与赛题指标")
        check("导航只保留 3 个任务入口", page.locator(".tablist .tab").count() == 3,
              f"{page.locator('.tablist .tab').count()} 项")
        check("三个入口名称清晰",
              all(label in page.inner_text(".rail") for label in ("任务工作台", "知识图谱", "赛题指标")))
        page.click("#mode-link")
        wait_until(lambda: page.locator("#body-scorecard .score-capability").count() >= 9,
                   timeout_s=20, what="赛题指标卡")
        check("赛题指标卡全部渲染",
              page.locator("#body-scorecard .score-capability").count() >= 9,
              f"{page.locator('#body-scorecard .score-capability').count()} 张")
        check("统一计分接口兼容状态已说明", bool(page.inner_text("#body-scorecard .scorecard-status").strip()))
        page.screenshot(path=str(SHOT_DIR / "01-scorecard.png"), full_page=True)

        print("\n2a. 来源健康度与系统健康面板（浏览器实测 + 与接口逐项核对）")
        health = page.evaluate("() => fetch('/api/system/health').then(r => r.json())")
        source_panel = page.locator("#body-scorecard article.score-capability").filter(
            has=page.locator("h3", has_text="来源健康度")).first
        system_panel = page.locator("#body-scorecard article.score-capability").filter(
            has=page.locator("h3", has_text="系统健康")).first
        check("来源健康度面板已渲染", source_panel.count() > 0)
        check("系统健康面板已渲染", system_panel.count() > 0)

        api_sources = health.get("sources") or []
        api_modules = health.get("modules") or []
        source_rows = source_panel.locator("tbody tr").count()
        check("来源健康度按来源逐行渲染",
              source_rows == len(api_sources),
              f"页面 {source_rows} 行 / 接口 {len(api_sources)} 个来源")
        # 该面板有两张表（模块表，其后是活跃降级表），行数必须只数第一张。
        module_rows = system_panel.locator("table").first.locator("tbody tr").count()
        check("系统健康按模块逐行渲染",
              module_rows == len(api_modules),
              f"页面 {module_rows} 行 / 接口 {len(api_modules)} 个模块")

        ok_modules = sum(1 for item in api_modules if item.get("state") == "ok")
        expected_badge = f"{ok_modules} / {len(api_modules)} 个模块正常"
        check("系统健康徽标与接口一致", expected_badge in system_panel.inner_text(),
              expected_badge)

        source_text = source_panel.inner_text()
        rendered = [
            (item.get("name") or item.get("id"))
            for item in api_sources
            if (item.get("name") or item.get("id")) in source_text
        ]
        check("来源行内容来自接口而非前端推算",
              len(rendered) == len(api_sources),
              f"{len(rendered)} / {len(api_sources)} 行可对上接口名称")

        status_labels = {"ok": "正常", "failed": "失败", "stale": "陈旧（保留历史数据）",
                         "partial": "部分成功", "skipped": "已跳过", "idle": "未运行"}
        mismatch = []
        for item in api_sources:
            if item.get("degradation"):
                continue
            label = status_labels.get(str(item.get("status")), str(item.get("status") or "未运行"))
            if label not in source_text:
                mismatch.append((item.get("id"), label))
        check("来源状态文案与接口状态取值一致", not mismatch, str(mismatch[:3]))

        source_panel.screenshot(path=str(DOC_SHOT_DIR / "09-source-health.png"))
        system_panel.screenshot(path=str(DOC_SHOT_DIR / "10-system-health.png"))
        source_panel.screenshot(path=str(SHOT_DIR / "09-source-health.png"))
        system_panel.screenshot(path=str(SHOT_DIR / "10-system-health.png"))

        print("\n2a2. 模型降级链与角色绑定（浏览器实测 + 与接口核对）")
        chain = page.evaluate("() => fetch('/api/system/model-chain').then(r => r.json())")
        chain_panel = page.locator("#body-scorecard article.score-capability").filter(
            has=page.locator("h3", has_text="模型降级链与角色绑定")).first
        check("模型降级链面板已渲染", chain_panel.count() > 0)
        levels = chain.get("levels") or []
        bindings = chain.get("role_bindings") or []
        level_rows = chain_panel.locator("table").first.locator("tbody tr").count()
        check("降级链逐级渲染", level_rows == len(levels),
              f"页面 {level_rows} 行 / 接口 {len(levels)} 级")
        check("当前生效层级与接口一致",
              f"第 {chain.get('active_level')} 级" in chain_panel.inner_text(),
              f"active_level={chain.get('active_level')}")
        role_rows = chain_panel.locator("table").nth(1).locator("tbody tr").count()
        check("角色绑定逐行渲染", role_rows == len(bindings),
              f"页面 {role_rows} 行 / 接口 {len(bindings)} 个角色")
        skip_reasons = [item.get("skip_reason") for item in levels if item.get("skip_reason")]
        check("每一级被跳过的原因都写在页面上",
              all(reason in chain_panel.inner_text() for reason in skip_reasons),
              f"{len(skip_reasons)} 条原因")
        chain_panel.screenshot(path=str(DOC_SHOT_DIR / "12-model-chain.png"))

        print("\n2b. 知识图谱可视化")
        page.click("#tab-knowledge")
        wait_until(lambda: page.locator("#body-knowledge .knowledge-map").count() == 1,
                   timeout_s=20, what="知识关系图")
        check("知识统计卡已渲染", page.locator("#body-knowledge .tile").count() == 4)
        check("文档类别分布已渲染", page.locator("#body-knowledge progress").count() > 0)
        check("来源—文档—知识关系已渲染", page.locator("#body-knowledge .knowledge-node").count() > 3)
        knowledge_text = page.inner_text("#body-knowledge")
        check("全文、摘要、章节和分块状态可见",
              all(label in knowledge_text for label in ("全文文档", "摘要/摘录", "可检索块", "已索引章节")))
        if page.locator("#body-knowledge .rag-document").count():
            page.locator("#body-knowledge .rag-document").first.locator(":scope > summary").click()
            detail_text = page.locator("#body-knowledge .rag-document").first.inner_text()
            check("文档可展开核查正文与块级状态",
                  "章节" in detail_text and ("正文块" in detail_text or "块" in detail_text))
        page.screenshot(path=str(SHOT_DIR / "02c-knowledge.png"), full_page=True)

        print("\n2b2. 术语语义字典与术语 → 文档两跳（浏览器实测 + 与接口核对）")
        terms_payload = page.evaluate("() => fetch('/api/knowledge/terms').then(r => r.json())")
        terms_api = terms_payload.get("items") or []
        wait_until(lambda: page.locator("#body-knowledge .term-card").count() >= 1,
                   timeout_s=20, what="术语卡")
        term_cards = page.locator("#body-knowledge .term-card").count()
        check("术语卡逐条渲染", term_cards == len(terms_api),
              f"页面 {term_cards} 张 / 接口 {len(terms_api)} 个术语")
        knowledge_now = page.inner_text("#body-knowledge")
        covered = [item for item in terms_api if item.get("covered")]
        check("已覆盖术语标出关联文档数",
              all(f"覆盖 {item['document_count']} 份文档" in knowledge_now for item in covered),
              f"{len(covered)} 个已覆盖术语")
        check("未覆盖术语如实标注而不是编造释义",
              all("语料未覆盖" in knowledge_now for item in terms_api if not item.get("covered")))

        term_graph = page.locator("#body-knowledge .term-graph")
        check("术语 → 文档两跳已渲染", term_graph.count() == 1)
        term_nodes = term_graph.locator(".knowledge-node.term").count()
        other_nodes = term_graph.locator(".knowledge-node.document, .knowledge-node.event").count()
        check("图谱里术语节点与文档节点分型渲染",
              term_nodes >= 1 and other_nodes >= 1,
              f"术语节点 {term_nodes} / 文档与事件节点 {other_nodes}")
        check("两跳卡片写明不等同跨文档推理",
              "不等于文档之间的跨文档推理" in knowledge_now)
        term_card = page.locator("#body-knowledge .card").filter(
            has=page.locator(".term-card")).first
        term_card.screenshot(path=str(DOC_SHOT_DIR / "11-term-dictionary.png"))

        print("\n2c. 标准资产仿真")
        page.click("#tab-overview")
        page.click("#body-simulation button.btn--ghost")
        wait_until(lambda: page.locator("#body-simulation .simulation-provenance").count() == 1,
                   timeout_s=15, what="标准样例预览")
        check("合成样例标记清晰", "合成仿真数据" in page.inner_text("#body-simulation"))
        check("假设确认前运行按钮禁用",
              page.locator("#body-simulation button.btn--primary").is_disabled())
        # 两个确认框：第一个是"标记为合成演示资产"，第二个才是"我同意纳入评估"。
        # 勾错那个不会解锁运行按钮，所以按文案定位。
        page.locator("#body-simulation .simulation-confirm").filter(
            has_text="我已核对以上来源和假设").locator("input").check()
        check("确认假设后可运行",
              not page.locator("#body-simulation button.btn--primary").is_disabled())
        page.locator("#body-simulation button.btn--primary").click()
        wait_until(lambda: page.locator("#body-simulation .simulation-results").count() == 1,
                   timeout_s=60, what="仿真匹配结论")
        check("去重资产与关系数同时展示",
              all(label in page.inner_text("#body-simulation")
                  for label in ("受影响资产", "待补信息资产", "风险—资产匹配项")))
        if page.locator("#body-simulation .simulation-results .link-button").count():
            page.locator("#body-simulation .simulation-results .link-button").first.click()
            wait_until(lambda: page.locator("#body-simulation .evidence-layers").count() == 1,
                       timeout_s=20, what="四层证据详情")
            detail_text = page.inner_text("#body-simulation .evidence-layers")
            check("详情分开事实、输入、推导与未知",
                  all(label in detail_text for label in ("来源事实", "资产输入", "系统推导", "未知与假设")))
        page.screenshot(path=str(SHOT_DIR / "02d-simulation.png"), full_page=True)

        print("\n3. 任务工作台内流式执行")
        page.click("#tab-overview")
        page.wait_for_timeout(200)
        page.click("#live-open")
        wait_until(lambda: page.eval_on_selector(
            "#panel-overview .live-source", "e => e.options.length") > 1,
            timeout_s=15, what="来源下拉框")
        check("来源下拉框来自后端登记表",
              page.eval_on_selector("#panel-overview .live-source", "e => e.options.length") >= 10)
        page.screenshot(path=str(SHOT_DIR / "00-live-before.png"), full_page=True)

        page.select_option("#panel-overview .live-source", FAST_SOURCE)
        page.select_option("#panel-overview .live-enrich", "0")
        page.click("#body-live button.btn--primary")

        wait_until(lambda: page.locator("#body-live .stage-card").count() >= 1,
                   timeout_s=90, what="第一张步骤卡片")
        first = page.locator("#body-live .stage-card").count()
        wait_until(lambda: page.locator("#body-live .stage-card").count() > first,
                   timeout_s=90, what="后续步骤卡片")
        check("步骤卡片是逐步长出，不是一次性输出",
              page.locator("#body-live .stage-card").count() > first,
              f"{first} -> {page.locator('#body-live .stage-card').count()}")

        wait_until(lambda: page.eval_on_selector(
            "#body-live button.btn--danger", "e => e.disabled"),
            timeout_s=300, what="运行结束")
        page.wait_for_timeout(400)

        check("四个阶段都出现", page.locator("#body-live .phase-sep").count() >= 4,
              str(page.eval_on_selector_all(
                  "#body-live .phase-sep", "els => els.map(e => e.textContent.trim())")))
        check("没有卡在“进行中”的残留卡片",
              page.locator("#body-live .stage-card--running").count() == 0)
        check("耗时显示为后端实测总耗时",
              "共耗时" in page.inner_text("#body-live .live-progress .elapsed"),
              page.inner_text("#body-live .live-progress .elapsed"))
        stats = page.eval_on_selector_all(
            "#body-live .live-progress .live-stat", "els => els.map(e => e.textContent)")
        check("实时计数不为零", not all(s.rstrip("0123456789").endswith(("步骤", "产出内容", "外部取回")) and s.endswith("0") for s in stats),
              str(stats))
        page.screenshot(path=str(SHOT_DIR / "02-live.png"), full_page=True)

        check("编排页可从导航回到任务台", page.is_visible("#tab-overview"))
        page.click("#tab-overview")
        page.wait_for_timeout(250)
        check("返回后确实回到了任务台", page.is_visible("#panel-overview"))

        print("\n3b. 类型筛选能把论文筛出来")
        page.click("#tab-knowledge")
        page.click('details[data-module="events"] > summary')
        wait_until(lambda: page.eval_on_selector(
            "#events-category", "e => e.options.length") > 1,
            timeout_s=20, what="类型下拉框")
        options = page.eval_on_selector(
            "#events-category", "e => Array.from(e.options).map(o => o.value)")
        check("类型下拉里有「论文」", "论文" in options, str(options))
        page.select_option("#events-category", "论文")
        page.click("#body-events button[type=submit]")
        # Wait for the list to stop changing, not merely to start: reading it as
        # soon as one row appeared caught a half-updated list and reported a
        # failure that a re-run could not reproduce.  Two identical reads is a
        # stable signal that does not depend on any label's wording.
        previous = -1
        for _ in range(100):
            current = page.locator("#body-events .event-item").count()
            if current >= 1 and current == previous:
                break
            previous = current
            page.wait_for_timeout(200)
        rows = page.locator("#body-events .event-item").count()
        labels = page.eval_on_selector_all(
            "#body-events .event-item", "els => els.map(e => e.textContent)")
        check("筛出来的每一条都标着「论文」",
              rows >= 1 and all("论文" in text for text in labels), f"{rows} 条")
        check("全站不再出现笼统的「知识」分类",
              "知识" not in page.inner_text("#body-events"))
        page.screenshot(path=str(SHOT_DIR / "03-papers.png"), full_page=True)

        print("\n4. 提问（本地流式）")
        page.click("#tab-overview")
        page.click('details[data-module="chat"] > summary')
        page.wait_for_timeout(200)

        print("\n4a. 推荐问法（取自固定评测集）")
        suggestions = page.evaluate("() => fetch('/api/qa/suggestions').then(r => r.json())")
        wait_until(lambda: page.locator("#body-chat .suggestion-chip").count() >= 1,
                   timeout_s=20, what="推荐问法")
        chips = page.locator("#body-chat .suggestion-chip").count()
        expected_chips = sum(len((group.get("questions") or [])[:4])
                             for group in (suggestions.get("items") or []))
        check("推荐问法按钮与接口同源", chips == expected_chips,
              f"页面 {chips} 个 / 接口可渲染 {expected_chips} 个")
        check("推荐问法注明取自固定评测集",
              "固定评测集" in page.inner_text("#body-chat"))
        suggestion_card = page.locator("#body-chat .chat-log > .card").filter(
            has_text="推荐问法").first
        suggestion_card.screenshot(path=str(DOC_SHOT_DIR / "13-question-suggestions.png"))

        page.fill("#body-chat textarea", QUESTION)
        page.click("#body-chat button.btn--primary")
        wait_until(lambda: page.locator("#body-chat .stream-line").count() >= 1,
                   timeout_s=60, what="第一段结论")
        check("结论按段输出", page.locator("#body-chat .stream-line").count() >= 1,
              f"{page.locator('#body-chat .stream-line').count()} 段")
        check("回答里同时给出执行轨迹",
              page.locator("#body-chat .stage-card").count() >= 1,
              f"{page.locator('#body-chat .stage-card').count()} 步")
        wait_until(lambda: page.eval_on_selector(
            "#body-chat button.btn--danger", "e => e.disabled"),
            timeout_s=120, what="回答结束")
        page.wait_for_timeout(300)
        sections = page.eval_on_selector_all(
            "#body-chat .block-title", "els => els.map(e => e.textContent.trim())")
        for expected in ("执行轨迹", "引用", "证据", "局限"):
            check(f"回答分区含“{expected}”", any(expected in s for s in sections))
        check("Agent context block disclosure is visible",
              any(title.startswith("Agent ") for title in sections))
        check("Agent context snapshot shows thread and four focus groups",
              page.locator("#body-chat .context-snapshot-head").count() == 1 and
              page.locator("#body-chat .context-focus").count() == 4)
        check("Finished answer updates the focus event",
              page.locator("#body-chat .context-focus").first.locator(".chip").count() >= 1)
        if page.locator("#body-chat .citation-drilldown").count():
            page.locator("#body-chat .citation-drilldown").first.locator("summary").click()
            citation = page.locator("#body-chat .citation-drilldown").first
            check("Citation drills down to a chunk or an explicit source-level limitation",
                  citation.locator(".rag-chunk").count() > 0 or citation.locator(".alert--warn").count() > 0)

        print("\n4b. 技术详情：本轮计划与工具调用")
        detail = page.locator("#body-chat details").filter(has_text="技术详情").first
        check("技术详情折叠区已渲染", detail.count() > 0)
        if detail.count():
            detail.locator("summary").first.click()
            page.wait_for_timeout(250)
            detail_text = detail.inner_text()
            check("技术详情列出工具调用与耗时",
                  "工具" in detail_text and "耗时" in detail_text)
            check("技术详情列出本轮计划",
                  "计划" in detail_text)
            detail.screenshot(path=str(DOC_SHOT_DIR / "14-technical-detail.png"))

        page.fill("#body-chat textarea", "\u524d\u8005\u5f71\u54cd\u54ea\u4e2a\u8d44\u4ea7\uff1f")
        page.click("#body-chat button.btn--primary")
        wait_until(lambda: page.locator("#body-chat .context-confirmation .alert--warn").count() == 1,
                   timeout_s=10, what="context ambiguity confirmation")
        check("Ambiguous reference pauses for confirmation",
              page.locator("#body-chat .context-confirm-actions").count() == 1)
        page.locator("#body-chat .context-confirm-actions .btn--ghost").click()
        page.screenshot(path=str(SHOT_DIR / "03-chat.png"), full_page=True)

        print("\n5. 提问（大模型转述，仅当已配置密钥）")
        toggle = page.locator("#body-chat input[type=checkbox]")
        if toggle.is_disabled():
            print("  [skip] 未配置模型密钥，开关不可用 —— 这正是预期行为")
        else:
            toggle.check()
            page.fill("#body-chat textarea", "CVE-2026-7482 影响哪些资产？")
            page.click("#body-chat button.btn--primary")
            if page.locator("#body-chat .context-confirm-actions").count():
                page.locator("#body-chat .context-confirm-actions .btn--primary").click()
            try:
                wait_until(lambda: page.locator("#body-chat .stream-block--model").count() > 0,
                           timeout_s=90, what="模型转述块")
                wait_until(lambda: page.eval_on_selector(
                    "#body-chat button.btn--danger", "e => e.disabled"),
                    timeout_s=120, what="模型输出结束")
                page.wait_for_timeout(300)
                lines = page.locator("#body-chat .stream-block--model .stream-line").count()
                check("模型逐字输出合并为一个段落（而非每字一段）", 1 <= lines <= 2,
                      f"{lines} 段")
                check("模型内容标注为“仅供阅读”",
                      "仅供阅读" in page.inner_text("#body-chat .stream-block--model"))
            except TimeoutError as exc:
                check("模型转述块出现", False, str(exc))
            page.screenshot(path=str(SHOT_DIR / "04-model.png"), full_page=True)

        browser.close()

    print("\n6. 控制台与网络")
    check("无 JS 报错", not console_errors, str(console_errors[:3]))
    check("无失败请求", not failed_requests, str(failed_requests[:3]))
    print(f"\n截图目录：{SHOT_DIR}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8020", help="服务地址")
    args = parser.parse_args()
    code = run(args.base)
    print("\n结果：" + ("全部通过" if code == 0 else f"{len(failures)} 项未通过 -> {failures}"))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
