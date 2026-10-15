"""连续运行核对工具的口径测试：窗口、缺口与预计达成日期。

判定规则必须与 /api/competition/scorecard 同源——当天是否计为"有计划运行"，
只看 kind 属于采集、且 detail.trigger == "scheduled"。手工补跑和 chat 运行都不算。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import check_continuous_run as check  # noqa: E402


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _day(offset: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=offset)).isoformat()


def _run(day: str, *, scheduled: bool = True, kind: str = "collect", run_id: str = "run-x") -> dict:
    return {
        "id": run_id,
        "kind": kind,
        "status": "completed",
        "started_at": f"{day}T01:00:00Z",
        "detail": {"trigger": "scheduled"} if scheduled else {},
    }


def test_window_is_the_trailing_days_ending_today():
    report = check.build_report(7, runs=[])
    days = [row["date"] for row in report["window"]["days"]]
    assert len(days) == 7
    assert days[-1] == _today()
    assert days[0] == _day(6)
    assert report["window"]["days_missing_scheduled_run"] == days


def test_only_scheduled_collect_runs_count():
    runs = [
        _run(_day(0)),
        _run(_day(1), scheduled=False),                       # 手工运行：不计入
        _run(_day(2), kind="chat"),                           # 非采集运行：不计入
        _run(_day(3), kind="scheduled_collect", run_id="run-4"),
    ]
    report = check.build_report(4, runs=runs)
    counts = {row["date"]: row["scheduled_run_count"] for row in report["window"]["days"]}
    assert counts[_day(0)] == 1
    assert counts[_day(1)] == 0
    assert counts[_day(2)] == 0
    assert counts[_day(3)] == 1


def test_eta_is_the_last_gap_plus_a_full_window():
    report = check.build_report(7, runs=[_run(_day(offset), run_id=f"run-{offset}") for offset in range(3)])
    missing = report["window"]["days_missing_scheduled_run"]
    assert missing, "窗口里应当仍有缺口"
    expected = (
        datetime.fromisoformat(max(missing)).date() + timedelta(days=7)
    ).isoformat()
    assert report["target_met_eta_utc"] == expected
    assert report["eta_note"]


def test_a_full_window_has_no_eta_and_is_met():
    runs = [_run(_day(offset), run_id=f"run-{offset}") for offset in range(7)]
    report = check.build_report(7, runs=runs)
    assert report["window"]["days_missing_scheduled_run"] == []
    assert report["target_met_eta_utc"] is None
    assert report["eta_note"] is None
    assert report["scorecard_view"]["target_met"] is True
    assert report["scorecard_view"]["consecutive_scheduled_days"] == 7


def test_report_records_its_own_source_and_rule():
    report = check.build_report(7, runs=[])
    assert "trigger" in report["source"]["rule"]
    assert report["source"]["database"], "必须记录读的是哪份库"
    assert report["timezone_note"]
