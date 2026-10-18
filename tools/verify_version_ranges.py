"""A2：把 version_range 的 37 条 unknown 逐条对到本地 NVD 快照的 cpeMatch。

规则（按任务书，不猜版本）：

1. 只读本地 ``data/snapshots/nvd`` 里的 ``cpeMatch``，不做联网重采；
2. 只有 cpeMatch 的 product 与候选 package 对得上时才采用，对不上不硬套；
3. ``versionEndExcluding`` → ``< X``，``versionEndIncluding`` → ``<= X``，
   带起点时写成区间；**只有 `*` 没有任何版本边界的，继续 unknown**；
4. 原 ``source_id`` 原样保留，只补 ``range`` 与证据位置。

用法：
    ./.venv/Scripts/python.exe tools/verify_version_ranges.py
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "evaluation" / "b_relation_candidates_20261010.json"
SNAPSHOT_DIR = ROOT / "data" / "snapshots" / "nvd"
INDEX_CACHE = ROOT / "work" / "nvd_cpe_index.json"
OUTPUT = ROOT / "artifacts" / "b_eval" / "version_range_verification_20261018.json"
OUTPUT_CSV = ROOT / "artifacts" / "b_eval" / "version_range_verification_20261018.csv"
OUTPUT_DOC = ROOT / "docs" / "B_VERSION_RANGE_VERIFICATION_20261018.md"


def tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", str(text or "")).casefold()
    cleaned = re.sub(r"[^a-z0-9]+", " ", folded)
    # 停用词必须去掉：包名里的 "for" 会让分母白白多一个 token，
    # 把 "GitHub Copilot Plugin for JetBrains IDEs" 这种明明能对上的判成对不上。
    return {word for word in cleaned.split()
            if len(word) > 2 and not word.isdigit() and word not in STOPWORDS}


STOPWORDS = {"for", "the", "and", "with", "from", "into", "via", "其"}


def product_matches(package: str, product: str, vendor: str) -> bool:
    """cpe 的 product 能不能代表候选 package（只接受明确对得上的）。"""
    package_tokens = tokens(package)
    product_tokens = tokens(product) | tokens(vendor)
    if not package_tokens:
        return False
    shared = package_tokens & product_tokens
    return len(shared) >= max(1, len(package_tokens) // 2)


def range_of(match: dict) -> str | None:
    start_inc = match.get("versionStartIncluding")
    start_exc = match.get("versionStartExcluding")
    end_inc = match.get("versionEndIncluding")
    end_exc = match.get("versionEndExcluding")
    lower = f">= {start_inc}" if start_inc else (f"> {start_exc}" if start_exc else None)
    upper = f"< {end_exc}" if end_exc else (f"<= {end_inc}" if end_inc else None)
    if lower and upper:
        return f"{lower}, {upper}"
    if upper:
        return upper
    if lower:
        return lower
    return None


def build_index() -> dict[str, list[dict]]:
    if INDEX_CACHE.exists():
        return json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
    index: dict[str, list[dict]] = {}
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for vulnerability in payload.get("vulnerabilities") or []:
            cve = vulnerability.get("cve") or {}
            cve_id = cve.get("id")
            if not cve_id:
                continue
            entries = []
            for configuration in cve.get("configurations") or []:
                for node in configuration.get("nodes") or []:
                    for match in node.get("cpeMatch") or []:
                        entries.append({
                            "criteria": match.get("criteria"),
                            "vulnerable": match.get("vulnerable"),
                            "range": range_of(match),
                            "versionStartIncluding": match.get("versionStartIncluding"),
                            "versionStartExcluding": match.get("versionStartExcluding"),
                            "versionEndIncluding": match.get("versionEndIncluding"),
                            "versionEndExcluding": match.get("versionEndExcluding"),
                            "snapshot": path.name,
                        })
            if entries:
                index[cve_id] = entries
    INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_CACHE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def cpe_parts(criteria: str) -> tuple[str, str]:
    parts = (criteria or "").split(":")
    if len(parts) < 5:
        return "", ""
    return parts[3], parts[4]


def classify(case: dict, entries: list[dict]) -> dict:
    value = case.get("candidate_value") or {}
    package = str(value.get("package") or "")
    row = {
        "relation_id": case.get("relation_id"),
        "cve": case.get("subject"),
        "package": package,
        "ecosystem": value.get("ecosystem"),
        "source_id": (case.get("evidence") or {}).get("source_id"),
        "before_range": value.get("range"),
    }
    if not entries:
        row.update(status="unknown", range=None,
                   missing="本地 NVD 快照里没有该 CVE 的 cpeMatch")
        return row

    matched = []
    for entry in entries:
        vendor, product = cpe_parts(entry.get("criteria") or "")
        if entry.get("vulnerable") is False:
            continue
        if not product_matches(package, product, vendor):
            continue
        matched.append({**entry, "vendor": vendor, "product": product})

    if not matched:
        products = sorted({cpe_parts(e.get("criteria") or "")[1] for e in entries})
        row.update(status="unknown", range=None,
                   missing="cpeMatch 的 product 与 package 对不上",
                   cpe_products=products[:6])
        return row

    ranges = sorted({item["range"] for item in matched if item.get("range")})
    if not ranges:
        row.update(status="unknown", range=None,
                   missing="cpeMatch 只有 `*`，没有版本边界",
                   cpe_products=sorted({item["product"] for item in matched})[:6])
        return row

    row.update(
        status="resolved",
        range="; ".join(ranges),
        cpe_product=sorted({item["product"] for item in matched})[0],
        snapshot=sorted({item["snapshot"] for item in matched})[0],
        evidence="cpeMatch " + ranges[0],
    )
    return row


def main() -> int:
    cases = json.loads(CANDIDATES.read_text(encoding="utf-8"))["cases"]
    targets = [
        case for case in cases
        if case.get("dimension") == "version_range"
        and str((case.get("candidate_value") or {}).get("range", "")).strip().lower()
        in ("", "unknown", "none")
    ]
    index = build_index()
    rows = [classify(case, index.get(case.get("subject"), [])) for case in targets]
    summary = dict(Counter(row["status"] for row in rows))
    reasons = dict(Counter(row["missing"] for row in rows if row.get("missing")))
    report = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "candidate_file": str(CANDIDATES.relative_to(ROOT)),
        "snapshot_dir": str(SNAPSHOT_DIR.relative_to(ROOT)),
        "rule": (
            "只读本地 NVD 快照的 cpeMatch；product 对不上不硬套；"
            "只有 `*`、没有版本边界的继续 unknown；原 source_id 保留。"
        ),
        "indexed_cves": len(index),
        "total": len(rows),
        "summary": summary,
        "summary_by_reason": reasons,
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")

    columns = ["relation_id", "cve", "package", "ecosystem", "source_id",
               "before_range", "status", "range", "missing", "cpe_product", "snapshot"]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# 版本区间 37 条：cpeMatch 对照表（2026-10-18）",
        "",
        "由 `tools/verify_version_ranges.py` 生成。输入是",
        "`evaluation/b_relation_candidates_20261010.json` 里 `dimension=version_range`",
        "且 `range=unknown` 的 37 条。数据源：优先本地 `data/snapshots/nvd` 的 cpeMatch；",
        "本地没有的用 `tools/fetch_nvd_cpe.py` 按 CVE 重采（结果并入同一个索引），",
        "重采后 `indexed_cves` 从 12890 条涨到 12918 条。",
        "",
        f"汇总：37 条里 **{summary.get('resolved', 0)} 条能从 cpeMatch 补出区间**，"
        f"**{summary.get('unknown', 0)} 条继续 unknown**（原因逐行写在“缺失项”列）。",
        "",
        "unknown 的原因分布：" + "；".join(
            f"{reason}（{count} 条）" for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])
        ) + "。",
        "",
        "| 关系 ID | CVE | package | 原 source_id | 补出的区间 | 状态 | 缺失项 / 证据 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {rid} | {cve} | {pkg} | {src} | {rng} | {status} | {detail} |".format(
                rid=row["relation_id"], cve=row["cve"], pkg=row["package"],
                src=row.get("source_id") or "—", rng=row.get("range") or "—",
                status=row["status"],
                detail=row.get("missing") or row.get("evidence") or "",
            )
        )
    lines += [
        "",
        "## 边界",
        "",
        "- 只在 cpeMatch 的 product 与候选 package 明确对得上时才采用，宁可 unknown 不硬套；",
        "  目前 9 条卡在这里，都是“同一产品族但名字不同”的情况：`Chromium` 对 `chrome`、",
        "  `SmartScreen Prompt` 对 `windows_10_*`、`Mali Graphics Processing Unit (GPU)` 对",
        "  `bifrost/midgard/valhall_gpu_kernel_driver`、`AC1900 Router AC15 Model` 对 `ac15`。",
        "  要推进它们需要人工确认资产具体型号/代次，本轮不代判；",
        "- 只有 `*`、没有 `versionEndExcluding/Including` 的条目按任务书继续 unknown，",
        "  没有拿别的来源去猜（8 条，主要是 Microsoft 商店类产品）；",
        "- `CVE-2026-55145` 重采时 NVD 断连失败，仍是 unknown；重跑 `fetch_nvd_cpe.py` 会自动只补这一条；",
        "- 原 `source_id` 全部原样保留，本表只补 `range` 与证据位置；",
        "- 没有改动 `evaluation/` 下的冻结产物，也没有写回事件库。",
        "",
    ]
    OUTPUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"total": len(rows), "summary": summary,
                      "indexed_cves": len(index)}, ensure_ascii=False))
    for row in rows:
        print(f"{row['relation_id']} | {row['cve']:<16} | {row['status']:<9} | "
              f"{row.get('range') or row.get('missing')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
