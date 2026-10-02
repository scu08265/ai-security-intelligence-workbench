"""B 任务问答评测：从人工金标准工作表计算指标（人工与自动严格分离）。

**判定口径（必须先看这里，避免事后调分母）**

输入是 `artifacts/b_eval/qa_gold_standard_worksheet.csv`（50 题）。只有人工列
**明确填写**的行才进入人工指标分母；`unknown` / 空白一律单列。

人工列取值（大小写不敏感）：

* `人工判定_答案正确性`：`correct` / `incorrect` / `partial` / `unknown`
* `人工判定_引用准确性`：`supported` / `partially_supported` / `unsupported`
  / `not_applicable` / `unknown`
* `人工判定_拒答正确性`：`correct` / `incorrect` / `not_applicable` / `unknown`

由此计算：

* **答案准确率**：`correct / (correct + incorrect + partial)`——`partial` 按"不完全正确"计入分母，
  同时单列 `partial` 数量；另有严格的 `correct / (correct + incorrect)` 作为对照口径。
* **引用准确率**：`supported / (supported + partially_supported + unsupported)`；
  `not_applicable`（本题不需要引用）与 `unknown` 不进分母。
* **拒答指标**：以「应拒答」为金标准，
  `拒答召回率 = 正确拒答数 / 应拒答且已判定题数`，
  `拒答精确率 = 正确拒答数 / 实际拒答且已判定题数`，并与机器事实（`should_refuse` / `system_refused`）
  交叉成混淆矩阵。拒答本身不视为正确——必须人工确认"该题确实缺少证据"。
* **按题型分项**：以上指标再按 `category` 分组，各自给出分子/分母。
* **延迟**：直接取工作表的 `latency_ms`（机器实测），仅在同一批 50 题上报告 P50/P95，
  与人工判定无关。分位数采用**最近秩（nearest-rank）口径、不做线性插值**，
  与既有 `formal_qa_results.json` 的报数一致（实测同为 427.1 / 584.6 ms）。

自动评审判定（`auto_*` 列、`qa_auto_review.json`）单独输出在 `auto_review` 段，
**绝不并入**任何人工指标。

用法::

    python tools/score_b_qa_annotations.py --out artifacts/b_eval/qa_human_score.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORKSHEET = ROOT / "artifacts" / "b_eval" / "qa_gold_standard_worksheet.csv"
AUTO_REVIEW = ROOT / "artifacts" / "b_eval" / "qa_auto_review.json"
FORMAL_RESULTS = ROOT / "artifacts" / "b_eval" / "formal_qa_results.json"
MACHINE_ADJUDICATION = ROOT / "artifacts" / "b_eval" / "qa_machine_adjudication.json"
TARGETS = (0.75, 0.90, 0.95)

ANSWER_CORRECTNESS = ("correct", "incorrect", "partial", "unknown")
CITATION_ACCURACY = ("supported", "partially_supported", "unsupported",
                     "not_applicable", "unknown")
REFUSAL_CORRECTNESS = ("correct", "incorrect", "not_applicable", "unknown")


def _norm(value: str) -> str:
    return (value or "").strip().casefold()


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.2f}%"


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return round(ordered[index], 1)


def load_rows(path: Path = WORKSHEET) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _answer_metrics(rows: list[dict]) -> dict:
    counted = Counter(_norm(r.get("人工判定_答案正确性")) for r in rows)
    correct = counted["correct"]
    incorrect = counted["incorrect"]
    partial = counted["partial"]
    denominator = correct + incorrect + partial
    return {
        "numerator": correct,
        "denominator": denominator,
        "rate": _rate(correct, denominator),
        "rule": "correct / (correct + incorrect + partial)；partial 按不完全正确计入分母",
        "strict_denominator": correct + incorrect,
        "strict_rate": _rate(correct, correct + incorrect),
        "partial_counted_not_correct": partial,
        "by_label": {k: counted[k] for k in ANSWER_CORRECTNESS if counted[k]},
        "undecided": counted["unknown"] + sum(
            1 for r in rows if not _norm(r.get("人工判定_答案正确性"))),
    }


def _citation_metrics(rows: list[dict]) -> dict:
    counted = Counter(_norm(r.get("人工判定_引用准确性")) for r in rows)
    supported = counted["supported"]
    partial = counted["partially_supported"]
    unsupported = counted["unsupported"]
    denominator = supported + partial + unsupported
    return {
        "numerator": supported,
        "denominator": denominator,
        "rate": _rate(supported, denominator),
        "rule": "supported / (supported + partially_supported + unsupported)；"
                "not_applicable（本题不需要引用）与 unknown 不进分母",
        "by_label": {k: counted[k] for k in CITATION_ACCURACY if counted[k]},
        "not_applicable": counted["not_applicable"],
        "undecided": counted["unknown"] + sum(
            1 for r in rows if not _norm(r.get("人工判定_引用准确性"))),
    }


def _refusal_metrics(rows: list[dict]) -> dict:
    """拒答指标：只在人工已判定「拒答正确性」的题目上计算。"""
    judged = [r for r in rows
              if _norm(r.get("人工判定_拒答正确性")) in {"correct", "incorrect"}]
    should_refuse = [r for r in judged if _norm(r.get("should_refuse")) == "true"]
    should_answer = [r for r in judged if _norm(r.get("should_refuse")) != "true"]
    correctly_refused = [r for r in should_refuse
                         if _norm(r.get("人工判定_拒答正确性")) == "correct"
                         and _norm(r.get("system_refused")) == "true"]
    actually_refused = [r for r in judged if _norm(r.get("system_refused")) == "true"]
    return {
        "judged_cases": len(judged),
        "should_refuse": {
            "n": len(should_refuse),
            "correctly_refused": len(correctly_refused),
            "refused_recall": _rate(len(correctly_refused), len(should_refuse)),
            "answered_by_system": sum(1 for r in should_refuse
                                      if _norm(r.get("system_refused")) != "true"),
        },
        "should_answer": {
            "n": len(should_answer),
            "answered_correctly": sum(1 for r in should_answer
                                      if _norm(r.get("人工判定_拒答正确性")) == "correct"),
            "wrongly_refused": sum(1 for r in should_answer
                                   if _norm(r.get("system_refused")) == "true"),
        },
        "refused_precision": _rate(len(correctly_refused), len(actually_refused)),
        "refusal_accuracy": _rate(
            sum(1 for r in judged if _norm(r.get("人工判定_拒答正确性")) == "correct"),
            len(judged)),
        "rule": "只有人工已判定 correct/incorrect 的题进入分母；not_applicable 与空白单列；"
                "拒答本身不等于正确",
        "not_applicable": sum(1 for r in rows
                              if _norm(r.get("人工判定_拒答正确性")) == "not_applicable"),
        "undecided": sum(1 for r in rows if _norm(r.get("人工判定_拒答正确性"))
                         in {"", "unknown"}),
    }


def _by_category(rows: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.get("category") or "（未分类）"].append(row)
    result = {}
    for category, items in sorted(grouped.items()):
        if not any(_norm(r.get("人工判定_答案正确性")) or
                   _norm(r.get("人工判定_引用准确性")) or
                   _norm(r.get("人工判定_拒答正确性")) for r in items):
            continue   # 完全没有人工判定的题型不进入人工分项指标
        result[category] = {
            "cases": len(items),
            "answer": _answer_metrics(items),
            "citation": _citation_metrics(items),
            "refusal": _refusal_metrics(items),
        }
    return result


def _target_row(label: str, value: float | None, numerator, denominator, scope: str) -> dict:
    """单个指标 vs 75%/90%/95% 的**逐指标**对照（禁止合成总分）。"""
    entry = {"metric": label, "value": value, "numerator": numerator,
             "denominator": denominator, "scope": scope, "comparison": {}}
    for target in TARGETS:
        key = f"{int(target * 100)}%"
        if value is None:
            entry["comparison"][key] = "不可对照（缺少金标准）"
        else:
            delta = round(value - target, 4)
            entry["comparison"][key] = (
                f"超出 {abs(delta) * 100:.2f} pt" if delta >= 0
                else f"差 {abs(delta) * 100:.2f} pt")
    return entry


def _machine_metrics(path: Path = FORMAL_RESULTS) -> dict:
    """机器实测指标（来自既有运行记录），与人工指标完全分开。"""
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    totals = payload.get("totals") or {}
    return {
        "source": str(path.relative_to(ROOT)),
        "batch": "50 题固定问答集，本轮实测运行记录",
        "document_hit_rate": totals.get("document_hit"),
        "term_hit_rate": totals.get("term_hit"),
        "refusal_consistency": totals.get("refusal_accuracy"),
        "citations": totals.get("citations"),
        "answer_semantic_accuracy": totals.get("answer_semantic_accuracy"),
        "confusion": payload.get("answer_refusal_confusion"),
        "latency_ms": payload.get("latency_ms"),
        "warning": "机器指标不等于准确率：引用命中/词命中/拒答一致率都是机械判定，"
                   "不得与人工准确率混用或相加",
    }


def _failure_samples(adjudication: list[dict] | None) -> list[dict]:
    """B 类裁定里"明显失败"或"证据/判据未定"的样本，供报告逐条说明原因。"""
    samples = []
    for item in adjudication or []:
        issues = []
        for name, block in (("答案正确性", item.get("answer_correctness") or {}),
                            ("引用支持性", item.get("citation_support") or {}),
                            ("拒答正确性", item.get("refusal_correctness") or {})):
            suggestion = block.get("suggestion")
            if suggestion in {"incorrect", "unsupported"}:
                issues.append(f"{name}={suggestion}")
            elif block.get("status") == "pending_human_review":
                issues.append(f"{name}=pending_human_review")
        if not issues:
            continue
        samples.append({
            "question_id": item.get("question_id"),
            "category": item.get("category"),
            "tier": "B_machine_assisted_suggestion",
            "issues": issues,
            "contested": bool(item.get("contested")),
            "reason": item.get("missing_evidence_or_criteria")
                      or (item.get("capability_analysis") or {}).get("conclusion")
                      or "见 qa_machine_adjudication.json 对应条目",
        })
    return samples


def score(rows: list[dict], auto_review: dict | None = None,
          machine: dict | None = None, adjudication: list[dict] | None = None) -> dict:
    """计算人工指标；无任何人工判定时 `computable` 为 False 并说明原因。"""
    human_judged = [r for r in rows if any(
        _norm(r.get(c)) for c in ("人工判定_答案正确性", "人工判定_引用准确性",
                                  "人工判定_拒答正确性", "人工最终标签"))]
    latencies = [float(r["latency_ms"]) for r in rows
                 if str(r.get("latency_ms") or "").strip()
                 and str(r["latency_ms"]).replace(".", "", 1).isdigit()]
    answer = _answer_metrics(rows)
    citation = _citation_metrics(rows)
    refusal = _refusal_metrics(rows)
    return {
        "schema_version": "b-qa-human-score-1.0",
        "computable": bool(human_judged) and bool(
            answer["denominator"] or citation["denominator"] or refusal["judged_cases"]),
        "cases_total": len(rows),
        "human_judged_cases": len(human_judged),
        "pending_human_cases": len(rows) - len(human_judged),
        "answer": answer,
        "citation": citation,
        "refusal": refusal,
        "by_category": _by_category(rows),
        "latency_ms": {
            "samples": len(latencies),
            "p50": _percentile(latencies, 0.5),
            "p95": _percentile(latencies, 0.95),
            "scope": "机器实测端到端耗时：与本轮 50 题工作表同一批运行记录，非历史数据；"
                     "分位数用最近秩口径、不做插值；超时阈值 5000 ms",
        },
        "errors": {
            "timeouts": sum(1 for r in rows if _norm(r.get("timeout")) == "true"),
            "failures": sum(1 for r in rows if (r.get("error") or "").strip()
                            and _norm(r["error"]) != "none"),
        },
        "note": None if human_judged else
                "当前没有任何人工金标准判定，人工指标不可计算；"
                "自动评审结果见 auto_review 段，两者不得混用。",
        "machine_metrics": machine or {},
        "target_comparison": _target_comparison(rows, answer, citation, refusal, machine),
        "failure_samples": _failure_samples(adjudication),
        "auto_review": auto_review or {},
    }


def _target_comparison(rows, answer, citation, refusal, machine) -> dict:
    """逐指标对照 75/90/95；人工指标缺金标准时不产出数值对照。"""
    entries = [
        _target_row("人工·答案准确率", answer["rate"], answer["numerator"],
                    answer["denominator"], "分母=已人工判定 correct/incorrect/partial 的题"),
        _target_row("人工·引用准确率", citation["rate"], citation["numerator"],
                    citation["denominator"],
                    "分母=已人工判定 supported/partially/unsupported 的题"),
        _target_row("人工·拒答召回率", refusal["should_refuse"]["refused_recall"],
                    refusal["should_refuse"]["correctly_refused"],
                    refusal["should_refuse"]["n"],
                    "分母=人工已判定的应拒答题"),
    ]
    if machine:
        document_hit = machine.get("document_hit_rate") or {}
        term_hit = machine.get("term_hit_rate") or {}
        refusal_consistency = machine.get("refusal_consistency") or {}
        citations = machine.get("citations") or {}
        entries += [
            _target_row("机器·引用命中率", document_hit.get("rate"), document_hit.get("ok"),
                        document_hit.get("n"), document_hit.get("scope", "机器实测")),
            _target_row("机器·预期词命中率", term_hit.get("rate"), term_hit.get("ok"),
                        term_hit.get("n"), term_hit.get("scope", "机器实测")),
            _target_row("机器·拒答一致率", refusal_consistency.get("rate"),
                        refusal_consistency.get("ok"), refusal_consistency.get("n"),
                        "机器实测：与 should_refuse 是否一致，不是人工核验"),
            _target_row("机器·引用可追溯率", citations.get("rate"),
                        citations.get("retrievable"), citations.get("total"),
                        "机器实测：引用 ID 是否能在库中取回"),
        ]
    return {
        "targets": [f"{int(t * 100)}%" for t in TARGETS],
        "rule": "逐指标对照，**不得**把不同指标合成单一总分；"
                "人工指标在无金标准时输出『不可对照』",
        "metrics": entries,
    }


def _load_adjudication(path: Path = MACHINE_ADJUDICATION) -> list[dict]:
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("cases") or []


def _load_auto_review() -> dict:
    if not AUTO_REVIEW.is_file():
        return {}
    payload = json.loads(AUTO_REVIEW.read_text(encoding="utf-8"))
    return {
        "source": str(AUTO_REVIEW.relative_to(ROOT)),
        "counts": payload.get("counts"),
        "metrics": payload.get("metrics"),
        "warning": "自动评审判定，**不是**人工指标；不得当作准确率使用",
    }


def _print(result: dict) -> None:
    print(json.dumps({k: result[k] for k in (
        "computable", "cases_total", "human_judged_cases", "pending_human_cases",
        "note")}, ensure_ascii=False, indent=1))
    for name in ("answer", "citation", "refusal"):
        block = result[name]
        if name == "refusal":
            rate = block.get("refusal_accuracy")
            print(f"  {'refusal':9s} accuracy={_pct(rate):>8s} "
                  f"judged={block.get('judged_cases')} "
                  f"refused_recall={_pct(block.get('should_refuse', {}).get('refused_recall'))} "
                  f"precision={_pct(block.get('refused_precision'))} "
                  f"undecided={block.get('undecided')}")
            continue
        print(f"  {name:9s} rate={_pct(block.get('rate')):>8s} "
              f"numerator={block.get('numerator')} "
              f"denominator={block.get('denominator')} "
              f"undecided={block.get('undecided')}")
    latency = result["latency_ms"]
    print(f"  latency   P50={latency['p50']} ms  P95={latency['p95']} ms  "
          f"samples={latency['samples']}")
    print(f"  errors    timeouts={result['errors']['timeouts']} "
          f"failures={result['errors']['failures']}")
    print(f"  failure_samples(B 类): {len(result.get('failure_samples') or [])} 条")


def main() -> int:
    parser = argparse.ArgumentParser(description="B 任务问答人工指标计算")
    parser.add_argument("--worksheet", type=Path, default=WORKSHEET)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if not args.worksheet.is_file():
        print("找不到工作表:", args.worksheet)
        return 2
    result = score(load_rows(args.worksheet), _load_auto_review(), _machine_metrics(),
                   _load_adjudication())
    _print(result)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                            encoding="utf-8")
        print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
