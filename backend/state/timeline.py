from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

class TimelineEmitter:
    """
    In-process event bus for task state transitions.
    Implements the exact event names and payloads defined in CONTRACTS.md Section 2.
    """
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []

    def subscribe(self, listener: Callable[[Dict[str, Any]], None]):
        self.listeners.append(listener)

    def _emit(self, event_name: str, task_id: str, payload: Dict[str, Any]):
        event = {
            "event_name": event_name,
            "task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        self.history.append(event)
        for listener in self.listeners:
            listener(event)

    def emit_task_created(self, task_id: str, request_text: str, created_at: str):
        self._emit("task.created", task_id, {
            "request_text": request_text,
            "created_at": created_at
        })

    def emit_task_active(self, task_id: str, previous_task_id: Optional[str] = None):
        self._emit("task.active", task_id, {
            "previous_task_id": previous_task_id
        })

    def emit_task_tool_running(self, task_id: str, tool_name: str):
        self._emit("task.tool_running", task_id, {
            "tool_name": tool_name
        })

    def emit_task_generating(self, task_id: str):
        self._emit("task.generating", task_id, {})

    def emit_task_speaking(self, task_id: str, speech_id: str):
        self._emit("task.speaking", task_id, {
            "speech_id": speech_id
        })

    def emit_task_completed(self, task_id: str):
        self._emit("task.completed", task_id, {})

    def emit_task_cancelled(self, task_id: str, reason: str):
        self._emit("task.cancelled", task_id, {
            "reason": reason
        })

    def emit_task_obsolete(self, task_id: str, superseded_by_task_id: str):
        self._emit("task.obsolete", task_id, {
            "superseded_by_task_id": superseded_by_task_id
        })

    def emit_task_failed(self, task_id: str, error: str):
        self._emit("task.failed", task_id, {
            "error": error
        })
