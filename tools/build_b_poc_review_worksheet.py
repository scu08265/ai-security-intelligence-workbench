"""B 任务 POC 维度：把 NVD Exploit 候选整理成**轻量人工签核表**。

背景：`event.poc[]` 现在由 NVD `references[].tags` 含 `Exploit` 的公开引用填充
（见 `docs/DATA_SOURCE_DECISIONS.md`），状态口径固定为 `public_exploit_reference`。
但 NVD 的 Exploit 标签比"存在可复现 PoC"宽得多——实测 32 条候选里既有
exploit-db / packetstorm 的利用代码，也有厂商安全公告和事件分析博客。

因此本工具**不改变系统口径**，只额外做一件事：按 URL 形态给出
"这条算不算可利用证据（exploit artifact）"的机器建议，供人工一次性签核。

边界：

* 只读候选文件，只写签核表与分类结果；不改数据库、不改系统口径、不改人工标签文件；
* 人工列（`人工判定_是否可利用证据`、`人工核验人`、`人工核验时间`）**由人工填写**；
* 不下载、不执行任何利用代码，仅依据 NVD 已记录的公开引用元数据。

用法::

    python tools/build_b_poc_review_worksheet.py \
        --candidates evaluation/b_relation_candidates_20261002_poc.json \
        --out artifacts/b_eval/relation_poc_review_20261002.csv \
        --classification-out artifacts/b_eval/relation_poc_classification_20261002.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CANDIDATES = ROOT / "evaluation" / "b_relation_candidates_20261002_poc.json"
WORKSHEET = ROOT / "artifacts" / "b_eval" / "relation_poc_review_20261002.csv"
CLASSIFICATION = ROOT / "artifacts" / "b_eval" / "relation_poc_classification_20261002.json"

COLUMNS = [
    "relation_id", "event_id", "cve", "url", "url_type", "host",
    "nvd_status", "source_id", "nvd_tags",
    "建议_是否可利用证据", "建议依据",
    "人工判定_是否可利用证据", "人工核验人", "人工核验时间", "人工备注",
]

# 人工可填的判定列（与工作表列名一致）
HUMAN_COLUMN = "人工判定_是否可利用证据"
HUMAN_SIGNATURE = ("人工核验人", "人工核验时间")
VALID_HUMAN_VALUES = {"yes", "no", "unknown", "not_applicable"}

# URL 形态 → (类型, 是否算可利用证据, 依据)
_SCRIPT_SUFFIXES = (".txt", ".rb", ".py", ".sh", ".pl", ".js", ".md")
_EXPLOIT_HOSTS = ("packetstormsecurity", "exploit-db.com", "exploit-db.org")
_ADVISORY_MARKERS = ("/security/advisories/", "/advisories/", "/security-advisories/")


def classify(url: str) -> tuple[str, str, str]:
    """返回 (url_type, suggestion, rationale)。规则固定、可复现、可人工推翻。"""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if any(marker in host for marker in _EXPLOIT_HOSTS):
        return ("公开利用库", "yes",
                "exploit-db / packetstorm 的条目通常直接给出利用代码或复现步骤")
    if "github.com" in host and any(marker in path for marker in _ADVISORY_MARKERS):
        return ("安全公告", "no", "安全公告说明漏洞与修复，不等于公开可利用证据")
    if "github.com" in host and ("/issues/" in path or "/pull/" in path):
        return ("issue/PR", "no", "issue/PR 是讨论或修复记录，默认不作为利用证据")
    if "github.com" in host:
        segments = [segment for segment in path.split("/") if segment]
        # 仓库名（而非 owner）以 CVE 命名时视为专用 PoC 仓库，例如 /lntrx/CVE-2021-28663
        if any("cve-" in segment for segment in segments):
            return ("专用 PoC 仓库", "yes", "仓库名以 CVE 命名，通常是针对该漏洞的 PoC 集合")
        return ("代码仓库/其他", "no", "仓库用途无法从 URL 判定，交人工确认")
    if path.endswith(_SCRIPT_SUFFIXES):
        return ("利用脚本文件", "yes", "URL 指向可直接读取的利用脚本/复现文件")
    if "crbug.com" in host or "bugs.chromium.org" in host:
        return ("缺陷跟踪", "no", "缺陷跟踪页默认不作为利用证据")
    return ("厂商/研究博客", "no",
            "分析/披露文章默认不作为可利用证据，人工可上修")


def build(candidates_path: Path) -> tuple[list[dict], dict]:
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for case in payload.get("cases") or []:
        if case.get("dimension") != "poc":
            continue
        url = str(case.get("object") or "")
        url_type, suggestion, rationale = classify(url)
        value = case.get("candidate_value") or {}
        evidence = case.get("evidence") or {}
        tags = value.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        rows.append({
            "relation_id": case.get("relation_id"),
            "event_id": case.get("subject"),
            "cve": case.get("subject"),
            "url": url,
            "url_type": url_type,
            "host": urlparse(url).netloc.lower(),
            "nvd_status": value.get("status") or "",
            "source_id": evidence.get("source_id") or "",
            "nvd_tags": "|".join(str(t) for t in tags),
            "建议_是否可利用证据": suggestion,
            "建议依据": rationale,
            "人工判定_是否可利用证据": "",
            "人工核验人": "",
            "人工核验时间": "",
            "人工备注": "",
        })
    rows.sort(key=lambda row: (row["cve"] or "", row["relation_id"] or ""))
    counts = Counter(row["url_type"] for row in rows)
    suggestion_counts = Counter(row["建议_是否可利用证据"] for row in rows)
    classification = {
        "schema_version": "b-poc-classification-1.0",
        "source": str(candidates_path.relative_to(ROOT)) if candidates_path.is_relative_to(ROOT)
                  else str(candidates_path),
        "status_semantics": "public_exploit_reference：NVD 打了 Exploit 标签的公开引用；"
                            "不代表本系统验证、复现或执行过该利用",
        "rule": "URL 形态分类（exploit-db/packetstorm=公开利用库；GitHub 安全公告；issue/PR；"
                "CVE 命名仓库；脚本文件；厂商/研究博客）。建议列只是机器建议，不是人工标签。",
        "candidates": len(rows),
        "events": len({row["event_id"] for row in rows}),
        "url_type_counts": dict(sorted(counts.items())),
        "machine_suggestion_counts": dict(sorted(suggestion_counts.items())),
        "human_decision_pending": len(rows),
        "never_executed": True,
        "cases": rows,
    }
    return rows, classification


def apply_labels(worksheet: Path, confirmed_input: Path, *, dry_run: bool,
                 force: bool) -> int:
    """把人工确认结果写进签核表；不覆盖已填人工判定（除非 --force）。"""
    with worksheet.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    with confirmed_input.open(encoding="utf-8-sig", newline="") as handle:
        decisions = {row["relation_id"]: row for row in csv.DictReader(handle)}

    problems: list[str] = []
    written = preserved = skipped = 0
    for index, row in enumerate(rows, start=2):
        decision = decisions.get(row.get("relation_id") or "")
        if not decision:
            skipped += 1
            continue
        value = (decision.get(HUMAN_COLUMN) or "").strip().casefold()
        if value not in VALID_HUMAN_VALUES:
            problems.append(f"第 {index} 行（{row['relation_id']}）：{HUMAN_COLUMN}={value!r} 非法，"
                            f"允许 {sorted(VALID_HUMAN_VALUES)}")
            continue
        signature = {column: (decision.get(column) or "").strip()
                     for column in HUMAN_SIGNATURE}
        if not all(signature.values()):
            problems.append(f"第 {index} 行（{row['relation_id']}）：缺少核验人或核验时间")
            continue
        if not force and (row.get(HUMAN_COLUMN) or "").strip():
            preserved += 1
            continue
        row[HUMAN_COLUMN] = value
        row.update(signature)
        row["人工备注"] = (decision.get("人工备注") or row.get("人工备注") or "").strip()
        written += 1

    for problem in problems:
        print(problem)
    if problems:
        print("存在非法输入，已中止，未写入")
        return 3
    print("签核表行数:", len(rows), "| 待写入:", written,
          "| 已有判定保留:", preserved, "| 未涉及:", skipped)
    if dry_run:
        return 0
    with worksheet.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print("已写入:", worksheet)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 POC 维度轻量人工签核表（只读候选）")
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--out", type=Path, default=WORKSHEET)
    parser.add_argument("--classification-out", type=Path, default=CLASSIFICATION)
    parser.add_argument("--apply", type=Path, default=None,
                        help="把人工确认后的结果写进签核表（需 --confirmed-input）")
    parser.add_argument("--confirmed-input", type=Path, default=None,
                        help="人工确认输入：relation_id + 人工判定_是否可利用证据 + 署名")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.apply or args.confirmed_input:
        worksheet = args.apply or args.out
        if not args.confirmed_input or not args.confirmed_input.is_file():
            print("缺少 --confirmed-input 文件")
            return 2
        if not worksheet.is_file():
            print("找不到签核表:", worksheet)
            return 2
        return apply_labels(worksheet, args.confirmed_input,
                            dry_run=args.dry_run, force=args.force)

    if not args.candidates.is_file():
        print("找不到候选文件:", args.candidates)
        return 2

    rows, classification = build(args.candidates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    args.classification_out.write_text(
        json.dumps(classification, ensure_ascii=False, indent=1), encoding="utf-8")

    print("POC 候选:", classification["candidates"], "条 | 事件:",
          classification["events"], "个")
    print("URL 类型:", json.dumps(classification["url_type_counts"], ensure_ascii=False))
    print("机器建议（是否可利用证据）:",
          json.dumps(classification["machine_suggestion_counts"], ensure_ascii=False))
    print("签核表:", args.out)
    print("分类结果:", args.classification_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
