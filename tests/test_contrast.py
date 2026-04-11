from __future__ import annotations

import unittest

from PIL import Image

from visual_annotation_mcp.annotate import pick_contrast_color, resolve_annotation_color


class ContrastTests(unittest.TestCase):
    def test_resolve_prefers_requested_color_when_contrast_is_sufficient(self) -> None:
        im = Image.new("RGB", (120, 120), (230, 230, 230))
        out = resolve_annotation_color(
            im,
            (20, 20, 100, 100),
            color="auto",
            prefer_color="red",
            min_contrast=140.0,
        )
        self.assertEqual(out.lower(), "#ff0000")

    def test_resolve_falls_back_when_preferred_color_blends_with_region(self) -> None:
        im = Image.new("RGB", (120, 120), (255, 34, 34))
        out = resolve_annotation_color(
            im,
            (20, 20, 100, 100),
            color="auto",
            prefer_color="red",
            min_contrast=140.0,
        )
        self.assertNotEqual(out.lower(), "#ff2222")

    def test_explicit_color_bypasses_auto_picker(self) -> None:
        im = Image.new("RGB", (120, 120), (255, 34, 34))
        out = resolve_annotation_color(
            im,
            (20, 20, 100, 100),
            color="#00ff00",
            prefer_color="red",
            min_contrast=140.0,
        )
        self.assertEqual(out, "#00ff00")

    def test_pick_contrast_color_returns_palette_rgb(self) -> None:
        im = Image.new("RGB", (80, 80), (0, 0, 0))
        picked = pick_contrast_color(im, (10, 10, 70, 70))
        self.assertIn(
            picked,
            {
                (255, 34, 34),
                (50, 220, 50),
                (50, 120, 255),
                (255, 220, 0),
                (255, 30, 200),
                (0, 220, 255),
            },
        )


if __name__ == "__main__":
    unittest.main()
