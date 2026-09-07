import uuid
from typing import Callable, Optional

from backend.state.task import Task, TaskStatus
from backend.state.interruption import handle_interrupt
from backend.state.fencing import validate_tool_result
from backend.state.timeline import TimelineEmitter


class TaskManager:
    """
    Wraps and delegates to the state modules (task.py, interruption.py,
    fencing.py, timeline.py) to expose the exact interface expected by
    agent_brain.py.
    """

    def __init__(self):
        self.active_task: Optional[Task] = None
        self.timeline = TimelineEmitter()

    def create_task(self, request_text: str) -> Task:
        """
        Creates a new task via existing Task class (or handles interruption
        if a task is already active), transitions it to ACTIVE, returns it.
        """
        if self.active_task and self.active_task.status not in {
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
            TaskStatus.OBSOLETE,
            TaskStatus.FAILED,
        }:
            # Interruption flow
            old_task_id = self.active_task.task_id
            new_task = handle_interrupt(self.active_task, request_text)
            
            # handle_interrupt already created it and moved it to ACTIVE.
            # We just need to emit the events.
            self.timeline.emit_task_obsolete(old_task_id, new_task.task_id)
            self.timeline.emit_task_created(new_task.task_id, new_task.request_text, new_task.created_at)
            self.timeline.emit_task_active(new_task.task_id, old_task_id)
            
            self.active_task = new_task
        else:
            # Normal creation flow
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            fence_token = f"fence-{uuid.uuid4().hex[:8]}"
            task = Task(
                task_id=task_id,
                fence_token=fence_token,
                request_text=request_text
            )
            self.timeline.emit_task_created(task.task_id, task.request_text, task.created_at)
            
            task.transition_to(TaskStatus.ACTIVE)
            self.timeline.emit_task_active(task.task_id)
            
            self.active_task = task

        return self.active_task

    def check_fence(self, fence_token: str) -> str:
        """
        Returns 'accepted' or 'rejected_stale'. Uses the real validate_tool_result
        logic under the hood.
        """
        if not self.active_task:
            return "rejected_stale"

        # Since agent_brain.py only passes fence_token, we construct a dummy
        # tool result dictionary using the active task's id to delegate to 
        # fencing.py's validate_tool_result logic.
        tool_result = {
            "task_id": self.active_task.task_id,
            "fence_token": fence_token,
        }
        validated = validate_tool_result(self.active_task, tool_result)
        return validated["status"]

    def complete_task(self, task_id: str) -> None:
        """
        Transitions the given task to COMPLETED via the existing state machine.
        """
        if not self.active_task or self.active_task.task_id != task_id:
            return

        # Fast-forward through necessary states to reach COMPLETED without
        # violating the VALID_TRANSITIONS in task.py
        if self.active_task.status == TaskStatus.ACTIVE:
            self.active_task.transition_to(TaskStatus.GENERATING)
        if self.active_task.status == TaskStatus.TOOL_RUNNING:
            self.active_task.transition_to(TaskStatus.GENERATING)
        if self.active_task.status == TaskStatus.GENERATING:
            self.active_task.transition_to(TaskStatus.SPEAKING)
        if self.active_task.status == TaskStatus.SPEAKING:
            self.active_task.transition_to(TaskStatus.COMPLETED)
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
