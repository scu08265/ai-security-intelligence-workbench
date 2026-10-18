"""A3：用故障注入证明"复测闭环"是真的在复测，而不是走过场。

两条边界：

1. **资产仍命中受影响区间 → 不能关闭。** 对在范围内的条目请求 ``verified``，
   系统必须降级为 ``fixed``、不写 ``closed_at``、并在 ``verification`` 里留下失败结论。
2. **资产升级到区间外 → 才关闭。** 真实改一次资产版本（合成演示资产），再逐条
   走单条 ``verified``，每条都要有 ``assessment_status_before/after`` 的复测证据。

全程走正式 HTTP 路由，不直接写库。

用法：
    ./.venv/Scripts/python.exe tools/verify_disposition_closure.py \
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
sys.path.insert(0, str(ROOT / "tools"))

from run_disposition_batch import Evidence, _event_ranges, smallest_safe_version  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dispositions(client: httpx.Client) -> list[dict[str, Any]]:
    payload = client.get("/api/dispositions", params={"limit": 1000}).json()
    return payload.get("items") or payload.get("dispositions") or []


def run(base: str, output_dir: Path, *, target_closes: int, operator: str,
        dry_run: bool, reset_to_version: str | None = None,
        skip_counterexample: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = Evidence(base, "a-ops", operator)
    result: dict[str, Any] = {"generated_at": _now(), "base_url": base, "dry_run": dry_run}

    with httpx.Client(base_url=base, timeout=120.0) as client:
        metrics_before = client.get("/api/dispositions/metrics").json()
        assets = {item["id"]: item for item in client.get("/api/assets").json()["items"]}
        rows = _dispositions(client)
        high_rows = [row for row in rows
                     if row.get("opened_priority") in {"critical", "high"}]
        if not high_rows:
            raise SystemExit("没有已登记的高优先级条目，先跑 tools/run_disposition_batch.py")

        asset_id = max(
            {row["asset_id"] for row in high_rows},
            key=lambda item: sum(1 for row in high_rows if row["asset_id"] == item),
        )
        asset = assets[asset_id]
        cohort = [row for row in high_rows if row["asset_id"] == asset_id]
        targets = [row for row in cohort if row.get("status") in {"in_progress", "fixed"}]
        if not targets and not reset_to_version:
            raise SystemExit("该资产上没有处于处置流转中的条目，可用 --reset-to-version 复位")

        # 可选：把演示资产放回"仍在受影响区间"的注入前状态，并让研判重新算成
        # affected。这样下面那条反例才是真的反例，关闭那条也才有
        # affected → not_affected 的 before/after，而不是两边都已经是 not_affected。
        reset: dict[str, Any] = {"applied": False}
        if reset_to_version and not dry_run:
            evidence.call(client, "POST", "/api/assets", {
                "id": asset_id,
                "name": asset.get("name"),
                "component": asset.get("component"),
                "ecosystem": asset.get("ecosystem"),
                "version": reset_to_version,
                "is_demo": bool(asset.get("is_demo")),
                "authorized": bool(asset.get("authorized", True)),
            })
            evidence.call(client, "POST", "/api/assessments/run", {})
            reopened = []
            for row in cohort:
                evidence.call(client, "PUT",
                             f"/api/dispositions/{row['event_id']}/{asset_id}", {
                                 "event_id": row["event_id"],
                                 "asset_id": asset_id,
                                 "status": "in_progress",
                                 "assignee": row.get("assignee") or "a-ops",
                                 "operator": operator,
                                 "note": "A3 复位：回到注入前的处置中状态",
                             })
                reopened.append(row["event_id"])
            targets = cohort
            asset = next(item for item in client.get("/api/assets").json()["items"]
                         if item["id"] == asset_id)
            reset = {"applied": True, "version": reset_to_version, "reopened": reopened}
            after_reset = client.get("/api/dispositions/metrics").json()
            reset["metrics_after_reset"] = {
                key: after_reset.get(key)
                for key in ("high_priority_total", "high_priority_closed",
                            "high_priority_registered", "high_priority_unopened",
                            "closure_rate", "registered_closure_rate")
            }
        result["reset"] = reset
        specs: list[str] = []
        for row in targets:
            event = evidence.call(client, "GET", f"/api/events/{row['event_id']}")["response"]
            specs.extend(_event_ranges(event))
        target_version = smallest_safe_version(specs)
        if target_version is None:
            raise SystemExit(f"算不出安全版本，受影响区间：{specs}")
        # 资产可能已经在安全版本上（例如上一轮已经升过）。这时不能再按
        # "最小安全版本"回写，否则会变成降级。当前版本已经躲开所有区间就保持不变。
        current = str(asset.get("version") or "").strip()
        if current:
            try:
                specs_parsed = [SpecifierSet(item) for item in specs]
                if all(Version(current) not in item for item in specs_parsed):
                    target_version = current
            except (InvalidSpecifier, InvalidVersion):
                pass
        result["subject"] = {
            "asset_id": asset_id,
            "component": asset.get("component"),
            "version_before": asset.get("version"),
            "is_demo": bool(asset.get("is_demo")),
            "target_version": target_version,
            "affected_ranges": sorted(set(specs)),
            "queue": [row["event_id"] for row in targets],
        }

        # ---- 边界 1：仍在区间内，关闭必须被拒绝 ----
        if skip_counterexample:
            result["counterexample"] = None
        else:
            counterexample = targets[0]
            body = {
                "event_id": counterexample["event_id"],
                "asset_id": asset_id,
                "status": "verified",
                "assignee": "a-ops",
                "operator": operator,
                "note": "A3 反例：资产仍在受影响区间，验证系统是否拒绝关闭",
            }
            step = evidence.call(client, "PUT",
                                 f"/api/dispositions/{counterexample['event_id']}/{asset_id}", body)
            payload = step["response"] or {}
            after = evidence.call(
                client, "GET",
                f"/api/dispositions/{counterexample['event_id']}/{asset_id}")["response"]
            # GET /api/dispositions/{event}/{asset} returns the disposition itself.
            disposition = after if isinstance(after, dict) else {}
            result["counterexample"] = {
                "event_id": counterexample["event_id"],
                "requested_status": body["status"],
                "applied_status": payload.get("applied_status"),
                "verification": payload.get("verification"),
                "closed_at": disposition.get("closed_at"),
                "stored_status": disposition.get("status"),
                "rejected": (
                    payload.get("applied_status") == "fixed"
                    and not disposition.get("closed_at")
                    and (payload.get("verification") or {}).get("passed") is False
                ),
            }

        # ---- 真实改一次资产版本（合成演示资产） ----
        upgrade = None
        if not dry_run:
            upgrade = evidence.call(client, "POST", "/api/assets", {
                "id": asset_id,
                "name": asset.get("name"),
                "component": asset.get("component"),
                "ecosystem": asset.get("ecosystem"),
                "version": target_version,
                "is_demo": bool(asset.get("is_demo")),
                "authorized": bool(asset.get("authorized", True)),
            })["response"]
            # 刻意不在这里重算研判：升级后仍保留升级前算出的 affected，
            # 让下面每条 verified 的复测自己去发现 not_affected，
            # 这样 verification.assessment_status_before/after 才是真的跃迁。
        result["upgrade"] = {
            "asset_id": asset_id,
            "version_before": asset.get("version"),
            "version_after": target_version,
            "response_version": (upgrade or {}).get("version"),
        }

        # ---- 边界 2：升级到区间外，逐条单条关闭 ----
        closes: list[dict[str, Any]] = []
        for row in targets[:max(0, target_closes)]:
            if dry_run:
                break
            step = evidence.call(client, "PUT",
                                 f"/api/dispositions/{row['event_id']}/{asset_id}", {
                                     "event_id": row["event_id"],
                                     "asset_id": asset_id,
                                     "status": "verified",
                                     "assignee": "a-ops",
                                     "operator": operator,
                                     "version_after": target_version,
                                     "note": "A3：合成资产升级到区间外后复测关闭",
                                 })
            payload = step["response"] or {}
            after = evidence.call(
                client, "GET", f"/api/dispositions/{row['event_id']}/{asset_id}")["response"]
            disposition = after if isinstance(after, dict) else {}
            verification = payload.get("verification") or {}
            closes.append({
                "event_id": row["event_id"],
                "requested_status": "verified",
                "applied_status": payload.get("applied_status"),
                "verification": {
                    "assessment_status_before": verification.get("assessment_status_before"),
                    "assessment_status_after": verification.get("assessment_status_after"),
                    "passed": verification.get("passed"),
                    "verdict": verification.get("verdict"),
                },
                "closed_at": disposition.get("closed_at"),
                "stored_status": disposition.get("status"),
                "version_after": disposition.get("version_after"),
            })
        result["closes"] = closes

        metrics_after = client.get("/api/dispositions/metrics").json()
        result["five_numbers"] = {
            key: {"before": metrics_before.get(key), "after": metrics_after.get(key)}
            for key in ("high_priority_total", "high_priority_closed",
                        "high_priority_registered", "high_priority_unopened",
                        "closure_rate", "registered_closure_rate")
        }
        result["status_breakdown"] = {
            "before": metrics_before.get("status_breakdown"),
            "after": metrics_after.get("status_breakdown"),
        }

    (output_dir / "verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "verification-evidence.json").write_text(
        json.dumps(evidence.to_json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8020")
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "artifacts" / "a_eval" / "disposition-operations-20261015")
    parser.add_argument("--closes", type=int, default=3,
                        help="升级后要逐条关闭几条（任务书要求 3 条）")
    parser.add_argument("--operator", default="tools/verify_disposition_closure.py")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset-to-version", default=None,
                        help="先把演示资产放回该版本并重算研判，用于生成干净的 before/after")
    parser.add_argument("--skip-counterexample", action="store_true",
                        help="A2 收尾用：资产已在区间外时不制造反例，只逐条复测关闭")
    args = parser.parse_args()

    result = run(args.base, args.output_dir, target_closes=args.closes,
                 operator=args.operator, dry_run=args.dry_run,
                 reset_to_version=args.reset_to_version,
                 skip_counterexample=args.skip_counterexample)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\noutput dir: {args.output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
