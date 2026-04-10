# Visual Annotation MCP

[![PyPI](https://img.shields.io/pypi/v/visual-annotation-mcp.svg)](https://pypi.org/project/visual-annotation-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/visual-annotation-mcp.svg)](https://pypi.org/project/visual-annotation-mcp/)
[![License](https://img.shields.io/pypi/l/visual-annotation-mcp.svg)](LICENSE)

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
2. **`inspect_elements`** — return JSON for every visible link, button, and
   similar control with a stable id (`e0`, `e1`, ...), its text/aria label,
   href, and CSS bounding box.
3. **`highlight_element`** — screenshot a region around an element by id and
   draw an annotation on it. The crop is automatically expanded to include a
   few nearby interactive elements so the viewer has visual context.
4. **`screenshot_viewport`** / **`screenshot_element`** — raw screenshots with
   no annotation.
5. **`annotate_last_image`** — draw additional shapes/labels on the image
   produced by the previous tool call, so annotations can be stacked.

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

### `inspect_elements()`
Return JSON with every visible link, button, `role="button"`, `role="link"`,
`role="menuitem"`, and submit/reset/button input on the current page. Each
entry has `id`, `tag`, `text`, `aria_label`, `role`, `href`, and `box_css`
(`x`, `y`, `width`, `height` in CSS pixels).

### `screenshot_viewport(full_page=False)`
Capture the current viewport (or the full scrolling page when `full_page=True`)
as a PNG.

### `screenshot_element(element_id)`
Tight PNG screenshot of a single DOM element by id.

### `highlight_element(element_id, ...)`
Screenshot a region around an element and draw an annotation on it.

| Parameter          | Default   | Description                                                                    |
| ------------------ | --------- | ------------------------------------------------------------------------------ |
| `element_id`       | —         | Id from a previous `inspect_elements` call.                                    |
| `padding`          | `16`      | Extra pixel margin around the computed crop.                                   |
| `style`            | `"circle"`| `circle`, `ellipse`, `rectangle`, `arrow`, or `text`.                          |
| `min_context`      | `6`       | Include at least this many nearby interactive elements in the crop.            |
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
    ├── security.py           # Optional host allowlist
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
