"""按当前定稿口径列出每个来源的 streak 与降级判定。

决策 1（A2）定稿后，"会不会被降级"不再等于"最近几次是不是满分"：

* ``failed`` / ``stale``               → 计入 streak
* ``partial`` 且**零产出**              → 计入 streak
* ``partial`` 且有产出（例如 ghsa 撞抓取预算）→ 不计入，且打断 streak
* ``ok``                               → 打断 streak

输出一张表与一份 JSON，用来说明"无人值守时段实际还有几个来源在产出"。

用法：
    ./.venv/Scripts/python.exe tools/check_degradation_policy.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import self_healing, sources, storage  # noqa: E402


def evaluate() -> dict[str, Any]:
    runs = storage.list_runs(limit=None)
    states = storage.all_source_states()
    active = {entry["source_id"]: entry for entry in storage.active_source_degradations()}
    registered = [spec.id for spec in sources.SOURCES]
    unattended = list(sources.recommended_sources())

    rows: list[dict[str, Any]] = []
    for source_id in sorted(set(registered) | set(states)):
        state = states.get(source_id) or {}
        detail = self_healing.streak_detail(source_id, runs)
        streak = detail["streak"]
        decision = self_healing.degradation_for(source_id, streak, state)
        entry = active.get(source_id)
        rows.append({
            "source_id": source_id,
            "status": state.get("status"),
            "last_success": state.get("last_success"),
            "events_count": state.get("events_count"),
            "last_error": state.get("last_error"),
            "newest_attempt": detail["newest_attempt"],
            "streak": streak,
            "would_degrade": bool(decision),
            "action": (decision or entry or {}).get("action"),
            "failure_class": (decision or entry or {}).get("failure_class"),
            "currently_cooling_down": source_id in active,
            "in_unattended_set": source_id in unattended,
        })

    degraded_now = [row["source_id"] for row in rows if row["would_degrade"]]
    return {
        "generated_at": storage.utcnow(),
        "policy": {
            "threshold": self_healing.CONSECUTIVE_FAILURE_THRESHOLD,
            "cooldown_hours": self_healing.DEGRADE_COOLDOWN_HOURS,
            "counted_as_failure": ["failed", "stale", "partial（零产出）"],
            "not_counted_as_failure": ["ok", "partial（有产出）"],
        },
        "unattended_source_count": len(unattended),
        "would_degrade_today": degraded_now,
        "currently_cooling_down": sorted(active),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "reports" / "degradation-policy-check.json")
    args = parser.parse_args()

    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )

    header = f"{'来源':<18}{'状态':<10}{'最近一次':<12}{'采到':<6}{'streak':<8}{'降级?':<8}动作"
    print(header)
    print("-" * 78)
    for row in report["rows"]:
        attempt = row["newest_attempt"] or {}
        produced = attempt.get("produced")
        produced_text = "—" if produced is None else ("是" if produced else "否")
        print(
            f"{row['source_id']:<18}{str(row['status']):<10}{str(attempt.get('status')):<12}"
            f"{produced_text:<6}{row['streak']:<8}"
            f"{('是' if row['would_degrade'] else '否'):<8}{row['action'] or '—'}"
        )
    print()
    print(f"无人值守采集来源数：{report['unattended_source_count']}")
    print(f"按新口径今天会被降级的来源：{report['would_degrade_today'] or '（无）'}")
    print(f"当前处于冷却中的来源：{report['currently_cooling_down'] or '（无）'}")
    print(f"\noutput: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
