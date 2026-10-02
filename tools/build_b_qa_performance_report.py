"""B 任务三：把多个问答评测批次汇总成**性能统计**（批次之间严格分开）。

设计原则：

* **不混合批次**。每个批次独立计算 mean / P50 / P95 / 超时 / 失败率；
  只有在题号集合完全一致时才做逐题对照，且对照只展示差异，不做合并统计。
* **只读既有结果文件**，不调用问答服务、不写数据库。
* 统计口径写明：单题端到端耗时（含本地检索），超时阈值取运行文件里的定义（默认 5000 ms）。

用法::

    python tools/build_b_qa_performance_report.py \
        --run A=artifacts/b_eval/formal_qa_results.json \
        --run B=artifacts/b_eval/formal_qa_performance_run2.json \
        --out artifacts/b_eval/qa_performance_stats.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _percentile(values: list[float], fraction: float) -> float | None:
    """最近秩分位数（与 tools/run_b_qa_eval.py 一致，不做插值）。"""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return round(ordered[index], 1)


def load_run(label: str, path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records") or []
    latencies = [float(r["latency_ms"]) for r in records
                 if r.get("latency_ms") is not None]
    return {
        "label": label,
        "source": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "cases": len(records),
        "latency_ms": {
            "samples": len(latencies),
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
            "p50": _percentile(latencies, 0.5),
            "p95": _percentile(latencies, 0.95),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "scope": "单题端到端耗时（含本地检索），同一批次内统计；"
                     "最近秩分位数、不做插值；超时阈值 5000 ms",
        },
        "outcomes": {
            "answered": sum(1 for r in records if not r.get("refused") and not r.get("error")),
            "refused": sum(1 for r in records if r.get("refused")),
            "errors": sum(1 for r in records if r.get("error")),
            "timeouts": sum(1 for r in records if r.get("timeout")),
            "failures": sum(1 for r in records if r.get("error") or r.get("timeout")),
        },
        "quality": {
            "document_hit": (payload.get("totals") or {}).get("document_hit"),
            "term_hit": (payload.get("totals") or {}).get("term_hit"),
            "refusal_accuracy": (payload.get("totals") or {}).get("refusal_accuracy"),
            "citations": (payload.get("totals") or {}).get("citations"),
            "answer_semantic_accuracy": (payload.get("totals") or {}).get(
                "answer_semantic_accuracy"),
        },
        "per_category": (payload.get("by_category") or {}),
        "_records": records,
    }


def compare(batches: list[dict]) -> dict:
    ids_by_batch = [{r["question_id"] for r in b["_records"]} for b in batches]
    same_ids = all(ids == ids_by_batch[0] for ids in ids_by_batch)
    comparison = {
        "same_question_ids": same_ids,
        "question_count": len(ids_by_batch[0]) if ids_by_batch else 0,
        "rule": "只有题号集合完全一致时才逐题对照；不同批次的分位数不得合并计算",
        "per_question": [],
        "outcome_changes": [],
    }
    if not same_ids or len(batches) < 2:
        return comparison
    base, other = batches[0], batches[-1]
    index_other = {r["question_id"]: r for r in other["_records"]}
    for record in base["_records"]:
        peer = index_other[record["question_id"]]
        delta = round(float(peer["latency_ms"]) - float(record["latency_ms"]), 1)
        comparison["per_question"].append({
            "question_id": record["question_id"],
            "category": record["category"],
            f"latency_ms_{base['label']}": record["latency_ms"],
            f"latency_ms_{other['label']}": peer["latency_ms"],
            "delta_ms": delta,
            "refused_same": bool(record.get("refused")) == bool(peer.get("refused")),
            "error_same": (record.get("error") or None) == (peer.get("error") or None),
        })
        if bool(record.get("refused")) != bool(peer.get("refused")):
            comparison["outcome_changes"].append({
                "question_id": record["question_id"],
                f"refused_{base['label']}": bool(record.get("refused")),
                f"refused_{other['label']}": bool(peer.get("refused")),
            })
    deltas = [item["delta_ms"] for item in comparison["per_question"]]
    comparison["delta_ms"] = {
        "mean": round(statistics.fmean(deltas), 1) if deltas else None,
        "p50": _percentile(deltas, 0.5),
        "min": min(deltas) if deltas else None,
        "max": max(deltas) if deltas else None,
        "scope": f"{other['label']} − {base['label']}（同一题逐题差值）",
    }
    return comparison


def build(runs: list[tuple[str, Path]]) -> dict:
    batches = [load_run(label, path) for label, path in runs]
    comparison = compare(batches)
    failures = [item for item in comparison["per_question"] if not item["refused_same"]]
    for batch in batches:
        batch.pop("_records", None)
    return {
        "schema_version": "b-qa-performance-1.0",
        "batches": batches,
        "comparison": comparison,
        "notes": {
            "no_mixing": "每个批次的分位数独立计算，绝不合并；逐题对照只展示差异",
            "env": "本机 .venv、本地 RAG（临时数据库副本）、串行执行、无网络问答服务",
            "scope": "计时覆盖单题端到端（检索+作答），不含进程启动",
            "quality_caveat": "文档/词命中为机械指标；语义答案准确率在人工金标准前不可计算",
        },
    }


def _print(stats: dict) -> None:
    for batch in stats["batches"]:
        latency = batch["latency_ms"]
        outcomes = batch["outcomes"]
        print(f"[{batch['label']}] {batch['source']}  n={batch['cases']}  "
              f"mean={latency['mean']}ms  P50={latency['p50']}ms  P95={latency['p95']}ms  "
              f"min={latency['min']}ms  max={latency['max']}ms")
        print(f"        作答={outcomes['answered']} 拒答={outcomes['refused']} "
              f"异常={outcomes['errors']} 超时={outcomes['timeouts']} 失败={outcomes['failures']}")
    comparison = stats["comparison"]
    print("题号集合一致:", comparison["same_question_ids"],
          "| 题数:", comparison["question_count"])
    if comparison.get("delta_ms"):
        print("逐题差值:", comparison["delta_ms"])
        print("作答/拒答发生变化的题:", comparison["outcome_changes"] or "无")


def main() -> int:
    parser = argparse.ArgumentParser(description="B 任务问答性能统计（批次严格分开）")
    parser.add_argument("--run", action="append", default=[],
                        help="形如 LABEL=path，可重复传入")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    runs = []
    for item in args.run:
        label, _, raw = item.partition("=")
        path = Path(raw or label)
        if not path.is_file():
            print("找不到运行文件:", path)
            return 2
        runs.append((label if raw else path.stem, path))
    if not runs:
        print("至少需要一个 --run LABEL=path")
        return 2
    stats = build(runs)
    _print(stats)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
        print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
