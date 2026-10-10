"""Record the production backup identity and rehearse a restore from it.

Writes ``db-backup.json`` next to the live-closure evidence: which file is the
production database, which file is its backup, the SHA256 of both, and the
result of copying the backup into a scratch directory and reading it back.
No SQL is executed against the production database itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
TABLES = ("events", "assets", "assessments", "assessment_dispositions", "runs")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _describe(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "sha256": _sha256(path),
    }


def _inspect(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        available = {
            row[0] for row in connection.execute("select name from sqlite_master where type='table'")
        }
        counts = {}
        for table in TABLES:
            counts[table] = (
                connection.execute(f"select count(*) from {table}").fetchone()[0]
                if table in available
                else None
            )
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    return {"row_counts": counts, "integrity_check": integrity}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-db", type=Path, default=ROOT / "data" / "intel.sqlite")
    parser.add_argument(
        "--backup",
        type=Path,
        default=ROOT / "artifacts" / "backups" / "intel-20261009-213026.sqlite",
    )
    parser.add_argument(
        "--baseline-db",
        type=Path,
        default=ROOT / "work" / "disposition-trial-cdx" / "intel.sqlite",
        help="pre-run copy that carries the closure baseline used by the evidence pack",
    )
    parser.add_argument(
        "--evidence-dir", type=Path,
        default=ROOT / "artifacts" / "a_eval" / "disposition-live-closure-20261008",
    )
    parser.add_argument("--work-dir", type=Path, default=ROOT / "work" / "disposition-restore-drill")
    args = parser.parse_args()

    production = args.production_db.resolve()
    backup = args.backup.resolve()
    baseline = args.baseline_db.resolve()
    for required, label in ((production, "production"), (backup, "backup"), (baseline, "baseline")):
        if not required.is_file():
            raise SystemExit(f"{label} database not found: {required}")

    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    restored = work / "intel-restored.sqlite"
    shutil.copy2(backup, restored)

    before = _describe(backup)
    after = _describe(restored)
    source_state = _inspect(backup)
    restored_state = _inspect(restored)

    payload = {
        "generated_at": _utcnow(),
        "production_database": {**_describe(production), **_inspect(production)},
        "backup": {
            **before,
            **source_state,
            "created_by": (ROOT / "scripts" / "backup_database.ps1").name,
            "note": ("任务书里写明的 artifacts/backups/intel-20261008-211841.sqlite 在本机不存在；"
                     "这是本轮实际存在的生产库备份，先备份再操作。"),
        },
        "closure_baseline_database": {
            **_describe(baseline),
            **_inspect(baseline),
            "note": ("闭环基线副本：16 个资产、117 条研判、0 条处置记录。"
                     "2026-10-08 证据包就是在这份基线上走完整 API 流程生成的。"),
        },
        "restore_drill": {
            "restored_to": str(restored),
            "restored_sha256": after["sha256"],
            "sha256_matches_backup": before["sha256"] == after["sha256"],
            "row_counts_match": source_state["row_counts"] == restored_state["row_counts"],
            "integrity_check": restored_state["integrity_check"],
            "read_only_after_restore": True,
            "passed": (
                before["sha256"] == after["sha256"]
                and source_state["row_counts"] == restored_state["row_counts"]
                and restored_state["integrity_check"] == "ok"
            ),
        },
        "rollback_commands": [
            "Stop-Process -Name python -ErrorAction SilentlyContinue  # 停掉本地服务",
            f"Copy-Item '{production}' "
            f"'{production.with_suffix('.before-rollback.sqlite')}' -Force",
            f"Copy-Item '{backup}' '{production}' -Force",
            r".\.venv\Scripts\python.exe -m uvicorn app.api:app --port 8000  # 重新启动",
            "Invoke-RestMethod http://127.0.0.1:8000/api/health  # 确认版本与健康状态",
        ],
        "rollback_note": (
            "回滚是文件级替换：把 backups 里的 sqlite 覆盖回 data/intel.sqlite。"
            "本条记录只做恢复演练（复制到 scratch 目录并校验哈希与行数），未替换生产库。"
        ),
    }

    target = args.evidence_dir.resolve() / "db-backup.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "written": str(target),
        "backup_sha256": before["sha256"],
        "restore_drill_passed": payload["restore_drill"]["passed"],
        "production_row_counts": payload["production_database"]["row_counts"],
        "baseline_row_counts": payload["closure_baseline_database"]["row_counts"],
    }, ensure_ascii=False, indent=2))
    return 0 if payload["restore_drill"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
