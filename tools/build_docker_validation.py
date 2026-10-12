"""Record the Docker acceptance evidence in ``reports/docker-validation.json``.

Step 2 of the local container acceptance.  ``scripts/run_docker_acceptance.cmd``
builds the image, starts the Compose stack and captures the raw log; this script
reads back the *live* container state and writes the evidence file the report
cites.

The checks mirror the ``container`` job in ``.github/workflows/ci.yml``: the
Compose file must validate, the container must be running and healthy, and the
health payload must report the version in ``VERSION``.  Every value is read from
the running stack; when a check does not pass the field is reported as false
instead of being filled in with an assumption.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = "ai-security-intelligence-workbench"
IMAGE = "ai-security-intelligence-workbench"

# Fallbacks for a CLI that is installed but not on this shell's PATH.
DOCKER_CANDIDATES = (
    r"D:\Docker\Docker\resources\bin\docker.exe",
    r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
)

# `docker compose config` prints the resolved environment and `docker inspect`
# prints the container's Env, so the captured log is the one artifact where a
# credential could reach the repository by accident.  These patterns and the
# values from .env are checked before the evidence is declared verified; only
# the file and line are reported, never the value.
SECRET_PATTERNS = (
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("github_fine_grained_token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("api_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
)
SECRET_NAME_HINTS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "WEBHOOK")
EVIDENCE_FILES = (
    "reports/docker-acceptance.log",
    "reports/docker-acceptance.complete",
    "reports/docker-validation.json",
)


def _environment_secret_values() -> list[str]:
    """Values of secret-looking names in .env, used only for substring checks."""
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return []
    values: list[str] = []
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        name, _, value = entry.partition("=")
        value = value.strip().strip('"').strip("'")
        if len(value) < 8:
            continue
        if any(hint in name.upper() for hint in SECRET_NAME_HINTS):
            values.append(value)
    return values


def _credential_findings() -> list[dict]:
    secrets = _environment_secret_values()
    findings: list[dict] = []
    for name in EVIDENCE_FILES:
        path = ROOT / name
        if not path.is_file():
            continue
        for index, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1,
        ):
            matched = [label for label, pattern in SECRET_PATTERNS if pattern.search(line)]
            if any(value in line for value in secrets):
                matched.append("value_from_env_file")
            for label in matched:
                findings.append({"file": name, "line": index, "match": label})
    return findings


def _docker() -> str | None:
    found = shutil.which("docker")
    if found:
        return found
    for candidate in DOCKER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


def _run(docker: str, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [docker, *args], cwd=ROOT, capture_output=True, text=True,
    )
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    return result.returncode, output


def _health(port: int) -> tuple[int, dict]:
    """Return (http_status, payload).  A refused connection reports status 0."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/health", timeout=10,
        ) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except (OSError, ValueError):
        return 0, {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-port", type=int, default=18000)
    parser.add_argument("--output", default="reports/docker-validation.json")
    args = parser.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    docker = _docker()
    if not docker:
        print(json.dumps({
            "version": version,
            "verified": False,
            "reason": "docker CLI not found on PATH or in a known install location",
        }, ensure_ascii=False, indent=2))
        return 2

    compose_code, compose_output = _run(docker, "compose", "config")
    client_code, client_version = _run(docker, "version", "--format", "{{.Client.Version}}")
    server_code, server_version = _run(docker, "version", "--format", "{{.Server.Version}}")
    image_code, _ = _run(docker, "image", "inspect", f"{IMAGE}:{version}")
    inspect_code, inspect_output = _run(
        docker, "inspect", "--format",
        "{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        CONTAINER,
    )
    running, _, health = inspect_output.partition("|")
    http_status, payload = _health(args.host_port)

    container_health = health or None
    reported_version = payload.get("version")
    credential_findings = _credential_findings()
    checks = {
        "compose_config_valid": compose_code == 0,
        "docker_server_available": server_code == 0,
        "image_built": image_code == 0,
        "container_running": inspect_code == 0 and running.strip().lower() == "true",
        "container_healthy": container_health == "healthy",
        "health_endpoint_reachable": http_status == 200,
        "health_status_ok": payload.get("status") == "ok",
        "reported_version_matches_version_file": reported_version == version,
        "evidence_has_no_credentials": not credential_findings,
    }
    verified = all(checks.values())

    report = {
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "docker_runtime_verified": verified,
        "docker_cli": docker,
        "docker_client": client_version if client_code == 0 else None,
        "docker_server": server_version if server_code == 0 else None,
        "compose_config_valid": checks["compose_config_valid"],
        "compose_config_error": None if compose_code == 0 else compose_output[:500],
        "image": f"{IMAGE}:{version}",
        "container_name": CONTAINER,
        "container_running": checks["container_running"],
        "container_health": container_health,
        "host_port": args.host_port,
        "health_endpoint_http_status": http_status,
        "health_response": payload or None,
        "checks": checks,
        "credential_findings": credential_findings,
        "evidence_log": "reports/docker-acceptance.log",
        "verified": verified,
    }

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output.relative_to(ROOT)),
        "verified": verified,
        "checks": checks,
    }, ensure_ascii=False, indent=2))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
