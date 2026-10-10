"""Screenshot the "处置闭环" card from the real UI against one database.

Serves the app with ``uvicorn`` on a loopback port, opens the "赛题指标" tab in a
real browser through Playwright, waits for the disposition card to render, and
records both a card crop and a full-page capture plus the rendered field values.

Requires the project runtime (``.venv``) with ``playwright`` installed and a
Chromium-compatible browser; pass ``--channel msedge`` to use an existing Edge
installation instead of downloading one.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--label", required=True, help="before / after, used in file names")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--channel", default="msedge")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    if not (data_dir / "intel.sqlite").is_file():
        raise SystemExit(f"no intel.sqlite under {data_dir}")
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT))
    import uvicorn

    from app import config
    from app.api import app as api_app

    config.DATA_DIR = data_dir
    config.SNAPSHOT_DIR = data_dir / "snapshots"
    config.DB_PATH = data_dir / "intel.sqlite"
    config.ensure_dirs()

    port = args.port or _free_port()
    server = uvicorn.Server(uvicorn.Config(api_app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import urllib.error
    import urllib.request

    base = f"http://127.0.0.1:{port}"
    health: dict[str, Any] = {}
    for _ in range(60):
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=2) as response:
                health = json.load(response)
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    if not health:
        raise SystemExit("application did not become healthy")

    from playwright.sync_api import sync_playwright

    card_png = out_dir / f"disposition-card-{args.label}.png"
    page_png = out_dir / f"scorecard-panel-{args.label}.png"
    summary: dict[str, Any] = {
        "label": args.label,
        "captured_at": _utcnow(),
        "url": base + "/",
        "data_dir": str(data_dir),
        "health": health,
    }
    with sync_playwright() as play:
        browser = play.chromium.launch(channel=args.channel, headless=True)
        page = browser.new_page(viewport={"width": 1680, "height": 1200})
        page.goto(base + "/", wait_until="networkidle")
        page.click("#tab-scorecard")
        card = page.locator("article.score-capability", has_text="处置闭环")
        card.wait_for(state="visible", timeout=30000)
        page.wait_for_timeout(500)
        summary["card_text"] = card.inner_text()
        summary["card_facts"] = [
            " ".join(fact.inner_text().split())
            for fact in card.locator(".score-fact").all()
        ]
        summary["card_badge"] = card.locator(".badge").inner_text()
        card.screenshot(path=str(card_png))
        page.screenshot(path=str(page_png))
        # Read the two API payloads from inside the page so the screenshot and
        # the recorded numbers come from the same origin and the same moment.
        summary["api_from_page"] = page.evaluate(
            """async () => {
                const scorecard = await (await fetch('/api/competition/scorecard')).json();
                const metrics = await (await fetch('/api/dispositions/metrics')).json();
                return {scorecard_disposition: scorecard.disposition, metrics};
            }"""
        )
        browser.close()

    summary["page_consistency"] = _consistency(summary)
    summary["screenshots"] = {"card": str(card_png), "panel": str(page_png)}
    (out_dir / f"screenshot-{args.label}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _consistency(summary: dict[str, Any]) -> dict[str, Any]:
    """Compare what the card renders with what the two APIs return."""
    facts = {}
    for entry in summary.get("card_facts") or []:
        parts = entry.split()
        if len(parts) >= 2:
            facts[parts[0]] = parts[1]
    api = summary.get("api_from_page") or {}
    scorecard = api.get("scorecard_disposition") or {}
    metrics = api.get("metrics") or {}
    rate = metrics.get("closure_rate")
    expected = {
        "高优先级总数": str(metrics.get("high_priority_total")),
        "已复测关闭": str(metrics.get("high_priority_closed")),
        "闭环率": (f"{round(rate * 100)}%" if isinstance(rate, (int, float)) else "暂无运行证据"),
    }
    mismatches = [
        {"field": key, "card": facts.get(key), "metrics": value}
        for key, value in expected.items()
        if facts.get(key) != value
    ]
    shared = ("high_priority_total", "high_priority_closed", "high_priority_verified",
              "closure_rate", "verified_rate", "status_breakdown", "findings_total")
    return {
        "card_fields": facts,
        "expected_from_metrics": expected,
        "mismatches": mismatches,
        "metrics_matches_scorecard": all(metrics.get(key) == scorecard.get(key) for key in shared),
        "consistent": not mismatches and all(metrics.get(key) == scorecard.get(key) for key in shared),
    }


if __name__ == "__main__":
    raise SystemExit(main())
