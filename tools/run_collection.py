"""One-shot collector entry point for Task Scheduler or cron.

Every invocation is already persisted in SQLite by ``agents.run_collection``.
This wrapper also appends one immutable JSONL row per source for convenient
seven-day evidence export.  It never creates historical rows on its own.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import agents, config, storage  # noqa: E402

DEFAULT_SOURCES = "cisa_kev,openalex,owasp_genai,nist_ai_rmf,mitre_atlas,eu_ai_act"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one auditable intelligence collection")
    parser.add_argument("--sources", default=DEFAULT_SOURCES,
                        help="comma-separated registered source IDs")
    parser.add_argument("--output", type=Path,
                        default=config.DATA_DIR / "evidence" / "collection_runs.jsonl")
    parser.add_argument("--close-gaps", action="store_true",
                        help="enrich every collected event inline (normally leave off)")
    parser.add_argument("--enrich-limit", type=int, default=6,
                        help="post-collection vulnerability enrichment budget; 0 disables")
    args = parser.parse_args()
    source_ids = [item.strip() for item in args.sources.split(",") if item.strip()]
    unknown = [item for item in source_ids if item not in agents.sources.BY_ID]
    if unknown:
        parser.error(f"unknown source IDs: {', '.join(unknown)}")

    storage.init_db()
    result = agents.run_collection(source_ids, close_gaps=args.close_gaps)
    enrichment = agents.run_enrichment(limit=args.enrich_limit) if args.enrich_limit > 0 else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8", newline="\n") as handle:
        for source in result["results"]:
            row = {
                "run_id": result["run_id"],
                "source_id": source["source_id"],
                "started_at": result["started_at"],
                "finished_at": result["finished_at"],
                "status": source["status"],
                "fetched": source["fetched"],
                "kept": source["kept"],
                "added": source["events_added"],
                "updated": source["events_updated"],
                "error": source["error"],
                "events": source["events"],
                "enrichment_run_id": (enrichment or {}).get("run_id"),
            }
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({
        "run_id": result["run_id"], "status": result["status"],
        "started_at": result["started_at"], "finished_at": result["finished_at"],
        "sources": len(result["results"]), "evidence_file": str(args.output),
        "enrichment": enrichment,
    }, ensure_ascii=False))
    return 0 if result["status"] in {"completed", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
