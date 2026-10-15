"""A1：批量入口的分类与"安全升级版本"计算。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import run_disposition_batch as batch  # noqa: E402


def test_smallest_safe_version_clears_every_range_at_once():
    # "< 0.29.0" 允许 0.29.0，但 "<= 0.29.0" 不允许，所以并集的最小安全版本是 0.29.1。
    assert batch.smallest_safe_version(["< 0.29.0", "<= 0.29.0"]) == "0.29.1"
    assert batch.smallest_safe_version(["< 0.29.0"]) == "0.29.0"
    assert batch.smallest_safe_version(["<= 0.26.0"]) == "0.26.1"


def test_smallest_safe_version_refuses_ranges_it_cannot_parse():
    assert batch.smallest_safe_version(["not a specifier"]) is None
    assert batch.smallest_safe_version([]) is None


def _item(status: str = "affected") -> dict:
    return {"event_id": "CVE-1", "asset_id": "asset-1", "priority": "high",
            "assessment_status": status}


def _event(rng: str = "< 0.29.0") -> dict:
    return {"id": "CVE-1", "affected": [{"package": "vllm", "range": rng}]}


def test_a_finding_already_out_of_range_goes_through_single_verification():
    row = batch.classify(_item(status="not_affected"), _event(),
                         {"component": "vllm", "version": "0.30.0", "is_demo": True})
    assert row["category"] == "already_out_of_range"
    assert row["action"] == "single_verified"


def test_a_synthetic_asset_with_a_known_target_is_actionable():
    row = batch.classify(_item(), _event(),
                         {"component": "vllm", "version": "0.10.0", "is_demo": True})
    assert row["category"] == "synthetic_actionable"
    assert row["target_version"] == "0.29.0"
    assert row["action"] == "batch_in_progress"


def test_a_real_asset_is_never_upgraded_by_this_tool():
    row = batch.classify(_item(), _event(),
                         {"component": "vllm", "version": "0.10.0", "is_demo": False})
    assert row["category"] == "not_actionable"
    assert "真实资产" in row["reason"]
    assert "action" not in row


def test_an_unparseable_range_is_left_unregistered():
    row = batch.classify(_item(), {"id": "CVE-1", "affected": [{"range": "unknown"}]},
                         {"component": "vllm", "version": "0.10.0", "is_demo": True})
    assert row["category"] == "not_actionable"
    assert "unknown" in row["reason"]


def test_an_event_without_a_range_is_left_unregistered():
    row = batch.classify(_item(), {"id": "CVE-1", "affected": []},
                         {"component": "vllm", "version": "0.10.0", "is_demo": True})
    assert row["category"] == "not_actionable"
    assert "受影响区间" in row["reason"]
