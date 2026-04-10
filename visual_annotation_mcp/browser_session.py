"""Playwright browser session: navigate, inspect interactive elements, screenshot."""

from __future__ import annotations

import json
from typing import Any

from playwright.async_api import Browser, ElementHandle, Page, async_playwright

from visual_annotation_mcp.annotate import (
    HighlightStyle,
    LabelPosition,
    annotate_region,
)
from visual_annotation_mcp.security import assert_url_allowed

INTERACTIVE_SELECTOR = (
    "a, button, [role='button'], [role='link'], [role='menuitem'], "
    "input[type='button'], input[type='submit'], input[type='reset']"
)


def _bbox_edge_distance_sq(a: dict[str, float], b: dict[str, float]) -> float:
    """Squared edge-to-edge distance between two axis-aligned bboxes; 0 if they overlap."""
    dx = max(b["x"] - (a["x"] + a["width"]), a["x"] - (b["x"] + b["width"]), 0.0)
    dy = max(b["y"] - (a["y"] + a["height"]), a["y"] - (b["y"] + b["height"]), 0.0)
    return dx * dx + dy * dy


class BrowserSession:
    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._handles: dict[str, ElementHandle] = {}
        self.last_image_bytes: bytes | None = None

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
        )
        self._page = await context.new_page()
        self._handles.clear()

    async def stop(self) -> None:
        self._handles.clear()
        self.last_image_bytes = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not started")
        return self._page

    async def navigate(self, url: str, wait_until: str = "load") -> str:
        assert_url_allowed(url)
        self._handles.clear()
        self.last_image_bytes = None
        await self.page.goto(url, wait_until=wait_until, timeout=60_000)
        title = await self.page.title()
        return f"Loaded {url!r} (title: {title!r})"

    async def inspect_elements(self) -> str:
        """List visible interactive elements with stable ids for follow-up tools."""
        self._handles.clear()
        raw_handles = await self.page.query_selector_all(INTERACTIVE_SELECTOR)
        elements: list[dict[str, Any]] = []

        for h in raw_handles:
            try:
                if not await h.is_visible():
                    continue
                box = await h.bounding_box()
                if not box or box["width"] < 1 or box["height"] < 1:
                    continue
            except Exception:
                continue

            eid = f"e{len(elements)}"
            self._handles[eid] = h
            tag = await h.evaluate("el => el.tagName.toLowerCase()")
            text = (await h.inner_text()).strip().replace("\n", " ")[:400]
            aria = (await h.get_attribute("aria-label")) or ""
            role = (await h.get_attribute("role")) or ""
            href = (await h.get_attribute("href")) or ""

            elements.append(
                {
                    "id": eid,
                    "tag": tag,
                    "text": text,
                    "aria_label": aria,
                    "role": role,
                    "href": href,
                    "box_css": {
                        "x": round(box["x"], 2),
                        "y": round(box["y"], 2),
                        "width": round(box["width"], 2),
                        "height": round(box["height"], 2),
                    },
                }
            )

        return json.dumps({"elements": elements, "count": len(elements)}, indent=2)

    def _get_handle(self, element_id: str) -> ElementHandle:
        h = self._handles.get(element_id)
        if h is None:
            raise ValueError(
                f"Unknown element id {element_id!r}. Call inspect_elements first after navigation."
            )
        return h

    async def screenshot_element(self, element_id: str) -> bytes:
        handle = self._get_handle(element_id)
        data = await handle.screenshot(type="png")
        self.last_image_bytes = data
        return data

    async def screenshot_viewport(self, full_page: bool = False) -> bytes:
        data = await self.page.screenshot(type="png", full_page=full_page)
        self.last_image_bytes = data
        return data

    async def screenshot_clipped(
        self,
        element_id: str,
        padding: int = 16,
        min_context: int = 0,
    ) -> tuple[bytes, dict[str, float]]:
        """
        Capture viewport region around element (CSS pixels), return png and element
        bounds **relative to the top-left of the captured image** in **pixel** coords.

        When ``min_context`` > 0, the clip is expanded so that at least that many of
        the nearest other interactive elements (by bbox edge distance) are also
        included, giving the viewer some surrounding context for orientation.
        """
        handle = self._get_handle(element_id)
        box = await handle.bounding_box()
        if not box:
            raise ValueError("Element has no bounding box")

        vp = self.page.viewport_size
        if not vp:
            raise RuntimeError("Viewport size unavailable")

        # Start with the target element's bbox; optionally grow it to include the
        # N nearest interactive neighbors so the viewer has visual reference points.
        union_x0 = box["x"]
        union_y0 = box["y"]
        union_x1 = box["x"] + box["width"]
        union_y1 = box["y"] + box["height"]

        if min_context > 0 and self._handles:
            # Reject oversized elements (e.g. container links wrapping a whole hero
            # banner) — they'd bloat the clip without helping the viewer orient.
            max_w = vp["width"] * 0.5
            max_h = vp["height"] * 0.5
            neighbors: list[tuple[float, dict[str, float]]] = []
            for other_id, other_handle in self._handles.items():
                if other_id == element_id:
                    continue
                try:
                    ob = await other_handle.bounding_box()
                except Exception:
                    ob = None
                if not ob or ob["width"] < 1 or ob["height"] < 1:
                    continue
                # Skip neighbors fully outside the viewport — they'd just bloat the clip.
                if (
                    ob["x"] + ob["width"] < 0
                    or ob["y"] + ob["height"] < 0
                    or ob["x"] > vp["width"]
                    or ob["y"] > vp["height"]
                ):
                    continue
                if ob["width"] > max_w or ob["height"] > max_h:
                    continue
                neighbors.append((_bbox_edge_distance_sq(box, ob), ob))

            neighbors.sort(key=lambda t: t[0])
            for _, nb in neighbors[:min_context]:
                union_x0 = min(union_x0, nb["x"])
                union_y0 = min(union_y0, nb["y"])
                union_x1 = max(union_x1, nb["x"] + nb["width"])
                union_y1 = max(union_y1, nb["y"] + nb["height"])

        pad = max(0, padding)
        clip_x = max(0.0, union_x0 - pad)
        clip_y = max(0.0, union_y0 - pad)
        clip_w = min(float(vp["width"]) - clip_x, (union_x1 - union_x0) + 2 * pad)
        clip_h = min(float(vp["height"]) - clip_y, (union_y1 - union_y0) + 2 * pad)
        if clip_w <= 0 or clip_h <= 0:
            raise ValueError("Computed clip region is empty")

        png = await self.page.screenshot(
            type="png",
            clip={"x": clip_x, "y": clip_y, "width": clip_w, "height": clip_h},
        )

        # device_scale_factor=1 → CSS px align with image pixels
        rel_x = box["x"] - clip_x
        rel_y = box["y"] - clip_y
        return png, {
            "x": rel_x,
            "y": rel_y,
            "width": box["width"],
            "height": box["height"],
        }

    async def highlight_element(
        self,
        element_id: str,
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
    ) -> bytes:
        png, rel = await self.screenshot_clipped(
            element_id, padding=padding, min_context=min_context
        )
        out = annotate_region(
            png,
            x=rel["x"],
            y=rel["y"],
            width=rel["width"],
            height=rel["height"],
            style=style,
            color=color,
            prefer_color=prefer_color,
            min_contrast=min_contrast,
            stroke_width=stroke_width,
            label=label,
            label_position=label_position,
            blur_background=blur_background,
        )
        self.last_image_bytes = out
        return out

    def annotate_last_image(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        style: HighlightStyle = "circle",
        color: str = "auto",
        prefer_color: str = "red",
        min_contrast: float = 140.0,
        label: str | None = None,
        label_position: LabelPosition = "auto",
        blur_background: bool = False,
        stroke_width: int = 4,
    ) -> bytes:
        if self.last_image_bytes is None:
            raise ValueError(
                "No prior screenshot in session; run screenshot_viewport or screenshot_element first."
            )
        out = annotate_region(
            self.last_image_bytes,
            x=x,
            y=y,
            width=width,
            height=height,
            style=style,
            color=color,
            prefer_color=prefer_color,
            min_contrast=min_contrast,
            stroke_width=stroke_width,
            label=label,
            label_position=label_position,
            blur_background=blur_background,
        )
        self.last_image_bytes = out
        return out
