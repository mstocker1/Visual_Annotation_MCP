"""Playwright browser session: navigate, inspect interactive elements, screenshot."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
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
    "input[type='button'], input[type='submit'], input[type='reset'], "
    "input:not([type='hidden']), textarea, select, [contenteditable='true']"
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
        try:
            self._browser = await self._playwright.chromium.launch(headless=True)
        except Exception as exc:
            # Give a clearer, actionable error when Chromium hasn't been
            # downloaded yet — this is the single most common first-run failure
            # for pip-installed users.
            msg = str(exc)
            hints = ("executable doesn't exist", "playwright install", "browser is not installed")
            if any(h in msg.lower() for h in hints):
                await self._playwright.stop()
                self._playwright = None
                raise RuntimeError(
                    "Playwright Chromium is not installed. Run one of:\n"
                    "  visual-annotation-mcp-install-browsers\n"
                    "  python -m playwright install chromium\n"
                    f"(original error: {exc})"
                ) from exc
            raise
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

    async def _wait_for_interactive_elements(self, timeout_ms: int = 5_000) -> None:
        """Best-effort wait for at least one visible interactive element."""
        if timeout_ms <= 0:
            return
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000.0)
        while True:
            handles = await self.page.query_selector_all(INTERACTIVE_SELECTOR)
            for h in handles:
                try:
                    if not await h.is_visible():
                        continue
                    box = await h.bounding_box()
                    if box and box["width"] >= 1 and box["height"] >= 1:
                        return
                except Exception:
                    continue
            if asyncio.get_running_loop().time() >= deadline:
                return
            await self.page.wait_for_timeout(150)

    async def _is_handle_uncovered(self, handle: ElementHandle) -> bool:
        """Return True if the element's center point is not covered by another element."""
        try:
            return bool(
                await handle.evaluate(
                    """
                    el => {
                      const r = el.getBoundingClientRect();
                      if (!r || r.width < 1 || r.height < 1) return false;
                      const cx = Math.min(window.innerWidth - 1, Math.max(0, r.left + r.width / 2));
                      const cy = Math.min(window.innerHeight - 1, Math.max(0, r.top + r.height / 2));
                      const top = document.elementFromPoint(cx, cy);
                      return !!top && (top === el || el.contains(top));
                    }
                    """
                )
            )
        except Exception:
            return False

    async def _ensure_actionable_element(
        self,
        handle: ElementHandle,
        timeout_ms: int = 8_000,
    ) -> dict[str, float]:
        """Wait until the element is visible, stable, in-view, and not covered."""
        if timeout_ms < 0:
            timeout_ms = 0
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000.0)
        last_error: str | None = None

        while True:
            remaining_ms = max(0, int((deadline - asyncio.get_running_loop().time()) * 1000))
            if remaining_ms <= 0 and timeout_ms > 0:
                break

            step_timeout = max(300, min(1_000, remaining_ms if timeout_ms > 0 else 1_000))
            try:
                await handle.wait_for_element_state("visible", timeout=step_timeout)
                await handle.scroll_into_view_if_needed(timeout=step_timeout)
                await handle.wait_for_element_state("stable", timeout=step_timeout)
                box = await handle.bounding_box()
                if not box or box["width"] < 1 or box["height"] < 1:
                    last_error = "element has no usable bounding box"
                elif not await self._is_handle_uncovered(handle):
                    last_error = "element is currently covered by another element"
                else:
                    return box
            except Exception as exc:
                last_error = str(exc)

            if timeout_ms == 0:
                break
            await self.page.wait_for_timeout(120)

        detail = f" Last observation: {last_error}." if last_error else ""
        raise ValueError(
            "Element is not actionable yet (it may still be loading, hidden, or covered)."
            f"{detail}"
        )

    async def inspect_elements(self, wait_timeout_ms: int = 5_000) -> str:
        """List visible interactive elements with stable ids for follow-up tools."""
        self._handles.clear()

        # Let dynamic pages settle before we snapshot interactive controls.
        await self.page.wait_for_load_state("domcontentloaded")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=min(wait_timeout_ms, 2_000))
        except Exception:
            pass
        await self._wait_for_interactive_elements(timeout_ms=wait_timeout_ms)

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
            dom_id = (await h.get_attribute("id")) or ""
            name = (await h.get_attribute("name")) or ""
            placeholder = (await h.get_attribute("placeholder")) or ""
            uncovered = await self._is_handle_uncovered(h)

            elements.append(
                {
                    "id": eid,
                    "tag": tag,
                    "text": text,
                    "aria_label": aria,
                    "role": role,
                    "href": href,
                    "dom_id": dom_id,
                    "name": name,
                    "placeholder": placeholder,
                    "is_covered": not uncovered,
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

    async def click_element(
        self,
        element_id: str,
        wait_timeout_ms: int = 8_000,
        post_wait_ms: int = 250,
        button: str = "left",
    ) -> str:
        if button not in {"left", "right", "middle"}:
            raise ValueError("button must be one of: left, right, middle")
        handle = self._get_handle(element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        await handle.click(button=button, timeout=max(1, wait_timeout_ms))
        if post_wait_ms > 0:
            await self.page.wait_for_timeout(post_wait_ms)
        return f"Clicked element {element_id!r} with button={button!r}."

    async def click_by_selector(
        self,
        selector: str,
        wait_timeout_ms: int = 8_000,
        post_wait_ms: int = 250,
        button: str = "left",
    ) -> str:
        if not selector.strip():
            raise ValueError("selector is required")
        if button not in {"left", "right", "middle"}:
            raise ValueError("button must be one of: left, right, middle")
        handle = await self._query_first_handle(selector)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        await handle.click(button=button, timeout=max(1, wait_timeout_ms))
        if post_wait_ms > 0:
            await self.page.wait_for_timeout(post_wait_ms)
        return f"Clicked selector {selector!r} with button={button!r}."

    async def click_by_role(
        self,
        role: str,
        name: str = "",
        wait_timeout_ms: int = 8_000,
        post_wait_ms: int = 250,
        exact: bool = False,
    ) -> str:
        role_value = role.strip()
        if not role_value:
            raise ValueError("role is required")

        role_locator = self.page.get_by_role(
            role_value,
            name=(name if name.strip() else None),
            exact=exact,
        ).first
        handle = await role_locator.element_handle(timeout=max(1, wait_timeout_ms))
        if handle is None:
            raise ValueError(f"No element found for role {role_value!r} and name {name!r}")

        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        await handle.click(timeout=max(1, wait_timeout_ms))
        if post_wait_ms > 0:
            await self.page.wait_for_timeout(post_wait_ms)
        return f"Clicked role={role_value!r} name={name!r}."

    async def _query_first_handle(self, selector: str) -> ElementHandle:
        handle = await self.page.query_selector(selector)
        if handle is None:
            raise ValueError(f"No element matched selector {selector!r}")
        return handle

    def _coerce_int(self, value: Any, *, field: str) -> int:
        try:
            return int(value)
        except Exception as exc:
            raise ValueError(f"{field} must be an integer") from exc

    async def _resolve_target_handle(
        self,
        selector: str | None = None,
        element_id: str | None = None,
    ) -> ElementHandle:
        if selector and selector.strip():
            return await self._query_first_handle(selector)
        if element_id and element_id.strip():
            return self._get_handle(element_id)
        raise ValueError("Either selector or element_id is required")

    @staticmethod
    def _text_match(haystack: str, needle: str, exact: bool, case_sensitive: bool) -> bool:
        left = haystack if case_sensitive else haystack.lower()
        right = needle if case_sensitive else needle.lower()
        if exact:
            return left == right
        return right in left

    async def _handle_text_blob(self, handle: ElementHandle) -> str:
        text = (await handle.inner_text()).strip().replace("\n", " ")
        aria = (await handle.get_attribute("aria-label")) or ""
        value = (await handle.get_attribute("value")) or ""
        title = (await handle.get_attribute("title")) or ""
        return " ".join(p for p in [text, aria, value, title] if p).strip()

    async def click_by_text(
        self,
        text: str,
        wait_timeout_ms: int = 8_000,
        post_wait_ms: int = 250,
        exact: bool = False,
        case_sensitive: bool = False,
    ) -> str:
        needle = text.strip()
        if not needle:
            raise ValueError("text is required")

        if wait_timeout_ms < 0:
            wait_timeout_ms = 0
        deadline = asyncio.get_running_loop().time() + (wait_timeout_ms / 1000.0)
        last_error: str | None = None

        while True:
            handles = await self.page.query_selector_all(INTERACTIVE_SELECTOR)
            candidates: list[tuple[bool, ElementHandle, str]] = []
            for h in handles:
                try:
                    if not await h.is_visible():
                        continue
                    blob = await self._handle_text_blob(h)
                    if not blob:
                        continue
                    if not self._text_match(blob, needle, exact=exact, case_sensitive=case_sensitive):
                        continue
                    candidates.append((await self._is_handle_uncovered(h), h, blob))
                except Exception:
                    continue

            candidates.sort(key=lambda item: (not item[0], len(item[2])))
            for _, handle, blob in candidates:
                try:
                    await self._ensure_actionable_element(handle, timeout_ms=min(1_000, max(300, wait_timeout_ms)))
                    await handle.click(timeout=max(1, wait_timeout_ms))
                    if post_wait_ms > 0:
                        await self.page.wait_for_timeout(post_wait_ms)
                    return f"Clicked element with text match {needle!r} (candidate={blob[:80]!r})."
                except Exception as exc:
                    last_error = str(exc)

            if wait_timeout_ms == 0 or asyncio.get_running_loop().time() >= deadline:
                break
            await self.page.wait_for_timeout(120)

        detail = f" Last observation: {last_error}." if last_error else ""
        raise ValueError(f"No actionable element matched text {needle!r}.{detail}")

    async def fill_element(
        self,
        element_id: str,
        text: str,
        wait_timeout_ms: int = 8_000,
        clear_first: bool = True,
    ) -> str:
        handle = self._get_handle(element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        if clear_first:
            await handle.fill(text, timeout=max(1, wait_timeout_ms))
        else:
            await handle.type(text, timeout=max(1, wait_timeout_ms))
        return f"Filled element {element_id!r} with {len(text)} characters."

    async def fill_by_selector(
        self,
        selector: str,
        text: str,
        wait_timeout_ms: int = 8_000,
        clear_first: bool = True,
    ) -> str:
        if not selector.strip():
            raise ValueError("selector is required")
        handle = await self._query_first_handle(selector)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        if clear_first:
            await handle.fill(text, timeout=max(1, wait_timeout_ms))
        else:
            await handle.type(text, timeout=max(1, wait_timeout_ms))
        return f"Filled selector {selector!r} with {len(text)} characters."

    async def fill_by_label(
        self,
        label: str,
        text: str,
        wait_timeout_ms: int = 8_000,
        clear_first: bool = True,
        exact: bool = False,
    ) -> str:
        label_value = label.strip()
        if not label_value:
            raise ValueError("label is required")

        locator = self.page.get_by_label(label_value, exact=exact).first
        handle = await locator.element_handle(timeout=max(1, wait_timeout_ms))
        if handle is None:
            raise ValueError(f"No field found for label {label_value!r}")

        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        if clear_first:
            await handle.fill(text, timeout=max(1, wait_timeout_ms))
        else:
            await handle.type(text, timeout=max(1, wait_timeout_ms))
        return f"Filled label {label_value!r} with {len(text)} characters."

    async def wait_for_selector(
        self,
        selector: str,
        timeout_ms: int = 10_000,
        state: str = "visible",
    ) -> str:
        if not selector.strip():
            raise ValueError("selector is required")
        if state not in {"attached", "detached", "visible", "hidden"}:
            raise ValueError("state must be one of: attached, detached, visible, hidden")

        await self.page.wait_for_selector(selector, state=state, timeout=max(1, timeout_ms))
        return f"Selector {selector!r} reached state={state!r}."

    async def wait_for_text(
        self,
        text: str,
        timeout_ms: int = 10_000,
        exact: bool = False,
        selector: str | None = None,
    ) -> str:
        needle = text.strip()
        if not needle:
            raise ValueError("text is required")

        if selector and selector.strip():
            locator = self.page.locator(selector).get_by_text(needle, exact=exact).first
        else:
            locator = self.page.get_by_text(needle, exact=exact).first

        await locator.wait_for(state="visible", timeout=max(1, timeout_ms))
        scope = f" within selector {selector!r}" if selector and selector.strip() else ""
        return f"Text {needle!r} is visible{scope}."

    async def dismiss_common_popups(
        self,
        wait_timeout_ms: int = 8_000,
        max_clicks: int = 3,
    ) -> str:
        labels = [
            "accept",
            "agree",
            "allow",
            "ok",
            "got it",
            "continue",
            "close",
            "dismiss",
            "no thanks",
        ]
        clicks = 0
        for label in labels:
            if clicks >= max_clicks:
                break
            try:
                await self.click_by_text(
                    text=label,
                    wait_timeout_ms=max(0, wait_timeout_ms // 2),
                    post_wait_ms=250,
                    exact=False,
                    case_sensitive=False,
                )
                clicks += 1
            except Exception:
                continue

        # Common close affordances that may not have text.
        icon_selectors = [
            "button[aria-label*='close' i]",
            "[role='button'][aria-label*='close' i]",
            "button[title*='close' i]",
            "button.modal-close",
            "button.close",
            "[data-testid*='close' i]",
        ]
        for selector in icon_selectors:
            if clicks >= max_clicks:
                break
            try:
                handle = await self.page.query_selector(selector)
                if handle is None or not await handle.is_visible():
                    continue
                await self._ensure_actionable_element(handle, timeout_ms=max(300, wait_timeout_ms // 2))
                await handle.click(timeout=max(1, wait_timeout_ms))
                await self.page.wait_for_timeout(200)
                clicks += 1
            except Exception:
                continue

        return f"Dismiss popup scan completed (clicked={clicks})."

    async def detect_blockers(
        self,
        max_candidates: int = 8,
        min_area_ratio: float = 0.08,
    ) -> str:
        data = await self.page.evaluate(
            """
            ({ maxCandidates, minAreaRatio }) => {
              const vw = window.innerWidth || 1;
              const vh = window.innerHeight || 1;
              const viewportArea = vw * vh;
              const out = [];

              const isVisible = (el) => {
                const cs = window.getComputedStyle(el);
                if (!cs || cs.display === 'none' || cs.visibility === 'hidden' || cs.opacity === '0') return false;
                const r = el.getBoundingClientRect();
                return !!r && r.width > 1 && r.height > 1;
              };

              const candidates = Array.from(document.querySelectorAll('body *'));
              for (const el of candidates) {
                if (!isVisible(el)) continue;
                const cs = window.getComputedStyle(el);
                const pos = cs.position || '';
                if (!(pos === 'fixed' || pos === 'sticky' || pos === 'absolute')) continue;

                const r = el.getBoundingClientRect();
                const x0 = Math.max(0, r.left);
                const y0 = Math.max(0, r.top);
                const x1 = Math.min(vw, r.right);
                const y1 = Math.min(vh, r.bottom);
                const w = Math.max(0, x1 - x0);
                const h = Math.max(0, y1 - y0);
                const area = w * h;
                const ratio = area / viewportArea;

                const zRaw = cs.zIndex || '0';
                const z = Number.parseInt(zRaw, 10);
                const zIndex = Number.isFinite(z) ? z : 0;

                const overlayLike = ratio >= minAreaRatio || zIndex >= 1000;
                if (!overlayLike) continue;

                out.push({
                  tag: (el.tagName || '').toLowerCase(),
                  id: el.id || '',
                  class_name: (el.className || '').toString().slice(0, 120),
                  role: el.getAttribute('role') || '',
                  aria_label: el.getAttribute('aria-label') || '',
                  z_index: zIndex,
                  area_ratio: Number(ratio.toFixed(4)),
                  box_css: {
                    x: Number(r.left.toFixed(2)),
                    y: Number(r.top.toFixed(2)),
                    width: Number(r.width.toFixed(2)),
                    height: Number(r.height.toFixed(2)),
                  }
                });
              }

              out.sort((a, b) => (b.area_ratio - a.area_ratio) || (b.z_index - a.z_index));
              return {
                count: out.length,
                blockers: out.slice(0, Math.max(1, maxCandidates)),
              };
            }
            """,
            {
                "maxCandidates": max(1, max_candidates),
                "minAreaRatio": max(0.01, min(1.0, float(min_area_ratio))),
            },
        )
        return json.dumps(data, indent=2)

    async def dismiss_overlay(
        self,
        selector: str | None = None,
        strategy: str = "auto",
        wait_timeout_ms: int = 8_000,
    ) -> str:
        mode = strategy.strip().lower()
        if mode not in {"auto", "esc", "click"}:
            raise ValueError("strategy must be one of: auto, esc, click")

        clicks = 0
        if selector and selector.strip():
            await self.click_by_selector(selector, wait_timeout_ms=wait_timeout_ms, post_wait_ms=200)
            clicks += 1
        elif mode in {"auto", "click"}:
            close_selectors = [
                "button[aria-label*='close' i]",
                "[role='button'][aria-label*='close' i]",
                "button[title*='close' i]",
                "[data-testid*='close' i]",
                "button.close",
                "button.modal-close",
            ]
            clicked = False
            for css in close_selectors:
                try:
                    h = await self.page.query_selector(css)
                    if h is None or not await h.is_visible():
                        continue
                    await self._ensure_actionable_element(h, timeout_ms=max(300, wait_timeout_ms // 2))
                    await h.click(timeout=max(1, wait_timeout_ms))
                    clicked = True
                    clicks += 1
                    break
                except Exception:
                    continue

            if not clicked and mode == "auto":
                try:
                    await self.click_by_text("close", wait_timeout_ms=max(300, wait_timeout_ms // 2))
                    clicks += 1
                except Exception:
                    pass

        if mode in {"auto", "esc"}:
            await self.press_key("Escape")

        await self.page.wait_for_timeout(200)
        remaining = json.loads(await self.detect_blockers(max_candidates=3)).get("count", 0)
        return f"Dismiss overlay attempted (clicks={clicks}, remaining_blockers={remaining})."

    async def close_cookie_banner(
        self,
        wait_timeout_ms: int = 8_000,
    ) -> str:
        labels = [
            "accept cookies",
            "accept all",
            "accept",
            "agree",
            "got it",
            "allow all",
            "continue",
        ]
        for label in labels:
            try:
                msg = await self.click_by_text(
                    label,
                    wait_timeout_ms=max(300, wait_timeout_ms // 2),
                    post_wait_ms=200,
                    exact=False,
                    case_sensitive=False,
                )
                return f"Cookie banner close attempt succeeded: {msg}"
            except Exception:
                continue

        for css in ["#onetrust-accept-btn-handler", "button[id*='cookie' i]", "button[class*='cookie' i]"]:
            try:
                msg = await self.click_by_selector(css, wait_timeout_ms=max(300, wait_timeout_ms // 2))
                return f"Cookie banner close attempt succeeded: {msg}"
            except Exception:
                continue

        return "Cookie banner close attempt completed; no matching control was found."

    async def select_option(
        self,
        selector: str | None = None,
        element_id: str | None = None,
        value: str | None = None,
        label: str | None = None,
        index: int | None = None,
        wait_timeout_ms: int = 8_000,
    ) -> str:
        if value is None and label is None and index is None:
            raise ValueError("One of value, label, or index is required")

        handle = await self._resolve_target_handle(selector=selector, element_id=element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)

        kwargs: dict[str, Any] = {"timeout": max(1, wait_timeout_ms)}
        if value is not None:
            kwargs["value"] = str(value)
        if label is not None:
            kwargs["label"] = str(label)
        if index is not None:
            kwargs["index"] = int(index)

        selected = await handle.select_option(**kwargs)
        return f"Selected option(s): {selected}."

    async def check_uncheck(
        self,
        checked: bool = True,
        selector: str | None = None,
        element_id: str | None = None,
        wait_timeout_ms: int = 8_000,
    ) -> str:
        handle = await self._resolve_target_handle(selector=selector, element_id=element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)

        if checked:
            await handle.check(timeout=max(1, wait_timeout_ms))
            return "Checked target control."
        await handle.uncheck(timeout=max(1, wait_timeout_ms))
        return "Unchecked target control."

    async def submit_form(
        self,
        selector: str | None = None,
        element_id: str | None = None,
        wait_timeout_ms: int = 8_000,
        post_wait_ms: int = 250,
    ) -> str:
        handle = await self._resolve_target_handle(selector=selector, element_id=element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)

        tag = (await handle.evaluate("el => el.tagName.toLowerCase()"))
        if tag == "form":
            await handle.evaluate("el => el.requestSubmit ? el.requestSubmit() : el.submit()")
        else:
            await handle.click(timeout=max(1, wait_timeout_ms))

        if post_wait_ms > 0:
            await self.page.wait_for_timeout(post_wait_ms)
        return "Submitted form target."

    async def upload_file(
        self,
        file_path: str,
        selector: str | None = None,
        element_id: str | None = None,
        wait_timeout_ms: int = 8_000,
    ) -> str:
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            raise ValueError(f"file_path does not exist or is not a file: {file_path!r}")

        handle = await self._resolve_target_handle(selector=selector, element_id=element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
        await handle.set_input_files(str(p), timeout=max(1, wait_timeout_ms))
        return f"Uploaded file {str(p)!r}."

    async def press_key(self, key: str, delay_ms: int = 0) -> str:
        if not key.strip():
            raise ValueError("key is required")
        await self.page.keyboard.press(key, delay=max(0, delay_ms))
        return f"Pressed key {key!r}."

    async def wait_for_url(
        self,
        url_contains: str,
        timeout_ms: int = 10_000,
        wait_until: str = "load",
    ) -> str:
        if not url_contains:
            raise ValueError("url_contains is required")

        if url_contains not in self.page.url:
            deadline = asyncio.get_running_loop().time() + (max(0, timeout_ms) / 1000.0)
            while True:
                if url_contains in self.page.url:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for URL containing {url_contains!r}. Current URL: {self.page.url!r}"
                    )
                await self.page.wait_for_timeout(100)

        try:
            await self.page.wait_for_load_state(wait_until=wait_until, timeout=min(timeout_ms, 5_000))
        except Exception:
            pass
        return f"URL matched {url_contains!r}: {self.page.url!r}."

    async def run_flow(self, steps: list[dict[str, Any]]) -> str:
        if not isinstance(steps, list) or not steps:
            raise ValueError("steps must be a non-empty list")

        results: list[dict[str, Any]] = []

        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Step {idx} must be an object")
            action = str(step.get("action") or "").strip().lower()
            if not action:
                raise ValueError(f"Step {idx} is missing 'action'")

            if action == "navigate":
                out = await self.navigate(
                    url=str(step.get("url") or ""),
                    wait_until=str(step.get("wait_until") or "load"),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "inspect_elements":
                raw = await self.inspect_elements(wait_timeout_ms=int(step.get("wait_timeout_ms", 5_000)))
                parsed = json.loads(raw)
                results.append(
                    {
                        "step": idx,
                        "action": action,
                        "count": int(parsed.get("count", 0)),
                    }
                )
            elif action == "click_element":
                out = await self.click_element(
                    element_id=str(step.get("element_id") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    post_wait_ms=int(step.get("post_wait_ms", 250)),
                    button=str(step.get("button") or "left"),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "click_by_selector":
                out = await self.click_by_selector(
                    selector=str(step.get("selector") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    post_wait_ms=int(step.get("post_wait_ms", 250)),
                    button=str(step.get("button") or "left"),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "click_by_role":
                out = await self.click_by_role(
                    role=str(step.get("role") or ""),
                    name=str(step.get("name") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    post_wait_ms=int(step.get("post_wait_ms", 250)),
                    exact=bool(step.get("exact", False)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "fill_element":
                out = await self.fill_element(
                    element_id=str(step.get("element_id") or ""),
                    text=str(step.get("text") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    clear_first=bool(step.get("clear_first", True)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "fill_by_label":
                out = await self.fill_by_label(
                    label=str(step.get("label") or ""),
                    text=str(step.get("text") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    clear_first=bool(step.get("clear_first", True)),
                    exact=bool(step.get("exact", False)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "click_by_text":
                out = await self.click_by_text(
                    text=str(step.get("text") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    post_wait_ms=int(step.get("post_wait_ms", 250)),
                    exact=bool(step.get("exact", False)),
                    case_sensitive=bool(step.get("case_sensitive", False)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "fill_by_selector":
                out = await self.fill_by_selector(
                    selector=str(step.get("selector") or ""),
                    text=str(step.get("text") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    clear_first=bool(step.get("clear_first", True)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "dismiss_common_popups":
                out = await self.dismiss_common_popups(
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    max_clicks=int(step.get("max_clicks", 3)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "detect_blockers":
                out = await self.detect_blockers(
                    max_candidates=int(step.get("max_candidates", 8)),
                    min_area_ratio=float(step.get("min_area_ratio", 0.08)),
                )
                results.append(
                    {
                        "step": idx,
                        "action": action,
                        "count": int(json.loads(out).get("count", 0)),
                    }
                )
            elif action == "dismiss_overlay":
                out = await self.dismiss_overlay(
                    selector=(None if step.get("selector") is None else str(step.get("selector"))),
                    strategy=str(step.get("strategy") or "auto"),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "close_cookie_banner":
                out = await self.close_cookie_banner(
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "wait_for_selector":
                out = await self.wait_for_selector(
                    selector=str(step.get("selector") or ""),
                    timeout_ms=int(step.get("timeout_ms", 10_000)),
                    state=str(step.get("state") or "visible"),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "wait_for_text":
                selector = step.get("selector")
                out = await self.wait_for_text(
                    text=str(step.get("text") or ""),
                    timeout_ms=int(step.get("timeout_ms", 10_000)),
                    exact=bool(step.get("exact", False)),
                    selector=(None if selector is None else str(selector)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "select_option":
                out = await self.select_option(
                    selector=(None if step.get("selector") is None else str(step.get("selector"))),
                    element_id=(None if step.get("element_id") is None else str(step.get("element_id"))),
                    value=(None if step.get("value") is None else str(step.get("value"))),
                    label=(None if step.get("label") is None else str(step.get("label"))),
                    index=(None if step.get("index") is None else self._coerce_int(step.get("index"), field="index")),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "check_uncheck":
                out = await self.check_uncheck(
                    checked=bool(step.get("checked", True)),
                    selector=(None if step.get("selector") is None else str(step.get("selector"))),
                    element_id=(None if step.get("element_id") is None else str(step.get("element_id"))),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "submit_form":
                out = await self.submit_form(
                    selector=(None if step.get("selector") is None else str(step.get("selector"))),
                    element_id=(None if step.get("element_id") is None else str(step.get("element_id"))),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    post_wait_ms=int(step.get("post_wait_ms", 250)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "upload_file":
                out = await self.upload_file(
                    file_path=str(step.get("file_path") or ""),
                    selector=(None if step.get("selector") is None else str(step.get("selector"))),
                    element_id=(None if step.get("element_id") is None else str(step.get("element_id"))),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "press_key":
                out = await self.press_key(
                    key=str(step.get("key") or ""),
                    delay_ms=int(step.get("delay_ms", 0)),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "wait_for_url":
                out = await self.wait_for_url(
                    url_contains=str(step.get("url_contains") or ""),
                    timeout_ms=int(step.get("timeout_ms", 10_000)),
                    wait_until=str(step.get("wait_until") or "load"),
                )
                results.append({"step": idx, "action": action, "message": out})
            elif action == "screenshot_viewport":
                await self.screenshot_viewport(full_page=bool(step.get("full_page", False)))
                results.append({"step": idx, "action": action, "message": "Captured viewport PNG."})
            elif action == "screenshot_element":
                await self.screenshot_element(
                    element_id=str(step.get("element_id") or ""),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                )
                results.append({"step": idx, "action": action, "message": "Captured element PNG."})
            elif action == "highlight_element":
                await self.highlight_element(
                    element_id=str(step.get("element_id") or ""),
                    padding=int(step.get("padding", 16)),
                    style=str(step.get("style") or "circle"),
                    min_context=int(step.get("min_context", 6)),
                    wait_timeout_ms=int(step.get("wait_timeout_ms", 8_000)),
                    color=str(step.get("color") or "auto"),
                    prefer_color=str(step.get("prefer_color") or "red"),
                    min_contrast=float(step.get("min_contrast", 140.0)),
                    label=(None if step.get("label") is None else str(step.get("label"))),
                    label_position=str(step.get("label_position") or "auto"),
                    blur_background=bool(step.get("blur_background", False)),
                    stroke_width=int(step.get("stroke_width", 4)),
                )
                results.append({"step": idx, "action": action, "message": "Captured highlighted PNG."})
            else:
                raise ValueError(f"Unsupported flow action at step {idx}: {action!r}")

        return json.dumps(
            {
                "ok": True,
                "steps_executed": len(results),
                "final_url": self.page.url,
                "results": results,
            },
            indent=2,
        )

    async def screenshot_element(self, element_id: str, wait_timeout_ms: int = 8_000) -> bytes:
        handle = self._get_handle(element_id)
        await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)
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
        wait_timeout_ms: int = 8_000,
    ) -> tuple[bytes, dict[str, float]]:
        """
        Capture viewport region around element (CSS pixels), return png and element
        bounds **relative to the top-left of the captured image** in **pixel** coords.

        When ``min_context`` > 0, the clip is expanded so that at least that many of
        the nearest other interactive elements (by bbox edge distance) are also
        included, giving the viewer some surrounding context for orientation.
        """
        handle = self._get_handle(element_id)
        box = await self._ensure_actionable_element(handle, timeout_ms=wait_timeout_ms)

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
        wait_timeout_ms: int = 8_000,
        color: str = "auto",
        prefer_color: str = "red",
        min_contrast: float = 140.0,
        label: str | None = None,
        label_position: LabelPosition = "auto",
        blur_background: bool = False,
        stroke_width: int = 4,
    ) -> bytes:
        png, rel = await self.screenshot_clipped(
            element_id,
            padding=padding,
            min_context=min_context,
            wait_timeout_ms=wait_timeout_ms,
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
