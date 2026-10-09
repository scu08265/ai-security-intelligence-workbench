"""把已有的人工标注按“关系内容”迁移到新批次的候选集上。

为什么不按 ``relation_id`` 迁移：候选集的 id 是按生成顺序编号的
（``BREL-<维度>-NNNN``）。一旦候选内容变化（例如 NVD CVSS 回填后新增了 cvss
候选），后续 id 会整体错位，旧标注就会张冠李戴。因此这里一律用
``(dimension, subject, normalized object)`` 对齐，并如实报告未对齐的数量。

用法::

    python tools/relabel_b_relation_candidates.py ^
        --from artifacts/b_eval/relation_candidates_labeled_all.json ^
        --system evaluation/b_relation_candidates_20261006.json ^
        --promote artifacts/b_eval/relation_new_positive_proposals_20261006.json ^
        --out artifacts/b_eval/relation_candidates_labeled_20261006.json

``--promote`` 是可选的显式“新增标注”清单：只有清单里写明的
``(dimension, subject, object)`` 才会被打上新标签，其余新候选保持
``pending_human_review``。这样每一处标注变化都能追溯到来源。
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


def _key(case: dict) -> tuple[str, str, str]:
    return (case["dimension"], case["subject"], _norm(case["object"]))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pending() -> dict:
    return {"status": "pending_human_review", "label": None,
            "verified_by": None, "verified_at": None, "note": None}


def relabel(source: dict, system: dict, promotions: dict | None) -> dict:
    carried_by_key: dict[tuple, dict] = {}
    for case in source.get("cases") or []:
        carried_by_key.setdefault(_key(case), case.get("annotation") or _pending())

    promotion_by_key = {_key(item): item for item in (promotions or {}).get("promotions", [])}

    cases: list[dict] = []
    counts = {"total": 0, "carried": 0, "promoted": 0, "pending": 0}
    seen_promotions: set[tuple] = set()
    for case in system.get("cases") or []:
        case = copy.deepcopy(case)
        key = _key(case)
        if key in promotion_by_key:
            promo = promotion_by_key[key]
            case["annotation"] = {
                "status": "human_verified",
                "label": promo["label"],
                "verified_by": promo.get("verified_by"),
                "verified_at": promo.get("verified_at"),
                "note": promo.get("note"),
            }
            case["promotion_evidence"] = promo.get("evidence")
            counts["promoted"] += 1
            seen_promotions.add(key)
        elif key in carried_by_key:
            case["annotation"] = carried_by_key[key]
            counts["carried"] += 1
        else:
            case["annotation"] = _pending()
            counts["pending"] += 1
        counts["total"] += 1
        cases.append(case)

    unmatched = [item for key, item in promotion_by_key.items()
                 if key not in seen_promotions]
    return {
        "schema_version": "b-relation-candidates-labeled-1.0",
        "counts": counts,
        "unmatched_promotions": unmatched,
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="按关系内容迁移人工标注到新候选集")
    parser.add_argument("--from", dest="source", type=Path, required=True,
                        help="已有的带标注候选文件（上一批次）")
    parser.add_argument("--system", type=Path, required=True,
                        help="新批次的系统候选文件（未标注）")
    parser.add_argument("--promote", type=Path, default=None,
                        help="可选：显式新增标注清单（promotions）")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    promotions = _load(args.promote) if args.promote else None
    result = relabel(_load(args.source), _load(args.system), promotions)
    result["source_labeled"] = str(args.source)
    result["system_output"] = str(args.system)
    if result["unmatched_promotions"]:
        print("警告：%d 条 promotion 没有匹配到候选：" % len(result["unmatched_promotions"]))
        for item in result["unmatched_promotions"]:
            print("   ", item.get("subject"), item.get("object"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("cases:", json.dumps(result["counts"], ensure_ascii=False))
    print("out:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
