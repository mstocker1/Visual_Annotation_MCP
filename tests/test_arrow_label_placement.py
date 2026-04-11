"""Unit tests for arrow + label placement in annotate_region."""

from __future__ import annotations

import io
import unittest

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


class ArrowLabelPlacementTests(unittest.TestCase):
    def test_tail_anchor_vertical_down_arrow(self) -> None:
        tail = (500.0, 100.0)
        tip = (500.0, 300.0)
        label_w, label_h = 160, 40
        ax, ay = _label_anchor_at_arrow_tail(tail, tip, label_w, label_h, (1000, 1000))

        cx = ax + label_w / 2
        self.assertLessEqual(abs(cx - tail[0]), 1)
        bottom_edge = ay + label_h
        self.assertLessEqual(bottom_edge, tail[1])
        self.assertLessEqual(tail[1] - bottom_edge, 10)


    def test_tail_anchor_vertical_up_arrow(self) -> None:
        tail = (500.0, 600.0)
        tip = (500.0, 300.0)
        label_w, label_h = 160, 40
        ax, ay = _label_anchor_at_arrow_tail(tail, tip, label_w, label_h, (1000, 1000))

        cx = ax + label_w / 2
        self.assertLessEqual(abs(cx - tail[0]), 1)
        self.assertGreaterEqual(ay, tail[1])
        self.assertLessEqual(ay - tail[1], 10)


    def test_tail_anchor_horizontal_right_arrow(self) -> None:
        tail = (200.0, 400.0)
        tip = (500.0, 400.0)
        label_w, label_h = 160, 40
        ax, ay = _label_anchor_at_arrow_tail(tail, tip, label_w, label_h, (1000, 1000))

        cy = ay + label_h / 2
        self.assertLessEqual(abs(cy - tail[1]), 1)
        right_edge = ax + label_w
        self.assertLessEqual(right_edge, tail[0])


    def test_arrow_length_grows_to_fit_label(self) -> None:
        tail_default, tip_default = _arrow_endpoints_for_bbox(
            500,
            500,
            10,
            10,
            (1000, 1000),
            min_length=0,
        )
        tail_long, tip_long = _arrow_endpoints_for_bbox(
            500,
            500,
            10,
            10,
            (1000, 1000),
            min_length=200,
        )
        default_len = (
            (tail_default[0] - tip_default[0]) ** 2
            + (tail_default[1] - tip_default[1]) ** 2
        ) ** 0.5
        long_len = (
            (tail_long[0] - tip_long[0]) ** 2 + (tail_long[1] - tip_long[1]) ** 2
        ) ** 0.5
        self.assertLess(default_len, long_len)
        self.assertGreaterEqual(long_len, 200)


    def test_annotate_region_arrow_with_label_runs(self) -> None:
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
        self.assertEqual(out[:8], b"\x89PNG\r\n\x1a\n")
        decoded = Image.open(io.BytesIO(out))
        self.assertEqual(decoded.size, (800, 600))


    def test_annotate_region_arrow_label_near_top_edge(self) -> None:
        png = _blank_png(800, 600)
        out = annotate_region(
            png,
            x=350,
            y=10,
            width=100,
            height=30,
            style="arrow",
            label="click to log in",
        )
        self.assertEqual(out[:8], b"\x89PNG\r\n\x1a\n")


    def test_annotate_region_explicit_label_position_still_relative_to_bbox(self) -> None:
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
        self.assertEqual(out[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
