#!/usr/bin/env bash
# Launch the Visual Annotation MCP server (stdio). Prefer repo .venv when present.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m visual_annotation_mcp
else
  exec python -m visual_annotation_mcp
fi
