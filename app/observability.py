"""Structured local logs and best-effort failure alerts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, storage


SECRET_MARKERS = ("KEY", "TOKEN", "PASSWORD", "SECRET", "AUTHORIZATION")


def log_path() -> Path:
    return config.DATA_DIR / "logs" / "workbench.jsonl"


def alert_path() -> Path:
    return config.DATA_DIR / "logs" / "alerts.jsonl"


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if any(marker in str(key).upper() for marker in SECRET_MARKERS):
                result[str(key)] = "[redacted]"
            else:
                result[str(key)] = _safe(item)
        return result
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


def _append(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True) + "\n")


def log_event(event: str, level: str = "info", **fields: Any) -> dict[str, Any]:
    payload = _safe({
        "timestamp": storage.utcnow(),
        "level": level.upper(),
        "event": event,
        **fields,
    })
    _append(log_path(), payload)
    if os.getenv("INTEL_JSON_LOGS", "0").strip().casefold() in {
        "1", "true", "yes", "on", "enabled",
    }:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
    return payload


def emit_alert(
    code: str, message: str, *, severity: str = "warning",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _safe({
        "timestamp": storage.utcnow(),
        "severity": severity,
        "code": code,
        "message": message,
        "context": context or {},
    })
    _append(alert_path(), payload)
    log_event("alert", level=severity, code=code, message=message, context=payload["context"])
    webhook = os.getenv("INTEL_ALERT_WEBHOOK_URL", "").strip()
    if webhook:
        try:
            import httpx

            httpx.post(webhook, json=payload, timeout=5.0)
        except Exception as exc:  # noqa: BLE001 - alert delivery is best effort
            log_event("alert_webhook_failed", level="error",
                      reason=f"{type(exc).__name__}: {exc}")
    return payload


def read_jsonl(path: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    return records[-max(1, min(limit, 1000)):]


def recent_alerts(limit: int = 100) -> dict[str, Any]:
    path = alert_path()
    items = read_jsonl(path, limit=limit)
    return {"items": items, "total": len(items), "path": str(path)}


def recent_logs(limit: int = 100) -> dict[str, Any]:
    path = log_path()
    items = read_jsonl(path, limit=limit)
    return {"items": items, "total": len(items), "path": str(path)}
