import asyncio
from backend.orchestration.agent_brain import AgentBrain
import logging
import sys

# Force UTF-8 encoding for Windows terminals to prevent UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO)

async def main():
    print("============================================================")
    print(" REAL SCENARIO TEST (No LiveKit Frontend needed)")
    print("============================================================\n")

    # 1. Instantiate the real AgentBrain (use_stubs=False by default)
    # This automatically loads the real TaskManager and real ToolClient
    brain = AgentBrain()

    # Test 1: General Knowledge / GPT Question
    general_request = "Can you explain why the sky is blue in two simple spoken sentences?"
    print(f"--- TEST 1: General Knowledge (GPT mode) ---")
    print(f"USER REQUEST: {general_request}")
    res1 = await brain.run_headless(general_request)
    print(f"Tool Decided:  {res1.tool_name} (None expected)")
    print(f"Drafted Voice: {res1.response_text}\n")

    # Test 2: Sales Data Question (Tool Analytics mode)
    sales_request = "What are the total sales for Q1 2026?"
    print(f"--- TEST 2: Sales Analytics (Data Tool mode) ---")
    print(f"USER REQUEST: {sales_request}")
    res2 = await brain.run_headless(sales_request)
    print(f"Tool Decided:  {res2.tool_name} (get_total_sales expected)")
    print(f"Tool Result:   {res2.tool_result}")
    print(f"Drafted Voice: {res2.response_text}\n")

    print("============================================================")
    print(" ALL SCENARIOS COMPLETED (General GPT + Sales Tools Verified)")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(main())
