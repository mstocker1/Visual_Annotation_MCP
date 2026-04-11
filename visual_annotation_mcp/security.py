"""Optional URL host allowlist via VISUAL_ANNOTATION_ALLOWED_HOSTS."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


def allowed_hosts() -> frozenset[str] | None:
    raw = os.environ.get("VISUAL_ANNOTATION_ALLOWED_HOSTS", "").strip()
    if not raw:
        return None
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


def allowed_file_roots() -> tuple[Path, ...] | None:
    raw = os.environ.get("VISUAL_ANNOTATION_ALLOWED_PATHS", "").strip()
    if not raw:
        return None

    roots: list[Path] = []
    for chunk in raw.split(","):
        val = chunk.strip().strip('"').strip("'")
        if not val:
            continue
        roots.append(Path(val).expanduser().resolve())
    return tuple(roots)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_file_path_allowed(file_path: str) -> Path:
    if not file_path or not file_path.strip():
        raise ValueError("file_path is required")

    candidate = Path(file_path).expanduser().resolve()
    roots = allowed_file_roots()
    if roots is None:
        return candidate

    for root in roots:
        if _is_relative_to(candidate, root):
            return candidate

    allowed = ", ".join(str(p) for p in roots)
    raise ValueError(
        f"Path {str(candidate)!r} is not in VISUAL_ANNOTATION_ALLOWED_PATHS. Allowed roots: {allowed}"
    )


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
