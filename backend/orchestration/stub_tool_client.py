"""
backend/orchestration/stub_tool_client.py
==========================================
Stub tool call -- CONTRACTS.md Section 5.

Behaviour (spec-literal):
  - Accepts { task_id, fence_token, tool_name, args }.
  - Waits a configurable fixed delay (default 3 s) to simulate a slow
    analytics query.
  - Returns a hardcoded result with the SAME fence_token it received.
    (vedantkhar's fencing layer is responsible for deciding accept/reject;
    this stub never modifies the token.)
  - If cancelled (asyncio.CancelledError) before the delay expires, propagates
    the error. Fencing is the real safety net regardless of cancellation outcome.

Tool registry: the stub supports a small fixed set of tool names that
match what agent_brain.py will ask for. Each returns deterministic fake data.

Owner: shlok (backend/orchestration/).
Replace with real moksh module (backend/tools/tool_client.py) once logged
as DONE in PROGRESS.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response shapes -- match CONTRACTS.md Section 4 exactly
# ---------------------------------------------------------------------------

@dataclass
class ToolRequest:
    task_id: str
    fence_token: str
    tool_name: str
    args: dict


@dataclass
class ToolResponse:
    task_id: str
    fence_token: str
    tool_name: str
    result: Optional[dict]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Hardcoded stub results (deterministic synthetic sales data)
# ---------------------------------------------------------------------------

_STUB_RESULTS: dict[str, Any] = {
    "get_total_sales": {
        "total_sales_usd": 4_820_500.00,
        "period": "Q1 2026",
        "currency": "USD",
        "_stub": True,
    },
    "get_sales_by_region": {
        "regions": {
            "North": 1_250_000.00,
            "South": 980_000.00,
            "East": 1_430_000.00,
            "West": 1_160_500.00,
        },
        "period": "Q1 2026",
        "_stub": True,
    },
    "get_top_products": {
        "top_products": [
            {"product": "DataForge Pro", "units_sold": 3_400, "revenue_usd": 1_700_000},
            {"product": "Analytics Suite", "units_sold": 2_100, "revenue_usd": 1_050_000},
            {"product": "ReportBuilder", "units_sold": 1_800, "revenue_usd": 540_000},
        ],
        "period": "Q1 2026",
        "_stub": True,
    },
    "get_sales_trend": {
        "monthly": [
            {"month": "Jan 2026", "revenue_usd": 1_450_000},
            {"month": "Feb 2026", "revenue_usd": 1_620_000},
            {"month": "Mar 2026", "revenue_usd": 1_750_500},
        ],
        "_stub": True,
    },
    "get_rep_performance": {
        "reps": [
            {"name": "Alice Chen", "revenue_usd": 890_000, "deals_closed": 42},
            {"name": "Bob Mehta", "revenue_usd": 760_000, "deals_closed": 35},
            {"name": "Carol Santos", "revenue_usd": 1_020_000, "deals_closed": 51},
        ],
        "period": "Q1 2026",
        "_stub": True,
    },
}

# Fallback for unknown tools -- still returns something so the pipeline
# doesn't crash during stub testing.
_UNKNOWN_TOOL_RESULT = {"message": "stub result for unknown tool", "_stub": True}


# ---------------------------------------------------------------------------
# Stub Tool Client
# ---------------------------------------------------------------------------

class StubToolClient:
    """
    Stub analytics tool client.

    Simulates a slow analytics query with a configurable delay.
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

        Waits self.delay_s seconds then returns a hardcoded result.
        Passes through task_id and fence_token unchanged.
        Raises asyncio.CancelledError if cancelled before completion
        (best-effort -- fencing must still be applied regardless).

        Args:
            request: ToolRequest with task_id, fence_token, tool_name, args.

        Returns:
            ToolResponse with the same task_id and fence_token, plus a
            hardcoded result dict.  All results carry _stub=True.
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
            result=dict(result),               # copy so tests can't mutate _STUB_RESULTS
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
            tool_name="get_total_sales",
            args={"period": "Q1 2026"},
        )

        print("=== Test 1: normal tool call ===")
        resp = await client.call_tool(req)
        assert resp.task_id == req.task_id
        assert resp.fence_token == req.fence_token   # echoed unchanged
        assert resp.error is None
        assert resp.result["_stub"] is True
        print(f"PASS: result={resp.result}")

        print("\n=== Test 2: cancellation propagates ===")
        import asyncio as _asyncio
        req2 = ToolRequest(
            task_id="task-test-002",
            fence_token="fence-test-def",
            tool_name="get_sales_by_region",
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

        print("\n=== Test 3: unknown tool returns stub fallback ===")
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
