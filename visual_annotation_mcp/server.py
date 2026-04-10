"""FastMCP entrypoint: navigate, inspect, screenshot, highlight."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypedDict

from mcp.server.fastmcp import Context, FastMCP, Image

from visual_annotation_mcp.annotate import HighlightStyle, LabelPosition
from visual_annotation_mcp.browser_session import BrowserSession


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
        "Open web pages, list interactive elements with ids, take screenshots, "
        "and draw highlights. Workflow: navigate → inspect_elements → "
        "highlight_element (or screenshot_*) using an element id from inspect."
    ),
)


def _browser(ctx: Context) -> BrowserSession:
    return ctx.request_context.lifespan_context["browser"]


@mcp.tool()
async def navigate(
    url: str,
    ctx: Context,
    wait_until: str = "load",
) -> str:
    """Go to a URL (HTTP/S). Clears element ids from a previous inspect."""
    return await _browser(ctx).navigate(url, wait_until=wait_until)


@mcp.tool()
async def inspect_elements(ctx: Context) -> str:
    """Return JSON of visible links/buttons and similar controls with ids (e0, e1, …) for screenshot/highlight tools."""
    return await _browser(ctx).inspect_elements()


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
) -> Any:
    """Screenshot a single DOM element by id from the last inspect_elements (tight crop)."""
    bs = _browser(ctx)
    data = await bs.screenshot_element(element_id)
    return [f"PNG screenshot of element {element_id!r}.", Image(data=data, format="png")]


@mcp.tool()
async def highlight_element(
    element_id: str,
    ctx: Context,
    padding: int = 16,
    style: HighlightStyle = "circle",
    min_context: int = 6,
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
        color=color,
        prefer_color=prefer_color,
        min_contrast=min_contrast,
        label=label,
        label_position=label_position,
        blur_background=blur_background,
        stroke_width=stroke_width,
    )
    desc_parts = [f"style={style!r}", f"min_context={min_context}", f"color={color!r}"]
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


def main() -> None:
    mcp.run(transport="stdio")
