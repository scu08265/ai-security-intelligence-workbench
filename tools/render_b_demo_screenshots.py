"""B 任务：把**真实运行记录**渲染成演示截图（不依赖 Playwright）。

背景：本项目 venv 未安装 playwright，`tools/capture_operations_screenshots.py` 无法直接复用
（它面向 A 负责人的运维页面，且强依赖 playwright）。本工具改用**已安装的 Microsoft Edge
headless 截图**能力，把 `artifacts/b_eval/demo_evidence.json` 中每条真实运行记录
（问题、完整回答、run_id、引用 chunk_id/字符区间、耗时、模式）渲染成页面并截图。

诚实边界（写进每张图里）：

* 截图内容是**真实运行结果的渲染页**，不是浏览器里逐字交互的会话录屏；
* 不伪造任何 run_id、引用 ID 或耗时——全部来自结果文件；
* 无引用的场景如实标注"（无引用）"。

用法::

    python tools/render_b_demo_screenshots.py \
        --results artifacts/b_eval/demo_evidence.json \
        --outdir docs/screenshots \
        --edge "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
DEFAULT_RESULTS = ROOT / "artifacts" / "b_eval" / "demo_evidence.json"
SLUGS = {"DEMO-01": "basic", "DEMO-02": "multiturn", "DEMO-03": "crossdoc",
         "DEMO-04": "refusal", "DEMO-05": "citation"}

PAGE = """<!doctype html><meta charset="utf-8"><title>{title}</title><style>
body{{margin:0;background:#0d1117;color:#c9d1d9;font-family:Consolas,'Microsoft YaHei',monospace}}
main{{padding:26px}}h1{{color:#f0f6fc;font-family:Arial;font-size:22px;margin:0 0 6px}}
h2{{color:#58a6ff;font-family:Arial;font-size:16px;margin:22px 0 8px}}
.meta{{font-size:13px;color:#8b949e;margin:2px 0}}
.kv{{font-size:13px;line-height:1.9}}.kv b{{color:#c9d1d9}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border:1px solid #30363d;padding:6px 8px;text-align:left}}
pre{{background:#161b22;border:1px solid #30363d;padding:16px;white-space:pre-wrap;
line-height:1.5;font-size:13px}}
</style><main>
<h1>{scenario_id} · {name}</h1>
<p class="meta">B 任务：现场演示证据渲染页（内容来自真实运行结果 {source}，非模拟数据）</p>
<p class="kv"><b>run_id</b>：{run_id}　<b>问题</b>：{question}<br>
<b>状态</b>：{status}　<b>拒答</b>：{refused}　<b>耗时</b>：{duration} ms　
<b>模式</b>：{mode}　<b>历史轮次</b>：{history}</p>
<h2>系统回答（截取前 {limit} 字；完整文本见结果文件）</h2>
<pre>{answer}</pre>
<h2>引用证据（{citation_count} 条，可追溯 {retrievable}/{citation_count}）</h2>
<table><tr><th>chunk_id</th><th>document_id</th><th>字符区间</th></tr>{rows}</table>
</main>"""


def render_page(result: dict, source: Path, limit: int = 1400) -> str:
    citations = result.get("citations") or []
    rows = "".join(
        f"<tr><td>{html.escape(str(c.get('chunk_id')))}</td>"
        f"<td>{html.escape(str(c.get('document_id')))}</td>"
        f"<td>{c.get('char_start')}–{c.get('char_end')}</td></tr>" for c in citations
    ) or "<tr><td colspan=3>（无引用）</td></tr>"
    return PAGE.format(
        title=f"{result.get('scenario_id')} {result.get('name')}",
        scenario_id=html.escape(str(result.get("scenario_id"))),
        name=html.escape(str(result.get("name"))),
        source=html.escape(str(source.relative_to(ROOT))),
        run_id=html.escape(str(result.get("run_id"))),
        question=html.escape(str(result.get("question"))),
        status=result.get("status"), refused=result.get("refused"),
        duration=result.get("duration_ms"), mode=html.escape(str(result.get("mode"))),
        history=result.get("history_turns"),
        limit=limit, answer=html.escape((result.get("answer") or "")[:limit]),
        citation_count=result.get("citation_count"),
        retrievable=result.get("citation_ids_retrievable"),
        rows=rows,
    )


def shoot(edge: Path, url: str, out: Path, size: str = "1600,1000") -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="edge_profile_") as profile:
        proc = subprocess.run(
            [str(edge), "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={profile}", f"--window-size={size}",
             "--virtual-time-budget=8000", f"--screenshot={out}", url],
            capture_output=True)
    ok = out.is_file() and out.stat().st_size > 5000
    if not ok:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
        print(f"[warn] 截图失败：{out}\n{stderr[:300]}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--outdir", type=Path, default=ROOT / "docs" / "screenshots")
    parser.add_argument("--edge", type=Path, default=DEFAULT_EDGE)
    parser.add_argument("--base", default=None,
                        help="可选：同时抓一张应用首页截图（如 http://127.0.0.1:8010/）")
    args = parser.parse_args()

    if not args.edge.is_file():
        print("找不到 Edge：", args.edge)
        return 2
    payload = json.loads(args.results.read_text(encoding="utf-8"))
    manifest = {"schema_version": "b-demo-screenshots-1.0",
                "source_results": str(args.results.relative_to(ROOT)),
                "note": "截图为真实运行结果的渲染页；未伪造 run_id/引用/耗时。",
                "shots": []}

    if args.base:
        target = args.outdir / "b-qa-00-workbench.png"
        if shoot(args.edge, args.base, target, size="1600,1100"):
            manifest["shots"].append({"kind": "app_ui", "scenario": "工作台首页",
                                      "url": args.base, "file": str(target.relative_to(ROOT))})

    with tempfile.TemporaryDirectory(prefix="b_qa_pages_") as tmp:
        tmpdir = Path(tmp)
        for result in payload["results"]:
            scenario = str(result.get("scenario_id"))
            slug = SLUGS.get(scenario, scenario.lower())
            page = tmpdir / f"{scenario}-{slug}.html"
            page.write_text(render_page(result, args.results), encoding="utf-8")
            target = args.outdir / f"b-qa-{scenario.split('-')[-1]}-{slug}.png"
            if shoot(args.edge, page.as_uri(), target):
                manifest["shots"].append({
                    "kind": "rendered_run_evidence", "scenario": scenario,
                    "name": result.get("name"), "run_id": result.get("run_id"),
                    "question": result.get("question"),
                    "citation_count": result.get("citation_count"),
                    "citations": result.get("citations") or [],
                    "duration_ms": result.get("duration_ms"),
                    "file": str(target.relative_to(ROOT)),
                })

    manifest_path = ROOT / "artifacts" / "b_eval" / "b_demo_screenshots.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("截图数量:", len(manifest["shots"]))
    for shot in manifest["shots"]:
        print("  -", shot["file"], "|", shot.get("run_id") or shot.get("url"))
    print("清单:", manifest_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
