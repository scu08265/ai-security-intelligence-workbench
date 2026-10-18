"""A2：cpeMatch 区间推导与"不猜版本"的边界。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import verify_version_ranges as ranges  # noqa: E402


def test_range_of_uses_the_bounds_that_exist():
    assert ranges.range_of({"versionEndExcluding": "1.3.0"}) == "< 1.3.0"
    assert ranges.range_of({"versionEndIncluding": "1.6.9"}) == "<= 1.6.9"
    assert ranges.range_of({
        "versionStartIncluding": "3.3.0", "versionEndExcluding": "3.15.0",
    }) == ">= 3.3.0, < 3.15.0"
    assert ranges.range_of({}) is None, "没有边界的条目不能编出一个区间"


def test_product_match_is_strict_enough_to_avoid_wrong_attribution():
    assert ranges.product_matches("MLflow", "mlflow", "lfprojects")
    assert ranges.product_matches("Langflow", "langflow", "langflow")
    # chrome 与 Chromium 是两个不同的 cpe product，宁可 unknown 也不硬套。
    assert not ranges.product_matches("Chromium", "chrome", "google")


def _case() -> dict:
    return {
        "relation_id": "BREL-VE-T", "subject": "CVE-2099-1",
        "candidate_value": {"package": "Langflow", "ecosystem": "Langflow", "range": "unknown"},
        "evidence": {"source_id": "kev:abc"},
    }


def test_a_matching_cpe_match_yields_a_range_and_keeps_the_source_id():
    row = ranges.classify(_case(), [{
        "criteria": "cpe:2.3:a:langflow:langflow:*:*:*:*:*:*:*:*",
        "vulnerable": True, "range": "< 1.3.0", "snapshot": "x.json",
    }])
    assert row["status"] == "resolved"
    assert row["range"] == "< 1.3.0"
    assert row["source_id"] == "kev:abc"


def test_a_wildcard_only_entry_stays_unknown():
    row = ranges.classify(_case(), [{
        "criteria": "cpe:2.3:a:langflow:langflow:*:*:*:*:*:*:*:*",
        "vulnerable": True, "range": None, "snapshot": "x.json",
    }])
    assert row["status"] == "unknown"
    assert "`*`" in row["missing"]


def test_no_cpe_match_at_all_names_that_fact():
    row = ranges.classify(_case(), [])
    assert row["status"] == "unknown"
    assert "没有该 CVE 的 cpeMatch" in row["missing"]


def test_an_unrelated_product_is_not_used():
    row = ranges.classify(_case(), [{
        "criteria": "cpe:2.3:a:apache:tomcat:*:*:*:*:*:*:*:*",
        "vulnerable": True, "range": "< 9.0.0", "snapshot": "x.json",
    }])
    assert row["status"] == "unknown"
    assert "对不上" in row["missing"]
