"""Generate a CycloneDX SBOM with Syft and run one bounded asset assessment.

The target is read only. Dependencies are inventoried from manifests; they are
not installed, imported, started, scanned over the network, or exploited.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import cyclonedx_assets  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path,
                        default=ROOT / "examples" / "asset_simulation" / "vllm-lab")
    parser.add_argument("--syft", type=Path,
                        default=ROOT / "artifacts" / "tools" / "syft" / "syft.exe")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts" / "sbom" / "vllm-lab.cdx.json")
    parser.add_argument("--result", type=Path,
                        default=ROOT / "artifacts" / "sbom" / "vllm-lab-assessment.json")
    parser.add_argument("--reuse-existing", action="store_true",
                        help="Reuse the existing immutable SBOM snapshot instead of generating a new one")
    parser.add_argument("--authorized", action="store_true",
                        help="Explicitly include this simulated batch in impact assessment")
    args = parser.parse_args()
    if not args.authorized:
        parser.error("--authorized is required; assessment scope is never inferred from an SBOM")
    if not args.syft.is_file():
        parser.error(f"Syft executable not found: {args.syft}")
    if not args.target.is_dir():
        parser.error(f"simulation target not found: {args.target}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.reuse_existing or not args.output.is_file():
        command = [str(args.syft), f"dir:{args.target}",
                   "-o", f"cyclonedx-json={args.output}"]
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode:
            return completed.returncode

    bom = json.loads(args.output.read_text(encoding="utf-8"))
    preview = cyclonedx_assets.preview(bom)
    imported = cyclonedx_assets.import_bom(bom, authorized=True)
    assessment = cyclonedx_assets.assess_batch(imported["batch_id"])
    result = {
        "tool": subprocess.check_output([str(args.syft), "version"], text=True),
        "target": str(args.target.resolve()),
        "sbom_path": str(args.output.resolve()),
        "preview": {key: value for key, value in preview.items() if key != "assets"},
        "components": [
            {"name": item["component"], "version": item["version"],
             "purl": item["sbom"]["purl"], "bom_ref": item["sbom"]["bom_ref"]}
            for item in preview["assets"]
        ],
        "import": imported,
        "assessment": assessment,
    }
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "batch_id": imported["batch_id"],
        "components": preview["deduplicated_asset_count"],
        "idempotent": imported["idempotent"],
        "relationships": assessment["assessment_relationship_count"],
        "status_counts": assessment["status_counts"],
        "result": str(args.result.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
