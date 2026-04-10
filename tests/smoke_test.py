"""End-to-end smoke test (no MCP stdio): browser session + highlight."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

from visual_annotation_mcp.browser_session import BrowserSession


def _sample_page_data_url() -> str:
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Test</title>
<style>body { font-family: sans-serif; padding: 40px; }
a, button { margin: 12px; padding: 12px 24px; display: inline-block; }</style></head>
<body>
  <nav>
    <button type="button">Home</button>
    <button type="button">About</button>
    <a href="/login">Login</a>
    <a href="/signup">Sign up</a>
  </nav>
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
        assert report["count"] >= 4, report

        login_id = None
        for el in report["elements"]:
            if el.get("tag") == "a" and "login" in (el.get("href") or "").lower():
                login_id = el["id"]
                break
            t = (el.get("text") or "").lower()
            if el.get("tag") == "a" and "login" in t:
                login_id = el["id"]
                break
        assert login_id is not None, report

        png = await session.highlight_element(login_id, padding=24, style="circle")
        assert png[:8] == b"\x89PNG\r\n\x1a\n", "Output should be PNG"

        viewport = await session.screenshot_viewport(full_page=False)
        assert viewport[:8] == b"\x89PNG\r\n\x1a\n"

        print("smoke_test: OK")
        print(f"  elements: {report['count']}, highlighted: {login_id}, png_bytes={len(png)}")
    finally:
        await session.stop()


if __name__ == "__main__":
    asyncio.run(main())
