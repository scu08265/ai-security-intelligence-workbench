"""Run and record a real Docker rollback from the current version and back."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
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


def _build_old_image(docker: str, version: str) -> None:
    work_dir = ROOT / "work"
    # work/ is gitignored, so it must be created before mkdtemp on clean
    # checkouts such as GitHub-hosted runners.
    work_dir.mkdir(parents=True, exist_ok=True)
    archive = work_dir / f"rollback-{version}.tar"
    source_dir = Path(tempfile.mkdtemp(prefix=f"rollback-{version}-", dir=work_dir))
    try:
        _run([
            "git", "-c", "safe.directory=*", "archive", "--format=tar",
            f"--output={archive}", f"v{version}",
        ])
        with tarfile.open(archive, "r") as bundle:
            bundle.extractall(source_dir)
        dockerfile = source_dir / "Dockerfile"
        dockerfile_text = dockerfile.read_text(encoding="utf-8")
        dockerfile_text = dockerfile_text.replace(
            "    PIP_NO_CACHE_DIR=1 \\\n",
            "    PIP_NO_CACHE_DIR=1 \\\n"
            "    PIP_DEFAULT_TIMEOUT=120 \\\n"
            "    PIP_RETRIES=10 \\\n",
            1,
        )
        if "COPY VERSION ./" not in dockerfile_text:
            dockerfile_text = dockerfile_text.replace(
                "COPY README.md ./\n",
                "COPY README.md ./\nCOPY VERSION ./\n",
                1,
            )
            dockerfile.write_text(dockerfile_text, encoding="utf-8")
        _run_build([
            docker, "build",
            "--build-arg", f"APP_VERSION={version}",
            "-t", f"{IMAGE_REPOSITORY}:{version}",
            ".",
        ], cwd=source_dir)
    finally:
        archive.unlink(missing_ok=True)
        shutil.rmtree(source_dir, ignore_errors=True)


def _build_current_image(docker: str, version: str) -> None:
    _run_build([
        docker, "build",
        "--build-arg", f"APP_VERSION={version}",
        "-t", f"{IMAGE_REPOSITORY}:{version}",
        ".",
    ])


def _run_build(command: list[str], *, cwd: Path = ROOT) -> str:
    last_error: RuntimeError | None = None
    for attempt in range(1, 4):
        try:
            return _run(command, cwd=cwd)
        except RuntimeError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(10)
    raise last_error or RuntimeError("Docker build failed.")


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


def _cleanup_compose(docker: str, host_port: int, current_version: str) -> None:
    try:
        _compose(docker, host_port, current_version, "down")
    except Exception:
        pass


def _wait_health(base_url: str, expected_version: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error = "health endpoint did not respond"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open(f"{base_url}/api/health", timeout=5) as response:
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


def _backup(docker: str, current_version: str) -> str:
    database = ROOT / "data" / "intel.sqlite"
    if not database.is_file():
        raise RuntimeError(f"Database not found: {database}")
    backup_dir = ROOT / "artifacts" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    name = f"intel-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
    target = backup_dir / name
    if sys.platform.startswith("win"):
        # On Docker Desktop for Windows the data directory is a DrvFs bind
        # mount. A Windows-side SQLite connection to the live WAL database
        # leaves shared-memory state that makes the next in-container
        # "PRAGMA journal_mode=WAL" fail with disk I/O error. Run the online
        # backup from a Linux container so all SQLite access stays on the
        # same side of the host/VM boundary.
        snippet = (
            "import sqlite3; "
            "src=sqlite3.connect('file:/backup-data/intel.sqlite?mode=ro', uri=True); "
            f"dst=sqlite3.connect('/backup-out/{name}'); "
            "src.backup(dst); dst.close(); src.close()"
        )
        _run([
            docker, "run", "--rm",
            "-v", f"{ROOT / 'data'}:/backup-data",
            "-v", f"{backup_dir}:/backup-out",
            f"{IMAGE_REPOSITORY}:{current_version}",
            "python", "-c", snippet,
        ])
    else:
        with sqlite3.connect(database) as source, sqlite3.connect(target) as destination:
            source.backup(destination)
    return str(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-port", type=int, default=18001)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--current-version",
        default=(ROOT / "VERSION").read_text(encoding="utf-8").strip(),
    )
    parser.add_argument("--previous-version", default="0.2.2")
    args = parser.parse_args()
    if not args.current_version or args.current_version == args.previous_version:
        parser.error("current and previous versions must be non-empty and different")

    report: dict[str, Any] = {
        "version": args.current_version,
        "current_version": args.current_version,
        "previous_version": args.previous_version,
        "generated_at": _utcnow(),
        "status": "running",
        "rollback_target": args.previous_version,
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

        report["build_previous"] = "started"
        _build_old_image(docker, args.previous_version)
        report["build_previous"] = "completed"
        report["build_current"] = "started"
        _build_current_image(docker, args.current_version)
        report["build_current"] = "completed"

        report["image_ids"] = {
            args.previous_version: _image_id(docker, args.previous_version),
            args.current_version: _image_id(docker, args.current_version),
        }
        report["legacy_build_compatibility"] = (
            f"v{args.previous_version} image build copies VERSION so /api/health "
            "reports the historical release version correctly."
        )
        report["backup_output"] = _backup(docker, args.current_version)

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

        _cleanup_compose(docker, args.host_port, args.current_version)
        _compose(docker, args.host_port, args.current_version, "up")
        report["before_rollback"] = _wait_health(
            base_url, args.current_version, args.timeout_seconds,
        )

        _compose(docker, args.host_port, args.current_version, "down")
        _compose(docker, args.host_port, args.previous_version, "up")
        report["after_rollback"] = _wait_health(
            base_url, args.previous_version, args.timeout_seconds,
        )

        _compose(docker, args.host_port, args.previous_version, "down")
        _compose(docker, args.host_port, args.current_version, "up")
        report["after_restore"] = _wait_health(
            base_url, args.current_version, args.timeout_seconds,
        )
        events_before = report["before_rollback"]["checks"]["events"]
        events_after = report["after_restore"]["checks"]["events"]
        report["events_preserved"] = events_before == events_after
        if not report["events_preserved"]:
            raise RuntimeError(
                f"Event count changed across rollback: {events_before} -> {events_after}"
            )

        _compose(docker, args.host_port, args.current_version, "down")
        report["status"] = "passed"
        report["finished_at"] = _utcnow()
        return_code = 0
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        report["finished_at"] = _utcnow()
        if docker:
            _cleanup_compose(docker, args.host_port, args.current_version)
        return_code = 1
    finally:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
