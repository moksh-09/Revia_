import pytest
import time
import threading
from backend.state.task import Task, TaskStatus
from backend.state.interruption import handle_interrupt
from backend.state.fencing import validate_tool_result

def test_happy_path_fencing():
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    task.transition_to(TaskStatus.ACTIVE)
    
    tool_result = {
        "task_id": "t1",
        "fence_token": "f1",
        "tool_name": "delayed_demo_work",
        "result": {"message": "done"},
        "error": None
    }
    
    validated = validate_tool_result(task, tool_result)
    assert validated["status"] == "accepted"

def test_stale_task_id_rejected():
    active_task = Task(task_id="t2", fence_token="f2", request_text="second request")
    active_task.transition_to(TaskStatus.ACTIVE)
    
    stale_result = {
        "task_id": "t1",  # Old task ID
        "fence_token": "f2", 
        "tool_name": "delayed_demo_work",
        "result": {"message": "done"},
        "error": None
    }
    
    validated = validate_tool_result(active_task, stale_result)
    assert validated["status"] == "rejected_stale"

def test_stale_fence_token_rejected():
    active_task = Task(task_id="t1", fence_token="new-fence", request_text="first request")
    active_task.transition_to(TaskStatus.ACTIVE)
    
    stale_result = {
        "task_id": "t1", 
        "fence_token": "old-fence", # Mismatched fence token
        "tool_name": "delayed_demo_work",
        "result": {"message": "done"},
        "error": None
    }
    
    validated = validate_tool_result(active_task, stale_result)
    assert validated["status"] == "rejected_stale"

def test_async_race_condition_simulation():
    """
    Simulates exactly the race condition in MASTER_README.md's "Full-duplex test example":
    1. Start a fake tool call with a fixed delay
    2. Interrupt while it's in flight (using handle_interrupt)
    3. Change the request
    4. Tool call completes and returns its delayed result with old fence_token
    5. Assert the result is rejected.
    """
    # Shared state mock Task Manager
    state = {
        "active_task": Task(task_id="t-first", fence_token="f-first", request_text="first request")
    }
    state["active_task"].transition_to(TaskStatus.ACTIVE)
    state["active_task"].transition_to(TaskStatus.TOOL_RUNNING)
    
    results_received = []
    
    def fake_tool_call(task_id, fence_token):
        # Inject fixed delay simulating slow work
        time.sleep(0.1)
        # Tool returns regardless of interruption
        results_received.append({
            "task_id": task_id,
            "fence_token": fence_token,
            "tool_name": "delayed_demo_work",
            "result": {"message": "done"},
            "error": None
        })
        
    # 1. Start the async tool call using the currently active task
    t = threading.Thread(target=fake_tool_call, args=(state["active_task"].task_id, state["active_task"].fence_token))
    t.start()
    
    # 2. Interrupt while it's in flight
    time.sleep(0.02)
    # 3. Change the request
    new_task = handle_interrupt(state["active_task"], new_request_text="Actually wait, make that Q2")
    state["active_task"] = new_task
    
    # 4. Wait for tool to finish and return its delayed result
    t.join()
    
    # 5. Result arrives at fencing layer, validated against CURRENT active task
    stale_result = results_received[0]
    validated = validate_tool_result(state["active_task"], stale_result)
    
    # Assert it is rejected because the active task has updated
    assert validated["status"] == "rejected_stale"

def test_llm_response_validation_gate():
    from backend.state.fencing import validate_llm_response
    
    task = Task(task_id="t1", fence_token="f1", request_text="first request")
    task.transition_to(TaskStatus.ACTIVE)
    task.transition_to(TaskStatus.GENERATING)
    
    llm_response = {
        "task_id": "t1",
        "fence_token": "f1",
        "response_text": "The first request is complete."
    }
    
    # 1. Happy path: Task is GENERATING, fence tokens match
    validated = validate_llm_response(task, llm_response.copy())
    assert validated["status"] == "accepted"
    
    # 2. Race condition: Task becomes OBSOLETE right before the check runs
    # This simulates handle_interrupt firing mid-generation.
    task.transition_to(TaskStatus.OBSOLETE)
    task.fence_token = ""
    
    validated_stale = validate_llm_response(task, llm_response.copy())
    assert validated_stale["status"] == "rejected_stale"

    # 3. Race condition: Fence tokens match, but state is somehow invalid
    task_2 = Task(task_id="t2", fence_token="f2", request_text="second request")
    task_2.transition_to(TaskStatus.CANCELLED) # Valid fence, but terminal state
    llm_response_2 = {
        "task_id": "t2",
        "fence_token": "f2",
        "response_text": "The second request is complete."
    }
    validated_stale_state = validate_llm_response(task_2, llm_response_2)
    assert validated_stale_state["status"] == "rejected_stale"

def test_stale_status_rejected_tool_result():
    active_task = Task(task_id="t1", fence_token="f1", request_text="first request")
    
    # Simulate an edge case where the task is OBSOLETE but the fence token was NOT cleared
    active_task.status = TaskStatus.OBSOLETE
    
    stale_result = {
        "task_id": "t1", 
        "fence_token": "f1", # Matches!
        "tool_name": "delayed_demo_work",
        "result": {"message": "done"},
        "error": None
    }
    
    validated = validate_tool_result(active_task, stale_result)
    assert validated["status"] == "rejected_stale"


