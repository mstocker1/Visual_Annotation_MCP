"""Draw highlights and annotations on PNG screenshots."""

from __future__ import annotations

import io
import math
from typing import Literal

from PIL import Image, ImageColor, ImageDraw, ImageFilter, ImageFont

HighlightStyle = Literal["circle", "ellipse", "rectangle", "arrow", "text"]
LabelPosition = Literal["auto", "top", "bottom", "left", "right"]

# Palette used by the auto contrast picker. Keeping this small and saturated
# so picks are visually distinct on most backgrounds. We deliberately omit
# black and white — they're extremes in RGB space and would always win the
# Euclidean distance race against light or dark surroundings, but vivid hue
# contrast is what actually makes an annotation "pop". Annotations should
# look like markers, not like shadows or outlines.
_PALETTE: dict[str, tuple[int, int, int]] = {
    "red": (255, 34, 34),
    "lime": (50, 220, 50),
    "blue": (50, 120, 255),
    "yellow": (255, 220, 0),
    "magenta": (255, 30, 200),
    "cyan": (0, 220, 255),
}

_FALLBACK_COLOR = "#ff2222"


def _load_font(size: int = 16) -> ImageFont.ImageFont:
    """Try common TrueType fonts; fall back to PIL's built-in bitmap font."""
    for name in (
        "arial.ttf",
        "Arial.ttf",
        "segoeui.ttf",
        "DejaVuSans.ttf",
        "Helvetica.ttf",
        "LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _region_bbox_int(
    x: float, y: float, w: float, h: float, img_size: tuple[int, int], pad: int = 0
) -> tuple[int, int, int, int]:
    W, H = img_size
    return (
        int(_clamp(x - pad, 0, W)),
        int(_clamp(y - pad, 0, H)),
        int(_clamp(x + w + pad, 0, W)),
        int(_clamp(y + h + pad, 0, H)),
    )


def _parse_color_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse a CSS color string into an RGB tuple; fall back to red on errors."""
    try:
        rgb = ImageColor.getrgb(color)
        return (rgb[0], rgb[1], rgb[2])
    except Exception:
        return (255, 34, 34)


def _dist_sq(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Plain Euclidean squared distance in RGB."""
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return dr * dr + dg * dg + db * db


def _region_average_rgb(
    im: Image.Image, bbox: tuple[int, int, int, int]
) -> tuple[float, float, float]:
    """Return the average RGB of ``im`` cropped to ``bbox``."""
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return (128.0, 128.0, 128.0)
    region = im.crop((x0, y0, x1, y1)).convert("RGB")
    small = region.resize(
        (max(1, min(32, region.width)), max(1, min(32, region.height)))
    )
    pixels = list(small.getdata())
    n = len(pixels) or 1
    return (
        sum(p[0] for p in pixels) / n,
        sum(p[1] for p in pixels) / n,
        sum(p[2] for p in pixels) / n,
    )


def pick_contrast_color(
    im: Image.Image, bbox: tuple[int, int, int, int]
) -> tuple[int, int, int]:
    """
    Sample the given bbox region of ``im`` and return an RGB tuple from the
    palette that has the greatest Euclidean distance from the region's
    average color.
    """
    avg = _region_average_rgb(im, bbox)
    return max(_PALETTE.values(), key=lambda c: _dist_sq(c, avg))


def resolve_annotation_color(
    im: Image.Image,
    bbox: tuple[int, int, int, int],
    color: str,
    prefer_color: str = "red",
    min_contrast: float = 140.0,
) -> str:
    """
    Resolve the final annotation color for a region.

    - If ``color`` is anything other than ``"auto"``, it is returned unchanged
      (i.e. the user has forced a specific color).
    - If ``color == "auto"``, the preferred color (``prefer_color``, default
      red) is used **if and only if** its Euclidean distance from the region's
      average RGB is at least ``min_contrast``. Otherwise the function falls
      back to the palette color with the greatest distance from the average.

    This lets the user say "always circle in red" while still letting the
    system swap in a contrasting color when the preferred one would blend in
    with the background (e.g. highlighting a red button on a red page).
    """
    if color and color != "auto":
        return color

    avg = _region_average_rgb(im, bbox)
    preferred_rgb = _parse_color_to_rgb(prefer_color)
    if _dist_sq(preferred_rgb, avg) >= min_contrast * min_contrast:
        return _rgb_to_hex(preferred_rgb)

    # Preferred color is too close to the surroundings. Pick the palette color
    # that's furthest from the average (and implicitly also far from the
    # preferred color, since it was close to the average).
    best = max(_PALETTE.values(), key=lambda c: _dist_sq(c, avg))
    return _rgb_to_hex(best)


def _region_luminance(im: Image.Image, bbox: tuple[int, int, int, int]) -> float:
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return 128.0
    region = im.crop((x0, y0, x1, y1)).convert("L")
    small = region.resize(
        (max(1, min(32, region.width)), max(1, min(32, region.height)))
    )
    pixels = list(small.getdata())
    return sum(pixels) / max(1, len(pixels))


def blur_except_region(
    im: Image.Image,
    bbox: tuple[int, int, int, int],
    radius: int = 10,
    feather: int = 12,
) -> Image.Image:
    """
    Return a copy of ``im`` where everything outside ``bbox`` is gaussian-blurred.
    A soft-edged mask (``feather``) is used to blend the sharp and blurred areas.
    """
    blurred = im.filter(ImageFilter.GaussianBlur(radius=radius))
    mask = Image.new("L", im.size, 0)
    md = ImageDraw.Draw(mask)
    x0, y0, x1, y1 = bbox
    md.rectangle((x0, y0, x1, y1), fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
    return Image.composite(im, blurred, mask)


def _draw_ellipse(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str,
    stroke_width: int,
) -> None:
    """Draw an ellipse that fully encloses the bbox, matching its aspect ratio."""
    cx = x + width / 2.0
    cy = y + height / 2.0
    pad = max(stroke_width * 2, 4)
    a = (width / 2.0) * math.sqrt(2) + pad
    b = (height / 2.0) * math.sqrt(2) + pad
    a = max(a, 12.0)
    b = max(b, 12.0)
    draw.ellipse(
        (cx - a, cy - b, cx + a, cy + b), outline=color, width=stroke_width
    )


def _draw_rectangle(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str,
    stroke_width: int,
) -> None:
    pad = stroke_width + 2
    draw.rectangle(
        (x - pad, y - pad, x + width + pad, y + height + pad),
        outline=color,
        width=stroke_width,
    )


def _draw_arrow(
    draw: ImageDraw.ImageDraw,
    p_from: tuple[float, float],
    p_to: tuple[float, float],
    color: str,
    stroke_width: int,
) -> None:
    """Draw a line from ``p_from`` to ``p_to`` with a filled triangular head at the tip."""
    draw.line([p_from, p_to], fill=color, width=stroke_width)
    dx = p_to[0] - p_from[0]
    dy = p_to[1] - p_from[1]
    if dx == 0 and dy == 0:
        return
    angle = math.atan2(dy, dx)
    head_len = max(stroke_width * 4, 16)
    head_half = math.radians(24)
    p1 = (
        p_to[0] - head_len * math.cos(angle - head_half),
        p_to[1] - head_len * math.sin(angle - head_half),
    )
    p2 = (
        p_to[0] - head_len * math.cos(angle + head_half),
        p_to[1] - head_len * math.sin(angle + head_half),
    )
    draw.polygon([p_to, p1, p2], fill=color)


def _arrow_endpoints_for_bbox(
    x: float,
    y: float,
    width: float,
    height: float,
    img_size: tuple[int, int],
    min_length: int = 0,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Compute sensible arrow endpoints for an arrow pointing at the given bbox.
    Prefers to come from above; falls back to below, right, or left if the
    top edge doesn't have enough room in the image.

    ``min_length`` bumps the arrow up to at least that many pixels long — used
    by the caller to reserve room for a label that will sit at the tail end.
    """
    W, H = img_size
    cx = x + width / 2.0
    cy = y + height / 2.0
    length = max(40, int(min(width, height)) + 30, int(min_length))

    # Try top, bottom, right, left (in that order) and pick the first that fits.
    candidates = [
        ("top", (cx, y - 6), (cx, y - 6 - length)),
        ("bottom", (cx, y + height + 6), (cx, y + height + 6 + length)),
        ("right", (x + width + 6, cy), (x + width + 6 + length, cy)),
        ("left", (x - 6, cy), (x - 6 - length, cy)),
    ]
    for _, tip, tail in candidates:
        if 0 <= tail[0] <= W and 0 <= tail[1] <= H:
            return tail, tip
    # Fall back to top even if it clips — better than nothing.
    return candidates[0][2], candidates[0][1]


def _label_anchor_at_arrow_tail(
    tail: tuple[float, float],
    tip: tuple[float, float],
    label_w: int,
    label_h: int,
    img_size: tuple[int, int],
    gap: int = 6,
) -> tuple[int, int]:
    """
    Return the top-left anchor for a label that should sit at the **tail** end
    of an arrow going from ``tail`` → ``tip``.

    The label is centered on the point that lies just past the tail, in the
    direction opposite the tip, so the arrow appears to emerge from the
    label's edge nearest the target: ``[ label ]──▶ target``. This avoids the
    label ever covering the arrow shaft, which was the previous behavior when
    the label was anchored to the target bbox instead of the arrow.
    """
    W, H = img_size
    dx = tip[0] - tail[0]
    dy = tip[1] - tail[1]
    length = math.hypot(dx, dy)
    if length == 0:
        # Degenerate arrow — fall back to centering the label on the tail.
        ax = int(_clamp(tail[0] - label_w / 2.0, 0, max(0, W - label_w)))
        ay = int(_clamp(tail[1] - label_h / 2.0, 0, max(0, H - label_h)))
        return ax, ay

    ux = dx / length
    uy = dy / length
    # Projected half-extent of the label in the arrow direction, plus a gap so
    # the label edge sits a few pixels off the tail point.
    half_extent = (abs(ux) * label_w + abs(uy) * label_h) / 2.0 + gap
    center_x = tail[0] - ux * half_extent
    center_y = tail[1] - uy * half_extent
    ax = int(round(center_x - label_w / 2.0))
    ay = int(round(center_y - label_h / 2.0))
    # Clamp into the image bounds so we still render if the image is tight.
    ax = int(_clamp(ax, 0, max(0, W - label_w)))
    ay = int(_clamp(ay, 0, max(0, H - label_h)))
    return ax, ay


def _measure_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont
) -> tuple[int, int]:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        # Very old Pillow fallback.
        return font.getsize(text) if hasattr(font, "getsize") else (len(text) * 8, 16)


def _choose_label_anchor(
    x: float,
    y: float,
    width: float,
    height: float,
    label_w: int,
    label_h: int,
    img_size: tuple[int, int],
    position: LabelPosition = "auto",
    gap: int = 10,
) -> tuple[int, int]:
    """Return the top-left anchor (in image pixels) for a text label of the given size."""
    W, H = img_size
    candidates: list[tuple[LabelPosition, tuple[int, int]]] = []
    cx = int(x + width / 2.0 - label_w / 2.0)
    below = (cx, int(y + height + gap))
    above = (cx, int(y - gap - label_h))
    right = (int(x + width + gap), int(y + height / 2.0 - label_h / 2.0))
    left = (int(x - gap - label_w), int(y + height / 2.0 - label_h / 2.0))
    if position == "auto":
        candidates = [("bottom", below), ("top", above), ("right", right), ("left", left)]
    else:
        mapping = {"top": above, "bottom": below, "left": left, "right": right}
        candidates = [(position, mapping[position])]

    def fits(anchor: tuple[int, int]) -> bool:
        ax, ay = anchor
        return 0 <= ax and ax + label_w <= W and 0 <= ay and ay + label_h <= H

    for _, anchor in candidates:
        if fits(anchor):
            return anchor
    # Nothing fit — clamp the first candidate into the image bounds.
    ax, ay = candidates[0][1]
    ax = int(_clamp(ax, 0, max(0, W - label_w)))
    ay = int(_clamp(ay, 0, max(0, H - label_h)))
    return ax, ay


def _draw_text_box(
    base: Image.Image,
    text: str,
    anchor: tuple[int, int],
    *,
    border_color: str,
    font_size: int = 16,
    padding: int = 8,
) -> None:
    """
    Draw a filled, bordered text box with ``text`` at ``anchor``. The fill and
    text colors are chosen automatically for legibility against ``base``.
    """
    draw = ImageDraw.Draw(base, "RGBA")
    font = _load_font(font_size)
    tw, th = _measure_text(draw, text, font)
    x, y = anchor
    box = (x, y, x + tw + padding * 2, y + th + padding * 2)
    # Sample the background under the label to decide light-on-dark vs dark-on-light.
    sample_bbox = (
        int(_clamp(box[0], 0, base.width)),
        int(_clamp(box[1], 0, base.height)),
        int(_clamp(box[2], 0, base.width)),
        int(_clamp(box[3], 0, base.height)),
    )
    luma = _region_luminance(base, sample_bbox)
    if luma < 140:
        bg = (255, 255, 255, 230)
        fg = (0, 0, 0, 255)
    else:
        bg = (0, 0, 0, 215)
        fg = (255, 255, 255, 255)
    draw.rectangle(box, fill=bg, outline=border_color, width=3)
    draw.text((x + padding, y + padding), text, fill=fg, font=font)


def annotate_region(
    png_bytes: bytes,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    style: HighlightStyle = "circle",
    color: str = "auto",
    prefer_color: str = "red",
    min_contrast: float = 140.0,
    stroke_width: int = 4,
    label: str | None = None,
    label_position: LabelPosition = "auto",
    blur_background: bool = False,
    blur_radius: int = 10,
) -> bytes:
    """
    Draw one or more annotations on ``png_bytes`` for the region defined by
    ``(x, y, width, height)`` in image pixel coordinates and return the new PNG.

    Parameters
    ----------
    style:
        One of ``circle``/``ellipse`` (aspect-ratio ellipse enclosing the bbox),
        ``rectangle`` (bounding rectangle with a small margin), ``arrow`` (arrow
        pointing at the bbox from the best nearby edge), or ``text`` (draws
        just a text label at/near the bbox; requires ``label``).
    color:
        ``"auto"`` resolves the final color from ``prefer_color`` with a
        contrast-based fallback (see below). Any other value is used as-is —
        pass e.g. ``"#00ff00"`` or ``"lime"`` to force a specific color.
    prefer_color:
        The user's preferred annotation color (default ``"red"``). When
        ``color == "auto"`` this color is used **unless** its Euclidean
        distance from the sampled surround is below ``min_contrast``, in which
        case the palette color with the most contrast is chosen instead.
        Supports any CSS color string.
    min_contrast:
        Minimum RGB distance (0–441) the preferred color needs to have from
        the sampled surround before we accept it. Default 140 — below that
        the auto picker falls back to the palette.
    label:
        Optional text drawn in a bordered text box near the bbox.
    label_position:
        Preferred side for the label relative to the bbox (``auto`` tries
        bottom → top → right → left). **Special case:** when ``style='arrow'``
        and ``label_position='auto'``, the label is instead anchored to the
        arrow's tail end so the arrow appears to emerge from the label
        (``[ label ]──▶ target``). Pass an explicit side (``'top'`` etc.) to
        force bbox-relative placement for arrows too.
    blur_background:
        If True, gaussian-blur everything outside the bbox so the target pops.
    """
    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    # Step 1 — optional background blur. This runs first so subsequent drawing
    # happens on the blurred image (the element stays sharp through the mask).
    if blur_background:
        target_bbox = _region_bbox_int(
            x, y, width, height, im.size, pad=max(6, stroke_width * 2)
        )
        im = blur_except_region(im, target_bbox, radius=blur_radius, feather=14)

    # Step 2 — resolve annotation color (preferred with contrast fallback).
    sample_bbox = _region_bbox_int(x, y, width, height, im.size, pad=24)
    resolved_color = resolve_annotation_color(
        im, sample_bbox, color, prefer_color=prefer_color, min_contrast=min_contrast
    )
    if not resolved_color:
        resolved_color = _FALLBACK_COLOR

    # Step 3 — pre-measure the label (if any). We need its dimensions before
    # drawing an arrow so the arrow can be extended far enough to leave room
    # for the label to sit beyond its tail.
    label_w = label_h = 0
    label_padding = 8
    label_font_size = 16
    if label:
        _measure_draw = ImageDraw.Draw(im)
        _measure_font = _load_font(label_font_size)
        _tw, _th = _measure_text(_measure_draw, label, _measure_font)
        label_w = _tw + label_padding * 2
        label_h = _th + label_padding * 2

    # Step 4 — draw the shape on an overlay.
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    arrow_tail: tuple[float, float] | None = None
    arrow_tip: tuple[float, float] | None = None

    if style in ("circle", "ellipse"):
        _draw_ellipse(draw, x, y, width, height, resolved_color, stroke_width)
    elif style == "rectangle":
        _draw_rectangle(draw, x, y, width, height, resolved_color, stroke_width)
    elif style == "arrow":
        # If the caller also supplied a label, extend the arrow so the label
        # fits entirely past the tail — otherwise the label can clip into the
        # shaft on near-the-edge targets.
        min_arrow_len = 0
        if label:
            min_arrow_len = max(label_w, label_h) + 24
        arrow_tail, arrow_tip = _arrow_endpoints_for_bbox(
            x, y, width, height, im.size, min_length=min_arrow_len
        )
        _draw_arrow(draw, arrow_tail, arrow_tip, resolved_color, stroke_width + 1)
    elif style == "text":
        if not label:
            raise ValueError("style='text' requires a non-empty label")
        # No shape drawn; label is the annotation.
    else:
        raise ValueError(f"Unknown style {style!r}")

    composed = Image.alpha_composite(im, overlay)

    # Step 5 — optional text label. Drawn directly on the composed image so
    # the label border and fill are the final rendered state.
    if label:
        if (
            style == "arrow"
            and arrow_tail is not None
            and arrow_tip is not None
            and label_position == "auto"
        ):
            # Anchor the label to the arrow's tail so the reader's eye goes
            # "text → arrow → target" and the label never covers the shaft.
            anchor = _label_anchor_at_arrow_tail(
                arrow_tail, arrow_tip, label_w, label_h, composed.size
            )
        else:
            anchor = _choose_label_anchor(
                x, y, width, height, label_w, label_h, composed.size, label_position
            )
        _draw_text_box(
            composed,
            label,
            anchor,
            border_color=resolved_color,
            font_size=label_font_size,
            padding=label_padding,
        )

    buf = io.BytesIO()
    composed.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def highlight_region(
    png_bytes: bytes,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    style: HighlightStyle = "circle",
    color: str = "#ff2222",
    stroke_width: int = 4,
) -> bytes:
    """Backwards-compatible wrapper around :func:`annotate_region`."""
    return annotate_region(
        png_bytes,
        x=x,
        y=y,
        width=width,
        height=height,
        style=style,
        color=color,
        stroke_width=stroke_width,
    )
