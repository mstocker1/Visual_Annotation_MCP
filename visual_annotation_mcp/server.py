"""FastMCP entrypoint: navigate, inspect, screenshot, highlight."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypedDict
from uuid import uuid4

from mcp.server.fastmcp import Context, FastMCP, Image

from visual_annotation_mcp.annotate import HighlightStyle, LabelPosition
from visual_annotation_mcp.browser_session import BrowserSession
from visual_annotation_mcp.errors import ErrorCode, MCPToolError
from visual_annotation_mcp.flow_contracts import parse_flow_json
from visual_annotation_mcp.observability import (
    clear_request_id,
    log_event,
    metrics_snapshot,
    observe_async,
    set_request_id,
)


class LifespanState(TypedDict):
    browser: BrowserSession


@asynccontextmanager
async def lifespan(_: FastMCP[LifespanState]) -> AsyncIterator[LifespanState]:
    session = BrowserSession()
    await session.start()
    try:
        yield LifespanState(browser=session)
    finally:
        await session.stop()


mcp = FastMCP(
    "Visual Annotation",
    lifespan=lifespan,
    instructions=(
        "Open web pages, list interactive/form elements with ids, click/fill/press "
        "to interact with the page, take screenshots, and draw highlights. "
        "Workflow: navigate → inspect_elements → click_element/fill_element → "
        "highlight_element (or screenshot_*)."
    ),
)


def _browser(ctx: Context) -> BrowserSession:
    return ctx.request_context.lifespan_context["browser"]


def _error_envelope(action: str, err: Exception) -> str:
    if isinstance(err, MCPToolError):
        payload = err.to_dict()
    else:
        payload = {
            "error_code": ErrorCode.EXECUTION_ERROR.value,
            "message": str(err) or err.__class__.__name__,
        }
    return json.dumps({"ok": False, "action": action, "error": payload}, indent=2)


async def _run_observed(
    action: str,
    runner: Any,
    *,
    metadata: dict[str, Any] | None = None,
) -> Any:
    request_id = set_request_id(uuid4().hex)
    try:
        log_event("info", "request_start", tool=action, metadata={"request_id": request_id, **(metadata or {})})
        result = await observe_async(action, runner, metadata=metadata)
        log_event("info", "request_end", tool=action, metadata={"request_id": request_id, "ok": True})
        return result
    except Exception as exc:
        log_event(
            "error",
            "request_end",
            tool=action,
            metadata={"request_id": request_id, "ok": False, "error": str(exc)},
        )
        raise
    finally:
        clear_request_id()


@mcp.tool()
async def navigate(
    url: str,
    ctx: Context,
    wait_until: str = "load",
) -> str:
    """Go to a URL (HTTP/S). Clears element ids from a previous inspect."""
    return await _run_observed(
        "navigate",
        lambda: _browser(ctx).navigate(url, wait_until=wait_until),
        metadata={"wait_until": wait_until},
    )


@mcp.tool()
async def inspect_elements(
    ctx: Context,
    wait_timeout_ms: int = 5_000,
) -> str:
    """Return JSON of visible interactive/form controls with ids (e0, e1, …).

    This call is content-aware: it can wait briefly for dynamic pages to render
    interactive controls before taking the snapshot.
    """
    return await _run_observed(
        "inspect_elements",
        lambda: _browser(ctx).inspect_elements(wait_timeout_ms=wait_timeout_ms),
        metadata={"wait_timeout_ms": wait_timeout_ms},
    )


@mcp.tool()
async def screenshot_viewport(
    ctx: Context,
    full_page: bool = False,
) -> Any:
    """Capture the current page (viewport or full scrolling page)."""
    bs = _browser(ctx)
    data = await bs.screenshot_viewport(full_page=full_page)
    scope = "full page" if full_page else "viewport"
    return [f"PNG screenshot ({scope}).", Image(data=data, format="png")]


@mcp.tool()
async def screenshot_element(
    element_id: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
) -> Any:
    """Screenshot a single DOM element by id from the last inspect_elements (tight crop).

    The tool waits for the element to become actionable (visible, in-view, not
    covered) up to ``wait_timeout_ms``.
    """
    bs = _browser(ctx)
    data = await bs.screenshot_element(element_id, wait_timeout_ms=wait_timeout_ms)
    return [f"PNG screenshot of element {element_id!r}.", Image(data=data, format="png")]


@mcp.tool()
async def click_element(
    element_id: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    post_wait_ms: int = 250,
    button: str = "left",
) -> str:
    """Click an inspected element id, waiting for it to become actionable first."""
    bs = _browser(ctx)
    return await bs.click_element(
        element_id=element_id,
        wait_timeout_ms=wait_timeout_ms,
        post_wait_ms=post_wait_ms,
        button=button,
    )


@mcp.tool()
async def click_by_selector(
    selector: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    post_wait_ms: int = 250,
    button: str = "left",
) -> str:
    """Click the first element matching a CSS selector."""
    bs = _browser(ctx)
    return await bs.click_by_selector(
        selector=selector,
        wait_timeout_ms=wait_timeout_ms,
        post_wait_ms=post_wait_ms,
        button=button,
    )


@mcp.tool()
async def click_by_role(
    role: str,
    ctx: Context,
    name: str = "",
    wait_timeout_ms: int = 8_000,
    post_wait_ms: int = 250,
    exact: bool = False,
) -> str:
    """Click by accessible role and optional name."""
    bs = _browser(ctx)
    return await bs.click_by_role(
        role=role,
        name=name,
        wait_timeout_ms=wait_timeout_ms,
        post_wait_ms=post_wait_ms,
        exact=exact,
    )


@mcp.tool()
async def fill_element(
    element_id: str,
    text: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    clear_first: bool = True,
) -> str:
    """Fill an inspected input-like element id with text."""
    bs = _browser(ctx)
    return await bs.fill_element(
        element_id=element_id,
        text=text,
        wait_timeout_ms=wait_timeout_ms,
        clear_first=clear_first,
    )


@mcp.tool()
async def fill_by_label(
    label: str,
    text: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    clear_first: bool = True,
    exact: bool = False,
) -> str:
    """Fill a field by its associated label text."""
    bs = _browser(ctx)
    return await bs.fill_by_label(
        label=label,
        text=text,
        wait_timeout_ms=wait_timeout_ms,
        clear_first=clear_first,
        exact=exact,
    )


@mcp.tool()
async def click_by_text(
    text: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    post_wait_ms: int = 250,
    exact: bool = False,
    case_sensitive: bool = False,
) -> str:
    """Click the first actionable interactive element whose text/label matches."""
    bs = _browser(ctx)
    return await bs.click_by_text(
        text=text,
        wait_timeout_ms=wait_timeout_ms,
        post_wait_ms=post_wait_ms,
        exact=exact,
        case_sensitive=case_sensitive,
    )


@mcp.tool()
async def fill_by_selector(
    selector: str,
    text: str,
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    clear_first: bool = True,
) -> str:
    """Fill a field selected by CSS selector (no inspect id needed)."""
    bs = _browser(ctx)
    return await bs.fill_by_selector(
        selector=selector,
        text=text,
        wait_timeout_ms=wait_timeout_ms,
        clear_first=clear_first,
    )


@mcp.tool()
async def dismiss_common_popups(
    ctx: Context,
    wait_timeout_ms: int = 8_000,
    max_clicks: int = 3,
) -> str:
    """Best-effort dismiss of cookie/modals using common labels and close icons."""
    bs = _browser(ctx)
    return await bs.dismiss_common_popups(
        wait_timeout_ms=wait_timeout_ms,
        max_clicks=max_clicks,
    )


@mcp.tool()
async def detect_blockers(
    ctx: Context,
    max_candidates: int = 8,
    min_area_ratio: float = 0.08,
) -> str:
    """Detect likely viewport blockers (modals/overlays) and return JSON metadata."""
    bs = _browser(ctx)
    return await bs.detect_blockers(
        max_candidates=max_candidates,
        min_area_ratio=min_area_ratio,
    )


@mcp.tool()
async def dismiss_overlay(
    ctx: Context,
    selector: str | None = None,
    strategy: str = "auto",
    wait_timeout_ms: int = 8_000,
) -> str:
    """Dismiss an overlay via selector or auto heuristics (+ optional Escape)."""
    bs = _browser(ctx)
    return await bs.dismiss_overlay(
        selector=selector,
        strategy=strategy,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool()
async def close_cookie_banner(
    ctx: Context,
    wait_timeout_ms: int = 8_000,
) -> str:
    """Best-effort cookie banner dismissal helper."""
    bs = _browser(ctx)
    return await bs.close_cookie_banner(wait_timeout_ms=wait_timeout_ms)


@mcp.tool()
async def press_key(
    key: str,
    ctx: Context,
    delay_ms: int = 0,
) -> str:
    """Press a keyboard key (for example: Enter, Escape, Tab)."""
    bs = _browser(ctx)
    return await bs.press_key(key=key, delay_ms=delay_ms)


@mcp.tool()
async def wait_for_url(
    url_contains: str,
    ctx: Context,
    timeout_ms: int = 10_000,
    wait_until: str = "load",
) -> str:
    """Wait until current URL contains the given fragment (useful between flow steps)."""
    bs = _browser(ctx)
    return await bs.wait_for_url(
        url_contains=url_contains,
        timeout_ms=timeout_ms,
        wait_until=wait_until,
    )


@mcp.tool()
async def wait_for_selector(
    selector: str,
    ctx: Context,
    timeout_ms: int = 10_000,
    state: str = "visible",
) -> str:
    """Wait for a selector to reach attached/detached/visible/hidden state."""
    bs = _browser(ctx)
    return await bs.wait_for_selector(
        selector=selector,
        timeout_ms=timeout_ms,
        state=state,
    )


@mcp.tool()
async def wait_for_text(
    text: str,
    ctx: Context,
    timeout_ms: int = 10_000,
    exact: bool = False,
    selector: str | None = None,
) -> str:
    """Wait for text to become visible globally or under a selector scope."""
    bs = _browser(ctx)
    return await bs.wait_for_text(
        text=text,
        timeout_ms=timeout_ms,
        exact=exact,
        selector=selector,
    )


@mcp.tool()
async def assert_element_exists(
    ctx: Context,
    selector: str | None = None,
    element_id: str | None = None,
) -> str:
    """Assert that an element exists by selector or inspected element id."""
    bs = _browser(ctx)
    return await bs.assert_element_exists(selector=selector, element_id=element_id)


@mcp.tool()
async def assert_element_visible(
    ctx: Context,
    selector: str | None = None,
    element_id: str | None = None,
    wait_timeout_ms: int = 8_000,
) -> str:
    """Assert that an element is visible/actionable."""
    bs = _browser(ctx)
    return await bs.assert_element_visible(
        selector=selector,
        element_id=element_id,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool()
async def assert_text_contains(
    text: str,
    ctx: Context,
    selector: str | None = None,
    case_sensitive: bool = False,
) -> str:
    """Assert that page (or selector scope) contains specific text."""
    bs = _browser(ctx)
    return await bs.assert_text_contains(
        text=text,
        selector=selector,
        case_sensitive=case_sensitive,
    )


@mcp.tool()
async def assert_url_matches(
    pattern: str,
    ctx: Context,
    regex: bool = False,
) -> str:
    """Assert that current URL contains a pattern or matches regex."""
    bs = _browser(ctx)
    return await bs.assert_url_matches(pattern=pattern, regex=regex)


@mcp.tool()
async def extract_element(
    ctx: Context,
    selector: str | None = None,
    element_id: str | None = None,
    attributes: list[str] | None = None,
    include_text: bool = True,
) -> str:
    """Extract structured data from one element (tag/id/role/text/attrs/box)."""
    bs = _browser(ctx)
    return await bs.extract_element(
        selector=selector,
        element_id=element_id,
        attributes=attributes,
        include_text=include_text,
    )


@mcp.tool()
async def extract_form_data(
    ctx: Context,
    selector: str = "form",
) -> str:
    """Extract key/value form field data from a form selector."""
    bs = _browser(ctx)
    return await bs.extract_form_data(selector=selector)


@mcp.tool()
async def extract_table(
    selector: str,
    ctx: Context,
) -> str:
    """Extract table headers and row objects from a table selector."""
    bs = _browser(ctx)
    return await bs.extract_table(selector=selector)


@mcp.tool()
async def extract_page_model(ctx: Context) -> str:
    """Extract a lightweight page model (headings, landmarks, forms, interactive count)."""
    bs = _browser(ctx)
    return await bs.extract_page_model()


@mcp.tool()
async def select_option(
    ctx: Context,
    selector: str | None = None,
    element_id: str | None = None,
    value: str | None = None,
    label: str | None = None,
    index: int | None = None,
    wait_timeout_ms: int = 8_000,
) -> str:
    """Select option on a <select> by value/label/index using selector or element id."""
    bs = _browser(ctx)
    return await bs.select_option(
        selector=selector,
        element_id=element_id,
        value=value,
        label=label,
        index=index,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool()
async def check_uncheck(
    ctx: Context,
    checked: bool = True,
    selector: str | None = None,
    element_id: str | None = None,
    wait_timeout_ms: int = 8_000,
) -> str:
    """Check or uncheck a checkbox/radio using selector or element id."""
    bs = _browser(ctx)
    return await bs.check_uncheck(
        checked=checked,
        selector=selector,
        element_id=element_id,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool()
async def submit_form(
    ctx: Context,
    selector: str | None = None,
    element_id: str | None = None,
    wait_timeout_ms: int = 8_000,
    post_wait_ms: int = 250,
) -> str:
    """Submit a form by form selector/id or clicking submit-capable element."""
    bs = _browser(ctx)
    return await bs.submit_form(
        selector=selector,
        element_id=element_id,
        wait_timeout_ms=wait_timeout_ms,
        post_wait_ms=post_wait_ms,
    )


@mcp.tool()
async def upload_file(
    file_path: str,
    ctx: Context,
    selector: str | None = None,
    element_id: str | None = None,
    wait_timeout_ms: int = 8_000,
) -> str:
    """Upload a local file into a file input using selector or element id."""
    bs = _browser(ctx)
    return await bs.upload_file(
        file_path=file_path,
        selector=selector,
        element_id=element_id,
        wait_timeout_ms=wait_timeout_ms,
    )


@mcp.tool()
async def highlight_element(
    element_id: str,
    ctx: Context,
    padding: int = 16,
    style: HighlightStyle = "circle",
    min_context: int = 6,
    wait_timeout_ms: int = 8_000,
    color: str = "auto",
    prefer_color: str = "red",
    min_contrast: float = 140.0,
    label: str | None = None,
    label_position: LabelPosition = "auto",
    blur_background: bool = False,
    stroke_width: int = 4,
) -> Any:
    """
    Screenshot the area around an element (viewport clip) and draw an annotation
    that fully encloses or points at it.

    Shape (``style``):
      - ``circle`` / ``ellipse`` — aspect-ratio ellipse enclosing the bbox (default).
      - ``rectangle`` — bounding rectangle with a small margin.
      - ``arrow`` — arrow pointing at the element from the nearest good edge.
      - ``text`` — no shape, only the ``label`` text box is drawn.

    Crop context (``min_context``):
      - ``0``      → tight crop, just the element itself.
      - ``3-5``    → compact reference.
      - ``6-10``   → generous reference (default 6).
      - ``12-20``  → wide overview.
    Oversized container links (>50% of viewport) are excluded so they don't bloat
    the crop. ``padding`` adds extra whitespace on top of the context expansion.

    Content-aware readiness:
      - Before capture, the server waits up to ``wait_timeout_ms`` for the target
        element to become actionable (visible, stable, scrolled into view, and
        not covered at its center point by another element).

    Visual effects:
      - ``color="auto"`` (default) resolves the final color via ``prefer_color``
        with a contrast-based fallback: the preferred color is used **unless**
        its Euclidean distance from the element's surround is below
        ``min_contrast``, in which case the most contrasting palette color
        (red/lime/blue/yellow/magenta/cyan) is chosen instead. This lets you
        say "always circle in red" while automatically swapping to a different
        hue on pages where red would blend in (e.g. target.com).
      - ``prefer_color`` (default ``"red"``) is your preferred annotation color
        for auto mode. Accepts any CSS color string.
      - To force a specific color regardless of contrast, pass it as ``color``
        (e.g. ``color="#00ff00"`` or ``color="lime"``). That bypasses the
        fallback logic entirely.
      - ``min_contrast`` (default 140) is the RGB distance threshold. Lower
        values make the preferred color "stickier"; higher values make the
        fallback more aggressive.
      - ``label`` draws a bordered text box near the element with automatic
        light-on-dark or dark-on-light legibility. Use ``label_position`` to
        pin it to a side (``auto`` tries bottom → top → right → left).
      - ``blur_background=True`` gaussian-blurs everything outside the element's
        bbox so the target visually pops. Good for "which button is X" style
        screenshots.
      - ``stroke_width`` controls the thickness of the shape's outline.
    """
    bs = _browser(ctx)
    data = await bs.highlight_element(
        element_id,
        padding=padding,
        style=style,
        min_context=min_context,
        wait_timeout_ms=wait_timeout_ms,
        color=color,
        prefer_color=prefer_color,
        min_contrast=min_contrast,
        label=label,
        label_position=label_position,
        blur_background=blur_background,
        stroke_width=stroke_width,
    )
    desc_parts = [
        f"style={style!r}",
        f"min_context={min_context}",
        f"wait_timeout_ms={wait_timeout_ms}",
        f"color={color!r}",
    ]
    if label:
        desc_parts.append(f"label={label!r}")
    if blur_background:
        desc_parts.append("blur_background=True")
    return [
        f"Highlighted element {element_id!r} ({', '.join(desc_parts)}).",
        Image(data=data, format="png"),
    ]


@mcp.tool()
def annotate_last_image(
    x: float,
    y: float,
    width: float,
    height: float,
    ctx: Context,
    style: HighlightStyle = "circle",
    color: str = "auto",
    prefer_color: str = "red",
    min_contrast: float = 140.0,
    label: str | None = None,
    label_position: LabelPosition = "auto",
    blur_background: bool = False,
    stroke_width: int = 4,
) -> Any:
    """
    Draw an annotation on the image produced by the last screenshot or highlight
    call in this session. Coordinates are in pixels relative to that image's
    top-left corner.

    Supports the same shapes and visual effects as ``highlight_element``:
    ``style`` (circle/ellipse/rectangle/arrow/text), ``color="auto"`` with
    ``prefer_color`` and ``min_contrast`` for a preferred-color-with-fallback
    picker, ``label`` for a bordered text box (with ``label_position``),
    ``blur_background`` to fade everything outside the target bbox, and
    ``stroke_width`` for outline thickness.

    This tool is additive — each call annotates on top of whatever was drawn by
    the previous call, so you can stack multiple shapes, labels, and arrows on
    the same image.
    """
    bs = _browser(ctx)
    data = bs.annotate_last_image(
        x=x,
        y=y,
        width=width,
        height=height,
        style=style,
        color=color,
        prefer_color=prefer_color,
        min_contrast=min_contrast,
        label=label,
        label_position=label_position,
        blur_background=blur_background,
        stroke_width=stroke_width,
    )
    return ["Annotated copy of the last screenshot.", Image(data=data, format="png")]


@mcp.tool()
async def run_flow(
    flow_json: str,
    ctx: Context,
) -> str:
    """
    Execute a multi-step interaction flow (legacy alias).

    This uses Sprint 0 validation contracts and returns a structured error
    envelope on failure rather than raising raw parse/validation exceptions.
    """
    return await run_flow_v2(flow_json=flow_json, ctx=ctx)


@mcp.tool()
async def run_flow_v2(
    flow_json: str,
    ctx: Context,
) -> str:
    """
    Execute a validated flow using contract version v2.

    Contract:
      - Input: JSON list of step objects, each with an `action`.
      - Validation: action name + required fields are checked before execution.
      - Output: JSON string with `ok=true` on success, or `ok=false` with
        `action` + `error` envelope on failure.

        Additional Sprint 1 actions:
            - click_by_selector, click_by_role
            - fill_by_label
            - wait_for_selector, wait_for_text

        Additional Sprint 2 actions:
            - detect_blockers, dismiss_overlay, close_cookie_banner
            - select_option, check_uncheck, submit_form, upload_file

        Additional Sprint 4 actions:
            - assert_element_exists, assert_element_visible
            - assert_text_contains, assert_url_matches
            - extract_element, extract_form_data, extract_table, extract_page_model
    """
    try:
        steps = parse_flow_json(flow_json)
        bs = _browser(ctx)
        return await _run_observed(
            "run_flow_v2",
            lambda: bs.run_flow(steps),
            metadata={"steps": len(steps)},
        )
    except Exception as exc:
        return _error_envelope("run_flow_v2", exc)


@mcp.tool()
async def observability_snapshot(ctx: Context) -> str:
    """Return in-memory per-tool latency/failure metrics snapshot as JSON."""
    _ = ctx
    return json.dumps({"ok": True, "metrics": metrics_snapshot()}, indent=2)


def main() -> None:
    mcp.run(transport="stdio")
