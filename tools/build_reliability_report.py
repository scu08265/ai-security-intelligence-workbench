"""Generate continuous-run, source-health, and timeliness deliverables."""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, observability, reliability, storage  # noqa: E402


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_source_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else [
        "source_id", "name", "current_status", "success_rate",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _latency_chart_svg(report: dict[str, Any]) -> str:
    timeliness = report["timeliness"]
    measured = max(1, int(timeliness["computable_samples"]))
    buckets = [
        ("<=6h", timeliness["within_6h"]["count"], "#31c48d"),
        (">6h-12h", timeliness["within_12h"]["count"] - timeliness["within_6h"]["count"], "#58a6ff"),
        (">12h-24h", timeliness["within_24h"]["count"] - timeliness["within_12h"]["count"], "#f6c344"),
        (">24h", measured - timeliness["within_24h"]["count"], "#f97066"),
        ("未知", timeliness["unknown_samples"], "#8b949e"),
        ("历史回填排除", timeliness["baseline_excluded_samples"], "#6e7681"),
    ]
    total = sum(item[1] for item in buckets)
    width, height = 960, 480
    left, top, bar_width = 170, 84, 680
    row_height, gap = 54, 15
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        '<text x="48" y="44" fill="#f0f6fc" font-size="25" font-family="Arial, sans-serif">发布到首次发现时延分布</text>',
        f'<text x="48" y="68" fill="#8b949e" font-size="14" font-family="Arial, sans-serif">可计算 {measured} 条，未知 {timeliness["unknown_samples"]} 条；目标：6/12/24 小时</text>',
    ]
    for index, (label, count, color) in enumerate(buckets):
        y = top + index * (row_height + gap)
        ratio = count / total if total else 0
        length = max(0, round(bar_width * ratio))
        rate = count / measured if measured and label not in {"未知", "历史回填排除"} else None
        value = f"{count} 条"
        if rate is not None:
            value += f" · {rate * 100:.1f}%"
        parts.extend([
            f'<text x="48" y="{y + 25}" fill="#c9d1d9" font-size="16" font-family="Arial, sans-serif">{html.escape(label)}</text>',
            f'<rect x="{left}" y="{y}" width="{bar_width}" height="34" rx="4" fill="#21262d"/>',
            f'<rect x="{left}" y="{y}" width="{length}" height="34" rx="4" fill="{color}"/>',
            f'<text x="{left + bar_width + 16}" y="{y + 23}" fill="#f0f6fc" font-size="15" font-family="Arial, sans-serif">{html.escape(value)}</text>',
        ])
    parts.append('</svg>')
    return "\n".join(parts)


def _source_chart_svg(report: dict[str, Any]) -> str:
    items = report["sources"]["items"]
    width, height = 960, 560
    left, top, bar_width, row_height = 260, 82, 520, 30
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0d1117"/>',
        '<text x="48" y="44" fill="#f0f6fc" font-size="25" font-family="Arial, sans-serif">来源成功率</text>',
        '<text x="48" y="68" fill="#8b949e" font-size="14" font-family="Arial, sans-serif">主动跳过不计入成功率分母；无历史尝试的来源显示未运行。</text>',
    ]
    for index, item in enumerate(items):
        y = top + index * row_height
        rate = item.get("success_rate")
        ratio = float(rate or 0)
        color = "#31c48d" if ratio >= 0.95 else "#f6c344" if ratio >= 0.7 else "#f97066"
        value = "未运行" if rate is None else f"{ratio * 100:.1f}%"
        parts.extend([
            f'<text x="48" y="{y + 20}" fill="#c9d1d9" font-size="13" font-family="Arial, sans-serif">{html.escape(str(item["id"]))}</text>',
            f'<rect x="{left}" y="{y}" width="{bar_width}" height="18" rx="4" fill="#21262d"/>',
            f'<rect x="{left}" y="{y}" width="{round(bar_width * ratio)}" height="18" rx="4" fill="{color}"/>',
            f'<text x="{left + bar_width + 14}" y="{y + 15}" fill="#f0f6fc" font-size="13" font-family="Arial, sans-serif">{value}</text>',
        ])
    parts.append('</svg>')
    return "\n".join(parts)


def _markdown_report(report: dict[str, Any]) -> str:
    timeliness = report["timeliness"]
    continuous = report["continuous_runs"]
    status = "已满足" if continuous["target_met"] else "积累中"
    lines = [
        "# 7 天连续运行与来源可靠性报告",
        "",
        f"- 版本：{report.get('version') or config.APP_VERSION}",
        f"- 生成时间：{report['generated_at']}",
        f"- 实际采集运行天数：{continuous['actual_run_days']} 天",
        f"- 计划任务运行天数：{continuous['scheduled_run_days']} 天",
        f"- 连续计划任务证据：{continuous['consecutive_executed_days']} / {continuous['target_days']} 天（{status}）",
        "- 统计口径：每个事件只取最早一次发现时间；异常发布时间和未来发布时间不进入时延分母。",
        "",
        "## 1. 发布到首次发现时延",
        "",
        "| 指标 | 数量 | 比例 | 赛题口径 |",
        "| --- | ---: | ---: | --- |",
    ]
    for key, label, target in (
        ("within_6h", "<=6 小时", "优秀目标"),
        ("within_12h", "<=12 小时", "良好目标"),
        ("within_24h", "<=24 小时", "合格目标"),
    ):
        item = timeliness[key]
        rate = "未知" if item["rate"] is None else f"{item['rate'] * 100:.2f}%"
        lines.append(f"| {label} | {item['count']} | {rate} | {target} |")
    lines.extend([
        f"| 可计算样本 | {timeliness['computable_samples']} | - | 有效发布时间和发现时间 |",
        f"| 有效分母 | {timeliness['effective_denominator']} | - | 监测后且发布时间有效的样本 |",
        f"| 监测后新增事件 | {timeliness['post_monitoring_samples']} | - | 首次发现时间晚于系统监测开始时间 |",
        f"| 未知样本 | {timeliness['unknown_samples']} | - | 缺失、异常或未来发布时间 |",
        f"| 历史回填排除 | {timeliness['baseline_excluded_samples']} | - | 系统首次监测前已经发布的数据 |",
        f"| 系统首次监测时间 | {timeliness['monitoring_started_at'] or '未知'} | - | 最早持久化采集运行开始时间 |",
        "",
        f"- 时延 P50：{timeliness['latency_seconds_p50']} 秒",
        f"- 时延 P95：{timeliness['latency_seconds_p95']} 秒",
        "",
        "## 2. 每日定时运行证据",
        "",
        "| 日期 | 实际采集 | 计划采集 | 实际运行数 | 计划运行数 | 计划成功 | 计划部分 | 计划失败 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for item in continuous["ledger"]:
        lines.append(
            f"| {item['date']} | {'是' if item['actual_executed'] else '否'} | "
            f"{'是' if item['scheduled_executed'] else '否'} | "
            f"{item['actual_run_count']} | {item['scheduled_run_count']} | "
            f"{item['scheduled_successful_run_count']} | "
            f"{item['scheduled_partial_run_count']} | "
            f"{item['scheduled_failed_run_count']} |"
        )
    lines.extend([
        "",
        "## 3. 来源健康",
        "",
        "| 来源 | 状态 | 成功率 | 成功/失败/陈旧/跳过 | P50 ms | P95 ms | 最近成功 |",
        "| --- | --- | ---: | --- | ---: | ---: | --- |",
    ])
    for item in report["sources"]["items"]:
        rate = "未知" if item["success_rate"] is None else f"{item['success_rate'] * 100:.1f}%"
        lines.append(
            f"| {item['id']} | {item['health_class']} | {rate} | "
            f"{item['successful_attempts']}/{item['failed_attempts']}/"
            f"{item['stale_attempts']}/{item['skipped_attempts']} | "
            f"{item['duration_ms_p50'] if item['duration_ms_p50'] is not None else '未知'} | "
            f"{item['duration_ms_p95'] if item['duration_ms_p95'] is not None else '未知'} | "
            f"{item['last_success'] or '未知'} |"
        )
    lines.extend(["", "## 4. 失败原因与降级策略", ""])
    for source_id, strategy in report["degradation_strategies"].items():
        lines.extend([
            f"### {source_id}",
            "",
            f"- 失败原因：{strategy['failure_reason']}",
            f"- 降级策略：{strategy['degradation']}",
            f"- 历史数据：{strategy['data_availability']}",
            f"- 人工动作：{strategy['manual_action']}",
            "",
        ])
    lines.extend([
        "## 5. 限制",
        "",
        "- 未达到 7 天时不得声称完成连续稳定性验证。",
        "- `actual_run_days` 统计任意采集运行；`scheduled_run_days` 只统计 `trigger=scheduled`。",
        "- 时延只使用监测后新增事件；监测前已发布的历史回填不进入有效分母。",
        "- 成功率只使用已有运行记录；主动跳过不计入成功率分母。",
        "- 本报告不补写历史运行，不把人工触发伪装成计划任务。",
        "",
    ])
    return "\n".join(lines)


def _write_daily_logs(output: Path, report: dict[str, Any]) -> list[str]:
    runs = storage.list_runs(limit=2000)
    by_id = {str(run.get("id")): run for run in runs}
    alerts = observability.recent_alerts(limit=1000)["items"]
    written: list[str] = []
    daily_dir = output / "daily-logs"
    for day in report["continuous_runs"]["ledger"]:
        if not (day["actual_executed"] or day["scheduled_executed"]):
            continue
        selected_runs = [
            by_id[run_id] for run_id in day["actual_run_ids"] if run_id in by_id
        ]
        scheduled_runs = [
            run for run in selected_runs
            if (run.get("detail") or {}).get("trigger") == "scheduled"
        ]
        day_alerts = [
            alert for alert in alerts
            if str(alert.get("timestamp") or "")[:10] == day["date"]
        ]
        payload = {
            "date": day["date"],
            "generated_at": report["generated_at"],
            "version": config.APP_VERSION,
            "scheduled_runs": [{
                "id": run.get("id"),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "summary": run.get("summary"),
                "scheduler": (run.get("detail") or {}).get("scheduler") or {},
                "sources": [{
                    "source_id": item.get("source_id"),
                    "status": item.get("status"),
                    "fetched": item.get("fetched"),
                    "kept": item.get("kept"),
                    "duration_ms": item.get("duration_ms"),
                    "error": item.get("error"),
                    "notes": item.get("notes") or [],
                } for item in (run.get("detail") or {}).get("results") or []],
            } for run in scheduled_runs],
            "actual_runs": [{
                "id": run.get("id"),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "trigger": (run.get("detail") or {}).get("trigger"),
                "task_id": ((run.get("detail") or {}).get("scheduler") or {}).get("task_id"),
            } for run in selected_runs],
            "alerts": day_alerts,
            "summary": {
                "actual_run_count": day["actual_run_count"],
                "scheduled_run_count": day["scheduled_run_count"],
                "scheduled_successful_run_count": day["scheduled_successful_run_count"],
                "scheduled_partial_run_count": day["scheduled_partial_run_count"],
                "scheduled_failed_run_count": day["scheduled_failed_run_count"],
            },
        }
        target = daily_dir / f"{day['date']}.json"
        _write_json(target, payload)
        written.append(day["date"])
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-owner reliability reports.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()
    storage.init_db()
    output = (ROOT / args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = reliability.build_reliability_report(days=args.days)
    rows = reliability.source_health_rows(report)

    _write_json(output / "source-health.json", {
        "version": report.get("version") or config.APP_VERSION,
        "generated_at": report["generated_at"],
        **report["sources"],
    })
    _write_json(output / "latency-summary.json", {
        "version": report.get("version") or config.APP_VERSION,
        "generated_at": report["generated_at"],
        **report["timeliness"],
    })
    _write_json(output / "reliability-report.json", report)
    _write_source_csv(output / "source-health.csv", rows)
    (output / "latency-chart.svg").write_text(_latency_chart_svg(report), encoding="utf-8")
    (output / "source-success-chart.svg").write_text(_source_chart_svg(report), encoding="utf-8")
    (output / "7-day-continuous-run-report.md").write_text(
        _markdown_report(report), encoding="utf-8",
    )
    daily_logs = _write_daily_logs(output, report)
    print(json.dumps({
        "output_dir": str(output),
        "daily_logs": daily_logs,
        "continuous_days": report["continuous_runs"]["consecutive_executed_days"],
        "target_days": report["continuous_runs"]["target_days"],
        "computable_latency_samples": report["timeliness"]["computable_samples"],
        "unknown_latency_samples": report["timeliness"]["unknown_samples"],
        "source_count": report["sources"]["source_count"],
        "warning_count": len(report["warnings"]),
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
