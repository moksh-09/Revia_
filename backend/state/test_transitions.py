import pytest
from backend.state.task import Task, TaskStatus, IllegalTransitionError

def test_happy_path_transitions():
    task = Task(task_id="test-1", fence_token="fence-1", request_text="hello world")
    assert task.status == TaskStatus.CREATED
    
    # Follow the full happy path
    task.transition_to(TaskStatus.ACTIVE)
    assert task.status == TaskStatus.ACTIVE
    
    task.transition_to(TaskStatus.TOOL_RUNNING)
    assert task.status == TaskStatus.TOOL_RUNNING
    
    task.transition_to(TaskStatus.GENERATING)
    assert task.status == TaskStatus.GENERATING
    
    task.transition_to(TaskStatus.SPEAKING)
    assert task.status == TaskStatus.SPEAKING
    
    task.transition_to(TaskStatus.COMPLETED)
    assert task.status == TaskStatus.COMPLETED

def test_alternate_happy_path_no_tools():
    # Active -> Generating direct transition
    task = Task(task_id="test-2", fence_token="fence-2", request_text="hello again")
    task.transition_to(TaskStatus.ACTIVE)
    task.transition_to(TaskStatus.GENERATING)
    assert task.status == TaskStatus.GENERATING

def test_interruption_to_terminal_states():
    # Test valid transitions to terminal states from various points
    task_a = Task(task_id="test-a", fence_token="fence-a", request_text="test")
    task_a.transition_to(TaskStatus.CANCELLED)
    assert task_a.status == TaskStatus.CANCELLED

    task_b = Task(task_id="test-b", fence_token="fence-b", request_text="test")
    task_b.transition_to(TaskStatus.ACTIVE)
    task_b.transition_to(TaskStatus.OBSOLETE)
    assert task_b.status == TaskStatus.OBSOLETE

    task_c = Task(task_id="test-c", fence_token="fence-c", request_text="test")
    task_c.transition_to(TaskStatus.ACTIVE)
    task_c.transition_to(TaskStatus.TOOL_RUNNING)
    task_c.transition_to(TaskStatus.FAILED)
    assert task_c.status == TaskStatus.FAILED

def test_illegal_transition_from_terminal_states():
    # Cannot move OUT of terminal states
    task = Task(task_id="test-terminal", fence_token="fence", request_text="test")
    
    task.status = TaskStatus.COMPLETED
    with pytest.raises(IllegalTransitionError, match="Cannot transition from TaskStatus.COMPLETED to TaskStatus.ACTIVE"):
        task.transition_to(TaskStatus.ACTIVE)

    task.status = TaskStatus.CANCELLED
    with pytest.raises(IllegalTransitionError, match="Cannot transition from TaskStatus.CANCELLED to TaskStatus.ACTIVE"):
        task.transition_to(TaskStatus.ACTIVE)

    task.status = TaskStatus.OBSOLETE
    with pytest.raises(IllegalTransitionError, match="Cannot transition from TaskStatus.OBSOLETE to TaskStatus.FAILED"):
        task.transition_to(TaskStatus.FAILED)

def test_illegal_skip_transitions():
    # Cannot skip mandatory states in happy path
    task = Task(task_id="test-skip", fence_token="fence", request_text="test")
    
    with pytest.raises(IllegalTransitionError, match="Cannot transition from TaskStatus.CREATED to TaskStatus.TOOL_RUNNING"):
        task.transition_to(TaskStatus.TOOL_RUNNING)
        
    task.transition_to(TaskStatus.ACTIVE)
    with pytest.raises(IllegalTransitionError, match="Cannot transition from TaskStatus.ACTIVE to TaskStatus.SPEAKING"):
        task.transition_to(TaskStatus.SPEAKING)

def test_updated_at_changes_on_transition():
    import time
    task = Task(task_id="test-time", fence_token="fence", request_text="test")
    old_updated_at = task.updated_at
    
    # slight delay may be needed if resolution is too fast, but string isoformat is usually fine
    time.sleep(0.001)
    task.transition_to(TaskStatus.ACTIVE)
    assert task.updated_at != old_updated_at
    assert task.updated_at >= task.created_at
