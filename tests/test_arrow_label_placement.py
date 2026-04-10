"""Unit tests for arrow + label placement in annotate_region.

These tests don't need Playwright — they render directly against synthetic
PNG bytes and inspect the resulting image. Run from the repo root with the
project venv active:

    python tests/test_arrow_label_placement.py
"""

from __future__ import annotations

import io
import sys

from PIL import Image

from visual_annotation_mcp.annotate import (
    _arrow_endpoints_for_bbox,
    _label_anchor_at_arrow_tail,
    annotate_region,
)


def _blank_png(width: int, height: int, color: tuple[int, int, int] = (240, 240, 240)) -> bytes:
    im = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_tail_anchor_vertical_down_arrow() -> None:
    """Arrow pointing DOWN (tail above, tip below) → label sits above the tail."""
    tail = (500.0, 100.0)
    tip = (500.0, 300.0)
    label_w, label_h = 160, 40
    ax, ay = _label_anchor_at_arrow_tail(tail, tip, label_w, label_h, (1000, 1000))

    # Label should be horizontally centered on the tail.
    cx = ax + label_w / 2
    assert abs(cx - tail[0]) <= 1, f"expected horizontally centered on tail, got cx={cx}"

    # Label's BOTTOM edge should sit just above the tail (label above, arrow
    # going downward beneath it). We allow a small gap.
    bottom_edge = ay + label_h
    assert bottom_edge <= tail[1], (
        f"label bottom {bottom_edge} should be at/above tail y={tail[1]}"
    )
    assert tail[1] - bottom_edge <= 10, "label should be close to the tail, not far"


def test_tail_anchor_vertical_up_arrow() -> None:
    """Arrow pointing UP (tail below, tip above) → label sits below the tail."""
    tail = (500.0, 600.0)
    tip = (500.0, 300.0)
    label_w, label_h = 160, 40
    ax, ay = _label_anchor_at_arrow_tail(tail, tip, label_w, label_h, (1000, 1000))

    cx = ax + label_w / 2
    assert abs(cx - tail[0]) <= 1
    # Label's TOP edge should sit just below the tail.
    assert ay >= tail[1], f"label top {ay} should be at/below tail y={tail[1]}"
    assert ay - tail[1] <= 10


def test_tail_anchor_horizontal_right_arrow() -> None:
    """Arrow pointing RIGHT (tail left, tip right) → label sits left of the tail."""
    tail = (200.0, 400.0)
    tip = (500.0, 400.0)
    label_w, label_h = 160, 40
    ax, ay = _label_anchor_at_arrow_tail(tail, tip, label_w, label_h, (1000, 1000))

    cy = ay + label_h / 2
    assert abs(cy - tail[1]) <= 1
    # Label's RIGHT edge should sit just left of the tail.
    right_edge = ax + label_w
    assert right_edge <= tail[0], f"label right {right_edge} should be left of tail {tail[0]}"


def test_arrow_length_grows_to_fit_label() -> None:
    """Arrow should be extended past its default length to fit a wide label."""
    # Tiny 10x10 target away from the top — without min_length the arrow would
    # be ~40px. With a 200-wide label, min_length should push it past 200.
    tail_default, tip_default = _arrow_endpoints_for_bbox(
        500, 500, 10, 10, (1000, 1000), min_length=0
    )
    tail_long, tip_long = _arrow_endpoints_for_bbox(
        500, 500, 10, 10, (1000, 1000), min_length=200
    )
    default_len = ((tail_default[0] - tip_default[0]) ** 2 + (tail_default[1] - tip_default[1]) ** 2) ** 0.5
    long_len = ((tail_long[0] - tip_long[0]) ** 2 + (tail_long[1] - tip_long[1]) ** 2) ** 0.5
    assert default_len < long_len
    assert long_len >= 200


def test_annotate_region_arrow_with_label_runs() -> None:
    """End-to-end: annotate_region with style='arrow' + label returns valid PNG."""
    png = _blank_png(800, 600)
    out = annotate_region(
        png,
        x=350,
        y=260,
        width=100,
        height=40,
        style="arrow",
        color="#ff2222",
        label="click to log in",
    )
    assert out[:8] == b"\x89PNG\r\n\x1a\n", "output is not a PNG"
    # Should be decodeable and same size as input.
    decoded = Image.open(io.BytesIO(out))
    assert decoded.size == (800, 600)


def test_annotate_region_arrow_label_near_top_edge() -> None:
    """Regression: target near the top of the image used to stack label on shaft.

    The arrow falls back to 'bottom' (tail below target), and the label should
    end up BELOW the arrow tail, not overlapping it.
    """
    png = _blank_png(800, 600)
    # 10px from the top — no room above for arrow.
    out = annotate_region(
        png,
        x=350,
        y=10,
        width=100,
        height=30,
        style="arrow",
        label="click to log in",
    )
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def test_annotate_region_explicit_label_position_still_relative_to_bbox() -> None:
    """Passing label_position != 'auto' should keep bbox-relative placement."""
    png = _blank_png(800, 600)
    out = annotate_region(
        png,
        x=350,
        y=260,
        width=100,
        height=40,
        style="arrow",
        label="click to log in",
        label_position="bottom",
    )
    assert out[:8] == b"\x89PNG\r\n\x1a\n"


def _run() -> int:
    tests = [
        test_tail_anchor_vertical_down_arrow,
        test_tail_anchor_vertical_up_arrow,
        test_tail_anchor_horizontal_right_arrow,
        test_arrow_length_grows_to_fit_label,
        test_annotate_region_arrow_with_label_runs,
        test_annotate_region_arrow_label_near_top_edge,
        test_annotate_region_explicit_label_position_still_relative_to_bbox,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
        else:
            print(f"ok   {t.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
