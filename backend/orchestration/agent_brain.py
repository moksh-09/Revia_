"""
backend/orchestration/agent_brain.py
======================================
LLM orchestration layer -- shlok, REVIA Phase 1.

Responsibilities (CONTRACTS.md Section 4 / MASTER_README.md Section 6):
  1. Receive a transcribed user utterance.
  2. Call Groq (openai/gpt-oss-20b) to decide which analytics tool to
     call (or none if the question can be answered directly).
  3. Call the tool through stub_tool_client (later: moksh's real module).
  4. Pass tool result + original request back to Groq to draft a spoken-answer
     text response.
  5. Emit llm.response_drafted { fence_token, response_text } per CONTRACTS.md
     Section 2.
  6. Pass the response text to stub_voice_client for spoken output.

Wiring:
  - Reads GROQ_API_KEY from .env (python-dotenv). Never hardcodes a key.
  - Uses stub_task_client for task_id + fence_token management.
  - Uses stub_tool_client for analytics calls.
  - Uses stub_voice_client for spoken output.
  - All stubs are swappable for real modules without changing this file's
    public interface.

Owner: shlok (backend/orchestration/).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from groq import AsyncGroq

from backend.orchestration.stub_task_client import StubTaskClient, Task, TaskEvent
from backend.orchestration.stub_tool_client import StubToolClient, ToolRequest, ToolResponse
from backend.orchestration.stub_voice_client import StubVoiceClient, SpeechEvent

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event -- llm.response_drafted (CONTRACTS.md Section 2)
# ---------------------------------------------------------------------------

@dataclass
class LLMResponseDraftedEvent:
    event: str = "llm.response_drafted"
    task_id: str = ""
    fence_token: str = ""
    response_text: str = ""
    emitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


EventListener = Callable[[Any], None]


# ---------------------------------------------------------------------------
# Tool definitions passed to Groq for tool-selection
# ---------------------------------------------------------------------------

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_total_sales",
            "description": (
                "Returns total sales revenue for a given period. "
                "Use when the user asks about overall/total revenue or sales figures."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period, e.g. 'Q1 2026', 'last month'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_by_region",
            "description": (
                "Returns sales broken down by geographic region. "
                "Use when the user asks about regional performance or comparisons."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period, e.g. 'Q1 2026'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_products",
            "description": (
                "Returns the top-performing products by revenue or units sold. "
                "Use when the user asks about best-sellers or product rankings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of top products to return.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_trend",
            "description": (
                "Returns month-over-month or week-over-week sales trend. "
                "Use when the user asks about trends, growth, or trajectory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                    "granularity": {
                        "type": "string",
                        "enum": ["monthly", "weekly"],
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rep_performance",
            "description": (
                "Returns individual sales rep performance metrics. "
                "Use when the user asks about reps, salespeople, or individuals."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                },
                "required": [],
            },
        },
    },
]

_SYSTEM_PROMPT = """\
You are REVIA, a voice-native sales data analyst. The user asks spoken questions
about sales data and you answer concisely in natural spoken language (no markdown,
no bullet lists -- answers must sound good when read aloud by a text-to-speech system).

You have access to analytics tools. When a user question requires data, call the
appropriate tool. If the question can be answered without data (e.g. a greeting),
answer directly without calling a tool.

Keep answers concise and conversational -- aim for 2-4 sentences maximum.
Always refer to dollar amounts and percentages in a natural spoken way
(say "four point eight million dollars" not "$4,800,000").
"""


# ---------------------------------------------------------------------------
# AgentBrain
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Returned by AgentBrain.run() -- full record of one request cycle."""
    task_id: str
    fence_token: str
    request_text: str
    tool_name: Optional[str]
    tool_result: Optional[dict]
    response_text: str
    speech_id: Optional[str]
    events: list[Any] = field(default_factory=list)
    aborted: bool = False       # True if fencing rejected the result mid-run
    abort_reason: Optional[str] = None


class AgentBrain:
    """
    LLM orchestration layer for REVIA.

    Wires: stub_task_client -> stub_tool_client -> Groq -> stub_voice_client.

    Each call to run() is for a single active task. If fencing rejects the
    tool result mid-flight, run() returns early with aborted=True and
    never passes anything to voice output.
    """

    def __init__(
        self,
        task_client: Optional[StubTaskClient] = None,
        tool_client: Optional[StubToolClient] = None,
        voice_client: Optional[StubVoiceClient] = None,
        groq_model: Optional[str] = None,
    ) -> None:
        """
        Args:
            task_client:  Stub (or real) Task Manager. Created fresh if None.
            tool_client:  Stub (or real) tool client. Created fresh if None.
            voice_client: Stub (or real) voice client. Created fresh if None.
            groq_model:   Groq model name. Reads GROQ_MODEL from .env if None.
                          Falls back to 'openai/gpt-oss-20b' if not set.
        """
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set. Add it to your .env file. "
                "Never hardcode API keys."
            )
        self._groq = AsyncGroq(api_key=api_key)
        self._model = groq_model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

        self._task_client = task_client or StubTaskClient()
        self._tool_client = tool_client or StubToolClient()
        self._voice_client = voice_client or StubVoiceClient()

        self._listeners: list[EventListener] = []
        self._event_log: list[Any] = []

        # Wire sub-client events into our unified log
        self._task_client.on_event(self._record_event)
        self._voice_client.on_event(self._record_event)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_event(self, listener: EventListener) -> None:
        """Register a listener for all events emitted during a run."""
        self._listeners.append(listener)

    @property
    def task_client(self) -> StubTaskClient:
        return self._task_client

    @property
    def tool_client(self) -> StubToolClient:
        return self._tool_client

    @property
    def voice_client(self) -> StubVoiceClient:
        return self._voice_client

    async def run(self, request_text: str) -> RunResult:
        """
        Process one user utterance end-to-end.

        Steps:
          1. Create task (task_id + fence_token).
          2. Call Groq to decide which tool to use (if any).
          3. Call the tool (with fence_token -- vedantkhar checks this).
          4. Check fence (stub: always accepted; real: rejects stale tokens).
          5. Call Groq to draft the spoken answer text.
          6. Emit llm.response_drafted.
          7. Pass text to voice client.

        Returns RunResult. If fencing rejects (aborted=True), no speech occurs.
        """
        run_events: list[Any] = []

        # Capture events from this run
        def _capture(event: Any) -> None:
            run_events.append(event)
            self._record_event(event)

        # Temporarily add a scoped listener -- we'll remove it after the run
        self._task_client.on_event(_capture)
        self._voice_client.on_event(_capture)

        try:
            # --- Step 1: Create task ---
            task = self._task_client.create_task(request_text)
            logger.info(
                "[Brain] run START  task_id=%s  fence=%s  request=%r",
                task.task_id, task.fence_token, request_text[:80],
            )

            # --- Step 2: Decide tool ---
            tool_name, tool_args = await self._decide_tool(request_text)
            logger.info(
                "[Brain] tool decision  task_id=%s  tool=%s  args=%s",
                task.task_id, tool_name, tool_args,
            )

            # --- Step 3: Call tool (if needed) ---
            tool_result: Optional[dict] = None
            if tool_name is not None:
                tool_req = ToolRequest(
                    task_id=task.task_id,
                    fence_token=task.fence_token,
                    tool_name=tool_name,
                    args=tool_args or {},
                )
                try:
                    tool_resp = await self._tool_client.call_tool(tool_req)
                except asyncio.CancelledError:
                    logger.warning(
                        "[Brain] tool call cancelled  task_id=%s  tool=%s",
                        task.task_id, tool_name,
                    )
                    return RunResult(
                        task_id=task.task_id,
                        fence_token=task.fence_token,
                        request_text=request_text,
                        tool_name=tool_name,
                        tool_result=None,
                        response_text="",
                        speech_id=None,
                        events=run_events,
                        aborted=True,
                        abort_reason="tool_call_cancelled",
                    )

                # --- Step 4: Fence check ---
                fence_status = self._task_client.check_fence(tool_resp.fence_token)
                if fence_status != "accepted":
                    logger.warning(
                        "[Brain] STALE RESULT REJECTED  task_id=%s  fence=%s  status=%s",
                        task.task_id, tool_resp.fence_token, fence_status,
                    )
                    return RunResult(
                        task_id=task.task_id,
                        fence_token=task.fence_token,
                        request_text=request_text,
                        tool_name=tool_name,
                        tool_result=None,
                        response_text="",
                        speech_id=None,
                        events=run_events,
                        aborted=True,
                        abort_reason="stale_result_rejected",
                    )

                tool_result = tool_resp.result
                logger.info(
                    "[Brain] tool result accepted  task_id=%s  tool=%s",
                    task.task_id, tool_name,
                )

            # --- Step 5: Draft spoken answer ---
            response_text = await self._draft_response(
                request_text=request_text,
                tool_name=tool_name,
                tool_result=tool_result,
            )
            logger.info(
                "[Brain] response drafted  task_id=%s  text=%r",
                task.task_id, response_text[:120],
            )

            # --- Step 6: Emit llm.response_drafted ---
            drafted_event = LLMResponseDraftedEvent(
                task_id=task.task_id,
                fence_token=task.fence_token,
                response_text=response_text,
            )
            _capture(drafted_event)
            logger.info(
                "[Brain] llm.response_drafted  task_id=%s  fence=%s",
                task.task_id, task.fence_token,
            )

            # --- Step 7: Speak the answer ---
            speech_id = await self._voice_client.speak(
                text=response_text,
                task_id=task.task_id,
            )

            # Mark task complete
            self._task_client.complete_task(task.task_id)

            return RunResult(
                task_id=task.task_id,
                fence_token=task.fence_token,
                request_text=request_text,
                tool_name=tool_name,
                tool_result=tool_result,
                response_text=response_text,
                speech_id=speech_id,
                events=run_events,
                aborted=False,
            )

        finally:
            # Remove the scoped listeners via the public API
            self._task_client.off_event(_capture)
            self._voice_client.off_event(_capture)

    # ------------------------------------------------------------------
    # Internal -- Groq calls
    # ------------------------------------------------------------------

    async def _decide_tool(
        self, request_text: str
    ) -> tuple[Optional[str], Optional[dict]]:
        """
        Ask Groq which tool to call for *request_text*.

        Returns (tool_name, args) or (None, None) if no tool is needed.
        """
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": request_text},
        ]

        response = await self._groq.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=_TOOL_DEFINITIONS,
            tool_choice="auto",
            max_tokens=256,
            temperature=0.0,   # deterministic tool selection
        )

        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            tc = msg.tool_calls[0]
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_args = {}
            return tool_name, tool_args

        # No tool call needed
        return None, None

    async def _draft_response(
        self,
        request_text: str,
        tool_name: Optional[str],
        tool_result: Optional[dict],
    ) -> str:
        """
        Ask Groq to draft a spoken-answer text response.

        If a tool result is available, it is included in the context.
        The result must sound natural when spoken aloud by Rime TTS.
        """
        if tool_result is not None:
            # Remove internal stub markers before passing to LLM
            clean_result = {k: v for k, v in tool_result.items() if k != "_stub"}
            data_context = (
                f"Tool called: {tool_name}\n"
                f"Data returned: {json.dumps(clean_result, indent=2)}"
            )
            user_message = (
                f"The user asked: {request_text}\n\n"
                f"Here is the data you retrieved:\n{data_context}\n\n"
                "Provide a concise spoken answer using this data. "
                "No markdown, no lists -- natural spoken language only."
            )
        else:
            user_message = request_text

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response = await self._groq.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=256,
            temperature=0.3,
            tool_choice="none",   # force text output; no tool-calling in draft step
        )

        content = response.choices[0].message.content
        if not content or not content.strip():
            # Model returned empty/None content -- can happen with some Groq models
            # when they default to tool-calling mode in a non-tool request.
            # Provide a safe fallback so the pipeline never delivers empty speech.
            logger.warning(
                "[Brain] _draft_response: model returned empty content, using fallback"
            )
            content = "I have retrieved the data for your request."
        return content.strip()

    # ------------------------------------------------------------------
    # Internal -- event recording
    # ------------------------------------------------------------------

    def _record_event(self, event: Any) -> None:
        self._event_log.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                logger.exception("[Brain] listener raised an exception")


# ---------------------------------------------------------------------------
# CLI entrypoint -- smoke test when run as __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    async def _smoke_test() -> None:
        print("\n" + "=" * 60)
        print("AgentBrain smoke test -- stub modules, real Groq call")
        print("=" * 60)

        # Fast stubs: 1 s tool delay, 2 s fake speech
        brain = AgentBrain(
            tool_client=StubToolClient(delay_s=1.0),
            voice_client=StubVoiceClient(speech_duration_s=2.0),
        )

        all_events: list[Any] = []
        brain.on_event(all_events.append)

        # --- Test 1: question that needs a tool ---
        print("\n--- Test 1: tool-calling question ---")
        result = await brain.run("What are the total sales for Q1?")
        print(f"\nTask ID:       {result.task_id}")
        print(f"Fence token:   {result.fence_token}")
        print(f"Tool called:   {result.tool_name}")
        print(f"Response text: {result.response_text}")
        print(f"Speech ID:     {result.speech_id}")
        print(f"Aborted:       {result.aborted}")
        print(f"Event count:   {len(result.events)}")
        assert not result.aborted
        assert result.tool_name == "get_total_sales"
        assert result.response_text
        assert result.speech_id
        print("PASS")

        # --- Test 2: conversational question (no tool needed) ---
        print("\n--- Test 2: conversational (no tool) ---")
        result2 = await brain.run("Hello, what can you help me with?")
        print(f"Tool called:   {result2.tool_name}")
        print(f"Response text: {result2.response_text}")
        assert not result2.aborted
        assert result2.response_text
        print("PASS")

        print("\n" + "=" * 60)
        print("All AgentBrain smoke tests passed.")
        print("=" * 60)
        print("\nNOTE: Results above are from stub tool calls + real Groq LLM.")
        print("      Mark as [STUB TEST -- not real evidence] in any PROGRESS entry.")

    asyncio.run(_smoke_test())
