"""按 CVE 重采 NVD 的 cpeMatch，补进本地索引（离线快照没有覆盖的那些）。

只在本地快照确实没有该 CVE 时才用。写入的条目形状与
``tools/verify_version_ranges.py`` 的 ``build_index()`` 一致，
所以补完之后重跑 ``verify_version_ranges.py`` 就会自动用上。

用法（需要能访问 services.nvd.nist.gov；有 key 时设 NVD_API_KEY）：
    ./.venv/Scripts/python.exe tools/fetch_nvd_cpe.py --delay 6
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
INDEX = ROOT / "work" / "nvd_cpe_index.json"
REPORT = ROOT / "artifacts" / "b_eval" / "version_range_verification_20261018.json"


def range_of(match: dict) -> str | None:
    start_inc = match.get("versionStartIncluding")
    start_exc = match.get("versionStartExcluding")
    end_inc = match.get("versionEndIncluding")
    end_exc = match.get("versionEndExcluding")
    lower = f">= {start_inc}" if start_inc else (f"> {start_exc}" if start_exc else None)
    upper = f"< {end_exc}" if end_exc else (f"<= {end_inc}" if end_inc else None)
    if lower and upper:
        return f"{lower}, {upper}"
    return upper or lower


def entries_of(payload: dict) -> list[dict]:
    entries: list[dict] = []
    for vulnerability in payload.get("vulnerabilities") or []:
        cve = vulnerability.get("cve") or {}
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
                        "snapshot": "live:" + str(cve.get("id")),
                    })
    return entries


def missing_cves() -> list[str]:
    if not REPORT.exists():
        raise SystemExit("先跑 tools/verify_version_ranges.py 生成对照表")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    return sorted({row["cve"] for row in report["rows"]
                   if row["status"] == "unknown"
                   and "没有该 CVE 的 cpeMatch" in (row.get("missing") or "")})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cve", action="append", default=[])
    parser.add_argument("--delay", type=float, default=6.0,
                        help="无 key 时 NVD 限速，建议 6 秒")
    args = parser.parse_args()

    targets = args.cve or missing_cves()
    if not targets:
        print("没有需要重采的 CVE")
        return 0
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    headers = {"User-Agent": "ai-security-intelligence-workbench"}
    if os.getenv("NVD_API_KEY"):
        headers["apiKey"] = os.environ["NVD_API_KEY"]

    fetched, empty, failed = 0, 0, 0
    with httpx.Client(timeout=45.0, headers=headers) as client:
        for number, cve_id in enumerate(targets, 1):
            try:
                response = client.get(API, params={"cveId": cve_id})
                response.raise_for_status()
                entries = entries_of(response.json())
            except Exception as exc:  # noqa: BLE001 - reported per CVE
                failed += 1
                print(f"[{number}/{len(targets)}] {cve_id} 失败：{type(exc).__name__}: {exc}")
                continue
            if entries:
                index[cve_id] = entries
                fetched += 1
                print(f"[{number}/{len(targets)}] {cve_id} 采到 {len(entries)} 条 cpeMatch")
            else:
                empty += 1
                print(f"[{number}/{len(targets)}] {cve_id} 没有 cpeMatch（保持 unknown）")
            if number < len(targets):
                time.sleep(max(0.0, args.delay))
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"\n完成：{fetched} 条有数据，{empty} 条无数据，{failed} 条失败；索引已写回 {INDEX}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
