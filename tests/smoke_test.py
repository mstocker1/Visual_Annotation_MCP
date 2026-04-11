"""End-to-end smoke test (no MCP stdio): browser session + annotation features.

Run from the repo root with the project venv active:

    python tests/smoke_test.py

Exits non-zero if any assertion fails.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from urllib.parse import quote

from visual_annotation_mcp.browser_session import BrowserSession

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _sample_page_data_url() -> str:
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Test</title>
<style>body { font-family: sans-serif; padding: 40px; background: #f0f0f0; }
nav { margin-bottom: 24px; }
a, button { margin: 12px; padding: 12px 24px; display: inline-block; }
button.red { background: #d62828; color: white; border: 0; border-radius: 6px; }
.hidden { display: none; }
#login-blocker {
    position: fixed;
    z-index: 9999;
    pointer-events: auto;
    background: rgba(255, 255, 255, 0.15);
}
</style></head>
<body>
  <nav>
    <button type="button">Home</button>
    <button type="button">About</button>
        <a id="login-link" href="/login">Login</a>
    <a href="/signup">Sign up</a>
  </nav>
  <button type="button" class="red">Delete account</button>
    <button id="delayed-btn" class="hidden" type="button">Async Action</button>
    <div id="login-blocker" aria-hidden="true"></div>
    <script>
        const blocker = document.getElementById('login-blocker');
        const login = document.getElementById('login-link');
        const r = login.getBoundingClientRect();
        blocker.style.left = `${r.left}px`;
        blocker.style.top = `${r.top}px`;
        blocker.style.width = `${r.width}px`;
        blocker.style.height = `${r.height}px`;
        setTimeout(() => blocker.remove(), 800);

        setTimeout(() => {
            const delayed = document.getElementById('delayed-btn');
            delayed.classList.remove('hidden');
            delayed.textContent = 'Async Action';
        }, 600);
    </script>
</body></html>"""
    return "data:text/html;charset=utf-8," + quote(html)


def _flow_page_data_url() -> str:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Flow Test</title>
<style>
body { font-family: sans-serif; margin: 0; padding: 24px; }
#cookie-modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}
#cookie-dialog {
    background: white;
    border-radius: 10px;
    padding: 16px;
    width: 320px;
}
#signup { display: none; margin-top: 20px; }
#step2 { display: none; margin-top: 20px; }
input { padding: 8px; min-width: 280px; }
button { margin-top: 10px; padding: 8px 12px; }
</style>
</head><body>
    <h1>Signup Flow</h1>
    <div id="cookie-modal">
        <div id="cookie-dialog" role="dialog" aria-label="Cookie dialog">
            <p>This site uses cookies.</p>
            <button id="accept-cookies" type="button">Accept Cookies</button>
        </div>
    </div>

    <section id="signup">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" placeholder="you@example.com" />
        <button id="next-btn" type="button">Continue</button>
    </section>

    <section id="step2">
        <p>Step 2 ready</p>
        <button id="finish-btn" type="button">Finish</button>
    </section>

    <script>
        const modal = document.getElementById('cookie-modal');
        const signup = document.getElementById('signup');
        const step2 = document.getElementById('step2');
        window.__flowStep = 'cookie';
        document.getElementById('accept-cookies').addEventListener('click', () => {
            modal.remove();
            signup.style.display = 'block';
            window.location.hash = 'signup';
            window.__flowStep = 'signup';
        });
        document.getElementById('next-btn').addEventListener('click', () => {
            signup.style.display = 'none';
            step2.style.display = 'block';
            window.location.hash = 'step2';
            window.__flowStep = 'step2';
        });
        document.getElementById('finish-btn').addEventListener('click', () => {
            window.location.hash = 'done';
            window.__flowStep = 'done';
        });
    </script>
</body></html>"""
        return "data:text/html;charset=utf-8," + quote(html)


def _form_page_data_url() -> str:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Form Test</title>
<style>
body { font-family: sans-serif; padding: 20px; }
form { display: grid; gap: 8px; max-width: 360px; }
label { display: block; }
</style></head><body>
    <h1>Profile Form</h1>
    <form id="profile-form">
        <label for="country">Country</label>
        <select id="country" name="country">
            <option value="us">United States</option>
            <option value="ca">Canada</option>
            <option value="mx">Mexico</option>
        </select>

        <label>
            <input id="terms" name="terms" type="checkbox" />
            Accept Terms
        </label>

        <label for="resume">Resume</label>
        <input id="resume" name="resume" type="file" />

        <button id="submit-profile" type="submit">Submit Profile</button>
    </form>

    <p id="result"></p>

    <script>
        window.__submitted = false;
        const form = document.getElementById('profile-form');
        const country = document.getElementById('country');
        const terms = document.getElementById('terms');
        const resume = document.getElementById('resume');
        form.addEventListener('submit', (ev) => {
            ev.preventDefault();
            window.__submitted = true;
            const fileName = resume.files && resume.files.length ? resume.files[0].name : '';
            document.getElementById('result').textContent = `submitted:${country.value}:${terms.checked}:${fileName}`;
        });
    </script>
</body></html>"""
        return "data:text/html;charset=utf-8," + quote(html)


def _extract_page_data_url() -> str:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Extract Test</title></head><body>
    <header><h1>Dashboard</h1></header>
    <main>
        <section aria-label="Metrics">
            <h2>Revenue</h2>
            <p id="blurb">Monthly summary</p>
        </section>
        <table id="sales-table">
            <thead>
                <tr><th>Product</th><th>Units</th></tr>
            </thead>
            <tbody>
                <tr><td>Alpha</td><td>10</td></tr>
                <tr><td>Beta</td><td>7</td></tr>
            </tbody>
        </table>
    </main>
    <footer>End</footer>
</body></html>"""
        return "data:text/html;charset=utf-8," + quote(html)


async def main() -> None:
    url = _sample_page_data_url()
    flow_url = _flow_page_data_url()
    form_url = _form_page_data_url()
    extract_url = _extract_page_data_url()
    session = BrowserSession()
    await session.start()
    try:
        msg = await session.navigate(url)
        assert "Loaded" in msg

        report = json.loads(await session.inspect_elements(wait_timeout_ms=6_000))
        assert report["count"] >= 6, report

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
        delayed_id = find(lambda el: (el.get("text") or "").strip() == "Async Action")

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

        # 7. Element was covered on initial paint; highlight waits until it is actionable.
        covered_then_ready = await session.highlight_element(login_id, wait_timeout_ms=5_000)
        assert covered_then_ready[:8] == _PNG_MAGIC

        # 8. Delayed element becomes visible after load; screenshot waits and succeeds.
        delayed = await session.screenshot_element(delayed_id, wait_timeout_ms=5_000)
        assert delayed[:8] == _PNG_MAGIC

        # 9. Viewport screenshot + stacking an annotation on top via annotate_last_image.
        viewport = await session.screenshot_viewport(full_page=False)
        assert viewport[:8] == _PNG_MAGIC
        stacked = session.annotate_last_image(
            x=40, y=40, width=120, height=40, style="rectangle", label="Nav"
        )
        assert stacked[:8] == _PNG_MAGIC

        # 10. Convenience dismiss helper can clear modal-driven blockers.
        await session.navigate(flow_url)
        dismiss_msg = await session.dismiss_common_popups(wait_timeout_ms=4_000, max_clicks=2)
        assert "clicked=" in dismiss_msg
        flow_report = json.loads(await session.inspect_elements(wait_timeout_ms=4_000))
        assert any(
            (el.get("dom_id") or "") in {"email", "next-btn", "finish-btn"}
            for el in flow_report["elements"]
        ), flow_report

        # 11. Convenience fill/click helpers in a deterministic sequence.
        await session.navigate(flow_url)
        flow_report = json.loads(await session.inspect_elements(wait_timeout_ms=4_000))
        accept_id = ""
        for el in flow_report["elements"]:
            if (el.get("dom_id") or "") == "accept-cookies":
                accept_id = el["id"]
                break
        assert accept_id, flow_report
        await session.click_element(accept_id)
        flow_report = json.loads(await session.inspect_elements(wait_timeout_ms=4_000))
        assert any((el.get("dom_id") or "") == "email" for el in flow_report["elements"])

        def flow_find2(predicate) -> str:
            for el in flow_report["elements"]:
                if predicate(el):
                    return el["id"]
            raise AssertionError(f"No flow element matched predicate; report={flow_report}")

        email_id = flow_find2(lambda el: (el.get("dom_id") or "") == "email")

        fill_selector_msg = await session.fill_by_selector("#email", "qa@example.com")
        assert "Filled selector" in fill_selector_msg
        click_text_msg = await session.click_by_text("Continue")
        assert "Clicked element with text match" in click_text_msg
        assert await session.page.evaluate("() => window.__flowStep") == "step2"

        # 12. Sprint 1 locator/wait tools.
        await session.navigate(flow_url)
        await session.wait_for_selector("#accept-cookies", state="visible")
        role_click = await session.click_by_role("button", name="Accept Cookies")
        assert "Clicked role=" in role_click
        await session.wait_for_text("Email")
        label_fill = await session.fill_by_label("Email", "sprint1@example.com")
        assert "Filled label" in label_fill
        selector_click = await session.click_by_selector("#next-btn")
        assert "Clicked selector" in selector_click
        await session.wait_for_selector("#finish-btn", state="visible")
        assert await session.page.evaluate("() => window.__flowStep") == "step2"

        flow_report = json.loads(await session.inspect_elements(wait_timeout_ms=4_000))
        finish_id = ""
        for el in flow_report["elements"]:
            if (el.get("dom_id") or "") == "finish-btn":
                finish_id = el["id"]
                break
        assert finish_id, flow_report

        flow_result = json.loads(
            await session.run_flow(
                [
                    {"action": "wait_for_text", "text": "Finish"},
                    {"action": "click_by_text", "text": "Finish"},
                    {"action": "wait_for_url", "url_contains": "data:text/html"},
                    {"action": "screenshot_viewport", "full_page": False},
                ]
            )
        )
        assert flow_result["ok"] is True
        assert flow_result["steps_executed"] == 4
        assert await session.page.evaluate("() => window.__flowStep") == "done"
        assert session.last_image_bytes is not None
        assert session.last_image_bytes[:8] == _PNG_MAGIC

        # 13. Sprint 2 overlay helpers.
        await session.navigate(flow_url)
        blockers = json.loads(await session.detect_blockers(max_candidates=5, min_area_ratio=0.05))
        assert blockers["count"] >= 1, blockers
        dismiss_overlay_msg = await session.dismiss_overlay(strategy="auto", wait_timeout_ms=4_000)
        assert "Dismiss overlay attempted" in dismiss_overlay_msg

        await session.navigate(flow_url)
        cookie_msg = await session.close_cookie_banner(wait_timeout_ms=4_000)
        assert "Cookie banner close attempt" in cookie_msg

        # 14. Sprint 2 form controls: select/check/upload/submit.
        await session.navigate(form_url)
        await session.wait_for_selector("#country")
        selected_msg = await session.select_option(selector="#country", value="ca")
        assert "Selected option" in selected_msg
        checked_msg = await session.check_uncheck(selector="#terms", checked=True)
        assert "Checked target control" in checked_msg

        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp:
                tmp.write("resume-data")
                tmp_path = tmp.name

            upload_msg = await session.upload_file(file_path=tmp_path, selector="#resume")
            assert "Uploaded file" in upload_msg
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        submit_msg = await session.submit_form(selector="#profile-form")
        assert "Submitted form target" in submit_msg
        assert await session.page.evaluate("() => window.__submitted") is True
        result_text = await session.page.evaluate("() => document.getElementById('result').textContent")
        assert "submitted:ca:true:" in result_text, result_text

        # 15. Sprint 2 actions inside run_flow.
        await session.navigate(form_url)
        tmp_path2 = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp2:
                tmp2.write("resume-data-2")
                tmp_path2 = tmp2.name

            flow_result2 = json.loads(
                await session.run_flow(
                    [
                        {"action": "select_option", "selector": "#country", "value": "mx"},
                        {"action": "check_uncheck", "selector": "#terms", "checked": True},
                        {"action": "upload_file", "selector": "#resume", "file_path": tmp_path2},
                        {"action": "submit_form", "selector": "#profile-form"},
                        {"action": "wait_for_text", "text": "submitted:mx:true"},
                    ]
                )
            )
        finally:
            if tmp_path2 and os.path.exists(tmp_path2):
                os.unlink(tmp_path2)

        assert flow_result2["ok"] is True
        assert flow_result2["steps_executed"] == 5

        # 16. Sprint 3 flow controls: retry, skip, store_as, conditional run.
        await session.navigate(form_url)
        flow_result3 = json.loads(
            await session.run_flow(
                [
                    {"action": "detect_blockers", "store_as": "blk"},
                    {
                        "action": "wait_for_text",
                        "text": "Profile Form",
                        "if_var": "blk",
                        "equals": {"count": 0},
                    },
                    {
                        "action": "wait_for_text",
                        "text": "THIS_WONT_EXIST",
                        "timeout_ms": 50,
                        "retry": {"max_attempts": 2, "backoff_ms": 0},
                        "on_error": "skip",
                    },
                    {"action": "wait_for_text", "text": "Profile Form"},
                ]
            )
        )
        assert flow_result3["ok"] is True
        assert flow_result3["steps_executed"] == 4
        assert "blk" in flow_result3.get("context", {})
        assert any(r.get("status") == "skipped" for r in flow_result3["results"])

        # 17. Sprint 4 assertions and extraction tools.
        await session.navigate(extract_url)
        assert "Assertion passed" in await session.assert_element_exists(selector="#sales-table")
        assert "Assertion passed" in await session.assert_element_visible(selector="#sales-table")
        assert "Assertion passed" in await session.assert_text_contains("Monthly summary")
        assert "Assertion passed" in await session.assert_url_matches("data:text/html")

        element_data = json.loads(
            await session.extract_element(
                selector="#blurb",
                attributes=["id"],
                include_text=True,
            )
        )
        assert element_data["id"] == "blurb"
        assert "Monthly summary" in element_data.get("text", "")

        table_data = json.loads(await session.extract_table("#sales-table"))
        assert table_data["row_count"] >= 2
        assert table_data["rows"][0]["Product"] == "Alpha"

        page_model = json.loads(await session.extract_page_model())
        assert page_model["interactive_count"] >= 0
        assert any(h.get("text") == "Dashboard" for h in page_model["headings"])

        # 18. Sprint 4 flow actions.
        flow_result4 = json.loads(
            await session.run_flow(
                [
                    {"action": "extract_page_model", "store_as": "pm"},
                    {"action": "assert_text_contains", "text": "Revenue"},
                    {
                        "action": "extract_table",
                        "selector": "#sales-table",
                        "store_as": "tbl",
                    },
                    {
                        "action": "assert_element_exists",
                        "selector": "#sales-table",
                        "if_var": "tbl",
                    },
                ]
            )
        )
        assert flow_result4["ok"] is True
        assert "pm" in flow_result4.get("context", {})
        assert "tbl" in flow_result4.get("context", {})

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
