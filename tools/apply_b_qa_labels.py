"""任务二：把裁定表里的人工判定**回填**到 50 题金标准工作表。

流程：人工只需在 `qa_adjudication_table.csv` 的三列里填写判定
（`人工判定_答案正确性` / `人工判定_引用准确性` / `人工判定_拒答正确性`）
以及署名，然后运行本工具，把结果同步到 `qa_gold_standard_worksheet.csv`，
再由 `tools/score_b_qa_annotations.py` 计算人工指标。

安全约束（与关系标注工具同口径）：

* 合法取值之外的标签、重复 question_id、表里不存在的 question_id **一律报错并中止**；
* 目标行**已有非空人工判定**时拒绝覆盖（除非显式 `--force`），避免抹掉已确认结果；
* 只写这 6 列，其余列原样保留；不触碰任何自动列。

用法::

    python tools/apply_b_qa_labels.py --dry-run        # 先看会写什么
    python tools/apply_b_qa_labels.py                   # 实际回填
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "b_eval"
ADJUDICATION = ARTIFACTS / "qa_adjudication_table.csv"
WORKSHEET = ARTIFACTS / "qa_gold_standard_worksheet.csv"

VALID = {
    "人工判定_答案正确性": ("correct", "incorrect", "partial", "unknown"),
    "人工判定_引用准确性": ("supported", "partially_supported", "unsupported",
                            "not_applicable", "unknown"),
    "人工判定_拒答正确性": ("correct", "incorrect", "not_applicable", "unknown"),
}
SIGNATURE = ("人工核验人", "人工核验时间", "人工备注")


class LabelImportError(RuntimeError):
    """裁定表不合法时抛出；调用方应中止而不是继续算指标。"""


def _load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def collect(rows: list[dict], known_ids: set[str]) -> tuple[dict, dict]:
    decisions: dict[str, dict] = {}
    summary: Counter = Counter()
    problems: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        qid = (row.get("question_id") or "").strip()
        if not qid:
            problems.append(f"第 {index} 行：question_id 为空")
            continue
        if qid in seen:
            problems.append(f"第 {index} 行：question_id {qid} 重复")
            continue
        seen.add(qid)
        if qid not in known_ids:
            problems.append(f"第 {index} 行：question_id {qid} 不在金标准工作表里")
            continue
        values = {column: (row.get(column) or "").strip().casefold()
                  for column in VALID}
        signature = {column: (row.get(column) or "").strip() for column in SIGNATURE}
        if not any(values.values()):
            summary["blank"] += 1
            continue
        for column, value in values.items():
            if value and value not in VALID[column]:
                problems.append(f"第 {index} 行（{qid}）：{column}={value!r} 非法，"
                                f"允许 {list(VALID[column])}")
        if not signature["人工核验人"] or not signature["人工核验时间"]:
            problems.append(f"第 {index} 行（{qid}）：缺少核验人或核验时间")
        decisions[qid] = {**values, **signature}
        summary["decided"] += 1
    if problems:
        raise LabelImportError("裁定表存在问题，已中止：\n  - " + "\n  - ".join(problems[:20]))
    return decisions, dict(summary)


def apply(decisions: dict, worksheet: list[dict], force: bool = False) -> Counter:
    counts: Counter = Counter()
    for row in worksheet:
        decision = decisions.get(row["question_id"])
        if not decision:
            continue
        if not force and any((row.get(column) or "").strip() for column in VALID):
            counts["skipped_preserved"] += 1
            continue
        for column, value in decision.items():
            row[column] = value
        counts["written"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="把问答裁定表回填到金标准工作表")
    parser.add_argument("--adjudication", type=Path, default=ADJUDICATION)
    parser.add_argument("--worksheet", type=Path, default=WORKSHEET)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for path in (args.adjudication, args.worksheet):
        if not path.is_file():
            print("找不到文件:", path)
            return 2

    worksheet = _load(args.worksheet)
    fields = list(worksheet[0].keys())
    known = {row["question_id"] for row in worksheet}
    try:
        decisions, summary = collect(_load(args.adjudication), known)
    except LabelImportError as exc:
        print(str(exc))
        return 3

    counts = apply(decisions, worksheet, force=args.force)
    print("裁定表:", summary, "| 回填:", dict(counts))
    if counts["skipped_preserved"]:
        print("  ⚠️ 有", counts["skipped_preserved"],
              "行已有人工判定，已保留（如需覆盖请加 --force）")
    if not decisions:
        print("  裁定为空，未写入任何内容")
        return 0
    if args.dry_run:
        for row in list(decisions)[:5]:
            print("  dry-run:", row, decisions[row])
        return 0
    with args.worksheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(worksheet)
    print("已回填:", args.worksheet)
    print("下一步：.venv\\Scripts\\python.exe tools\\score_b_qa_annotations.py "
          "--out artifacts\\b_eval\\qa_human_score.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
