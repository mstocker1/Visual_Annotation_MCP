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


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
