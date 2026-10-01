"""Run and record a real Docker rollback from 0.2.2 to 0.2.1 and back."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "reports" / "rollback-validation.json"
COMPOSE_OVERRIDE = ROOT / "work" / "rollback-compose.override.yml"
IMAGE_REPOSITORY = "ai-security-intelligence-workbench"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _docker() -> str:
    candidates = [
        shutil.which("docker"),
        r"C:\Program Files\Docker\Docker\resources\bin\docker.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Docker CLI was not found.")


def _run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=merged_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return completed.stdout.strip()


def _image_id(docker: str, version: str) -> str:
    image = f"{IMAGE_REPOSITORY}:{version}"
    return _run([docker, "image", "inspect", image, "--format", "{{.Id}}"])


def _image_has_version(docker: str, version: str) -> bool:
    image = f"{IMAGE_REPOSITORY}:{version}"
    try:
        values = json.loads(_run([
            docker, "image", "inspect", image, "--format", "{{json .Config.Env}}",
        ]))
    except (RuntimeError, json.JSONDecodeError):
        return False
    return f"APP_VERSION={version}" in values


def _build_old_image(docker: str, version: str) -> None:
    archive = ROOT / "work" / f"rollback-{version}.tar"
    source_dir = Path(tempfile.mkdtemp(prefix=f"rollback-{version}-", dir=ROOT / "work"))
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run([
            "git", "-c", "safe.directory=*", "archive", "--format=tar",
            f"--output={archive}", f"v{version}",
        ])
        with tarfile.open(archive, "r") as bundle:
            bundle.extractall(source_dir)
        _run([
            docker, "build",
            "--build-arg", f"APP_VERSION={version}",
            "-t", f"{IMAGE_REPOSITORY}:{version}",
            ".",
        ], cwd=source_dir)
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(source_dir, ignore_errors=True)


def _build_current_image(docker: str, version: str) -> None:
    _run([
        docker, "build",
        "--build-arg", f"APP_VERSION={version}",
        "-t", f"{IMAGE_REPOSITORY}:{version}",
        ".",
    ])


def _compose(docker: str, host_port: int, version: str, action: str) -> str:
    command = [
        docker, "compose",
        "-p", "ai-security-rollback-validation",
        "-f", str(ROOT / "docker-compose.yml"),
        "-f", str(COMPOSE_OVERRIDE),
    ]
    if action == "up":
        command.extend(["up", "-d", "--no-build"])
    elif action == "down":
        command.extend(["down", "--remove-orphans"])
    else:
        raise ValueError(action)
    return _run(command, env={
        "APP_VERSION": version,
        "HOST_PORT": str(host_port),
    })


def _wait_health(base_url: str, expected_version: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "health endpoint did not respond"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/health", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "ok" and payload.get("version") == expected_version:
                return payload
            last_error = f"unexpected health payload: {payload}"
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(
        f"{base_url}/api/health did not report version {expected_version}: {last_error}"
    )


def _backup(docker: str) -> str:
    del docker
    if shutil.which("powershell"):
        return _run([
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(ROOT / "scripts" / "backup_database.ps1"),
        ])
    raise RuntimeError("PowerShell was not found.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-port", type=int, default=18001)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    report: dict[str, Any] = {
        "version": "0.2.2",
        "generated_at": _utcnow(),
        "status": "running",
        "rollback_target": "0.2.1",
        "docker_runtime_verified": False,
    }
    docker = ""
    try:
        docker = _docker()
        _run([docker, "version", "--format", "{{.Server.Version}}"])
        report["docker_runtime_verified"] = True
        report["docker_server_version"] = _run([
            docker, "version", "--format", "{{.Server.Version}}",
        ])

        if not _image_has_version(docker, "0.2.1"):
            report["build_0_2_1"] = "started"
            _build_old_image(docker, "0.2.1")
            report["build_0_2_1"] = "completed"
        if not _image_has_version(docker, "0.2.2"):
            report["build_0_2_2"] = "started"
            _build_current_image(docker, "0.2.2")
            report["build_0_2_2"] = "completed"

        report["image_ids"] = {
            "0.2.1": _image_id(docker, "0.2.1"),
            "0.2.2": _image_id(docker, "0.2.2"),
        }
        report["backup_output"] = _backup(docker)

        COMPOSE_OVERRIDE.parent.mkdir(parents=True, exist_ok=True)
        COMPOSE_OVERRIDE.write_text(
            "\n".join([
                "services:",
                "  workbench:",
                "    container_name: ai-security-intelligence-workbench-rollback",
                "    ports:",
                f'      - "127.0.0.1:{args.host_port}:8000"',
                "",
            ]),
            encoding="utf-8",
        )
        base_url = f"http://127.0.0.1:{args.host_port}"

        _compose(docker, args.host_port, "0.2.2", "up")
        report["before_rollback"] = _wait_health(base_url, "0.2.2", args.timeout_seconds)

        _compose(docker, args.host_port, "0.2.2", "down")
        _compose(docker, args.host_port, "0.2.1", "up")
        report["after_rollback"] = _wait_health(base_url, "0.2.1", args.timeout_seconds)

        _compose(docker, args.host_port, "0.2.1", "down")
        _compose(docker, args.host_port, "0.2.2", "up")
        report["after_restore"] = _wait_health(base_url, "0.2.2", args.timeout_seconds)
        events_before = report["before_rollback"]["checks"]["events"]
        events_after = report["after_restore"]["checks"]["events"]
        report["events_preserved"] = events_before == events_after
        if not report["events_preserved"]:
            raise RuntimeError(
                f"Event count changed across rollback: {events_before} -> {events_after}"
            )

        _compose(docker, args.host_port, "0.2.2", "down")
        report["status"] = "passed"
        report["finished_at"] = _utcnow()
        return_code = 0
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        report["finished_at"] = _utcnow()
        return_code = 1
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
