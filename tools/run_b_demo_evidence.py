"""B 任务阶段 F：在隔离副本上跑 5 个演示场景并留存可复现证据。

场景：基础事实问答 / 多轮追问 / 跨文档问答 / 证据不足拒答 / 引用定位与导出。

要求与限制：

* **真实库只读**：先复制 `intel.sqlite` 到临时目录，再把 `INTEL_DATA_DIR` 指过去。
* **不伪造**：每个场景记录真实 `run_id`、耗时、引用 ID 与答案原文；
  失败的场景如实记录为 `failed` 或 `partial`。
* 截图：本环境无法截图，输出中显式标注 `screenshot: not_captured`。

用法::

    python tools/run_b_demo_evidence.py --out artifacts/b_eval/demo_evidence.json
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import agents, config, rag_corpus, storage  # noqa: E402

SOURCE_DATA_DIR = Path(r"D:\ICT\intel-data-b")

SCENARIOS: tuple[dict, ...] = (
    {"scenario_id": "DEMO-01", "name": "基础事实问答",
     "question": "DistillGuard 这篇论文的标题是什么？", "history": []},
    {"scenario_id": "DEMO-02", "name": "多轮追问",
     "question": "它检测什么？",
     "history": [{"role": "user", "content": "DistillGuard 是做什么的？"},
                 {"role": "assistant", "content": "DistillGuard: Malicious NPM Package Detection"}]},
    {"scenario_id": "DEMO-03", "name": "跨文档问答",
     "question": "AUROC 在哪些文档中被讨论？", "history": []},
    {"scenario_id": "DEMO-04", "name": "证据不足拒答",
     "question": "明天的天气怎么样？", "history": []},
    {"scenario_id": "DEMO-05", "name": "引用定位与导出",
     "question": "什么是提示词注入？", "history": []},
)


def main() -> int:
    parser = argparse.ArgumentParser(description="B 任务演示证据")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "demo_evidence.json")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="b_demo_"))
    (workdir / "snapshots").mkdir()
    shutil.copy2(SOURCE_DATA_DIR / "intel.sqlite", workdir / "intel.sqlite")
    config.DATA_DIR = workdir
    config.SNAPSHOT_DIR = workdir / "snapshots"
    config.DB_PATH = workdir / "intel.sqlite"

    environment = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "data_dir_used": str(workdir),
        "source_data_dir": str(SOURCE_DATA_DIR) + " (只读，未写入)",
        "model_mode": config.mode_label(),
        "retrieval_index": "keyword-v1 (app/rag_corpus.KeywordIndex / app/rag.retrieve_chunks)",
        "screenshot": "not_captured（本环境无法截图，仅保留可复现的输入输出与运行 ID）",
    }

    results = []
    for scenario in SCENARIOS:
        started = time.perf_counter()
        status = "ok"
        error = None
        try:
            answer = agents.answer(scenario["question"], history=scenario["history"])
        except Exception as exc:  # noqa: BLE001 - 如实记录失败
            answer, status, error = {}, "failed", f"{type(exc).__name__}: {exc}"
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)

        citations = answer.get("document_citations") or []
        verified = [c for c in citations
                    if rag_corpus.get_chunk(c.get("chunk_id") or "") is not None]
        refused = not (answer.get("related_event_ids") or citations)
        results.append({
            "scenario_id": scenario["scenario_id"],
            "name": scenario["name"],
            "status": status,
            "error": error,
            "run_id": answer.get("run_id"),
            "asked_at": storage.utcnow(),
            "question": scenario["question"],
            "history_turns": len(scenario["history"]),
            "answer": (answer.get("answer") or "")[:600],
            "refused": refused,
            "event_ids": answer.get("related_event_ids") or [],
            "citation_count": len(citations),
            "citation_ids_retrievable": len(verified),
            "citations": [{"chunk_id": c.get("chunk_id"), "document_id": c.get("document_id"),
                           "char_start": c.get("char_start"), "char_end": c.get("char_end")}
                          for c in citations],
            "duration_ms": elapsed_ms,
            "mode": answer.get("mode"),
        })
        print("[%s] %-10s run_id=%s citations=%d refused=%s %.0fms" % (
            scenario["scenario_id"], scenario["name"], answer.get("run_id"),
            len(citations), refused, elapsed_ms))

    export = storage.export_snapshot()
    payload = {
        "schema_version": "b-demo-evidence-1.0",
        "generated_at": storage.utcnow(),
        "environment": environment,
        "results": results,
        "export_check": {
            "events": export["counts"].get("events"),
            "assets": export["counts"].get("assets"),
            "assessments": export["counts"].get("assessments"),
            "note": "导出接口在副本上执行，用于验证引用可随快照导出。",
        },
        "limitations": [
            "跨文档综合能力尚未实现：DEMO-03 只验证检索层能返回多篇文档，不代表推理成功。",
            "多轮追问在 RAG 路径不继承会话上下文，DEMO-02 如实记录其真实表现。",
            "本环境无法截图，未生成任何页面截图；所有证据均为可复现的文本与 ID。",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
