"""
Real integration check: your fencing logic vs moksh's real ToolClient.

Simulates the exact race condition from MASTER_README.md's "Full-duplex
test example": a tool call is in flight, the task gets interrupted
(OBSOLETE) before the tool call returns, and the late result must be
rejected by your fencing check -- using moksh's ACTUAL ToolClient, not a
stub.
"""
from backend.state.task import Task, TaskStatus
from backend.state.fencing import validate_tool_result
from backend.tools.tool_client import ToolClient

def main():
    # 1. Create a task, move it into TOOL_RUNNING (as it would be mid-flow)
    task = Task(task_id="t1", fence_token="f1", request_text="what are total sales?")
    task.transition_to(TaskStatus.ACTIVE)
    task.transition_to(TaskStatus.TOOL_RUNNING)

    # 2. moksh's real tool client, with an artificial delay simulating a
    #    slow analytics query (his real delay_seconds mechanism)
    client = ToolClient(delay_seconds=3)

    # 3. Simulate an interruption happening WHILE the tool call is in flight.
    #    In the real system this would happen concurrently; here we simulate
    #    the ordering explicitly since this is a synchronous script.
    #    The old task is invalidated BEFORE the tool result comes back.
    original_fence_token = task.fence_token
    task.transition_to(TaskStatus.OBSOLETE)
    task.fence_token = "invalidated-by-interrupt"

    # 4. The tool call finally completes and returns -- using the OLD
    #    fence_token, exactly as CONTRACTS.md Section 3 describes:
    #    "moksh's in-flight tool call, if it completes anyway, emits
    #    tool.result with the OLD fence_token"
    print("Calling moksh's real ToolClient (will take ~3s to simulate delay)...")
    result = client.call(
        task_id="t1",
        fence_token=original_fence_token,  # the OLD token, now stale
        tool_name="total_sales",
    )
    print(f"Raw result from moksh's ToolClient: {result}")

    # 5. Your real fencing check against this real result
    validated = validate_tool_result(task, result)
    print(f"Fencing check result: {validated['status']}")

    assert validated["status"] == "rejected_stale", (
        f"FAIL: expected rejected_stale, got {validated['status']}"
    )
    print("\nPASS: stale tool result correctly rejected end-to-end "
          "(real fencing.py + real moksh ToolClient)")

    # 6. Sanity check: confirm the HAPPY PATH also still works with real
    #    moksh code (no interruption -- result should be accepted)
    task2 = Task(task_id="t2", fence_token="f2", request_text="what are total sales?")
    task2.transition_to(TaskStatus.ACTIVE)
    task2.transition_to(TaskStatus.TOOL_RUNNING)

    client_fast = ToolClient(delay_seconds=0)
    result2 = client_fast.call(task_id="t2", fence_token="f2", tool_name="total_sales")
    validated2 = validate_tool_result(task2, result2)

    assert validated2["status"] == "accepted", (
        f"FAIL: expected accepted, got {validated2['status']}"
    )
    print(f"PASS: happy path also correctly accepted "
          f"(result={result2['result']})")

if __name__ == "__main__":
    main()
