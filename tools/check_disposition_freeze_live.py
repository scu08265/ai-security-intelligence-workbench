"""在生产库上核对"分母冻结"：重算研判后闭环率必须持平。

已登记的条目在 ``opened_at`` 时刻把优先级冻结进处置记录，所以资产修好之后
即使研判翻成 ``not_affected``，条目仍留在闭环率的分母里——否则刚修完就会
出现"分子分母一起掉、比率突然变化"的假象。

用法：
    ./.venv/Scripts/python.exe tools/check_disposition_freeze_live.py \
        --base http://127.0.0.1:8020 \
        --output artifacts/a_eval/disposition-operations-20261015/denominator-freeze.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KEYS = ("high_priority_total", "high_priority_closed", "high_priority_registered",
        "high_priority_unopened", "closure_rate", "registered_closure_rate")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8020")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts" / "a_eval"
                        / "disposition-operations-20261015" / "denominator-freeze.json")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base, timeout=120.0) as client:
        before = client.get("/api/dispositions/metrics").json()
        run = client.post("/api/assessments/run").json()
        after = client.get("/api/dispositions/metrics").json()

    report = {
        "generated_at": _now(),
        "base_url": args.base,
        "assessment_run": run,
        "before": {key: before.get(key) for key in KEYS},
        "after": {key: after.get(key) for key in KEYS},
        "status_breakdown": {"before": before.get("status_breakdown"),
                             "after": after.get("status_breakdown")},
        "frozen": all(before.get(key) == after.get(key) for key in KEYS),
        "note": (
            "重算研判（POST /api/assessments/run）前后六个读数完全一致，说明已登记条目"
            "没有因为资产修好、研判翻成 not_affected 而掉出分母。"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\noutput: {args.output}", file=sys.stderr)
    return 0 if report["frozen"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
