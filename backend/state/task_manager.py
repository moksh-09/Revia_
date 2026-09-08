import uuid
from typing import Callable, Optional

from backend.state.task import Task, TaskStatus
from backend.state.interruption import handle_interrupt
from backend.state.fencing import validate_tool_result, validate_llm_response
from backend.state.timeline import TimelineEmitter


_TERMINAL_STATUSES = {
    TaskStatus.COMPLETED,
    TaskStatus.CANCELLED,
    TaskStatus.OBSOLETE,
    TaskStatus.FAILED,
}


class TaskManager:
    """
    Wraps and delegates to the state modules (task.py, interruption.py,
    fencing.py, timeline.py) to expose the exact interface expected by
    agent_brain.py.
    """

    def __init__(self):
        self.active_task: Optional[Task] = None
        self.tasks: dict[str, Task] = {}
        self.last_interrupted_task_id: Optional[str] = None
        self.timeline = TimelineEmitter()

    def create_task(self, request_text: str) -> Task:
        """
        Creates a new task via existing Task class (or handles interruption
        if a task is already active), transitions it to ACTIVE, returns it.
        """
        if self.active_task and self.active_task.status not in _TERMINAL_STATUSES:
            # Interruption flow while active task was non-terminal
            old_task_id = self.active_task.task_id
            new_task = handle_interrupt(self.active_task, request_text)
            
            self.timeline.emit_task_obsolete(old_task_id, new_task.task_id)
            self.timeline.emit_task_created(new_task.task_id, new_task.request_text, new_task.created_at)
            self.timeline.emit_task_active(new_task.task_id, old_task_id)
            
            self.tasks[new_task.task_id] = new_task
            self.active_task = new_task
            self.last_interrupted_task_id = None
        else:
            # Normal creation flow (or after obsolete_active_task was called)
            parent_id = self.last_interrupted_task_id
            if not parent_id and self.active_task:
                if self.active_task.status == TaskStatus.OBSOLETE:
                    parent_id = self.active_task.task_id

            task_id = f"task-{uuid.uuid4().hex[:8]}"
            fence_token = f"fence-{uuid.uuid4().hex[:8]}"
            task = Task(
                task_id=task_id,
                fence_token=fence_token,
                request_text=request_text,
                parent_task_id=parent_id,
            )
            self.timeline.emit_task_created(task.task_id, task.request_text, task.created_at)
            
            task.transition_to(TaskStatus.ACTIVE)
            self.timeline.emit_task_active(task.task_id, parent_id)
            
            self.tasks[task.task_id] = task
            self.active_task = task
            self.last_interrupted_task_id = None

        return self.active_task

    def start_tool_running(self, task_id: str, tool_name: str) -> bool:
        """Transitions active task to TOOL_RUNNING and emits event."""
        if not self.active_task or self.active_task.task_id != task_id:
            return False
        if self.active_task.status != TaskStatus.ACTIVE:
            return False
        self.active_task.transition_to(TaskStatus.TOOL_RUNNING)
        self.timeline.emit_task_tool_running(task_id, tool_name)
        return True

    def start_generating(self, task_id: str) -> bool:
        """Transitions active task to GENERATING and emits event."""
        if not self.active_task or self.active_task.task_id != task_id:
            return False
        if self.active_task.status not in (TaskStatus.ACTIVE, TaskStatus.TOOL_RUNNING):
            return False
        self.active_task.transition_to(TaskStatus.GENERATING)
        self.timeline.emit_task_generating(task_id)
        return True

    def start_speaking(self, task_id: str, speech_id: str) -> bool:
        """Transitions active task to SPEAKING and emits event."""
        if not self.active_task or self.active_task.task_id != task_id:
            return False
        if self.active_task.status not in (TaskStatus.ACTIVE, TaskStatus.GENERATING):
            return False
        self.active_task.transition_to(TaskStatus.SPEAKING)
        self.timeline.emit_task_speaking(task_id, speech_id)
        return True

    def cancel_active_task(self, reason: str = "user_cancelled") -> Optional[Task]:
        """Cancels current non-terminal task, invalidates fence token, emits event."""
        if not self.active_task or self.active_task.status in _TERMINAL_STATUSES:
            return None
        cancelled_task = self.active_task
        task_id = cancelled_task.task_id
        cancelled_task.transition_to(TaskStatus.CANCELLED)
        cancelled_task.fence_token = ""
        self.timeline.emit_task_cancelled(task_id, reason)
        return cancelled_task

    def fail_task(self, task_id: str, error: str) -> None:
        """Fails the specified task, invalidates fence token, emits event."""
        task = self.tasks.get(task_id) or (self.active_task if self.active_task and self.active_task.task_id == task_id else None)
        if not task or task.status in _TERMINAL_STATUSES:
            return
        task.transition_to(TaskStatus.FAILED)
        task.fence_token = ""
        self.timeline.emit_task_failed(task_id, error)

    def check_fence(self, task_id: str, fence_token: str) -> str:
        """
        Returns 'accepted' or 'rejected_stale'. Uses the real validate_tool_result
        logic under the hood.
        """
        if not self.active_task:
            return "rejected_stale"

        tool_result = {
            "task_id": task_id,
            "fence_token": fence_token,
        }
        validated = validate_tool_result(self.active_task, tool_result)
        return validated["status"]

    def check_llm_response(self, llm_response: dict) -> str:
        """Returns 'accepted' or 'rejected_stale' for an llm.response_drafted payload."""
        if not self.active_task:
            return "rejected_stale"
        validated = validate_llm_response(self.active_task, llm_response.copy())
        return validated["status"]

    def get_active_task(self) -> Optional[Task]:
        """Return the currently active task, if any."""
        return self.active_task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Return a task by task_id."""
        return self.tasks.get(task_id) or (self.active_task if self.active_task and self.active_task.task_id == task_id else None)

    def obsolete_active_task(self, superseded_by_task_id: Optional[str] = None) -> None:
        """
        Obsolete the current non-terminal task on voice interrupt.

        Does not create a replacement task — that happens when the next
        transcribed utterance arrives via create_task().
        """
        if not self.active_task or self.active_task.status in _TERMINAL_STATUSES:
            return

        old_task_id = self.active_task.task_id
        self.last_interrupted_task_id = old_task_id
        self.active_task.transition_to(TaskStatus.OBSOLETE)
        self.active_task.fence_token = ""
        self.timeline.emit_task_obsolete(old_task_id, superseded_by_task_id)

    def complete_task(self, task_id: str) -> None:
        """
        Transitions the given task to COMPLETED via the existing state machine.
        """
        task = self.get_task(task_id)
        if not task or task.status in _TERMINAL_STATUSES:
            return

        # Walk forward through the pipeline states that may have been skipped
        if task.status == TaskStatus.ACTIVE:
            task.transition_to(TaskStatus.GENERATING)
        elif task.status == TaskStatus.TOOL_RUNNING:
            task.transition_to(TaskStatus.GENERATING)

        if task.status == TaskStatus.GENERATING:
            task.transition_to(TaskStatus.SPEAKING)
            
        if task.status == TaskStatus.SPEAKING:
            task.transition_to(TaskStatus.COMPLETED)
            self.timeline.emit_task_completed(task_id)

    def on_event(self, listener: Callable) -> None:
        """
        Registers a listener that fires on every event timeline.py emits.
        """
        self.timeline.subscribe(listener)

    def off_event(self, listener: Callable) -> None:
        """
        Unregisters the listener.
        """
        if listener in self.timeline.listeners:
            self.timeline.listeners.remove(listener)
