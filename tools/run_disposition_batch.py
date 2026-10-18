"""A1：用新入口把待处置队列真实推进一批，并留下可核验的证据。

走的全部是正式 HTTP 路由（不是直接写库）：

* ``GET  /api/dispositions/metrics``     登记前后各读一次
* ``GET  /api/dispositions/pending``     47/5 条待处置队列
* ``GET  /api/events/{id}`` 与 ``GET /api/assets``  取受影响区间与资产版本
* ``POST /api/dispositions/batch``       逐条校验的批量登记入口
* ``PUT  /api/dispositions/{e}/{a}``     单条登记（``verified`` 只能走这条，触发系统复测）

分类规则（与任务书一致）：

1. ``already_out_of_range``  资产版本已不在受影响区间 → 单条走 ``verified``；
2. ``synthetic_actionable``  合成资产且升级目标可判定 → 批量登记 ``in_progress``；
3. ``not_actionable``        判定不了、资产不真实、或区间无法解析 → **不登记**，写明原因。

工具不会把没做的事登记成已闭环：``verified`` 一律走单条路由并接受系统复测结果，
批量入口只用于 ``in_progress``。

用法：
    ./.venv/Scripts/python.exe tools/run_disposition_batch.py \
        --base http://127.0.0.1:8020 \
        --output-dir artifacts/a_eval/disposition-operations-20261015
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_ASSIGNEE = "a-ops"
DEFAULT_OPERATOR = "tools/run_disposition_batch.py"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _candidates(spec_text: str) -> list[str]:
    """从 ``< 0.29.0`` / ``<= 0.26.0`` 这类区间里推出候选升级版本。"""
    token = spec_text.strip().split()[-1] if spec_text.strip() else ""
    if not token:
        return []
    out = [token]
    parts = token.split(".")
    if len(parts) >= 2 and parts[-1].isdigit():
        bumped = [*parts[:-1], str(int(parts[-1]) + 1)]
        out.append(".".join(bumped))
    return out


def smallest_safe_version(specs: list[str]) -> str | None:
    """给出同时躲开所有受影响区间的最小版本，作为演示升级目标。

    只用于合成演示资产：它是"要让复测通过需要升到哪一版"的算术结果，
    不代表生产环境已经发布过这个版本。
    """
    parsed: list[SpecifierSet] = []
    for spec in specs:
        try:
            parsed.append(SpecifierSet(spec))
        except InvalidSpecifier:
            return None
    if not parsed:
        return None
    candidates: list[str] = []
    for spec in specs:
        candidates.extend(_candidates(spec))
    safe: list[Version] = []
    for candidate in candidates:
        try:
            version = Version(candidate)
        except InvalidVersion:
            continue
        if all(version not in spec for spec in parsed):
            safe.append(version)
    return str(min(safe)) if safe else None


class Evidence:
    """Every request/response pair, in order, with timestamps."""

    def __init__(self, base: str, assignee: str, operator: str) -> None:
        self.base = base
        self.assignee = assignee
        self.operator = operator
        self.steps: list[dict[str, Any]] = []

    def call(self, client: httpx.Client, method: str, path: str,
             body: Any = None) -> dict[str, Any]:
        at = _now()
        response = client.request(method, path, json=body) if body is not None \
            else client.request(method, path)
        try:
            payload = response.json()
        except ValueError:
            payload = response.text[:500]
        step = {
            "at": at,
            "method": method,
            "path": path,
            "request": body,
            "status_code": response.status_code,
            "response": payload,
        }
        self.steps.append(step)
        return step

    def to_json(self) -> dict[str, Any]:
        return {
            "generated_at": _now(),
            "base_url": self.base,
            "assignee": self.assignee,
            "operator": self.operator,
            "steps": self.steps,
        }


def _event_ranges(event: dict[str, Any]) -> list[str]:
    return [
        str(item.get("range"))
        for item in (event.get("affected") or [])
        if item.get("range")
    ]


def classify(item: dict[str, Any], event: dict[str, Any],
             asset: dict[str, Any]) -> dict[str, Any]:
    """一条待处置条目的分类与依据（只读，不写库）。"""
    specs = _event_ranges(event)
    version = str(asset.get("version") or "")
    status = str(item.get("assessment_status") or "")
    base = {
        "event_id": item.get("event_id"),
        "asset_id": item.get("asset_id"),
        "priority": item.get("priority"),
        "assessment_status": status,
        "component": asset.get("component"),
        "asset_version": version,
        "asset_is_demo": bool(asset.get("is_demo")),
        "affected_ranges": specs,
    }
    if not specs:
        return {**base, "category": "not_actionable",
                "reason": "事件没有可解析的受影响区间，无法判定动作"}
    if status != "affected":
        return {**base, "category": "already_out_of_range",
                "reason": f"当前研判为 {status}，不在受影响区间",
                "action": "single_verified"}
    if not asset.get("is_demo"):
        return {**base, "category": "not_actionable",
                "reason": "真实资产：本机没有该资产的变更授权，不代做升级"}
    target = smallest_safe_version(specs)
    if target is None:
        return {**base, "category": "not_actionable",
                "reason": f"受影响区间无法解析为可比较的版本：{specs}"}
    if Version(target) <= Version(version or "0"):
        return {**base, "category": "not_actionable",
                "reason": f"算出的安全版本 {target} 不高于当前版本 {version}"}
    return {**base, "category": "synthetic_actionable",
            "reason": f"合成资产且升级目标可判定：{version} → {target}",
            "target_version": target,
            "action": "batch_in_progress"}


def run(base: str, output_dir: Path, *, assignee: str, operator: str,
        note: str, dry_run: bool) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Evidence(base, assignee, operator)

    with httpx.Client(base_url=base, timeout=60.0) as client:
        before = evidence.call(client, "GET", "/api/dispositions/metrics")["response"]
        queue = evidence.call(client, "GET", "/api/dispositions/pending",
                              None)["response"]
        assets = {item["id"]: item
                  for item in evidence.call(client, "GET", "/api/assets")["response"]["items"]}

        classified: list[dict[str, Any]] = []
        for item in queue.get("items") or []:
            event = evidence.call(
                client, "GET", f"/api/events/{item['event_id']}",
            )["response"]
            asset = assets.get(item["asset_id"]) or {}
            classified.append(classify(item, event, asset))

        batch_items = [
            {
                "event_id": row["event_id"],
                "asset_id": row["asset_id"],
                "status": "in_progress",
                "assignee": assignee,
                "note": note,
                "version_before": row["asset_version"],
            }
            for row in classified if row["category"] == "synthetic_actionable"
        ]
        batch_result: dict[str, Any] | None = None
        if batch_items and not dry_run:
            batch_result = evidence.call(
                client, "POST", "/api/dispositions/batch", {"items": batch_items},
            )["response"]

        verified_results: list[dict[str, Any]] = []
        for row in classified:
            if row["category"] != "already_out_of_range" or dry_run:
                continue
            body = {
                "event_id": row["event_id"],
                "asset_id": row["asset_id"],
                "status": "verified",
                "assignee": assignee,
                "operator": operator,
            }
            step = evidence.call(
                client, "PUT",
                f"/api/dispositions/{row['event_id']}/{row['asset_id']}", body,
            )
            verified_results.append({
                "event_id": row["event_id"],
                "asset_id": row["asset_id"],
                "status_code": step["status_code"],
                "requested_status": (step["response"] or {}).get("requested_status"),
                "applied_status": (step["response"] or {}).get("applied_status"),
                "verification": (step["response"] or {}).get("verification"),
            })

        after = before if dry_run else \
            evidence.call(client, "GET", "/api/dispositions/metrics")["response"]

    unregistered = [
        {"event_id": row["event_id"], "asset_id": row["asset_id"],
         "category": row["category"], "reason": row["reason"]}
        for row in classified if row["category"] == "not_actionable"
    ]
    summary = {
        "generated_at": _now(),
        "base_url": base,
        "dry_run": dry_run,
        "assignee": assignee,
        "counts": {
            "pending": len(classified),
            "synthetic_actionable": sum(1 for r in classified if r["category"] == "synthetic_actionable"),
            "already_out_of_range": sum(1 for r in classified if r["category"] == "already_out_of_range"),
            "not_actionable": len(unregistered),
        },
        "five_numbers": {
            "before": {k: before.get(k) for k in
                       ("high_priority_total", "high_priority_registered",
                        "high_priority_unopened", "closure_rate",
                        "registered_closure_rate")},
            "after": {k: after.get(k) for k in
                      ("high_priority_total", "high_priority_registered",
                       "high_priority_unopened", "closure_rate",
                       "registered_closure_rate")},
        },
        "batch_result": batch_result,
        "single_verified": verified_results,
        "unregistered": unregistered,
    }

    (output_dir / "queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "classification.json").write_text(
        json.dumps({"generated_at": _now(), "items": classified},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "metrics-before.json").write_text(
        json.dumps(before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "metrics-after.json").write_text(
        json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "evidence.json").write_text(
        json.dumps(evidence.to_json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8020")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "artifacts" / "a_eval" / "disposition-operations-20261015")
    parser.add_argument("--assignee", default=DEFAULT_ASSIGNEE)
    parser.add_argument("--operator", default=DEFAULT_OPERATOR)
    parser.add_argument("--note",
                        default="A1：合成演示资产登记处置中，处置前版本见 version_before")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run(args.base, args.output_dir, assignee=args.assignee,
                  operator=args.operator, note=args.note, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\noutput dir: {args.output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
