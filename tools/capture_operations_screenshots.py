"""Capture A-owner operational screenshots using the installed Microsoft Edge."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def _screenshot(page, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    print(f"[ok] {path}")


def _code_page(page, title: str, content: str) -> None:
    page.set_content(
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "body{margin:0;background:#0d1117;color:#c9d1d9;font-family:Consolas,monospace}"
        "main{padding:28px}h1{color:#f0f6fc;font-family:Arial,sans-serif;font-size:24px}"
        "pre{padding:20px;border:1px solid #30363d;background:#161b22;white-space:pre-wrap;"
        "line-height:1.55;font-size:14px}</style></head><body><main>"
        f"<h1>{html.escape(title)}</h1><pre>{html.escape(content)}</pre>"
        "</main></body></html>",
        wait_until="load",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8010")
    parser.add_argument("--edge", default=str(DEFAULT_EDGE))
    parser.add_argument("--output", default="docs/screenshots")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.edge, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})

        page.goto(args.base, wait_until="networkidle")
        page.get_by_role("tab", name="赛题指标").click()
        page.wait_for_timeout(1000)
        _screenshot(page, output / "03-scorecard.png")

        page.goto(f"{args.base}/api/health", wait_until="networkidle")
        _screenshot(page, output / "01-health.png")

        report = json.loads((ROOT / "reports" / "reliability-report.json").read_text(encoding="utf-8"))
        source_lines = "\n".join(
            f"{item['id']:<12} {item['current_status']:<10} "
            f"{'未知' if item['success_rate'] is None else f'{item['success_rate'] * 100:.1f}%':>7}  "
            f"P50={item['duration_ms_p50'] if item['duration_ms_p50'] is not None else '未知'}ms  "
            f"P95={item['duration_ms_p95'] if item['duration_ms_p95'] is not None else '未知'}ms"
            for item in report["sources"]["items"]
        )
        reliability_summary = (
            f"连续定时运行：{report['continuous_runs']['consecutive_executed_days']} / "
            f"{report['continuous_runs']['target_days']} 天\n"
            f"<=6h：{report['timeliness']['within_6h']['count']}  "
            f"<=12h：{report['timeliness']['within_12h']['count']}  "
            f"<=24h：{report['timeliness']['within_24h']['count']}\n"
            f"可计算时延样本：{report['timeliness']['computable_samples']}  "
            f"未知样本：{report['timeliness']['unknown_samples']}  "
            f"历史回填排除：{report['timeliness']['baseline_excluded_samples']}\n\n"
            "来源健康：\n" + source_lines
        )
        _code_page(page, "来源可靠性与监测时效", reliability_summary)
        _screenshot(page, output / "02-reliability.png")

        summary = (
            f"连续运行：{report['continuous_runs']['consecutive_executed_days']} / "
            f"{report['continuous_runs']['target_days']} 天\n"
            f"可计算时延样本：{report['timeliness']['computable_samples']}\n"
            f"未知时延样本：{report['timeliness']['unknown_samples']}\n"
            f"历史回填排除：{report['timeliness']['baseline_excluded_samples']}\n"
            f"来源记录数：{report['sources']['source_count']}\n\n"
            "reports/\n"
            "  7-day-continuous-run-report.md\n"
            "  source-health.csv\n"
            "  source-health.json\n"
            "  latency-summary.json\n"
            "  latency-chart.svg\n"
            "  source-success-chart.svg\n"
        )
        _code_page(page, "A 项报告与图表输出", summary)
        _screenshot(page, output / "04-reports.png")

        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        _code_page(page, "CI 与 Compose 配置", ci + "\n\n# docker-compose.yml\n" + compose)
        _screenshot(page, output / "05-ci-workflow.png")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
