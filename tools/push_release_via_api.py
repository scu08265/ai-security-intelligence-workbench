"""Push a release or daily snapshot through the GitHub REST API.

This avoids the Windows git-remote-https helper that crashes on some hosts.
The token is read only from GITHUB_TOKEN and is never written to logs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parent.parent
GIT = Path(r"D:\Git\cmd\git.exe")


def _git(*args: str, check: bool = True) -> str:
    command = [
        str(GIT if GIT.exists() else "git"),
        "-c", f"safe.directory={ROOT.as_posix()}",
        *args,
    ]
    result = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout.decode("utf-8", errors="replace")


class GitHub:
    def __init__(self, token: str) -> None:
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "ai-security-intelligence-workbench",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=60.0,
        )

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.client.request(method, path, **kwargs)
        if response.status_code >= 400:
            detail = response.text[:500].replace("\n", " ")
            raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
        return response.json() if response.content else None


def _tracked_files(full_tree: bool, base_commit: str | None) -> list[tuple[str, str, str | None]]:
    modes: dict[str, str] = {}
    for record in _git("ls-files", "-s", "-z").split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        modes[path] = mode

    if full_tree:
        return [(path, mode, None) for path, mode in sorted(modes.items())]
    if not base_commit:
        base_commit = _git("rev-parse", "HEAD^").strip()

    changed: list[tuple[str, str, str | None]] = []
    raw = _git("diff", "--name-status", "-z", base_commit, "HEAD")
    fields = [item for item in raw.split("\0") if item]
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            old_path = fields[index]
            path = fields[index + 1]
            index += 2
            changed.append((old_path, modes.get(old_path, "100644"), None))
            changed.append((path, modes.get(path, "100644"), None))
        else:
            path = fields[index]
            index += 1
            if status == "D":
                changed.append((path, modes.get(path, "100644"), None))
            else:
                changed.append((path, modes.get(path, "100644"), None))
    return changed


def _blob(github: GitHub, repo: str, path: str) -> str:
    # Use the exact blob stored in Git, not the working-tree bytes. Windows
    # checkouts may materialize CRLF while the repository blobs use LF; sending
    # the working-tree form rewrites every text file in the remote commit.
    result = subprocess.run(
        [
            str(GIT if GIT.exists() else "git"),
            "-c", f"safe.directory={ROOT.as_posix()}",
            "-C", str(ROOT),
            "cat-file", "blob", f"HEAD:{path}",
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.decode("utf-8", errors="replace").strip()
            or f"Unable to read Git blob HEAD:{path}"
        )
    data = result.stdout
    payload = github.request(
        "POST", f"/repos/{repo}/git/blobs",
        json={
            "content": base64.b64encode(data).decode("ascii"),
            "encoding": "base64",
        },
    )
    return str(payload["sha"])


def _identity() -> tuple[str, str]:
    name = _git("config", "--get", "user.name", check=False).strip()
    email = _git("config", "--get", "user.email", check=False).strip()
    if not name or not email:
        raise RuntimeError("Repository user.name/user.email are not configured.")
    return name, email


def _commit_payload(github: GitHub, repo: str) -> tuple[str, str, str]:
    name, email = _identity()
    message = _git("show", "-s", "--format=%B", "HEAD").strip()
    date = _git("show", "-s", "--format=%aI", "HEAD").strip()
    return message, date, json.dumps({
        "name": name, "email": email, "date": date,
    })


def push(
    *, repo: str, branch: str, tag: str | None,
    full_tree: bool, base_commit: str | None,
    sync_tags: list[str] | None = None,
) -> dict[str, Any]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set.")
    github = GitHub(token)
    branch_exists = True
    try:
        ref = github.request("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        remote_commit_sha = str(ref["object"]["sha"])
    except RuntimeError as exc:
        if "GitHub API 404:" not in str(exc):
            raise
        branch_exists = False
        remote_commit_sha = ""

    if full_tree:
        parent = base_commit or remote_commit_sha or _git("rev-parse", "HEAD^").strip()
        remote_commit = github.request("GET", f"/repos/{repo}/git/commits/{parent}")
        base_tree = str(remote_commit["tree"]["sha"])
    else:
        parent = base_commit or _git("rev-parse", "HEAD^").strip()
        base = github.request("GET", f"/repos/{repo}/git/commits/{parent}")
        base_tree = str(base["tree"]["sha"])

    elements: list[dict[str, Any]] = []
    for path, mode, _unused in _tracked_files(full_tree, parent):
        if full_tree or _git("cat-file", "-e", f"HEAD:{path}", check=False) is not None:
            if not (ROOT / path).exists():
                elements.append({
                    "path": path, "mode": mode, "type": "blob", "sha": None,
                })
            else:
                elements.append({
                    "path": path, "mode": "100755" if mode == "100755" else "100644",
                    "type": "blob", "sha": _blob(github, repo, path),
                })

    tree = github.request(
        "POST", f"/repos/{repo}/git/trees",
        json={"base_tree": base_tree, "tree": elements},
    )
    message, _date, author = _commit_payload(github, repo)
    commit = github.request(
        "POST", f"/repos/{repo}/git/commits",
        json={
            "message": message,
            "tree": tree["sha"],
            "parents": [parent],
            "author": json.loads(author),
            "committer": json.loads(author),
        },
    )
    if branch_exists:
        github.request(
            "PATCH", f"/repos/{repo}/git/refs/heads/{branch}",
            json={"sha": commit["sha"], "force": True},
        )
    else:
        github.request(
            "POST", f"/repos/{repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]},
        )

    def update_tag(tag_name: str, commit_sha: str, tagger: dict[str, Any]) -> str:
        tag_object = github.request(
            "POST", f"/repos/{repo}/git/tags",
            json={
                "tag": tag_name,
                "message": f"Release {tag_name}",
                "object": commit_sha,
                "type": "commit",
                "tagger": tagger,
            },
        )
        try:
            github.request("GET", f"/repos/{repo}/git/ref/tags/{tag_name}")
            github.request(
                "PATCH", f"/repos/{repo}/git/refs/tags/{tag_name}",
                json={"sha": tag_object["sha"], "force": True},
            )
        except RuntimeError:
            github.request(
                "POST", f"/repos/{repo}/git/refs",
                json={"ref": f"refs/tags/{tag_name}", "sha": tag_object["sha"]},
            )
        return str(tag_object["sha"])

    tagger = json.loads(author)
    updated_tags: dict[str, str] = {}
    if tag:
        updated_tags[tag] = update_tag(tag, commit["sha"], tagger)
    for tag_name in sync_tags or []:
        local_commit = _git("rev-list", "-n", "1", tag_name).strip()
        if local_commit:
            updated_tags[tag_name] = update_tag(tag_name, local_commit, tagger)
    return {
        "branch": branch,
        "commit": commit["sha"],
        "tag": tag,
        "updated_tags": updated_tags,
        "remote_previous_commit": remote_commit_sha,
        "branch_created": not branch_exists,
        "full_tree": full_tree,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="scu08265/ai-security-intelligence-workbench")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--tag", default="")
    parser.add_argument("--sync-tag", action="append", default=[])
    parser.add_argument("--full-tree", action="store_true")
    parser.add_argument("--base-commit", default="")
    args = parser.parse_args()
    try:
        result = push(
            repo=args.repo,
            branch=args.branch,
            tag=args.tag or None,
            full_tree=args.full_tree,
            base_commit=args.base_commit or None,
            sync_tags=args.sync_tag,
        )
    except Exception as exc:  # noqa: BLE001 - CLI must return actionable output
        print(json.dumps({
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "completed", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
