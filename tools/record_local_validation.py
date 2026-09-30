"""Record local equivalents of the CI checks and explicit blockers."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def _run(name: str, command: list[str]) -> dict:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {
        "name": name,
        "command": command,
        "passed": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def main() -> int:
    node = shutil.which("node")
    pytest_temp = ROOT / "work" / "pytest-basetemp"
    pytest_temp.mkdir(parents=True, exist_ok=True)
    checks = [
        _run("pytest", [
            str(PYTHON), "-m", "pytest", "-q",
            f"--basetemp={pytest_temp}",
        ]),
        _run("pip_check", [str(PYTHON), "-m", "pip", "check"]),
    ]
    if node:
        checks.append(_run("frontend_syntax", [node, "--check", "app/static/app.js"]))

    compose_error = None
    try:
        yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
        compose_ok = True
    except Exception as exc:  # noqa: BLE001 - validation evidence
        compose_ok = False
        compose_error = f"{type(exc).__name__}: {exc}"
    checks.append({
        "name": "compose_yaml",
        "command": ["yaml.safe_load", "docker-compose.yml"],
        "passed": compose_ok,
        "exit_code": 0 if compose_ok else 1,
        "stderr_tail": compose_error or "",
    })

    docker = shutil.which("docker")
    docker_report_path = ROOT / "reports" / "docker-validation.json"
    docker_report = {}
    if docker_report_path.exists():
        docker_report = json.loads(
            docker_report_path.read_text(encoding="utf-8-sig")
        )
    docker_verified = bool(docker_report.get("verified"))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "checks": checks,
        "all_local_checks_passed": all(item["passed"] for item in checks),
        "docker": {
            "available": bool(docker) or docker_verified,
            "path": docker,
            "build_verified": docker_verified,
            "healthy_container_verified": docker_verified,
            "container_health": docker_report.get("container_health"),
            "blocker": None if docker_verified else (
                None if docker else "Docker CLI/daemon is not available to this sandbox account."
            ),
        },
    }
    output = ROOT / "reports" / "local-validation.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "all_local_checks_passed": payload["all_local_checks_passed"],
        "docker_available": payload["docker"]["available"],
    }, ensure_ascii=False))
    return 0 if payload["all_local_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
