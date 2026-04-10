"""Optional URL host allowlist via VISUAL_ANNOTATION_ALLOWED_HOSTS."""

from __future__ import annotations

import os
from urllib.parse import urlparse


def allowed_hosts() -> frozenset[str] | None:
    raw = os.environ.get("VISUAL_ANNOTATION_ALLOWED_HOSTS", "").strip()
    if not raw:
        return None
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


def assert_url_allowed(url: str) -> None:
    hosts = allowed_hosts()
    if hosts is None:
        return
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("URL has no host; navigation denied when allowlist is set.")
    if host not in hosts:
        raise ValueError(
            f"Host {host!r} is not in VISUAL_ANNOTATION_ALLOWED_HOSTS. "
            f"Allowed: {', '.join(sorted(hosts))}"
        )
