from dataclasses import dataclass
from itertools import count
from typing import Optional


@dataclass
class Task:
    task_id: str
    fence_token: str
    request_text: str
    status: str = "ACTIVE"
    parent_task_id: Optional[str] = None


class StubTaskClient:
    """Minimal Task Manager stub for local development."""

    def __init__(self):
        self._task_counter = count(1)
        self._fence_counter = count(1)
        self.current_task: Optional[Task] = None

    def create_task(
        self,
        request_text: str,
        parent_task_id: Optional[str] = None,
    ) -> Task:
        task_number = next(self._task_counter)
        fence_number = next(self._fence_counter)

        task = Task(
            task_id=f"task-{task_number}",
            fence_token=f"fence-{fence_number}",
            request_text=request_text,
            status="ACTIVE",
            parent_task_id=parent_task_id,
        )

        self.current_task = task
        return task

    def interrupt(self, new_request_text: str) -> Task:
        old_task = self.current_task

        if old_task is not None:
            old_task.status = "OBSOLETE"

        parent_task_id = old_task.task_id if old_task else None

        return self.create_task(
            request_text=new_request_text,
            parent_task_id=parent_task_id,
        )

    def accept_tool_result(self, task_id: str, fence_token: str) -> bool:
        """Stub behavior: always accepts tool results."""
        return True
    
    
    
    