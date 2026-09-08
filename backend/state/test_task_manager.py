import pytest
from backend.state.task_manager import TaskManager
from backend.state.task import TaskStatus

def test_task_manager_agent_brain_usage():
    manager = TaskManager()

    # Track events
    emitted_events = []
    def listener(event):
        emitted_events.append(event)
    
    # 1. Confirm on_event works
    manager.on_event(listener)

    # 2. Create a task
    task1 = manager.create_task("Run the first request")
    assert task1 is not None
    assert task1.task_id.startswith("task-")
    assert task1.fence_token.startswith("fence-")
    assert task1.status == TaskStatus.ACTIVE

    # Check if events were emitted for task1 creation
    assert len(emitted_events) == 2
    assert emitted_events[0]["event_name"] == "task.created"
    assert emitted_events[1]["event_name"] == "task.active"
    
    # 3. Simulate an interruption (creates a new task while first is active)
    task2 = manager.create_task("Wait, change the request")
    assert task2 is not None
    assert task2.task_id != task1.task_id
    assert task2.fence_token != task1.fence_token
    assert task2.status == TaskStatus.ACTIVE
    
    # Check if the active_task was updated to task2
    assert manager.active_task.task_id == task2.task_id
    
    # Events for interruption: obsolete, created, active
    assert len(emitted_events) == 5
    assert emitted_events[2]["event_name"] == "task.obsolete"
    assert emitted_events[2]["task_id"] == task1.task_id
    assert emitted_events[3]["event_name"] == "task.created"
    assert emitted_events[3]["task_id"] == task2.task_id
    assert emitted_events[4]["event_name"] == "task.active"
    assert emitted_events[4]["task_id"] == task2.task_id

    # 4. Simulate a stale fence_token check (from the first, interrupted task)
    stale_result = manager.check_fence(task1.task_id, task1.fence_token)
    assert stale_result == "rejected_stale"
    
    # Simulate a valid fence_token check (from the second, active task)
    valid_result = manager.check_fence(task2.task_id, task2.fence_token)
    assert valid_result == "accepted"

    # A valid fence paired with the wrong task ID is still stale.
    assert manager.check_fence(task1.task_id, task2.fence_token) == "rejected_stale"

    # 5. complete_task
    manager.complete_task(task2.task_id)
    assert manager.active_task.status == TaskStatus.COMPLETED
    
    # The fast-forward transition emits task.completed
    assert emitted_events[-1]["event_name"] == "task.completed"
    assert emitted_events[-1]["task_id"] == task2.task_id

    # 6. Confirm off_event works
    manager.off_event(listener)
    
    # Action that emits an event to test if listener still receives it
    manager.complete_task("random_task") # Won't emit because no matching task, but let's try a new task
    manager.create_task("Hello again")
    
    # The listener should not have received the new events
    # We were at 6 events (2 for task1, 3 for task2 interrupt, 1 for task2 complete)
    assert len(emitted_events) == 6
