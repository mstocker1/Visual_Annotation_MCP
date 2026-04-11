# Visual Annotation MCP

[![PyPI](https://img.shields.io/pypi/v/visual-annotation-mcp.svg)](https://pypi.org/project/visual-annotation-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/visual-annotation-mcp.svg)](https://pypi.org/project/visual-annotation-mcp/)
[![License](https://img.shields.io/pypi/l/visual-annotation-mcp.svg)](LICENSE)
[![CI](https://github.com/mstocker1/Visual_Annotation_MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/mstocker1/Visual_Annotation_MCP/actions/workflows/ci.yml)

A Model Context Protocol server that lets an LLM open web pages, list the
interactive elements on them, take screenshots, and draw annotations —
circles, ellipses, rectangles, arrows, and labeled text boxes — with
smart color contrast and optional background blur.

Built on top of [Playwright](https://playwright.dev/python/) (headless
Chromium) and [Pillow](https://pillow.readthedocs.io/).

## What it does

Given a URL, the server exposes a small set of tools that together form a
simple workflow:

```
navigate  →  inspect_elements  →  highlight_element  →  (annotate_last_image)
```

1. **`navigate`** — open a URL in a headless Chromium.
2. **`inspect_elements`** — return JSON for visible interactive and form
  elements (links, buttons, input/textarea/select, etc.) with stable ids
  (`e0`, `e1`, ...), text/aria metadata, DOM metadata, coverage status,
  and CSS bounding boxes.
3. **`click_element` / `fill_element` / `press_key` / `wait_for_url`** —
  interact with the page to dismiss blockers, fill fields, and move between
  steps.
4. **Convenience tools** — **`click_by_text`**, **`fill_by_selector`**, and
  **`dismiss_common_popups`** for quick interaction without a prior element id.
5. **`highlight_element`** — screenshot a region around an element by id and
   draw an annotation on it. The crop is automatically expanded to include a
   few nearby interactive elements so the viewer has visual context.
6. **`screenshot_viewport`** / **`screenshot_element`** — raw screenshots with
   no annotation.
7. **`annotate_last_image`** — draw additional shapes/labels on the image
   produced by the previous tool call, so annotations can be stacked.
8. **`run_flow`** — run a JSON list of steps for repeatable multi-step
  journeys (for example: signup, onboarding, checkout).

All shape drawing, color resolution, and image effects live in
`visual_annotation_mcp/annotate.py` and can be used as a normal Python library
independent of the MCP server.

## Features

### Shapes
- **`circle`** / **`ellipse`** — an aspect-ratio ellipse sized to fully
  enclose the element's bounding box (no more "red dot in the middle of a
  wide link").
- **`rectangle`** — bounding rectangle with a small margin.
- **`arrow`** — line with a filled arrowhead, pointing at the element from
  whichever nearby edge (top / bottom / right / left) actually fits in the
  cropped image.
- **`text`** — standalone text box; also available as a `label` parameter on
  any of the above shapes.

### Dynamic crop context
The crop around the target is grown to include the N nearest interactive
elements (by bounding-box edge distance) so the viewer can orient themselves.
Oversized container links (>50% of the viewport in either dimension) are
excluded so one giant hero-banner link can't bloat the crop. `min_context` is
tunable per call:

| `min_context` | Use case                                              |
| ------------- | ----------------------------------------------------- |
| `0`           | Tight crop, element only                              |
| `3-5`         | Compact reference                                     |
| `6-10`        | Default (6) — generous reference                      |
| `12-20`       | Wide overview                                         |

### Smart color resolution
`color="auto"` (the default) uses a preferred-with-fallback model:

- The annotation color defaults to `prefer_color="red"`.
- Before drawing, the surrounding pixels are sampled. If the Euclidean RGB
  distance from the average surround to the preferred color is at least
  `min_contrast` (default `140`), the preferred color is used.
- Otherwise the system falls back to the palette color (red, lime, blue,
  yellow, magenta, cyan) with the greatest distance from that average —
  e.g. on target.com's red header strip, preferred red falls back to **cyan**.
- Passing an explicit color (`color="#00ff00"`, `color="lime"`, etc.) bypasses
  the fallback entirely.
- `prefer_color` accepts any CSS color string, so users can say "always
  circle in lime" while still getting automatic contrast correction.

### Labels
`label="Click here"` draws a bordered text box near the element. The fill and
text colors are picked automatically for legibility against whatever pixels
sit under the label (light-on-dark or dark-on-light), and the border matches
the shape's resolved color. `label_position` can be `auto` (bottom → top →
right → left), or pinned to any side.

### Background blur
`blur_background=True` applies a feathered Gaussian blur to everything
outside the target's bounding box, leaving the element sharp. Good for
"which button is X" style screenshots where the rest of the page is noisy.

## Delivery roadmap

- Sprint execution plan: `docs/SPRINT_EXECUTION_PLAN.md`
- Ticket backlog: `docs/sprints/BACKLOG.md`
- Acceptance matrix: `docs/sprints/ACCEPTANCE_MATRIX.md`
- Risks and release gates: `docs/sprints/RISKS_AND_GATES.md`
- Swarm planning notes: `docs/sprints/SWARM_NOTES.md`
- Flow v2 contract: `docs/sprints/FLOW_V2_CONTRACT.md`
- Sprint 6 closeout: `docs/sprints/SPRINT6_CLOSEOUT.md`
- Operations runbook: `docs/OPERATIONS.md`
- Release notes and migration guidance: `docs/RELEASE_NOTES_AND_MIGRATION.md`
- Changelog: `CHANGELOG.md`

## Release Readiness Gates

For local pre-release verification:

```bash
python -m pip install -e .[dev]
ruff check visual_annotation_mcp tests/test_flow_contracts.py tests/test_flow_executor.py tests/test_observability.py tests/test_security.py
pydocstyle visual_annotation_mcp
mypy visual_annotation_mcp
coverage run -m unittest discover -s tests -p "test_*.py"
coverage report
python tests/smoke_test.py
pip-audit --ignore-vuln CVE-2026-1703
```

## Installation

### From PyPI (recommended)

```bash
pip install visual-annotation-mcp
visual-annotation-mcp-install-browsers   # downloads headless Chromium
```

The second step is required once per machine: `pip` installs the Python
package but not the browser binary Playwright needs. It's equivalent to
`python -m playwright install chromium` but discoverable from the installed
console scripts.

Python **3.11+** is required.

### From source (for development)

```bash
git clone https://github.com/mstocker1/Visual_Annotation_MCP
cd Visual_Annotation_MCP

python -m venv .venv
# Windows
.venv\Scripts\pip install -e .
.venv\Scripts\visual-annotation-mcp-install-browsers
# macOS / Linux
source .venv/bin/activate
pip install -e .
visual-annotation-mcp-install-browsers
```

## Wiring it into Claude Code

The repo ships with a project-scoped `.mcp.json`:

```json
{
  "mcpServers": {
    "visual-annotation": {
      "type": "stdio",
      "command": "${VISUAL_ANNOTATION_PYTHON:-python}",
      "args": ["-m", "visual_annotation_mcp"],
      "env": {}
    }
  }
}
```

Open this repo in Claude Code and approve the project MCP server when
prompted. Run `/mcp` to confirm **visual-annotation** is connected.

### If `python` isn't on the GUI PATH (common on Windows)

Any of these work:

1. Set `VISUAL_ANNOTATION_PYTHON` to the venv interpreter before starting
   Claude Code (e.g. `C:\path\to\repo\.venv\Scripts\python.exe`).
2. Replace `command` in `.mcp.json` with that full path directly.
3. On Windows, point `command`/`args` at `powershell` +
   `scripts\run_visual_mcp.ps1`. On macOS/Linux use `scripts/run_visual_mcp.sh`.

The bundled helper scripts prefer the repo's `.venv` automatically.

### First launch can be slow

The first call that needs a browser downloads and launches Chromium. If
Claude Code times out the MCP handshake, start it with a higher startup
timeout, e.g.

```bash
MCP_TIMEOUT=120000 claude
```

## Running without Claude

The package also runs as a standalone MCP stdio server:

```bash
python -m visual_annotation_mcp
```

For end-to-end verification without any MCP client at all, run the smoke
test:

```bash
python tests/smoke_test.py
```

It exercises every shape, the label, the blur effect, the contrast fallback,
`annotate_last_image` stacking, and raw screenshots against an in-memory
data URL. It exits non-zero on any assertion failure.

## Tool reference

### `navigate(url, wait_until="load")`
Go to a URL (HTTP/S only). Clears element ids from any previous `inspect_elements`.

### `inspect_elements(wait_timeout_ms=5000)`
Return JSON with every visible link, button, `role="button"`, `role="link"`,
`role="menuitem"`, input/textarea/select controls, and contenteditable
elements on the current page. Each entry has `id`, `tag`, `text`,
`aria_label`, `role`, `href`, `dom_id`, `name`, `placeholder`,
`is_covered`, and `box_css` (`x`, `y`, `width`, `height` in CSS pixels).

`wait_timeout_ms` lets dynamic pages finish rendering controls before the
snapshot is taken.

### `screenshot_viewport(full_page=False)`
Capture the current viewport (or the full scrolling page when `full_page=True`)
as a PNG.

### `screenshot_element(element_id, wait_timeout_ms=8000)`
Tight PNG screenshot of a single DOM element by id.

Before capture, the element is waited until actionable: visible, stable,
scrolled into view, and not center-covered by another element.

### `click_element(element_id, wait_timeout_ms=8000, post_wait_ms=250, button="left")`
Click an element id from `inspect_elements`. Before clicking, the target is
waited until actionable (visible, stable, scrolled into view, not covered at
its center point).

### `click_by_selector(selector, wait_timeout_ms=8000, post_wait_ms=250, button="left")`
Click the first actionable element matched by a CSS selector.

### `click_by_role(role, name="", wait_timeout_ms=8000, post_wait_ms=250, exact=False)`
Click the first actionable element matched by accessible role and optional
accessible name.

### `fill_element(element_id, text, wait_timeout_ms=8000, clear_first=True)`
Fill a text-like control (input/textarea/contenteditable) by inspected id.

### `fill_by_label(label, text, wait_timeout_ms=8000, clear_first=True, exact=False)`
Fill a field using associated label text.

### `click_by_text(text, wait_timeout_ms=8000, post_wait_ms=250, exact=False, case_sensitive=False)`
Click the first actionable interactive element whose text, aria-label, value,
or title matches the supplied string.

### `fill_by_selector(selector, text, wait_timeout_ms=8000, clear_first=True)`
Fill an input-like control selected by CSS selector without requiring an
`inspect_elements` id.

### `dismiss_common_popups(wait_timeout_ms=8000, max_clicks=3)`
Best-effort modal/cookie dismiss helper. Tries common labels (`accept`,
`agree`, `close`, `dismiss`, etc.) and close-icon selectors.

### `detect_blockers(max_candidates=8, min_area_ratio=0.08)`
Return JSON metadata for likely viewport blockers (modals/overlays), including
z-index, area ratio, and CSS box coordinates.

### `dismiss_overlay(selector=None, strategy="auto", wait_timeout_ms=8000)`
Dismiss overlays by selector or automatic close strategies (`auto`, `esc`,
`click`).

### `close_cookie_banner(wait_timeout_ms=8000)`
Best-effort helper to close cookie banners via common text labels and selectors.

### `press_key(key, delay_ms=0)`
Send a key press to the active page (`Enter`, `Escape`, `Tab`, etc.).

### `wait_for_url(url_contains, timeout_ms=10000, wait_until="load")`
Wait for URL transitions between flow steps, including hash changes.

### `wait_for_selector(selector, timeout_ms=10000, state="visible")`
Wait for a selector to reach `attached`, `detached`, `visible`, or `hidden`.

### `wait_for_text(text, timeout_ms=10000, exact=False, selector=None)`
Wait for text to become visible globally, or scoped under a selector.

### `assert_element_exists(selector=None, element_id=None)`
Assert that an element exists (selector or inspected id required).

### `assert_element_visible(selector=None, element_id=None, wait_timeout_ms=8000)`
Assert that an element is visible/actionable.

### `assert_text_contains(text, selector=None, case_sensitive=False)`
Assert that given text exists on page or within selector scope.

### `assert_url_matches(pattern, regex=False)`
Assert that current URL contains a pattern or matches regex.

### `extract_element(selector=None, element_id=None, attributes=None, include_text=True)`
Extract one element's structural data (tag/id/role/text/attrs/bbox).

### `extract_form_data(selector="form")`
Extract key/value data from form fields inside a form selector.

### `extract_table(selector)`
Extract table headers and row objects from a table selector.

### `extract_page_model()`
Extract lightweight page model: headings, landmarks, forms, interactive count.

### `select_option(selector=None, element_id=None, value=None, label=None, index=None, wait_timeout_ms=8000)`
Select option(s) in a `<select>` by value, label, or index using either
selector or element id.

### `check_uncheck(checked=True, selector=None, element_id=None, wait_timeout_ms=8000)`
Check or uncheck a checkbox/radio using selector or element id.

### `submit_form(selector=None, element_id=None, wait_timeout_ms=8000, post_wait_ms=250)`
Submit a form target by form selector/id or via submit-capable control click.

### `upload_file(file_path, selector=None, element_id=None, wait_timeout_ms=8000)`
Upload a local file to a file input using selector or element id.

### `highlight_element(element_id, ...)`
Screenshot a region around an element and draw an annotation on it.

| Parameter          | Default   | Description                                                                    |
| ------------------ | --------- | ------------------------------------------------------------------------------ |
| `element_id`       | —         | Id from a previous `inspect_elements` call.                                    |
| `padding`          | `16`      | Extra pixel margin around the computed crop.                                   |
| `style`            | `"circle"`| `circle`, `ellipse`, `rectangle`, `arrow`, or `text`.                          |
| `min_context`      | `6`       | Include at least this many nearby interactive elements in the crop.            |
| `wait_timeout_ms`  | `8000`    | Max wait for actionable target (visible, stable, in-view, not covered).        |
| `color`            | `"auto"`  | `"auto"` for preferred-with-fallback, or any CSS color to force.               |
| `prefer_color`     | `"red"`   | Preferred color for auto mode; any CSS color.                                  |
| `min_contrast`     | `140`     | RGB distance threshold before the auto picker falls back to the palette.      |
| `label`            | `None`    | Optional text drawn in a bordered text box near the element.                   |
| `label_position`   | `"auto"`  | `auto` / `top` / `bottom` / `left` / `right`.                                  |
| `blur_background`  | `False`   | Gaussian-blur everything outside the element's bbox.                           |
| `stroke_width`     | `4`       | Shape outline width in pixels.                                                 |

### `annotate_last_image(x, y, width, height, ...)`
Draw an additional annotation on the image from the previous call, at the
given pixel bounding box. Accepts all of the visual parameters above
(`style`, `color`, `prefer_color`, `min_contrast`, `label`, `label_position`,
`blur_background`, `stroke_width`). Calls stack, so you can build up a
multi-shape diagram with repeated invocations.

### `run_flow(flow_json)`
Execute a multi-step flow in one call. `flow_json` is a JSON array where each
step includes an `action` and action-specific fields.

Optional per-step flow controls:
- `store_as`: save step result in flow context
- `if_var`: run step only if a context key is truthy
- `equals`: optional value check used with `if_var`
- `retry`: `{ "max_attempts": int>=1, "backoff_ms": int>=0 }`
- `on_error`: `"fail" | "skip" | "fallback_action"`
- `fallback_action`: action object used when `on_error="fallback_action"`

Supported actions:
- `navigate`
- `inspect_elements`
- `click_element`
- `click_by_selector`
- `click_by_role`
- `fill_element`
- `fill_by_label`
- `click_by_text`
- `fill_by_selector`
- `dismiss_common_popups`
- `detect_blockers`
- `dismiss_overlay`
- `close_cookie_banner`
- `wait_for_selector`
- `wait_for_text`
- `assert_element_exists`
- `assert_element_visible`
- `assert_text_contains`
- `assert_url_matches`
- `extract_element`
- `extract_form_data`
- `extract_table`
- `extract_page_model`
- `select_option`
- `check_uncheck`
- `submit_form`
- `upload_file`
- `press_key`
- `wait_for_url`
- `screenshot_viewport`
- `screenshot_element`
- `highlight_element`

Example:

```json
[
  {"action":"navigate","url":"https://example.com"},
  {"action":"dismiss_common_popups"},
  {"action":"fill_by_selector","selector":"input[name='email']","text":"qa@example.com"},
  {"action":"click_by_text","text":"Continue"},
  {"action":"wait_for_url","url_contains":"signup"},
  {"action":"screenshot_viewport"}
]
```

### `observability_snapshot()`
Return in-memory per-tool metrics as JSON:

- calls
- failures
- avg_ms
- max_ms

## Optional URL allowlist

Set `VISUAL_ANNOTATION_ALLOWED_HOSTS` in the MCP server's environment to
restrict which hosts can be navigated to:

```json
{
  "mcpServers": {
    "visual-annotation": {
      "type": "stdio",
      "command": "${VISUAL_ANNOTATION_PYTHON:-python}",
      "args": ["-m", "visual_annotation_mcp"],
      "env": {
        "VISUAL_ANNOTATION_ALLOWED_HOSTS": "example.com,docs.example.com"
      }
    }
  }
}
```

Comma-separated hostnames, no scheme. Any navigation to a host outside the
list raises an error. Leave unset to allow all hosts.

## Optional file path allowlist (uploads)

Set `VISUAL_ANNOTATION_ALLOWED_PATHS` in the MCP server environment to
restrict file uploads to approved roots:

```json
{
  "mcpServers": {
    "visual-annotation": {
      "type": "stdio",
      "command": "${VISUAL_ANNOTATION_PYTHON:-python}",
      "args": ["-m", "visual_annotation_mcp"],
      "env": {
        "VISUAL_ANNOTATION_ALLOWED_PATHS": "C:/Users/me/Downloads,C:/work/safe-files"
      }
    }
  }
}
```

When set, `upload_file` rejects any path outside the configured roots.

## Optional telemetry flag

Set `VISUAL_ANNOTATION_TELEMETRY=1` to emit extra telemetry metric events in
structured logs (off by default).

## Layout

```
Visual_Annotation_MCP/
├── .github/workflows/
│   └── publish.yml           # Build + PyPI trusted publishing on git tag
├── .mcp.json                 # Project-scoped MCP config
├── CLAUDE.md                 # Claude Code project instructions
├── LICENSE                   # MIT
├── pyproject.toml            # PEP 621 metadata, hatch-vcs dynamic versioning
├── README.md
├── scripts/
│   ├── run_visual_mcp.ps1    # Windows launcher (prefers repo .venv)
│   └── run_visual_mcp.sh     # POSIX launcher (prefers repo .venv)
├── tests/
│   └── smoke_test.py         # End-to-end check, no MCP stdio needed
└── visual_annotation_mcp/
    ├── __main__.py           # python -m visual_annotation_mcp
    ├── annotate.py           # Shape primitives, blur, contrast picker
    ├── browser_session.py    # Playwright session wrapper
    ├── install.py            # visual-annotation-mcp-install-browsers
    ├── observability.py      # Structured logs + metrics + redaction
    ├── security.py           # URL/file allowlist checks
    └── server.py             # FastMCP tool definitions
```

## Releasing

Versioning is driven by git tags via
[`hatch-vcs`](https://github.com/ofek/hatch-vcs): the version injected into
the built wheel is whatever the most recent `v*` tag is, with a dev suffix
for untagged commits. You never edit a version number by hand.

One-time PyPI setup (per project):

1. Create the project once on PyPI (either by uploading the very first
   release manually with `twine`, or by configuring a *pending* trusted
   publisher without any release yet).
2. In the project's **Publishing** settings on pypi.org, add a new
   **Trusted Publisher** with:
   - PyPI project name: `visual-annotation-mcp`
   - Owner: `mstocker1`
   - Repository: `Visual_Annotation_MCP`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`
3. On GitHub, create an environment named `pypi` under
   **Settings → Environments** (no secrets needed with trusted publishing;
   optionally add a deployment protection rule for extra safety).

After that, cutting a release is:

```bash
git tag v0.1.0
git push origin v0.1.0
```

`.github/workflows/publish.yml` will build the sdist and wheel, upload them
to PyPI, and attach the artefacts to the workflow run.

Regular pushes and pull requests also run the build step (without
publishing) so broken packaging changes get caught in CI.

## License

MIT — see [LICENSE](LICENSE). This project depends on third-party libraries
(`mcp`, `playwright`, `pillow`) via pip and does not embed their source
code, so their licenses do not propagate to your use of this package.
