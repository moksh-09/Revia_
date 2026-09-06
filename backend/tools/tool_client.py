"""
Tool client for REVIA.

Receives task/fence information, executes deterministic analytics,
and returns the result using the agreed tool-call contract.
"""

import time

from .dataset import get_dataset
from .analytics import (
    total_sales,
    sales_by_region,
    sales_by_product,
    top_products,
    sales_trend,
)


class ToolClient:
    def __init__(self, delay_seconds=0):
        self.delay_seconds = delay_seconds
        self.data = get_dataset()

    def call(self, task_id, fence_token, tool_name, args=None):
        """
        Execute a tool using the REVIA tool-call contract.

        Returns:
            {
                "task_id": str,
                "fence_token": str,
                "tool_name": str,
                "result": dict | int | list,
                "error": str | None
            }
        """

        if args is None:
            args = {}

        # Artificial delay used for interruption/stale-result scenarios.
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        try:
            result = self._execute_tool(tool_name, args)

            return {
                "task_id": task_id,
                "fence_token": fence_token,
                "tool_name": tool_name,
                "result": result,
                "error": None,
            }

        except ValueError as exc:
            return {
                "task_id": task_id,
                "fence_token": fence_token,
                "tool_name": tool_name,
                "result": None,
                "error": str(exc),
            }

        except Exception as exc:
            return {
                "task_id": task_id,
                "fence_token": fence_token,
                "tool_name": tool_name,
                "result": None,
                "error": f"Tool execution failed: {exc}",
            }

    def _execute_tool(self, tool_name, args):
        """Map a tool name to the corresponding deterministic function."""

        if tool_name == "total_sales":
            return total_sales(self.data)

        if tool_name == "sales_by_region":
            return sales_by_region(self.data)

        if tool_name == "sales_by_product":
            return sales_by_product(self.data)

        if tool_name == "top_products":
            limit = args.get("limit", 5)

            if not isinstance(limit, int) or limit <= 0:
                raise ValueError("limit must be a positive integer")

            return top_products(self.data, limit)

        if tool_name == "sales_trend":
            return sales_trend(self.data)

        raise ValueError(f"Unknown tool: {tool_name}")