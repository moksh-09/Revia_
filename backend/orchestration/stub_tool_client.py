"""
backend/orchestration/stub_tool_client.py
==========================================
Stub tool call -- CONTRACTS.md Section 5.

Behaviour (spec-literal):
  - Accepts { task_id, fence_token, tool_name, args }.
  - Waits a configurable fixed delay (default 3 s) to simulate delayed work.
  - Returns a neutral result with the SAME fence_token it received.
    (vedantkhar's fencing layer is responsible for deciding accept/reject;
    this stub never modifies the token.)
  - If cancelled (asyncio.CancelledError) before the delay expires, propagates
    the error. Fencing is the real safety net regardless of cancellation outcome.

Tool registry: the stub supports one neutral delayed demonstration workload.

Owner: shlok (backend/orchestration/).
This is a demonstration/test workload, not a product data source.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

from backend.orchestration.tool_contract import ToolRequest, ToolResponse


# Re-export contract types for orchestration callers.
__all__ = ["ToolRequest", "ToolResponse", "StubToolClient"]


# ---------------------------------------------------------------------------
# Neutral deterministic result
# ---------------------------------------------------------------------------

_STUB_RESULTS: dict[str, Any] = {
    "delayed_demo_work": {
        "message": "Delayed operation completed.",
    },
}

# Fallback for unknown tools -- still returns something so the pipeline
# doesn't crash during stub testing.
_UNKNOWN_TOOL_RESULT = {"message": "Delayed operation completed."}


# ---------------------------------------------------------------------------
# Stub Tool Client
# ---------------------------------------------------------------------------

class StubToolClient:
    """
    Generic delayed demonstration tool client.

    Simulates delayed work with a configurable delay.
    Correct fence_token passthrough is the responsibility of vedantkhar's
    fencing layer -- this stub echoes whatever token it receives unchanged.
    """

    def __init__(self, delay_s: float = 3.0) -> None:
        """
        Args:
            delay_s: Simulated query delay in seconds. Set to 0 for instant
                     results in unit tests, or >5 s to reliably trigger
                     Scenario B (interrupt during tool execution).
        """
        if delay_s < 0:
            raise ValueError("delay_s must be >= 0")
        self.delay_s = delay_s

    async def call_tool(self, request: ToolRequest) -> ToolResponse:
        """
        Execute a stubbed tool call.

        Waits self.delay_s seconds then returns a neutral result.
        Passes through task_id and fence_token unchanged.
        Raises asyncio.CancelledError if cancelled before completion
        (best-effort -- fencing must still be applied regardless).

        Args:
            request: ToolRequest with task_id, fence_token, tool_name, args.

        Returns:
            ToolResponse with the same task_id and fence_token, plus a
            neutral result dict.
        """
        logger.info(
            "[StubTool] call_tool  tool=%s  task_id=%s  delay=%.1fs",
            request.tool_name, request.task_id, self.delay_s,
        )

        # asyncio.CancelledError propagates naturally here -- callers that
        # cancel this coroutine get the error. Per contract: fencing is the
        # real safety net regardless of whether cancellation succeeds.
        if self.delay_s > 0:
            await asyncio.sleep(self.delay_s)

        result = _STUB_RESULTS.get(request.tool_name, _UNKNOWN_TOOL_RESULT)

        logger.info(
            "[StubTool] call_tool DONE  tool=%s  task_id=%s  fence_token=%s",
            request.tool_name, request.task_id, request.fence_token,
        )
        return ToolResponse(
            task_id=request.task_id,
            fence_token=request.fence_token,   # echoed unchanged -- vedantkhar checks this
            tool_name=request.tool_name,
            result=dict(result),               # copy so tests can't mutate the result
            error=None,
        )

    def available_tools(self) -> list[str]:
        """Return the list of tool names this stub supports."""
        return list(_STUB_RESULTS.keys())


# ---------------------------------------------------------------------------
# Quick smoke-test when run as __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async def _smoke_test() -> None:
        client = StubToolClient(delay_s=1.0)

        print(f"\nAvailable tools: {client.available_tools()}\n")

        req = ToolRequest(
            task_id="task-test-001",
            fence_token="fence-test-abc",
            tool_name="delayed_demo_work",
            args={},
        )

        print("=== Test 1: normal tool call ===")
        resp = await client.call_tool(req)
        assert resp.task_id == req.task_id
        assert resp.fence_token == req.fence_token   # echoed unchanged
        assert resp.error is None
        assert resp.result["message"] == "Delayed operation completed."
        print(f"PASS: result={resp.result}")

        print("\n=== Test 2: cancellation propagates ===")
        import asyncio as _asyncio
        req2 = ToolRequest(
            task_id="task-test-002",
            fence_token="fence-test-def",
            tool_name="delayed_demo_work",
            args={},
        )
        call_task = _asyncio.create_task(client.call_tool(req2))
        await _asyncio.sleep(0.1)   # let it start
        call_task.cancel()
        try:
            await call_task
            print("FAIL: CancelledError not raised")
        except _asyncio.CancelledError:
            print("PASS: CancelledError propagated as expected")

        print("\n=== Test 3: unknown tool returns neutral fallback ===")
        req3 = ToolRequest(
            task_id="task-test-003",
            fence_token="fence-test-ghi",
            tool_name="nonexistent_tool",
            args={},
        )
        client3 = StubToolClient(delay_s=0)
        resp3 = await client3.call_tool(req3)
        assert resp3.result is not None
        print(f"PASS: fallback result={resp3.result}")

        print("\nAll StubToolClient tests passed.")

    asyncio.run(_smoke_test())
