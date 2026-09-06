from backend.state.task import Task

def validate_tool_result(active_task: Task, tool_result: dict) -> dict:
    """
    Validates a tool result against the currently active task to prevent 
    stale results from updating state or triggering speech.
    
    Returns the tool_result dictionary with an added 'status' field 
    set to 'accepted' or 'rejected_stale'.
    """
    if not isinstance(tool_result, dict):
        return {"status": "rejected_stale", "error": "Invalid result format"}

    result_task_id = tool_result.get("task_id")
    result_fence_token = tool_result.get("fence_token")
    
    # Check if task_id matches the currently-active task's id
    if result_task_id != active_task.task_id:
        tool_result["status"] = "rejected_stale"
        return tool_result
        
    # Check if fence_token matches the active task's current fence_token
    if result_fence_token != active_task.fence_token:
        tool_result["status"] = "rejected_stale"
        return tool_result
        
    from backend.state.task import TaskStatus
    valid_states = {TaskStatus.ACTIVE, TaskStatus.TOOL_RUNNING, TaskStatus.GENERATING}
    if active_task.status not in valid_states:
        tool_result["status"] = "rejected_stale"
        return tool_result
        
    tool_result["status"] = "accepted"
    return tool_result

def validate_llm_response(active_task: Task, llm_response: dict) -> dict:
    """
    Validates an LLM-generated response against the currently active task 
    right before it is allowed to proceed to Rime (TTS).
    
    This intentionally reuses the exact same fencing check as tools 
    (comparing task_id and fence_token) to ensure one single mechanism
    protects against stale outputs, per MASTER_README.md Section 2.
    """
    # Reuse the same core fence check as tool validation
    # llm.response_drafted event payload: { fence_token, response_text, ... }
    # To reuse validate_tool_result exactly, we can wrap the response temporarily,
    # or just perform the same exact check natively. For cleanest reuse, we'll
    # pass it through validate_tool_result with a dummy tool_name.
    
    wrapper = {
        "task_id": llm_response.get("task_id"),
        "fence_token": llm_response.get("fence_token"),
        "tool_name": "_internal_llm_gate",
        "result": llm_response.get("response_text")
    }
    
    validated = validate_tool_result(active_task, wrapper)
    
    # Check if the task itself is in a valid state for generation to complete
    if validated["status"] == "accepted":
        from backend.state.task import TaskStatus
        if active_task.status not in {TaskStatus.ACTIVE, TaskStatus.GENERATING}:
            validated["status"] = "rejected_stale"
            
    # Apply the result back to the LLM response object
    llm_response["status"] = validated["status"]
    return llm_response
