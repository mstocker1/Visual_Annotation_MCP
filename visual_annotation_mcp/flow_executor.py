"""Flow execution engine with retry, conditional, and fallback semantics."""

from __future__ import annotations

import asyncio
import re
from typing import Any

_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


class FlowExecutor:
    async def run(
        self,
        steps: list[dict[str, Any]],
        execute_action: Any,
        final_url_getter: Any,
    ) -> dict[str, Any]:
        context: dict[str, Any] = {}
        results: list[dict[str, Any]] = []

        for idx, raw_step in enumerate(steps, start=1):
            step = self._render_step(raw_step, context)
            action = str(step.get("action") or "").strip().lower()

            if not self._should_run(step, context):
                results.append({"step": idx, "action": action, "status": "skipped", "reason": "condition"})
                continue

            retry_cfg = step.get("retry") if isinstance(step.get("retry"), dict) else {}
            max_attempts = max(1, int(retry_cfg.get("max_attempts", 1)))
            backoff_ms = max(0, int(retry_cfg.get("backoff_ms", 0)))

            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    payload = await execute_action(action, step)
                    if isinstance(step.get("store_as"), str) and str(step.get("store_as")).strip():
                        context[str(step.get("store_as"))] = payload
                    row = {"step": idx, "action": action, "status": "completed", "attempt": attempt}
                    if isinstance(payload, dict):
                        row.update(payload)
                    else:
                        row["message"] = str(payload)
                    results.append(row)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_attempts and backoff_ms > 0:
                        await asyncio.sleep(backoff_ms / 1000.0)
                    if attempt < max_attempts:
                        continue

                    on_error = str(step.get("on_error") or "fail").strip().lower()
                    if on_error == "skip":
                        results.append(
                            {
                                "step": idx,
                                "action": action,
                                "status": "skipped",
                                "reason": "on_error=skip",
                                "error": str(exc),
                            }
                        )
                        break

                    if on_error == "fallback_action":
                        fb = step.get("fallback_action")
                        if not isinstance(fb, dict) or not str(fb.get("action") or "").strip():
                            raise ValueError(
                                f"Step {idx} configured on_error=fallback_action but fallback_action is invalid"
                            ) from exc

                        fb_step = self._render_step(fb, context)
                        fb_action = str(fb_step.get("action") or "").strip().lower()
                        fb_payload = await execute_action(fb_action, fb_step)
                        row = {
                            "step": idx,
                            "action": action,
                            "status": "fallback_completed",
                            "fallback_action": fb_action,
                            "attempt": attempt,
                            "error": str(exc),
                        }
                        if isinstance(fb_payload, dict):
                            row["fallback_result"] = fb_payload
                        else:
                            row["fallback_result"] = {"message": str(fb_payload)}
                        results.append(row)
                        break

                    raise RuntimeError(f"Flow step {idx} action {action!r} failed: {exc}") from exc

            if last_exc is not None and results and results[-1].get("status") in {"skipped", "fallback_completed"}:
                continue

        return {
            "ok": True,
            "steps_executed": len(results),
            "final_url": str(final_url_getter()),
            "results": results,
            "context": context,
        }

    def _should_run(self, step: dict[str, Any], context: dict[str, Any]) -> bool:
        if_var = step.get("if_var")
        if if_var is None:
            return True
        key = str(if_var)
        current = context.get(key)
        if "equals" in step:
            return current == step.get("equals")
        return bool(current)

    def _render_step(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        return self._render_value(step, context)

    def _render_value(self, value: Any, context: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {k: self._render_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_value(v, context) for v in value]
        if not isinstance(value, str):
            return value

        full = _VAR_PATTERN.fullmatch(value)
        if full:
            key = full.group(1)
            resolved = self._resolve_context_path(context, key)
            return value if resolved is None else resolved

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            resolved = self._resolve_context_path(context, key)
            if resolved is None:
                return match.group(0)
            return str(resolved)

        return _VAR_PATTERN.sub(repl, value)

    def _resolve_context_path(self, context: dict[str, Any], path: str) -> Any | None:
        parts = path.split(".")
        cur: Any = context
        for part in parts:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
                continue
            return None
        return cur
