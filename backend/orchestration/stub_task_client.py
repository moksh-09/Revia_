"""
backend/orchestration/stub_task_client.py
==========================================
Stub Task Manager -- CONTRACTS.md Section 5.

Behaviour (spec-literal):
  - create_task(request_text) -> returns new task_id + fence_token, status=ACTIVE.
  - interrupt(task_id) -> emits task.obsolete for the old task, then
    task.created + task.active for a new task.
  - Does NOT implement real fencing -- check_fence() always returns "accepted".
  - get_active_task() -> current active Task (or None if nothing active).

IMPORTANT: Only this stub (and vedantkhar's real module) may write task status.
No other module in backend/orchestration/ sets task.status directly.

Owner: shlok (backend/orchestration/).
Replace with real vedantkhar module once logged as DONE in PROGRESS.md.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task object -- matches CONTRACTS.md Section 1 schema exactly
# ---------------------------------------------------------------------------

@dataclass
class Task:
    task_id: str
    fence_token: str
    status: str                       # Only this module (stub) writes this field
    created_at: str
    updated_at: str
    request_text: str
    parent_task_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "fence_token": self.fence_token,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request_text": self.request_text,
            "parent_task_id": self.parent_task_id,
        }


# ---------------------------------------------------------------------------
# Event payloads -- match CONTRACTS.md Section 2
# ---------------------------------------------------------------------------

@dataclass
class TaskEvent:
    event: str           # e.g. "task.created", "task.active", "task.obsolete"
    task_id: str
    payload: dict = field(default_factory=dict)
    emitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


EventListener = Callable[[TaskEvent], None]


# ---------------------------------------------------------------------------
# Stub Task Manager
# ---------------------------------------------------------------------------

class StubTaskClient:
    """
    Stub Task Manager for shlok's orchestration layer.

    All fence checks return 'accepted' (no real fencing -- that is
    vedantkhar's job). Numbers and decisions here are stub behaviour only.
    """

    def __init__(self) -> None:
        self._active_task: Optional[Task] = None
        self._all_tasks: dict[str, Task] = {}
        self._listeners: list[EventListener] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_event(self, listener: EventListener) -> None:
        """Register a listener that will be called for every task event."""
        self._listeners.append(listener)

    def off_event(self, listener: EventListener) -> None:
        """Remove a previously registered event listener (no-op if not registered)."""
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def create_task(self, request_text: str) -> Task:
        """
        Create and activate a new task for *request_text*.

        Returns the new Task (status=ACTIVE, fence_token freshly generated).
        The previous active task is NOT automatically obsoleted -- call
        interrupt() for that.
        """
        now = datetime.now(timezone.utc).isoformat()
        task = Task(
            task_id=f"task-{uuid.uuid4().hex[:12]}",
            fence_token=f"fence-{uuid.uuid4().hex[:16]}",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            request_text=request_text,
            parent_task_id=(
                self._active_task.task_id if self._active_task else None
            ),
        )
        self._all_tasks[task.task_id] = task
        self._active_task = task

        logger.info(
            "[StubTask] task.created  task_id=%s  fence_token=%s",
            task.task_id, task.fence_token,
        )
        self._emit(TaskEvent(
            event="task.created",
            task_id=task.task_id,
            payload={
                "request_text": request_text,
                "created_at": now,
            },
        ))
        self._emit(TaskEvent(
            event="task.active",
            task_id=task.task_id,
            payload={"previous_task_id": task.parent_task_id},
        ))
        return task

    def interrupt(self, interrupted_task_id: str, new_request_text: str) -> Task:
        """
        Simulate an interrupt event per CONTRACTS.md Section 3:
          1. Move *interrupted_task_id* -> OBSOLETE, emit task.obsolete.
          2. Create a new task for *new_request_text*, emit task.created + task.active.

        Returns the newly created active Task.
        """
        now = datetime.now(timezone.utc).isoformat()

        # --- Obsolete the old task ---
        old_task = self._all_tasks.get(interrupted_task_id)
        if old_task is not None and old_task.status not in {
            "COMPLETED", "CANCELLED", "OBSOLETE", "FAILED"
        }:
            old_task.status = "OBSOLETE"
            old_task.updated_at = now
            logger.info(
                "[StubTask] task.obsolete  task_id=%s", interrupted_task_id
            )
            self._emit(TaskEvent(
                event="task.obsolete",
                task_id=interrupted_task_id,
                payload={"superseded_by_task_id": None},   # filled below
            ))

        # --- Create new active task ---
        new_task = Task(
            task_id=f"task-{uuid.uuid4().hex[:12]}",
            fence_token=f"fence-{uuid.uuid4().hex[:16]}",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            request_text=new_request_text,
            parent_task_id=interrupted_task_id,
        )
        self._all_tasks[new_task.task_id] = new_task
        self._active_task = new_task

        # Back-patch the superseded_by field on the obsolete event
        # (re-emit a richer version since we now have the new task_id)
        if old_task is not None:
            self._emit(TaskEvent(
                event="task.obsolete",
                task_id=interrupted_task_id,
                payload={"superseded_by_task_id": new_task.task_id},
            ))

        logger.info(
            "[StubTask] task.created (after interrupt)  task_id=%s  fence_token=%s",
            new_task.task_id, new_task.fence_token,
        )
        self._emit(TaskEvent(
            event="task.created",
            task_id=new_task.task_id,
            payload={
                "request_text": new_request_text,
                "created_at": now,
            },
        ))
        self._emit(TaskEvent(
            event="task.active",
            task_id=new_task.task_id,
            payload={"previous_task_id": interrupted_task_id},
        ))
        return new_task

    def complete_task(self, task_id: str) -> None:
        """Mark *task_id* as COMPLETED. Only valid for the active task."""
        task = self._all_tasks.get(task_id)
        if task is None:
            logger.warning("[StubTask] complete_task: unknown task_id=%s", task_id)
            return
        if task.status in {"COMPLETED", "CANCELLED", "OBSOLETE", "FAILED"}:
            logger.debug(
                "[StubTask] complete_task: task %s already terminal (%s) -- silently ignored",
                task_id, task.status,
            )
            return
        now = datetime.now(timezone.utc).isoformat()
        task.status = "COMPLETED"
        task.updated_at = now
        if self._active_task and self._active_task.task_id == task_id:
            self._active_task = None
        logger.info("[StubTask] task.completed  task_id=%s", task_id)
        self._emit(TaskEvent(event="task.completed", task_id=task_id, payload={}))

    def check_fence(self, task_id: str, fence_token: str) -> str:
        """
        Stub fence check -- always returns 'accepted'.

        Real fencing (fence_token comparison against active task) is
        vedantkhar's responsibility in backend/state/fencing.py.
        This stub satisfies the interface contract without implementing
        the real safety logic.
        """
        logger.debug(
            "[StubTask] check_fence  task_id=%s fence_token=%s  -> accepted (stub, no real fencing)",
            task_id,
            fence_token,
        )
        return "accepted"

    def check_llm_response(self, llm_response: dict) -> str:
        """Stub LLM gate -- always returns accepted."""
        return "accepted"

    def start_tool_running(self, task_id: str, tool_name: str) -> bool:
        task = self._all_tasks.get(task_id)
        if task and task.status == "ACTIVE":
            task.status = "TOOL_RUNNING"
            self._emit(TaskEvent(event="task.tool_running", task_id=task_id, payload={"tool_name": tool_name}))
            return True
        return False

    def start_generating(self, task_id: str) -> bool:
        task = self._all_tasks.get(task_id)
        if task and task.status in ("ACTIVE", "TOOL_RUNNING"):
            task.status = "GENERATING"
            self._emit(TaskEvent(event="task.generating", task_id=task_id, payload={}))
            return True
        return False

    def start_speaking(self, task_id: str, speech_id: str) -> bool:
        task = self._all_tasks.get(task_id)
        if task and task.status in ("ACTIVE", "GENERATING"):
            task.status = "SPEAKING"
            self._emit(TaskEvent(event="task.speaking", task_id=task_id, payload={"speech_id": speech_id}))
            return True
        return False

    def cancel_active_task(self, reason: str = "user_cancelled") -> Optional[Task]:
        if self._active_task and self._active_task.status not in ("COMPLETED", "CANCELLED", "OBSOLETE", "FAILED"):
            task_id = self._active_task.task_id
            self._active_task.status = "CANCELLED"
            self._active_task.fence_token = ""
            self._emit(TaskEvent(event="task.cancelled", task_id=task_id, payload={"reason": reason}))
            return self._active_task
        return None

    def get_active_task(self) -> Optional[Task]:
        """Return the currently active Task, or None."""
        return self._active_task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Return any task by ID."""
        return self._all_tasks.get(task_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, event: TaskEvent) -> None:
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("[StubTask] listener raised an exception")


# ---------------------------------------------------------------------------
# Quick smoke-test when run as __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    events: list[TaskEvent] = []

    client = StubTaskClient()
    client.on_event(events.append)

    print("\n=== Test 1: create_task ===")
    t1 = client.create_task("Run the first request")
    assert t1.status == "ACTIVE"
    assert client.get_active_task().task_id == t1.task_id
    print(f"PASS: task created  task_id={t1.task_id}  fence={t1.fence_token}")

    print("\n=== Test 2: check_fence (stub -- always accepted) ===")
    result = client.check_fence(t1.task_id, t1.fence_token)
    assert result == "accepted"
    print(f"PASS: check_fence -> {result}")

    print("\n=== Test 3: interrupt -> obsolete old, create new ===")
    t2 = client.interrupt(t1.task_id, "Actually, change the request.")
    assert t2.status == "ACTIVE"
    assert client.get_task(t1.task_id).status == "OBSOLETE"
    assert client.get_active_task().task_id == t2.task_id
    obsolete_events = [e for e in events if e.event == "task.obsolete"]
    assert any(
        e.payload.get("superseded_by_task_id") == t2.task_id
        for e in obsolete_events
    )
    print(f"PASS: T1 -> OBSOLETE  T2 -> ACTIVE  task_id={t2.task_id}")

    print("\n=== Test 4: complete_task ===")
    client.complete_task(t2.task_id)
    assert client.get_task(t2.task_id).status == "COMPLETED"
    assert client.get_active_task() is None
    print("PASS: T2 -> COMPLETED")

    print("\nAll StubTaskClient tests passed.")
