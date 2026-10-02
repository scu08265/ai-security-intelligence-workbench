"""Create or return a GitHub pull request through the REST API."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx


def _client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url="https://api.github.com",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-security-intelligence-workbench",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=60.0,
    )


def _response_json(response: httpx.Response) -> Any:
    if response.status_code >= 400:
        detail = response.text[:1000].replace("\n", " ")
        raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
    return response.json() if response.content else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="scu08265/ai-security-intelligence-workbench")
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body-file", type=Path, required=True)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set.")
    body = args.body_file.read_text(encoding="utf-8")

    with _client(token) as client:
        owner = args.repo.split("/", 1)[0]
        existing = _response_json(client.get(
            f"/repos/{args.repo}/pulls",
            params={
                "state": "open",
                "head": f"{owner}:{args.head}",
                "base": args.base,
            },
        ))
        if existing:
            pull = existing[0]
            status = "existing"
        else:
            pull = _response_json(client.post(
                f"/repos/{args.repo}/pulls",
                json={
                    "title": args.title,
                    "head": args.head,
                    "base": args.base,
                    "body": body,
                    "draft": args.draft,
                },
            ))
            status = "created"

    print(json.dumps({
        "status": status,
        "number": pull.get("number"),
        "html_url": pull.get("html_url"),
        "head_sha": (pull.get("head") or {}).get("sha"),
        "base": args.base,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
