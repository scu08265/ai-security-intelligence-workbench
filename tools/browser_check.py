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


def run(base: str) -> int:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
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
        check("首页优先展示风险处置指标",
              "立即处置" in page.inner_text("#panel-overview"))

        print("\n2. 三入口结构与赛题指标")
        check("导航只保留 3 个任务入口", page.locator(".tablist .tab").count() == 3,
              f"{page.locator('.tablist .tab').count()} 项")
        check("三个入口名称清晰",
              all(label in page.inner_text(".rail") for label in ("任务工作台", "知识图谱", "赛题指标")))
        page.click("#mode-link")
        wait_until(lambda: page.locator("#body-scorecard .score-capability").count() == 5,
                   timeout_s=20, what="五类赛题指标")
        check("五类赛题能力均直接展示", page.locator("#body-scorecard .score-capability").count() == 5)
        check("统一计分接口兼容状态已说明", bool(page.inner_text("#body-scorecard .scorecard-status").strip()))
        page.screenshot(path=str(SHOT_DIR / "01-scorecard.png"), full_page=True)

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

        print("\n2c. 标准资产仿真")
        page.click("#tab-overview")
        page.click("#body-simulation button.btn--ghost")
        wait_until(lambda: page.locator("#body-simulation .simulation-provenance").count() == 1,
                   timeout_s=15, what="标准样例预览")
        check("合成样例标记清晰", "合成仿真数据" in page.inner_text("#body-simulation"))
        check("假设确认前运行按钮禁用",
              page.locator("#body-simulation button.btn--primary").is_disabled())
        page.check("#body-simulation .simulation-confirm input")
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
        wait_until(lambda: page.locator("#body-events .event-item").count() >= 1,
                   timeout_s=20, what="论文列表")
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
