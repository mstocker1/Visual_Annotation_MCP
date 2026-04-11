"""Unit tests for FlowExecutor control-flow semantics."""

from __future__ import annotations

import unittest
from typing import Any

from visual_annotation_mcp.flow_executor import FlowExecutor


class FlowExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_succeeds_on_second_attempt(self) -> None:
        attempts = {"n": 0}

        async def execute_action(action: str, step: dict[str, Any]) -> dict[str, Any]:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise RuntimeError("first failure")
            return {"message": "ok"}

        ex = FlowExecutor()
        out = await ex.run(
            steps=[{"action": "fake", "retry": {"max_attempts": 2, "backoff_ms": 0}}],
            execute_action=execute_action,
            final_url_getter=lambda: "about:blank",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["results"][0]["attempt"], 2)

    async def test_on_error_skip(self) -> None:
        async def execute_action(action: str, step: dict[str, Any]) -> dict[str, Any]:
            if action == "bad":
                raise RuntimeError("boom")
            return {"message": "done"}

        ex = FlowExecutor()
        out = await ex.run(
            steps=[{"action": "bad", "on_error": "skip"}, {"action": "good"}],
            execute_action=execute_action,
            final_url_getter=lambda: "about:blank",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["results"][0]["status"], "skipped")
        self.assertEqual(out["results"][1]["status"], "completed")

    async def test_on_error_fallback_action(self) -> None:
        async def execute_action(action: str, step: dict[str, Any]) -> dict[str, Any]:
            if action == "bad":
                raise RuntimeError("boom")
            return {"message": f"ran:{action}"}

        ex = FlowExecutor()
        out = await ex.run(
            steps=[
                {
                    "action": "bad",
                    "on_error": "fallback_action",
                    "fallback_action": {"action": "good"},
                }
            ],
            execute_action=execute_action,
            final_url_getter=lambda: "about:blank",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["results"][0]["status"], "fallback_completed")
        self.assertEqual(out["results"][0]["fallback_action"], "good")

    async def test_store_and_condition_and_interpolation(self) -> None:
        async def execute_action(action: str, step: dict[str, Any]) -> dict[str, Any]:
            return {"message": f"text={step.get('text', '')}", "value": step.get("value", "")}

        ex = FlowExecutor()
        out = await ex.run(
            steps=[
                {"action": "seed", "value": "Continue", "store_as": "button_text"},
                {
                    "action": "use",
                    "if_var": "button_text",
                    "equals": {"message": "text=", "value": "Continue"},
                    "text": "{{ button_text.value }}",
                },
            ],
            execute_action=execute_action,
            final_url_getter=lambda: "about:blank",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["results"]), 2)


if __name__ == "__main__":
    unittest.main()
