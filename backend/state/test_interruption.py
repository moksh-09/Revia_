import pytest
from backend.state.task import Task, TaskStatus
from backend.state.interruption import handle_interrupt

def test_interrupt_during_created():
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    assert task.status == TaskStatus.CREATED
    
    new_task = handle_interrupt(task, new_request_text="second request")
    
    assert task.status == TaskStatus.OBSOLETE
    assert task.fence_token == ""  # Invalidated
    
    assert new_task.status == TaskStatus.ACTIVE
    assert new_task.parent_task_id == "t1"
    assert new_task.request_text == "second request"

def test_interrupt_during_active():
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    task.transition_to(TaskStatus.ACTIVE)
    
    new_task = handle_interrupt(task, new_request_text="second request")
    
    assert task.status == TaskStatus.OBSOLETE
    assert task.fence_token == ""
    assert new_task.status == TaskStatus.ACTIVE

def test_interrupt_during_tool_running():
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    task.transition_to(TaskStatus.ACTIVE)
    task.transition_to(TaskStatus.TOOL_RUNNING)
    
    new_task = handle_interrupt(task, new_request_text="second request")
    
    assert task.status == TaskStatus.OBSOLETE
    assert task.fence_token == ""
    assert new_task.status == TaskStatus.ACTIVE

def test_interrupt_during_generating():
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    task.transition_to(TaskStatus.ACTIVE)
    task.transition_to(TaskStatus.GENERATING)
    
    new_task = handle_interrupt(task, new_request_text="second request")
    
    assert task.status == TaskStatus.OBSOLETE
    assert task.fence_token == ""
    assert new_task.status == TaskStatus.ACTIVE

def test_interrupt_during_speaking():
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    task.transition_to(TaskStatus.ACTIVE)
    task.transition_to(TaskStatus.GENERATING)
    task.transition_to(TaskStatus.SPEAKING)
    
    new_task = handle_interrupt(task, new_request_text="second request")
    
    assert task.status == TaskStatus.OBSOLETE
    assert task.fence_token == ""
    assert new_task.status == TaskStatus.ACTIVE
