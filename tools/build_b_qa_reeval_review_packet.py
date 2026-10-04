"""生成"覆盖全部 50 题"的重评测人工确认清单（20261002 批次）。

队长要求人工核验材料**一次覆盖 50 题**，而不是分批零散追问。本工具把新批次的
系统回答、引用、机器建议（B 类）、旧人工标签（改造前基线）与变化点整理成一份
markdown 清单，供人工一次性裁定。

边界：

* 只读产物 + 只写这一份清单；不改人工标签、不改旧产物、不改数据库。
* 清单里出现的"机器建议"始终标注为 B 类；人工列由人工填写，工具不代填。
* 逐题标出"答案/引用是否与改造前逐字一致"，便于对未变化的题批量沿用旧标签。

用法::

    python tools/build_b_qa_reeval_review_packet.py \
        --out artifacts/b_eval/qa_reeval_20261002_review_packet.md
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACTS = ROOT / "artifacts" / "b_eval"
QA_DATASET = ROOT / "evaluation" / "b_formal_qa_set.json"
NEW_RESULTS = ARTIFACTS / "formal_qa_results_20261002.json"
NEW_ADJUDICATION = ARTIFACTS / "qa_machine_adjudication_20261002.json"
OLD_RESULTS = ARTIFACTS / "formal_qa_results.json"
OLD_SHEET = ARTIFACTS / "qa_gold_standard_worksheet.csv"

JUDGEMENTS = ("人工判定_答案正确性", "人工判定_引用准确性", "人工判定_拒答正确性")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _old_labels() -> dict[str, dict]:
    if not OLD_SHEET.is_file():
        return {}
    with OLD_SHEET.open(encoding="utf-8-sig", newline="") as handle:
        return {row["question_id"]: row for row in csv.DictReader(handle)}


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + " …"


def _cites(record: dict) -> list[tuple[str, str, str]]:
    return [(str(c.get("document_id") or ""), str(c.get("chunk_id") or ""),
             _clip(str(c.get("quote") or ""), 110))
            for c in (record.get("citations_detail") or [])]


def _diff_flags(new: dict, old: dict) -> list[str]:
    flags = []
    if (new.get("answer_full") or "") != (old.get("answer_full") or ""):
        flags.append("答案文本有变")
    if _cites(new) != _cites(old):
        flags.append("引用有变")
    if bool(new.get("refused")) != bool(old.get("refused")):
        flags.append(f"拒答行为翻转（旧={'拒答' if old.get('refused') else '作答'} → "
                     f"新={'拒答' if new.get('refused') else '作答'}）")
    return flags or ["与改造前逐字一致"]


def _block(case: dict, record: dict, adjudication: dict, old_record: dict,
           old_label: dict, *, detailed: bool) -> list[str]:
    qid = case["question_id"]
    dims = {name: adjudication[name] for name in
            ("answer_correctness", "citation_support", "refusal_correctness")}
    lines = [
        f"### {qid}｜{case.get('category')}｜{'应拒答' if case.get('should_refuse') else '应作答'}"
        f"｜变化：{'；'.join(_diff_flags(record, old_record))}",
        "",
        f"- 问题：{case.get('question')}",
    ]
    history = case.get("history") or []
    if history:
        lines.append("- 上文：" + " / ".join(
            f"{item.get('role')}: {_clip(str(item.get('content')), 60)}" for item in history))
    expected_docs = record.get("expected_document_keys") or []
    expected_terms = record.get("expected_answer_terms") or []
    if expected_docs or expected_terms:
        lines.append(f"- 预期：文档 {expected_docs or '—'}；要点 {expected_terms or '—'}")
    lines.append(f"- 系统实际：{'拒答' if record.get('refused') else '作答'}"
                 f"（耗时 {record.get('latency_ms')} ms）")
    answer = record.get("answer_full") or ""
    lines.append(f"- 系统回答：{_clip(answer, 700 if detailed else 320)}")
    citations = _cites(record)
    if citations:
        lines.append(f"- 引用（{len(citations)} 条）：")
        for doc, chunk, quote in citations[: (99 if detailed else 3)]:
            lines.append(f"    - `{chunk}` @ {doc}：{quote}")
    else:
        lines.append("- 引用：无")
    for name, label in (("answer_correctness", "答案正确性"),
                        ("citation_support", "引用支持性"),
                        ("refusal_correctness", "拒答正确性")):
        block = dims[name]
        lines.append(f"- 机器建议（B 类）·{label}：**{block.get('suggestion')}**"
                     f"（{block.get('status')}，{block.get('confidence')}）"
                     f"—— {_clip(str(block.get('rationale') or ''), 220)}")
    lines.append(f"- 改造前人工标签：答案={old_label.get(JUDGEMENTS[0]) or '（空）'}；"
                 f"引用={old_label.get(JUDGEMENTS[1]) or '（空）'}；"
                 f"拒答={old_label.get(JUDGEMENTS[2]) or '（空）'}")
    if detailed:
        lines.append(f"- 机器建议的待确认项：{_clip(str(adjudication.get('contested_reason') or '无'), 300)}")
        missing = adjudication.get("missing_evidence_or_criteria")
        if missing:
            lines.append(f"- 缺失证据/判据：{_clip(str(missing), 300)}")
        lines.append(f"- 需要人决定：{_clip(str(adjudication.get('expected_action') or ''), 200)}")
    lines.append("")
    return lines


def build() -> str:
    dataset = {c["question_id"]: c for c in _load(QA_DATASET)["cases"]}
    new = {r["question_id"]: r for r in _load(NEW_RESULTS)["records"]}
    old = {r["question_id"]: r for r in _load(OLD_RESULTS)["records"]}
    adjudications = {c["question_id"]: c for c in _load(NEW_ADJUDICATION)["cases"]}
    labels = _old_labels()

    order = sorted(dataset)
    unchanged, changed, contested = [], [], []
    for qid in order:
        flags = _diff_flags(new[qid], old[qid])
        if flags == ["与改造前逐字一致"]:
            unchanged.append(qid)
        elif adjudications[qid].get("contested"):
            contested.append(qid)
        else:
            changed.append(qid)
    contested = sorted(set(contested) | {q for q in order
                                         if bool(new[q]["refused"]) != bool(old[q]["refused"])})

    lines = [
        "# B 任务问答重评测 · 人工确认清单（2026-10-02 批次）",
        "",
        "本清单覆盖**全部 50 题**，用于一次性人工裁定。所有“机器建议”均为 B 类"
        "（机器辅助建议），**不是**人工金标准；人工列请填 "
        "`artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv` 的三个"
        "`人工判定_*` 列。",
        "",
        f"- 答案与引用与改造前逐字一致：**{len(unchanged)} 题**（可批量确认是否沿用旧标签）",
        f"- 有变化且非争议：**{len(changed)} 题**",
        f"- 争议口径或拒答行为翻转：**{len(contested)} 题**",
        "",
        "标签口径：答案正确性 `correct / partial / incorrect / unknown / not_applicable`；"
        "引用支持性 `supported / partially_supported / unsupported / not_applicable / unknown`；"
        "拒答正确性 `correct / incorrect / not_applicable / unknown`。"
        "`partial`、`unknown` 不计为正确；空值不计入分母。",
        "",
        "## 一、与改造前逐字一致的题（批量确认）",
        "",
        "| 题号 | 题型 | 改造前人工标签（答/引/拒） | 机器建议（答/引/拒） |",
        "| --- | --- | --- | --- |",
    ]
    for qid in unchanged:
        label = labels.get(qid, {})
        adj = adjudications[qid]
        lines.append(
            f"| {qid} | {dataset[qid].get('category')} | "
            f"{label.get(JUDGEMENTS[0]) or '（空）'} / {label.get(JUDGEMENTS[1]) or '（空）'} / "
            f"{label.get(JUDGEMENTS[2]) or '（空）'} | "
            f"{adj['answer_correctness']['suggestion']} / {adj['citation_support']['suggestion']} / "
            f"{adj['refusal_correctness']['suggestion']} |")
    lines += ["", "## 二、有变化、无口径争议的题", ""]
    for qid in changed:
        lines += _block(dataset[qid], new[qid], adjudications[qid], old[qid],
                        labels.get(qid, {}), detailed=False)
    lines += ["## 三、争议口径与拒答行为翻转的题（详版）", ""]
    for qid in contested:
        lines += _block(dataset[qid], new[qid], adjudications[qid], old[qid],
                        labels.get(qid, {}), detailed=True)

    header = [
        "<!-- 由 tools/build_b_qa_reeval_review_packet.py 生成；"
        "机器建议为 B 类，人工标签需人工填写 -->",
        "",
    ]
    return "\n".join(header + lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成覆盖 50 题的复核清单（只读）")
    parser.add_argument("--out", type=Path,
                        default=ARTIFACTS / "qa_reeval_20261002_review_packet.md")
    args = parser.parse_args()
    for path in (NEW_RESULTS, NEW_ADJUDICATION, OLD_RESULTS):
        if not path.is_file():
            print("缺少必需文件:", path)
            return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build(), encoding="utf-8")
    print("复核清单已写入:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
