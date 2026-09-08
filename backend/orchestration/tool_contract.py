"""Generic task-scoped tool request and response contracts."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ToolRequest:
    task_id: str
    fence_token: str
    tool_name: str
    args: dict[str, Any]


@dataclass
class ToolResponse:
    task_id: str
    fence_token: str
    tool_name: str
    result: Optional[dict[str, Any] | int | list[Any]]
    error: Optional[str]

