"""MCP server for browser inspection, screenshots, and on-image highlights."""

# Version is injected at build time by hatch-vcs, which writes _version.py
# into this package. During editable installs from a fresh checkout with no
# tag history, fall back to a sentinel so imports still work.
try:
    from visual_annotation_mcp._version import __version__
except ImportError:  # pragma: no cover - only hit in source tree without a build
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
