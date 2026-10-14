"""The baseline snapshot and the report must move together, not drift apart."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import refresh_metrics_snapshot as refresh  # noqa: E402

BASELINE = ROOT / "docs" / "METRICS_BASELINE.md"
SNAPSHOT = ROOT / "docs" / "report" / "metrics_snapshot.json"


def _sample_snapshot() -> dict:
    return {
        "snapshot_date": "2099-01-01",
        "snapshot_time_local": "2099-01-01 12:00 CST",
        "database": {
            "path": "data/intel.sqlite", "size_bytes": 1234, "sha256": "a" * 64,
            "counts": {key: 7 for key in refresh.COUNTED_TABLES},
        },
        "scorecard": {
            "cumulative_actual_run_days": 3, "cumulative_scheduled_run_days": 2,
            "scheduled_run_days_7d": 2, "continuous_target_met": False,
            "first_collection_date": "2098-12-30", "events_loaded": 7, "events_total": 7,
            "truncated": False, "within_6h_rate": 0.5, "within_12h_rate": 0.6,
            "within_24h_rate": 0.7, "effective_denominator": 4,
            "latency_p50_hours": 1.5, "enrichment_sample": 7,
        },
        "disposition": {
            "high_priority_total": 1, "high_priority_closed": 0,
            "closure_rate": 0.0, "verified_rate": 0.0, "findings_total": 1,
        },
        "relation": {"precision": 1.0, "recall": 0.5, "f1": 0.66, "tp": 1, "fp": 0, "fn": 1},
    }


def test_rendered_block_carries_the_date_and_both_markers():
    block = refresh.render_block(_sample_snapshot())
    assert refresh.START in block
    assert refresh.END in block
    assert "2099-01-01" in block
    # The window status is stated, not assumed: this sample is not met.
    assert "target_met = false" in block


def test_rewriting_is_idempotent():
    original = BASELINE.read_text(encoding="utf-8")
    snapshot = _sample_snapshot()
    once = original.split(refresh.START, 1)[0] + refresh.render_block(snapshot) \
        + original.split(refresh.END, 1)[1]
    twice = once.split(refresh.START, 1)[0] + refresh.render_block(snapshot) \
        + once.split(refresh.END, 1)[1]
    assert once == twice
    # Rewriting must not disturb the sections outside the marked block.
    assert "## 3. 哪些指标能用这条基线" in once
    assert "## 4. 引用规则" in once


def test_the_committed_baseline_agrees_with_the_committed_snapshot():
    """A refresh that updates only one of the two files fails here."""
    if not SNAPSHOT.is_file():
        return
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    baseline = BASELINE.read_text(encoding="utf-8")
    card = snapshot["scorecard"]
    assert f"events_total = {card['events_total']}" in baseline
    assert f"累计有采集日期 | {card['cumulative_actual_run_days']} 天" in baseline
    assert f"target_met = {str(card['continuous_target_met']).lower()}" in baseline
