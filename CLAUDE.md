# Visual Annotation MCP — Claude Code

## One-time setup (this repo)

1. Create a venv and install (from repo root):

   `python -m venv .venv`

   Windows: `.venv\Scripts\pip install -e .` then `.venv\Scripts\python -m playwright install chromium`

   macOS/Linux: `source .venv/bin/activate && pip install -e . && python -m playwright install chromium`

2. MCP config is in `.mcp.json` (project scope). Claude Code may ask you to **approve** project MCP servers once; if tools do not appear, run `claude mcp reset-project-choices` and restart.

3. If the server fails to start because `python` is not on PATH for the GUI (common on Windows), either:
   - set `VISUAL_ANNOTATION_PYTHON` to your venv interpreter before starting Claude Code (full path to `python.exe` or `python`), or
   - replace the `command` in `.mcp.json` with that full path, or
   - on Windows only, point `command`/`args` at `powershell` + `-File scripts/run_visual_mcp.ps1` (run from this repo root).

4. First browser launch can be slow; if needed start Claude with a higher MCP startup timeout, e.g. `MCP_TIMEOUT=120000` (units per your shell / Claude docs).

5. In Claude Code, run `/mcp` and confirm **visual-annotation** is connected. Tools: `navigate`, `inspect_elements`, `screenshot_viewport`, `screenshot_element`, `highlight_element`, `annotate_last_image`.

## Quick manual test prompt

After opening a project that contains this `.mcp.json`, ask Claude to: navigate to `https://example.com`, run `inspect_elements`, take a viewport screenshot, and describe what it sees.

Optional host allowlist: set `VISUAL_ANNOTATION_ALLOWED_HOSTS` (comma-separated hostnames, no `https://`) in the server `env` block of `.mcp.json` if you want to restrict URLs.
