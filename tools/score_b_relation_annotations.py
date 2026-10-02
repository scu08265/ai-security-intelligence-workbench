"""B 任务阶段 D：关系标注的 TP / FP / FN 统计程序。

判定规则（必须写在前面，避免事后调分母）：

* 只有 `annotation.status == "human_verified"` 且 `annotation.label` 明确的候选才进入统计。
* `label == "positive"`：人工确认该关系成立——**金标准正例**。
* `label == "negative"`：人工确认该关系不成立——**金标准负例**。
* `label == "unknown"` / `"not_applicable"`：人工判定为无法定论或不适用，**单列，不计入 P/R**。
* `annotation.status != "human_verified"`（含 `pending_human_review`）：**未核验**，不计入任何分母。

系统侧预测使用 `prediction.verdict` 字段（`present` / `missing`）。
**缺省视为 `present`**：候选本身就是系统抽取出来的关系，被收录即代表系统主张它成立。
脚本会把这个缺省假设写进输出（`prediction_default`），不会悄悄替换。

* 金标准 positive 且系统 present → **TP**
* 金标准 negative 且系统 present → **FP**
* 金标准 positive 且系统 missing → **FN**
* 金标准 negative 且系统 missing → **TN**

**召回率与 F1 的额外前提**：候选集**就是系统的输出**，其中天然不含"应当抽取但没抽到"的关系。
因此 FN 没有来源，仅凭候选文件**无法**计算召回率与 F1。若要计算，需要额外提供金标准清单
（`--gold`，JSON 内含 `expected_relation_ids`：应抽取的关系 ID 全集）：

    python tools/score_b_relation_annotations.py --gold evaluation/b_relation_gold.json

没有 `--gold` 时，脚本输出 precision，并把 recall / F1 标为 `null` 且说明原因。

由于当前没有任何人工标注，程序会如实输出 `computable: false`，而不是给出 0 或 100%。

用法::

    python tools/score_b_relation_annotations.py --input evaluation/b_relation_candidates.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERIFIED = "human_verified"
POSITIVE, NEGATIVE = "positive", "negative"
UNDETERMINED = {"unknown", "not_applicable"}


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or (precision + recall) == 0:
        return None
    return round(2 * precision * recall / (precision + recall), 4)


def score(payload: dict, gold: dict | None = None) -> dict:
    """计算分维度与微/宏平均的 TP/FP/FN、precision、recall、F1。

    `gold` 可选，格式：``{"expected_relation_ids": [...]}``，
    表示"应当抽取的关系 ID 全集"；只有提供它才可能得到 FN。
    """
    counters: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0,
                 "undetermined": 0, "pending": 0, "total": 0}
    )
    verified_present: set[str] = set()
    prediction_default_used = 0
    for case in payload.get("cases") or []:
        bucket = counters[case["dimension"]]
        bucket["total"] += 1
        annotation = case.get("annotation") or {}
        label = annotation.get("label")
        if annotation.get("status") != VERIFIED:
            bucket["pending"] += 1
            continue
        if label in UNDETERMINED:
            bucket["undetermined"] += 1
            continue
        verdict = (case.get("prediction") or {}).get("verdict")
        if verdict not in {"present", "missing"}:
            # 候选本身就是系统输出：缺省视为系统主张该关系成立
            verdict = "present"
            prediction_default_used += 1
        if label == POSITIVE:
            bucket["tp" if verdict == "present" else "fn"] += 1
            if verdict == "present":
                verified_present.add(str(case.get("relation_id")))
        elif label == NEGATIVE:
            bucket["fp" if verdict == "present" else "tn"] += 1
        else:
            bucket["pending"] += 1

    per_dimension = {}
    micro = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    macro_precisions, macro_recalls = [], []

    # 只有当金标准给出"应当抽取的关系全集"时，才能算出 FN。
    # 支持两种写法：ID 列表（FN 归入 unknown 维度）或 {ID: 维度} 映射。
    raw_expected = gold.get("expected_relation_ids") or [] if gold else []
    if isinstance(raw_expected, dict):
        expected_ids = set(raw_expected)
        expected_dimension = dict(raw_expected)
    else:
        expected_ids = set(raw_expected)
        expected_dimension = {}
    fn_source_available = bool(expected_ids)
    missing_ids = sorted(expected_ids - verified_present) if fn_source_available else []
    if fn_source_available:
        by_dimension = {c["relation_id"]: c["dimension"] for c in payload.get("cases") or []}
        by_dimension.update(expected_dimension)
        for relation_id in missing_ids:
            dimension = by_dimension.get(relation_id, "unknown")
            counters[dimension]["fn"] += 1

    for dim, bucket in sorted(counters.items()):
        precision = _rate(bucket["tp"], bucket["tp"] + bucket["fp"])
        recall = _rate(bucket["tp"], bucket["tp"] + bucket["fn"]) if fn_source_available else None
        per_dimension[dim] = {
            **bucket,
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
            "evaluable": (bucket["tp"] + bucket["fp"] + bucket["fn"]) > 0,
        }
        micro["tp"] += bucket["tp"]
        micro["fp"] += bucket["fp"]
        micro["fn"] += bucket["fn"]
        micro["tn"] += bucket["tn"]
        if precision is not None:
            macro_precisions.append(precision)
        if recall is not None:
            macro_recalls.append(recall)

    evaluable = micro["tp"] + micro["fp"] + micro["fn"]
    micro_precision = _rate(micro["tp"], micro["tp"] + micro["fp"])
    micro_recall = _rate(micro["tp"], micro["tp"] + micro["fn"]) if fn_source_available else None
    return {
        "computable": evaluable > 0,
        "rule": "只有 annotation.status=human_verified 且 label 明确的候选进入统计；"
                "pending_human_review 与 unknown/not_applicable 单列，不计入任何分母。",
        "prediction_default": {
            "used": prediction_default_used,
            "assumption": "缺少 prediction.verdict 时视为 present（候选即系统输出）",
        },
        "fn_source": {
            "available": fn_source_available,
            "expected_relation_ids": len(expected_ids) if fn_source_available else None,
            "missing_relation_ids": missing_ids[:50] if fn_source_available else None,
            "reason": None if fn_source_available else
                      "候选集即系统输出，缺少'应抽取但未抽取'的金标准清单，FN 无来源，"
                      "因此 recall 与 F1 不可计算（只有 precision 可计算）",
        },
        "per_dimension": per_dimension,
        "micro": {
            **micro,
            "precision": micro_precision,
            "recall": _rate(micro["tp"], micro["tp"] + micro["fn"]) if fn_source_available else None,
            "f1": _f1(micro_precision, micro_recall),
            "evaluable_samples": evaluable,
        },
        "macro": {
            "precision": round(sum(macro_precisions) / len(macro_precisions), 4)
                         if macro_precisions else None,
            "recall": round(sum(macro_recalls) / len(macro_recalls), 4)
                      if macro_recalls else None,
            "f1": _f1(
                round(sum(macro_precisions) / len(macro_precisions), 4) if macro_precisions else None,
                round(sum(macro_recalls) / len(macro_recalls), 4) if macro_recalls else None,
            ),
            "dimensions_with_metrics": len(macro_precisions),
        },
        "note": None if evaluable else
                "当前没有任何人工核验标注，TP/FP/FN 不可计算；pending 数量见各维度。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="B 任务关系标注 TP/FP/FN 统计")
    parser.add_argument("--input", type=Path,
                        default=ROOT / "evaluation" / "b_relation_candidates.json")
    parser.add_argument("--gold", type=Path, default=None,
                        help="可选的应抽取关系全集（JSON: {expected_relation_ids: [...]}），"
                             "提供后才可能计算 recall/F1")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    gold = json.loads(args.gold.read_text(encoding="utf-8")) if args.gold else None
    result = score(payload, gold)
    print(json.dumps({k: v for k, v in result.items()
                      if k in {"computable", "micro", "macro", "note",
                               "prediction_default", "fn_source"}},
                     ensure_ascii=False, indent=1))
    for dim, bucket in result["per_dimension"].items():
        print("  %-18s total=%-4d pending=%-4d undetermined=%-3d TP=%-3d FP=%-3d FN=%-3d P=%s R=%s F1=%s" % (
            dim, bucket["total"], bucket["pending"], bucket["undetermined"],
            bucket["tp"], bucket["fp"], bucket["fn"],
            bucket["precision"], bucket["recall"], bucket["f1"]))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print("结果已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
