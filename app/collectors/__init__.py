"""Collector plumbing: bounded HTTP with backoff, and source dispatch.

Failure handling is deliberately loud rather than forgiving.  A collector that
cannot reach its source returns `status="failed"` with the real error, and the
caller records it against the source.  Nothing is ever substituted for missing
data.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .. import config, provenance, storage, sources

USER_AGENT = f"ai-sec-intel/{config.APP_VERSION} (competition research; +https://localhost)"
# arXiv has intermittently returned 406 from specific edge nodes even for a
# valid Atom request.  Retrying is bounded by BACKOFF_SECONDS and a permanent
# incompatibility is still surfaced after the retry budget is exhausted.
RETRY_STATUS = {406, 408, 425, 429, 500, 502, 503, 504, 522, 524}
BACKOFF_SECONDS = (1.0, 2.0, 4.0)
MAX_DETAIL_FETCHES = 80  # per run, bounds a single collection's cost

# Tests inject an httpx.MockTransport here so the suite never touches the network.
_transport: httpx.BaseTransport | None = None


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


class FetchError(RuntimeError):
    """Raised when a request cannot be completed within the retry budget."""


@dataclass
class CollectOutcome:
    source_id: str
    status: str  # ok | partial | failed | skipped
    events: list[dict] = field(default_factory=list)
    fetched: int = 0
    filtered: int = 0
    error: str | None = None
    snapshot_hash: str | None = None
    cursor: str | None = None
    notes: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status in {"ok", "partial"}


def http_request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
    timeout: float = 25.0,
    retries: int = len(BACKOFF_SECONDS),
) -> httpx.Response:
    """Perform one request, retrying transient failures with backoff."""
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, */*"}
    request_headers.update(headers or {})
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            with httpx.Client(transport=_transport, follow_redirects=True, timeout=timeout) as client:
                response = client.request(method, url, params=params, json=json_body, headers=request_headers)
            if response.status_code in RETRY_STATUS and attempt < retries:
                delay = _retry_delay(response, attempt)
                time.sleep(delay)
                continue
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
                continue
            raise FetchError(f"{type(exc).__name__}: {exc}") from exc

    raise FetchError(str(last_error) if last_error else "unreachable")


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "").strip()
    if retry_after.isdigit():
        return min(float(retry_after), 60.0)
    return BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]


def get_json(url: str, **kwargs: Any) -> tuple[Any, str]:
    """GET and decode JSON.  Returns (payload, raw_text) where raw_text is what
    gets hashed and snapshotted, so the snapshot is the bytes we actually read."""
    response = http_request("GET", url, **kwargs)
    if response.status_code >= 400:
        raise FetchError(_describe_http_error(response))
    try:
        return response.json(), response.text
    except ValueError as exc:
        raise FetchError(f"响应不是有效 JSON：{exc}") from exc


def post_json(url: str, body: Any, **kwargs: Any) -> tuple[Any, str]:
    response = http_request("POST", url, json_body=body, **kwargs)
    if response.status_code >= 400:
        raise FetchError(_describe_http_error(response))
    try:
        return response.json(), response.text
    except ValueError as exc:
        raise FetchError(f"响应不是有效 JSON：{exc}") from exc


def _describe_http_error(response: httpx.Response) -> str:
    detail = ""
    try:
        payload = response.json()
        detail = str(payload.get("message") or payload.get("error") or "")[:180]
    except ValueError:
        detail = response.text[:180].replace("\n", " ")
    suffix = f"：{detail}" if detail else ""
    if response.status_code == 403 and "rate limit" in detail.casefold():
        return f"HTTP 403 速率限制（未配置访问令牌）{suffix}"
    return f"HTTP {response.status_code}{suffix}"


def record_snapshot(source_id: str, raw: str, suffix: str = "json") -> str:
    return storage.save_snapshot(source_id, raw, suffix=suffix)


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------

def _load_collectors() -> dict[str, Callable[..., CollectOutcome]]:
    from . import knowledge, vuln

    return {
        "nvd": vuln.collect_nvd,
        "mitre_cve": vuln.collect_mitre_cve,
        "osv": vuln.collect_osv,
        "ghsa": vuln.collect_ghsa,
        "cisa_kev": vuln.collect_cisa_kev,
        "msrc": vuln.collect_msrc,
        "arxiv": knowledge.collect_arxiv,
        "openalex": knowledge.collect_openalex,
        "rss": knowledge.collect_rss,
        "page": knowledge.collect_page,
        "document": knowledge.collect_document,
    }


def available_collectors() -> dict[str, str]:
    return {key: key for key in _load_collectors()}


def collect(source_id: str, since: str | None = None) -> CollectOutcome:
    """Run one collector.  Never raises for upstream problems; returns the failure."""
    spec = sources.get(source_id)
    if spec is None:
        return CollectOutcome(source_id=source_id, status="skipped", error="未注册的数据源")

    if spec.requires_token_env:
        import os
        if not os.getenv(spec.requires_token_env, "").strip():
            return CollectOutcome(
                source_id=source_id,
                status="skipped",
                error=f"缺少环境变量 {spec.requires_token_env}，未尝试采集（不以空结果冒充成功）",
            )

    collector = _load_collectors().get(spec.collector)
    if collector is None:
        return CollectOutcome(source_id=source_id, status="skipped", error=f"没有实现采集器 {spec.collector}")

    started = time.monotonic()
    discovered_at = storage.utcnow()
    try:
        outcome = collector(spec, since)
    except FetchError as exc:
        outcome = CollectOutcome(source_id=source_id, status="failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller, never hidden
        outcome = CollectOutcome(
            source_id=source_id, status="failed", error=f"{type(exc).__name__}: {exc}"
        )
    outcome.source_id = source_id
    outcome.events = [
        provenance.annotate_discovery(event, source_id, discovered_at)
        for event in outcome.events
    ]
    outcome.duration_ms = int((time.monotonic() - started) * 1000)
    return outcome
