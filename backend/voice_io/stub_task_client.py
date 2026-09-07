"""Temporary Task Manager client used until backend/state/ is available."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class StubTask:
    task_id: str
    fence_token: str
    status: str
    created_at: str
    updated_at: str
    request_text: str
    parent_task_id: str | None


class StubTaskManager:
    """In-memory Stub Task Manager defined by CONTRACTS.md Section 5."""

    def __init__(self) -> None:
        self.active_task: StubTask | None = None
        self.events: list[dict[str, Any]] = []

    @staticmethod
    def _new_task(request_text: str, parent_task_id: str | None) -> StubTask:
        timestamp = _timestamp()
        return StubTask(
            task_id=str(uuid4()),
            fence_token=str(uuid4()),
            status="ACTIVE",
            created_at=timestamp,
            updated_at=timestamp,
            request_text=request_text,
            parent_task_id=parent_task_id,
        )

    def _emit_created_and_active(
        self, task: StubTask, previous_task_id: str | None
    ) -> None:
        self.events.extend((
            {
                "event": "task.created",
                "task_id": task.task_id,
                "request_text": task.request_text,
                "created_at": task.created_at,
            },
            {
                "event": "task.active",
                "task_id": task.task_id,
                "previous_task_id": previous_task_id,
            },
        ))

    def create_task(
        self, request_text: str, parent_task_id: str | None = None
    ) -> StubTask:
        previous_task_id = self.active_task.task_id if self.active_task else None
        task = self._new_task(request_text, parent_task_id)
        self.active_task = task
        self._emit_created_and_active(task, previous_task_id)
        return task

    def handle_interrupt(self, request_text: str = "") -> StubTask:
        previous_task = self.active_task
        new_task = self._new_task(
            request_text=request_text,
            parent_task_id=previous_task.task_id if previous_task else None,
        )
        if previous_task:
            self.events.append({
                "event": "task.obsolete",
                "task_id": previous_task.task_id,
                "superseded_by_task_id": new_task.task_id,
            })

        self.active_task = new_task
        self._emit_created_and_active(
            new_task,
            previous_task.task_id if previous_task else None,
        )
        return new_task

    @staticmethod
    def accept_tool_result() -> str:
        return "accepted"