from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

class TaskStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    TOOL_RUNNING = "TOOL_RUNNING"
    GENERATING = "GENERATING"
    SPEAKING = "SPEAKING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    OBSOLETE = "OBSOLETE"
    FAILED = "FAILED"

class IllegalTransitionError(Exception):
    """Raised when an invalid task state transition is attempted."""
    pass

VALID_TRANSITIONS = {
    TaskStatus.CREATED: {
        TaskStatus.ACTIVE, TaskStatus.CANCELLED, TaskStatus.OBSOLETE, TaskStatus.FAILED
    },
    TaskStatus.ACTIVE: {
        TaskStatus.TOOL_RUNNING, TaskStatus.GENERATING, TaskStatus.CANCELLED, TaskStatus.OBSOLETE, TaskStatus.FAILED
    },
    TaskStatus.TOOL_RUNNING: {
        TaskStatus.GENERATING, TaskStatus.CANCELLED, TaskStatus.OBSOLETE, TaskStatus.FAILED
    },
    TaskStatus.GENERATING: {
        TaskStatus.SPEAKING, TaskStatus.CANCELLED, TaskStatus.OBSOLETE, TaskStatus.FAILED
    },
    TaskStatus.SPEAKING: {
        TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.OBSOLETE, TaskStatus.FAILED
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.OBSOLETE: set(),
    TaskStatus.FAILED: set(),
}

class Task(BaseModel):
    task_id: str
    fence_token: str
    status: TaskStatus = TaskStatus.CREATED
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_text: str
    parent_task_id: Optional[str] = None

    def transition_to(self, new_status: TaskStatus):
        """
        Safely transitions the task to a new state.
        Only allows transitions explicitly defined in VALID_TRANSITIONS.
        Updates the updated_at timestamp on successful transition.
        """
        if new_status not in VALID_TRANSITIONS[self.status]:
            raise IllegalTransitionError(
                f"Cannot transition from {self.status} to {new_status}"
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc).isoformat()
