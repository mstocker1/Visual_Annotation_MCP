"""Structured logging, redaction, and in-memory metrics for MCP tools."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from contextvars import ContextVar
from threading import Lock
from typing import Any, Awaitable, Callable
from uuid import uuid4

_LOG = logging.getLogger("visual_annotation_mcp")

_REQUEST_ID: ContextVar[str] = ContextVar("visual_annotation_request_id", default="")

_METRICS_LOCK = Lock()
_METRICS: dict[str, dict[str, float | int]] = {}

_SECRET_KEYS = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "set_cookie",
}

_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*")


def telemetry_enabled() -> bool:
    raw = os.environ.get("VISUAL_ANNOTATION_TELEMETRY", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def ensure_request_id() -> str:
    cur = _REQUEST_ID.get()
    if cur:
        return cur
    rid = uuid4().hex
    _REQUEST_ID.set(rid)
    return rid


def set_request_id(request_id: str | None = None) -> str:
    rid = request_id or uuid4().hex
    _REQUEST_ID.set(rid)
    return rid


def clear_request_id() -> None:
    _REQUEST_ID.set("")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k).strip().lower()
            if key in _SECRET_KEYS:
                out[str(k)] = "***REDACTED***"
            else:
                out[str(k)] = redact_value(v)
        return out

    if isinstance(value, list):
        return [redact_value(v) for v in value]

    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)

    if isinstance(value, str):
        return _BEARER_RE.sub("Bearer ***REDACTED***", value)

    return value


def _record_metric(tool: str, elapsed_ms: float, ok: bool) -> None:
    with _METRICS_LOCK:
        row = _METRICS.setdefault(
            tool,
            {"calls": 0, "failures": 0, "total_ms": 0.0, "max_ms": 0.0},
        )
        row["calls"] = int(row["calls"]) + 1
        row["total_ms"] = float(row["total_ms"]) + float(elapsed_ms)
        row["max_ms"] = max(float(row["max_ms"]), float(elapsed_ms))
        if not ok:
            row["failures"] = int(row["failures"]) + 1


def metrics_snapshot() -> dict[str, Any]:
    with _METRICS_LOCK:
        out: dict[str, Any] = {}
        for tool, row in _METRICS.items():
            calls = int(row["calls"])
            total_ms = float(row["total_ms"])
            avg_ms = 0.0 if calls == 0 else round(total_ms / calls, 2)
            out[tool] = {
                "calls": calls,
                "failures": int(row["failures"]),
                "avg_ms": avg_ms,
                "max_ms": round(float(row["max_ms"]), 2),
            }
        return out


def log_event(level: str, event: str, *, tool: str, metadata: dict[str, Any] | None = None) -> None:
    payload = {
        "event": event,
        "request_id": ensure_request_id(),
        "tool": tool,
        "metadata": redact_value(metadata or {}),
        "ts_ms": int(time.time() * 1000),
    }
    message = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    if level == "error":
        _LOG.error(message)
    else:
        _LOG.info(message)


async def observe_async(
    tool: str,
    runner: Callable[[], Awaitable[Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> Any:
    start = time.perf_counter()
    log_event("info", "tool_start", tool=tool, metadata=metadata)
    try:
        result = await runner()
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        _record_metric(tool, elapsed_ms, ok=False)
        log_event(
            "error",
            "tool_error",
            tool=tool,
            metadata={
                "elapsed_ms": round(elapsed_ms, 2),
                "error": str(exc),
                **(metadata or {}),
            },
        )
        raise

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    _record_metric(tool, elapsed_ms, ok=True)
    log_event(
        "info",
        "tool_success",
        tool=tool,
        metadata={"elapsed_ms": round(elapsed_ms, 2), **(metadata or {})},
    )

    if telemetry_enabled():
        log_event("info", "telemetry_metric", tool=tool, metadata={"elapsed_ms": round(elapsed_ms, 2)})

    return result
