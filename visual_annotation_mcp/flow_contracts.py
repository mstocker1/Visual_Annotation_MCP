"""Flow schema validation and parsing helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from visual_annotation_mcp.errors import ErrorCode, MCPToolError

# Sprint 0 schema v2: action-centric steps with action-specific required fields.
ACTION_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "navigate": ("url",),
    "inspect_elements": (),
    "click_element": ("element_id",),
    "click_by_selector": ("selector",),
    "click_by_role": ("role",),
    "fill_element": ("element_id", "text"),
    "fill_by_label": ("label", "text"),
    "click_by_text": ("text",),
    "fill_by_selector": ("selector", "text"),
    "dismiss_common_popups": (),
    "detect_blockers": (),
    "dismiss_overlay": (),
    "close_cookie_banner": (),
    "wait_for_selector": ("selector",),
    "wait_for_text": ("text",),
    "assert_element_exists": (),
    "assert_element_visible": (),
    "assert_text_contains": ("text",),
    "assert_url_matches": ("pattern",),
    "extract_element": (),
    "extract_form_data": (),
    "extract_table": ("selector",),
    "extract_page_model": (),
    "select_option": (),
    "check_uncheck": (),
    "submit_form": (),
    "upload_file": ("file_path",),
    "press_key": ("key",),
    "wait_for_url": ("url_contains",),
    "screenshot_viewport": (),
    "screenshot_element": ("element_id",),
    "highlight_element": ("element_id",),
}

SUPPORTED_ACTIONS = tuple(ACTION_REQUIRED_FIELDS.keys())


def parse_flow_json(flow_json: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(flow_json)
    except json.JSONDecodeError as exc:
        raise MCPToolError(
            code=ErrorCode.INVALID_JSON,
            message="flow_json must be valid JSON.",
            details={"line": exc.lineno, "column": exc.colno, "msg": exc.msg},
        ) from exc

    if not isinstance(parsed, list):
        raise MCPToolError(
            code=ErrorCode.INVALID_FLOW,
            message="flow_json must decode to a non-empty list of step objects.",
        )
    if not parsed:
        raise MCPToolError(
            code=ErrorCode.INVALID_FLOW,
            message="Flow must contain at least one step.",
        )

    _validate_steps(parsed)
    return parsed


def _validate_steps(steps: Iterable[Any]) -> None:
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=f"Step {index} must be an object.",
            )

        action_raw = step.get("action")
        action = str(action_raw or "").strip().lower()
        if not action:
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=f"Step {index} is missing 'action'.",
            )

        if action not in ACTION_REQUIRED_FIELDS:
            raise MCPToolError(
                code=ErrorCode.UNSUPPORTED_ACTION,
                message=f"Unsupported action at step {index}: {action!r}.",
                details={"supported_actions": list(SUPPORTED_ACTIONS)},
            )

        required = ACTION_REQUIRED_FIELDS[action]
        missing = [field for field in required if _is_missing(step.get(field))]
        if missing:
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=f"Step {index} action {action!r} missing required field(s): {', '.join(missing)}.",
            )

        _validate_action_specific(index=index, action=action, step=step)


def _validate_action_specific(index: int, action: str, step: dict[str, Any]) -> None:
    if action in {"select_option", "check_uncheck", "submit_form", "upload_file"}:
        has_selector = not _is_missing(step.get("selector"))
        has_element_id = not _is_missing(step.get("element_id"))
        if not (has_selector or has_element_id):
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=(
                    f"Step {index} action {action!r} requires one of selector or element_id."
                ),
            )

    if action == "select_option":
        has_value = not _is_missing(step.get("value"))
        has_label = not _is_missing(step.get("label"))
        has_index = step.get("index") is not None
        if not (has_value or has_label or has_index):
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=(
                    f"Step {index} action 'select_option' requires one of value, label, or index."
                ),
            )

    if action in {"assert_element_exists", "assert_element_visible", "extract_element"}:
        has_selector = not _is_missing(step.get("selector"))
        has_element_id = not _is_missing(step.get("element_id"))
        if not (has_selector or has_element_id):
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=(
                    f"Step {index} action {action!r} requires one of selector or element_id."
                ),
            )

    retry = step.get("retry")
    if retry is not None:
        if not isinstance(retry, dict):
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=f"Step {index} field 'retry' must be an object.",
            )
        if "max_attempts" in retry:
            try:
                max_attempts = int(retry.get("max_attempts", 1))
            except Exception as exc:
                raise MCPToolError(
                    code=ErrorCode.INVALID_STEP,
                    message=f"Step {index} retry.max_attempts must be an integer.",
                ) from exc
            if max_attempts < 1:
                raise MCPToolError(
                    code=ErrorCode.INVALID_STEP,
                    message=f"Step {index} retry.max_attempts must be >= 1.",
                )
        if "backoff_ms" in retry:
            try:
                backoff_ms = int(retry.get("backoff_ms", 0))
            except Exception as exc:
                raise MCPToolError(
                    code=ErrorCode.INVALID_STEP,
                    message=f"Step {index} retry.backoff_ms must be an integer.",
                ) from exc
            if backoff_ms < 0:
                raise MCPToolError(
                    code=ErrorCode.INVALID_STEP,
                    message=f"Step {index} retry.backoff_ms must be >= 0.",
                )

    if "if_var" in step and _is_missing(step.get("if_var")):
        raise MCPToolError(
            code=ErrorCode.INVALID_STEP,
            message=f"Step {index} field 'if_var' must be a non-empty string.",
        )

    if "store_as" in step and _is_missing(step.get("store_as")):
        raise MCPToolError(
            code=ErrorCode.INVALID_STEP,
            message=f"Step {index} field 'store_as' must be a non-empty string.",
        )

    on_error = step.get("on_error")
    if on_error is not None:
        mode = str(on_error).strip().lower()
        if mode not in {"fail", "skip", "fallback_action"}:
            raise MCPToolError(
                code=ErrorCode.INVALID_STEP,
                message=(
                    f"Step {index} on_error must be one of: fail, skip, fallback_action."
                ),
            )
        if mode == "fallback_action":
            fb = step.get("fallback_action")
            if not isinstance(fb, dict) or _is_missing(fb.get("action")):
                raise MCPToolError(
                    code=ErrorCode.INVALID_STEP,
                    message=(
                        f"Step {index} on_error=fallback_action requires a fallback_action object with action."
                    ),
                )


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
