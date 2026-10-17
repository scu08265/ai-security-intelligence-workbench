"""Refresh the dated snapshot in METRICS_BASELINE.md and the report's numbers.

The snapshot is a moving target: the collection task adds events every hour, so
any hand-written figure goes stale within a day.  Rather than have the report
drift from the baseline -- or hand-edit two places and hope they agree -- this
rewrites the marked block from live demo-machine readings and writes the same
readings to ``docs/report/metrics_snapshot.json``, which the report generator
consumes.  One source, two consumers.

    python tools/refresh_metrics_snapshot.py            # show what would change
    python tools/refresh_metrics_snapshot.py --write    # rewrite baseline + json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import competition_scorecard as cs, config, reliability, storage  # noqa: E402

BASELINE = ROOT / "docs" / "METRICS_BASELINE.md"
SNAPSHOT_JSON = ROOT / "docs" / "report" / "metrics_snapshot.json"
START = "<!-- snapshot:start"
END = "<!-- snapshot:end -->"
COUNTED_TABLES = (
    "runs", "events", "event_aliases", "assets", "assessments",
    "assessment_dispositions", "rag_documents", "rag_chunks", "duplicate_candidates",
)

# Which source categories count as vulnerability reporting for the competition's
# timeliness question.  Taken from the registry rather than invented here, so the
# report cannot end up with its own definition of "vulnerability source".
CLASS_OF_CATEGORY = {
    "cve_database": "vulnerability",
    "ecosystem_advisory": "vulnerability",
    "community_advisory": "vulnerability",
    "exploitation_intel": "vulnerability",
    "vendor_advisory": "vulnerability",
    "security_blog": "vulnerability",
    "academic_paper": "academic",
    "policy_regulation": "policy",
    "technical_standard": "policy",
    "risk_framework": "policy",
    "threat_framework": "policy",
}
CLASS_LABEL = {
    "vulnerability": "漏洞类（赛题口径）",
    "academic": "学术类（不计入赛题分母）",
    "policy": "政策类（不计入赛题分母）",
}


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def latency_breakdown(timeliness: dict) -> dict:
    """Split the post-monitoring latency samples by source class.

    The competition asks for vulnerability information specifically, so the
    report needs both the mixed figure and the split; computing the split here
    keeps the two from being edited independently, which is how the report once
    ended up stating 267 samples in one table and 296 in another.
    """
    from app import sources as registry

    buckets: dict[str, list[float]] = {}
    per_source: dict[str, list[float]] = {}
    for record in timeliness.get("records") or []:
        if not record.get("valid"):
            continue
        source_id = str(record.get("source_id") or "unknown")
        hours = float(record.get("latency_seconds") or 0) / 3600.0
        spec = registry.get(source_id)
        klass = CLASS_OF_CATEGORY.get(getattr(spec, "category", ""), "other")
        buckets.setdefault(klass, []).append(hours)
        per_source.setdefault(source_id, []).append(hours)

    def summarize(values: list[float]) -> dict:
        return {
            "n": len(values),
            "p50_hours": round(_percentile(values, 0.5), 2),
            "max_hours": round(max(values), 1),
            "within_6h": sum(1 for value in values if value <= 6),
            "within_24h": sum(1 for value in values if value <= 24),
        }

    return {
        "mixed": summarize([item for values in buckets.values() for item in values]),
        "classes": [
            {"key": key, "label": CLASS_LABEL.get(key, "其他"), **summarize(buckets[key])}
            for key in ("vulnerability", "academic", "policy", "other") if buckets.get(key)
        ],
        "per_source": [
            {"source_id": source_id,
             "class": CLASS_OF_CATEGORY.get(getattr(registry.get(source_id), "category", ""), "other"),
             **summarize(values)}
            for source_id, values in sorted(per_source.items(), key=lambda item: -len(item[1]))
        ],
    }


def read_live() -> dict:
    db_path = config.DB_PATH
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in COUNTED_TABLES
        }

    card = cs.scorecard()
    monitoring = card["monitoring_7d"]
    events, _ = storage.list_events(limit=None)
    started = cs._monitoring_metrics()["monitoring_started_at"]["value"]
    timeliness = reliability.timeliness_stats(events, monitoring_started_at=reliability._parse(started))
    continuous = reliability.continuous_run_evidence(7)
    relation = card["b_evaluation"]["active_relation"]
    disposition = card["disposition"]

    def value(block, key):
        item = block.get(key)
        return item.get("value") if isinstance(item, dict) else item

    return {
        "snapshot_date": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d"),
        "snapshot_time_local": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "database": {
            "path": "data/intel.sqlite",
            "size_bytes": db_path.stat().st_size,
            "sha256": digest,
            "counts": counts,
        },
        "scorecard": {
            "cumulative_actual_run_days": value(monitoring, "cumulative_actual_run_days"),
            "cumulative_scheduled_run_days": value(monitoring, "cumulative_scheduled_run_days"),
            "scheduled_run_days_7d": value(monitoring, "scheduled_run_days"),
            "continuous_executed_days": value(monitoring, "continuous_executed_days"),
            "continuous_target_met": continuous["target_met"],
            "first_collection_date": value(monitoring, "cumulative_first_collection_date"),
            "events_loaded": card["corpus"]["events_loaded"],
            "events_total": card["corpus"]["events_total"],
            "truncated": card["corpus"]["truncated"],
            "within_6h_rate": value(monitoring, "within_6h_rate"),
            "within_12h_rate": value(monitoring, "within_12h_rate"),
            "within_24h_rate": value(monitoring, "within_24h_rate"),
            "effective_denominator": timeliness.get("effective_denominator"),
            "latency_p50_hours": round((timeliness.get("latency_seconds_p50") or 0) / 3600, 2),
            "enrichment_sample": card["enrichment"]["event_sample_size"],
        },
        "disposition": {
            "high_priority_total": disposition["high_priority_total"],
            "high_priority_closed": disposition["high_priority_closed"],
            # ``high_priority_closed`` counts verified *and* accepted; the two
            # must stay separable or "accepted risk" reads as "repaired".
            "high_priority_verified": disposition.get("high_priority_verified"),
            "high_priority_registered": disposition.get("high_priority_registered"),
            "high_priority_unopened": disposition.get("high_priority_unopened"),
            "closure_rate": disposition["closure_rate"],
            "verified_rate": disposition["verified_rate"],
            "registered_closure_rate": disposition.get("registered_closure_rate"),
            "mean_time_to_close_hours": disposition.get("mean_time_to_close_hours"),
            "status_breakdown": disposition.get("status_breakdown"),
            "findings_total": disposition["findings_total"],
        },
        "relation": {
            "precision": relation.get("precision"),
            "recall": relation.get("recall"),
            "f1": relation.get("f1"),
            "tp": relation.get("tp"),
            "fp": relation.get("fp"),
            "fn": relation.get("fn"),
        },
        "latency_by_class": latency_breakdown(timeliness),
        "enrichment": card["enrichment"],
    }


def render_block(snapshot: dict) -> str:
    db = snapshot["database"]
    counts = db["counts"]
    card = snapshot["scorecard"]
    disp = snapshot["disposition"]
    accepted = (disp.get("status_breakdown") or {}).get("accepted")
    relation = snapshot["relation"]
    return "\n".join([
        f"{START} 由 tools/refresh_metrics_snapshot.py 重写，不要手工改这一段 -->",
        "",
        f"快照时间 **{snapshot['snapshot_date']}**（本机时区 {snapshot['snapshot_time_local']}），"
        "取自演示机本仓库 `data/intel.sqlite`。采集计划任务每小时运行，数据库持续增长，"
        "因此这份快照会过期——刷新方式是重跑 "
        "`python tools/refresh_metrics_snapshot.py --write`，报告里的数字来自同一个快照文件，"
        "所以两边不会各写一份。",
        "",
        "| 项 | 值 |",
        "| --- | --- |",
        "| 路径 | `data/intel.sqlite`（仓库内） |",
        f"| 大小 | {db['size_bytes']:,} 字节 |",
        f"| SHA-256 | `{db['sha256']}` |",
        f"| runs | {counts['runs']} |",
        f"| events / event_aliases | {counts['events']} / {counts['event_aliases']} |",
        f"| assets / assessments / assessment_dispositions | {counts['assets']} / "
        f"{counts['assessments']} / {counts['assessment_dispositions']} |",
        f"| rag_documents / rag_chunks | {counts['rag_documents']} / {counts['rag_chunks']} |",
        f"| duplicate_candidates | {counts['duplicate_candidates']} |",
        "",
        "## 2. 同一时点的接口读数（与页面同源）",
        "",
        "取自 `/api/competition/scorecard`，快照时间同上。",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 累计有采集日期 | {card['cumulative_actual_run_days']} 天"
        f"（首次采集 {card['first_collection_date']}） |",
        f"| 累计定时运行日期 | {card['cumulative_scheduled_run_days']} 天 |",
        f"| 赛题连续运行（7 天窗口） | 窗口内 {card['scheduled_run_days_7d']} 天有定时运行，"
        f"连续 {card['continuous_executed_days']} 天，"
        f"`target_met = {str(card['continuous_target_met']).lower()}`"
        f"（累计 {card['cumulative_scheduled_run_days']} 天；日界为 UTC 00:00 / 北京 08:00） |",
        f"| 语料 | `events_loaded = {card['events_loaded']}` / "
        f"`events_total = {card['events_total']}`，`truncated = {str(card['truncated']).lower()}` |",
        f"| 监测时效性（混合口径，附录） | 6 小时内 {card['within_6h_rate']:.1%}，12 小时内 {card['within_12h_rate']:.1%}，"
        f"24 小时内 {card['within_24h_rate']:.1%}；p50 = {card['latency_p50_hours']} 小时"
        f"（{card['effective_denominator']} 个有效样本） |",
        f"| 处置闭环 | 高优先级 {disp['high_priority_total']} / 已关闭 "
        f"{disp['high_priority_closed']}（复测 {disp.get('high_priority_verified')} / "
        f"接受风险 {accepted}）/ `closure_rate = {disp['closure_rate']}` / "
        f"`verified_rate = {disp['verified_rate']}` / `findings_total = {disp['findings_total']}` |",
        f"| 关系评测（当前批次口径） | P = {relation['precision']}，R = {relation['recall']}，"
        f"F1 = {relation['f1']}（TP {relation['tp']} / FP {relation['fp']} / FN {relation['fn']}） |",
        f"| 富化样本量 | {card['enrichment_sample']} 个事件 |",
        "",
        END,
    ])


def rewrite_baseline(snapshot: dict) -> str:
    text = BASELINE.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit("METRICS_BASELINE.md is missing the snapshot markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return head + render_block(snapshot) + tail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite the baseline and the snapshot json")
    parser.add_argument("--json-only", action="store_true", help="write the json without touching the markdown")
    parser.add_argument("--tests", default="",
                        help='last full-suite summary line, e.g. "698 passed, 0 skipped"')
    args = parser.parse_args()

    snapshot = read_live()
    # The suite result is tied to the commit, not to the clock, so it is passed
    # in rather than measured here; keeping the previous value when it is omitted
    # stops a refresh from silently blanking it.
    if args.tests.strip():
        snapshot["tests"] = args.tests.strip()
    elif SNAPSHOT_JSON.is_file():
        try:
            previous = json.loads(SNAPSHOT_JSON.read_text(encoding="utf-8"))
            if previous.get("tests"):
                snapshot["tests"] = previous["tests"]
        except (OSError, json.JSONDecodeError):
            pass
    SNAPSHOT_JSON.parent.mkdir(parents=True, exist_ok=True)
    if args.write or args.json_only:
        SNAPSHOT_JSON.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.write:
        BASELINE.write_text(rewrite_baseline(snapshot), encoding="utf-8")

    print(json.dumps({
        "snapshot_date": snapshot["snapshot_date"],
        "events": snapshot["scorecard"]["events_total"],
        "collection_days": snapshot["scorecard"]["cumulative_actual_run_days"],
        "scheduled_days": snapshot["scorecard"]["cumulative_scheduled_run_days"],
        "latency_p50_hours": snapshot["scorecard"]["latency_p50_hours"],
        "tests": snapshot.get("tests"),
        "written": bool(args.write or args.json_only),
        "baseline": str(BASELINE.relative_to(ROOT)),
        "json": str(SNAPSHOT_JSON.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
