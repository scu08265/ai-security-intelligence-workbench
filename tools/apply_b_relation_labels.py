"""B 任务：把人工填写的复核表（CSV）回灌成评分脚本可读的 JSON。

**为什么需要这个工具**：人工在 `relation_final_review_worksheet.csv` 里填标签，
而 `tools/score_b_relation_annotations.py` 读的是候选 JSON 的 `annotation` 字段。
两者之间原本没有通路，导致"标完了也算不出指标"。本工具补上这一步。

规则：

* **只读原始候选**，写入**新的** JSON（默认 `artifacts/b_eval/relation_candidates_labeled.json`），
  绝不覆盖 `evaluation/b_relation_candidates.json`。
* 空白标签 → 保持 `pending_human_review`，不计入分母。
* 合法标签：`positive` / `negative` / `unknown` / `not_applicable`。
* **非法标签、重复 relation_id、候选里不存在的 relation_id 一律报错并中止**，
  不会静默丢弃。
* 填了标签但缺 `人工核验人` 或 `人工核验时间` 时给出警告（不中止），
  因为署名是可追溯性要求的一部分。

用法::

    python tools/apply_b_relation_labels.py \
        --worksheet artifacts/b_eval/relation_annotation_worksheet_v2.csv \
        --out artifacts/b_eval/relation_candidates_labeled.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANDIDATES = ROOT / "evaluation" / "b_relation_candidates.json"
LABEL_COLUMN = "待人工填写_最终标签"
VALID_LABELS = {"positive", "negative", "unknown", "not_applicable"}


class LabelImportError(RuntimeError):
    """标签表不合法时抛出；调用方应中止而不是继续算指标。"""


def _display(path: Path) -> str:
    """仓库内路径显示为相对路径；仓库外（例如临时副本）显示绝对路径。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_candidates(path: Path = CANDIDATES) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {case["relation_id"]: case for case in payload["cases"]}


def read_worksheet(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def apply_labels(rows: list[dict], candidates: dict[str, dict]) -> tuple[dict, dict]:
    """返回 (标注后的 candidate payload, 统计摘要)。"""
    seen: set[str] = set()
    problems: list[str] = []
    illegal_labels: Counter = Counter()
    counts: Counter = Counter()
    missing_signature: list[str] = []

    labeled = {rid: dict(case) for rid, case in candidates.items()}

    for index, row in enumerate(rows, start=2):   # 第 1 行是表头
        relation_id = (row.get("relation_id") or "").strip()
        if not relation_id:
            problems.append(f"第 {index} 行：relation_id 为空")
            continue
        if relation_id in seen:
            problems.append(f"第 {index} 行：relation_id {relation_id} 重复出现")
            continue
        seen.add(relation_id)
        if relation_id not in candidates:
            problems.append(f"第 {index} 行：relation_id {relation_id} 不在候选集中")
            continue

        raw = (row.get(LABEL_COLUMN) or "").strip()
        if not raw:
            counts["blank"] += 1
            continue
        label = raw.casefold()
        if label not in VALID_LABELS:
            illegal_labels[raw] += 1
            problems.append(
                f"第 {index} 行：标签 {raw!r} 非法，允许值 {sorted(VALID_LABELS)}")
            continue

        verifier = (row.get("人工核验人") or "").strip()
        verified_at = (row.get("人工核验时间") or "").strip()
        if not verifier or not verified_at:
            missing_signature.append(relation_id)

        labeled[relation_id]["annotation"] = {
            "status": "human_verified",
            "label": label,
            "verified_by": verifier or None,
            "verified_at": verified_at or None,
            "note": (row.get("人工备注") or "").strip() or None,
        }
        counts[label] += 1

    if problems:
        raise LabelImportError("标签表存在问题，已中止：\n  - " + "\n  - ".join(problems[:20]))

    summary = {
        "worksheet_rows": len(rows),
        "blank": counts["blank"],
        "positive": counts["positive"],
        "negative": counts["negative"],
        "unknown": counts["unknown"],
        "not_applicable": counts["not_applicable"],
        "human_verified_total": (counts["positive"] + counts["negative"]
                                 + counts["unknown"] + counts["not_applicable"]),
        "illegal_labels": dict(illegal_labels),
        "missing_signature": missing_signature[:20],
        "missing_signature_count": len(missing_signature),
    }
    return labeled, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="把人工标签从 CSV 回灌成评分用 JSON")
    parser.add_argument("--worksheet", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "relation_annotation_worksheet_v2.csv")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "artifacts" / "b_eval" / "relation_candidates_labeled.json")
    args = parser.parse_args()

    if not args.worksheet.is_file():
        print("找不到复核表:", args.worksheet)
        return 2
    candidates = load_candidates(args.candidates)
    try:
        labeled, summary = apply_labels(read_worksheet(args.worksheet), candidates)
    except LabelImportError as exc:
        print(str(exc))
        return 3

    payload = {
        "schema_version": "b-relation-candidates-labeled-1.0",
        "description": "由 tools/apply_b_relation_labels.py 从人工复核表回灌生成；"
                       "原始候选文件未被修改。",
        "source_candidates": _display(args.candidates),
        "source_worksheet": _display(args.worksheet),
        "import_summary": summary,
        "cases": list(labeled.values()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("已回灌:", summary["human_verified_total"], "条人工标签 /", summary["worksheet_rows"], "行")
    print("  空白:", summary["blank"], "| positive:", summary["positive"],
          "| negative:", summary["negative"], "| unknown:", summary["unknown"],
          "| not_applicable:", summary["not_applicable"])
    if summary["missing_signature_count"]:
        print("  警告：", summary["missing_signature_count"],
              "条已标标签但缺少核验人或时间（前 5 条：",
              ", ".join(summary["missing_signature"][:5]), "）")
    print("输出:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
