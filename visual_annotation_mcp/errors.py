"""Shared error model for MCP tool contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    INVALID_JSON = "invalid_json"
    INVALID_FLOW = "invalid_flow"
    INVALID_STEP = "invalid_step"
    UNSUPPORTED_ACTION = "unsupported_action"
    EXECUTION_ERROR = "execution_error"


@dataclass(slots=True)
class MCPToolError(Exception):
    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.code.value,
            "message": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload
