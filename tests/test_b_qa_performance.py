"""B 任务三：问答性能统计工具与产物的测试。

重点：

* 批次之间**不得混合**——每个批次独立算分位数，只有题号一致时才逐题对照；
* 超时/异常/失败按运行文件如实汇总；
* 真实产物（历史批次 A 与重复批次 B）题号一致、作答/拒答结果一致。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_b_qa_performance_report as perf  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
RUN_A = ARTIFACTS / "formal_qa_results.json"
RUN_B = ARTIFACTS / "formal_qa_performance_run2.json"
STATS = ARTIFACTS / "qa_performance_stats.json"


def _write_run(path: Path, records: list[dict]) -> Path:
    payload = {"totals": {}, "by_category": {}, "records": records}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _record(qid: str, latency: float, refused: bool = False, category: str = "基础事实问答"):
    return {"question_id": qid, "category": category, "latency_ms": latency,
            "refused": refused, "error": None, "timeout": latency > 5000}


def test_batches_are_summarised_separately(tmp_path):
    first = _write_run(tmp_path / "a.json", [_record("Q1", 100.0), _record("Q2", 200.0)])
    second = _write_run(tmp_path / "b.json", [_record("Q1", 110.0), _record("Q2", 210.0)])
    stats = perf.build([("A", first), ("B", second)])
    assert [b["label"] for b in stats["batches"]] == ["A", "B"]
    assert stats["batches"][0]["latency_ms"]["p50"] == 100.0
    assert stats["batches"][1]["latency_ms"]["p50"] == 110.0
    # 顶层不得出现合并后的分位数
    assert "latency_ms" not in stats
    assert stats["comparison"]["same_question_ids"] is True
    deltas = {item["question_id"]: item["delta_ms"]
              for item in stats["comparison"]["per_question"]}
    assert deltas == {"Q1": 10.0, "Q2": 10.0}


def test_different_question_sets_are_not_compared(tmp_path):
    first = _write_run(tmp_path / "a.json", [_record("Q1", 100.0)])
    second = _write_run(tmp_path / "b.json", [_record("Q9", 100.0)])
    stats = perf.build([("A", first), ("B", second)])
    assert stats["comparison"]["same_question_ids"] is False
    assert stats["comparison"]["per_question"] == []
    assert "不得合并" in stats["comparison"]["rule"]


def test_outcome_changes_are_reported(tmp_path):
    first = _write_run(tmp_path / "a.json", [_record("Q1", 100.0, refused=False)])
    second = _write_run(tmp_path / "b.json", [_record("Q1", 120.0, refused=True)])
    stats = perf.build([("A", first), ("B", second)])
    changes = stats["comparison"]["outcome_changes"]
    assert len(changes) == 1
    assert changes[0]["question_id"] == "Q1"
    assert changes[0]["refused_A"] is False and changes[0]["refused_B"] is True


def test_real_batches_share_the_same_question_set():
    if not RUN_B.is_file():
        pytest.skip("重复批次不存在（先运行 tools/run_b_qa_eval.py --out …run2.json）")
    a = json.loads(RUN_A.read_text(encoding="utf-8"))["records"]
    b = json.loads(RUN_B.read_text(encoding="utf-8"))["records"]
    assert len(a) == len(b) == 50
    assert [r["question_id"] for r in a] == [r["question_id"] for r in b]
    # 两批的作答/拒答结果必须一致，否则说明行为不稳定
    assert [bool(r["refused"]) for r in a] == [bool(r["refused"]) for r in b]


def test_real_stats_keep_batches_separate_and_report_deltas():
    if not STATS.is_file():
        pytest.skip("性能统计不存在（先运行 tools/build_b_qa_performance_report.py）")
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    assert [b["label"] for b in stats["batches"]] == ["A", "B"]
    for batch in stats["batches"]:
        assert batch["cases"] == 50
        assert batch["latency_ms"]["samples"] == 50
        assert batch["outcomes"]["errors"] == 0
        assert batch["outcomes"]["timeouts"] == 0
    assert stats["comparison"]["same_question_ids"] is True
    assert len(stats["comparison"]["per_question"]) == 50
    assert stats["comparison"]["outcome_changes"] == []
    assert "不合并" in stats["notes"]["no_mixing"]
    assert "最近秩" in stats["batches"][0]["latency_ms"]["scope"]
