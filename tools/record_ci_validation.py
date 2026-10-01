"""Wait for GitHub Actions on a commit and write CI validation evidence."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPORT = ROOT / "reports" / "ci-validation.json"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _client(token: str | None) -> httpx.Client:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-security-intelligence-workbench",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(
        base_url="https://api.github.com",
        headers=headers,
        timeout=60.0,
        follow_redirects=True,
    )


def _response_json(response: httpx.Response) -> Any:
    if response.status_code >= 400:
        detail = response.text[:500].replace("\n", " ")
        raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
    return response.json() if response.content else None


def _jobs(client: httpx.Client, repo: str, run_id: int) -> list[dict[str, Any]]:
    payload = _response_json(client.get(f"/repos/{repo}/actions/runs/{run_id}/jobs"))
    return [
        {
            "name": item.get("name"),
            "status": item.get("status"),
            "conclusion": item.get("conclusion"),
            "html_url": item.get("html_url"),
        }
        for item in payload.get("jobs") or []
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="scu08265/ai-security-intelligence-workbench")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow", default="ci.yml")
    parser.add_argument("--wait-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    run: dict[str, Any] = {
        "workflow": "CI",
        "workflow_url": (
            f"https://github.com/{args.repo}/actions/workflows/{args.workflow}"
        ),
        "branch": args.branch,
        "head_sha": args.head_sha,
        "status": "pending",
        "conclusion": None,
        "generated_at": _utcnow(),
    }
    try:
        with _client(os.getenv("GITHUB_TOKEN", "").strip() or None) as client:
            deadline = time.monotonic() + args.wait_seconds
            selected: dict[str, Any] | None = None
            last_read_error: Exception | None = None
            while time.monotonic() < deadline:
                try:
                    payload = _response_json(client.get(
                        f"/repos/{args.repo}/actions/runs",
                        params={
                            "branch": args.branch,
                            "head_sha": args.head_sha,
                            "event": "push",
                            "per_page": 20,
                        },
                    ))
                    last_read_error = None
                except (httpx.HTTPError, RuntimeError) as exc:
                    last_read_error = exc
                    time.sleep(args.poll_seconds)
                    continue
                candidates = [
                    item for item in payload.get("workflow_runs") or []
                    if str(item.get("path") or "").endswith(args.workflow)
                ]
                if candidates:
                    selected = max(
                        candidates,
                        key=lambda item: str(item.get("created_at") or ""),
                    )
                    if selected.get("status") == "completed":
                        break
                time.sleep(args.poll_seconds)
            if selected is None:
                if last_read_error is not None:
                    raise RuntimeError(f"Could not read Actions status: {last_read_error}")
                raise RuntimeError(
                    f"No {args.workflow} run found for {args.head_sha} on {args.branch}."
                )
            while True:
                try:
                    jobs = _jobs(client, args.repo, int(selected["id"]))
                    break
                except (httpx.HTTPError, RuntimeError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(args.poll_seconds)
            run.update({
                "run_id": selected.get("id"),
                "run_url": selected.get("html_url"),
                "status": selected.get("status"),
                "conclusion": selected.get("conclusion"),
                "created_at": selected.get("created_at"),
                "updated_at": selected.get("updated_at"),
                "jobs": jobs,
            })
    except Exception as exc:
        run["status"] = "failed_to_read"
        run["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(run, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0 if run.get("status") == "completed" and run.get("conclusion") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
