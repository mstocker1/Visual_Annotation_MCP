# Launch the Visual Annotation MCP server (stdio). Prefer repo .venv when present.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    & $venvPy -m visual_annotation_mcp
} else {
    python -m visual_annotation_mcp
}
