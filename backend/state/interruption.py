import uuid
from backend.state.task import Task, TaskStatus

def handle_interrupt(current_task: Task, new_request_text: str = "") -> Task:
    """
    Handles an interruption event by moving the current task to OBSOLETE,
    invalidating its fence token, and returning a newly created ACTIVE task.
    """
    terminal_states = {
        TaskStatus.COMPLETED, 
        TaskStatus.CANCELLED, 
        TaskStatus.OBSOLETE, 
        TaskStatus.FAILED
    }
    
    if current_task.status not in terminal_states:
        # Move current task to OBSOLETE based on CONTRACTS.md Section 5
        current_task.transition_to(TaskStatus.OBSOLETE)
        # Invalidate its fence token
        current_task.fence_token = ""
        
    new_task = Task(
        task_id=f"task-{uuid.uuid4().hex[:8]}",
        fence_token=f"fence-{uuid.uuid4().hex[:8]}",
        request_text=new_request_text,
        parent_task_id=current_task.task_id
    )
    
    # According to CONTRACTS.md Section 3/5, create new task and mark ACTIVE
    new_task.transition_to(TaskStatus.ACTIVE)
    return new_task
