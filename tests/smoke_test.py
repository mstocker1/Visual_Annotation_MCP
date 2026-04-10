"""End-to-end smoke test (no MCP stdio): browser session + annotation features.

Run from the repo root with the project venv active:

    python tests/smoke_test.py

Exits non-zero if any assertion fails.
"""

from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

from visual_annotation_mcp.browser_session import BrowserSession

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _sample_page_data_url() -> str:
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Test</title>
<style>body { font-family: sans-serif; padding: 40px; background: #f0f0f0; }
nav { margin-bottom: 24px; }
a, button { margin: 12px; padding: 12px 24px; display: inline-block; }
button.red { background: #d62828; color: white; border: 0; border-radius: 6px; }
</style></head>
<body>
  <nav>
    <button type="button">Home</button>
    <button type="button">About</button>
    <a href="/login">Login</a>
    <a href="/signup">Sign up</a>
  </nav>
  <button type="button" class="red">Delete account</button>
</body></html>"""
    return "data:text/html;charset=utf-8," + quote(html)


async def main() -> None:
    url = _sample_page_data_url()
    session = BrowserSession()
    await session.start()
    try:
        msg = await session.navigate(url)
        assert "Loaded" in msg

        report = json.loads(await session.inspect_elements())
        assert report["count"] >= 5, report

        def find(predicate) -> str:
            for el in report["elements"]:
                if predicate(el):
                    return el["id"]
            raise AssertionError(f"No element matched predicate; report={report}")

        login_id = find(
            lambda el: el.get("tag") == "a"
            and ("login" in (el.get("href") or "").lower() or "login" in (el.get("text") or "").lower())
        )
        delete_id = find(lambda el: (el.get("text") or "").strip() == "Delete account")

        # 1. Classic circle highlight with context expansion.
        png = await session.highlight_element(login_id, padding=16, style="circle", min_context=4)
        assert png[:8] == _PNG_MAGIC

        # 2. Rectangle style.
        rect = await session.highlight_element(login_id, style="rectangle")
        assert rect[:8] == _PNG_MAGIC

        # 3. Arrow style.
        arrow = await session.highlight_element(login_id, style="arrow")
        assert arrow[:8] == _PNG_MAGIC

        # 4. Label + blurred background.
        labeled = await session.highlight_element(
            login_id,
            style="circle",
            label="Click here to sign in",
            blur_background=True,
        )
        assert labeled[:8] == _PNG_MAGIC

        # 5. Preferred-color fallback: red button on a light gray surround
        # should KEEP preferred red (plenty of contrast with #f0f0f0).
        red_ok = await session.highlight_element(
            delete_id, style="circle", color="auto", prefer_color="red"
        )
        assert red_ok[:8] == _PNG_MAGIC

        # 6. Explicit forced color bypasses the fallback.
        forced = await session.highlight_element(
            delete_id, style="circle", color="#00ff00"
        )
        assert forced[:8] == _PNG_MAGIC

        # 7. Viewport screenshot + stacking an annotation on top via annotate_last_image.
        viewport = await session.screenshot_viewport(full_page=False)
        assert viewport[:8] == _PNG_MAGIC
        stacked = session.annotate_last_image(
            x=40, y=40, width=120, height=40, style="rectangle", label="Nav"
        )
        assert stacked[:8] == _PNG_MAGIC

        print("smoke_test: OK")
        print(
            f"  elements={report['count']} "
            f"login={login_id} delete={delete_id} "
            f"sizes: circle={len(png)} rect={len(rect)} arrow={len(arrow)} "
            f"labeled={len(labeled)} red_auto={len(red_ok)} forced={len(forced)}"
        )
    finally:
        await session.stop()


if __name__ == "__main__":
    asyncio.run(main())
