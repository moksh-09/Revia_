"""
backend/orchestration/agent_brain.py
======================================
LLM orchestration layer -- shlok, REVIA Phase 1.

Responsibilities (CONTRACTS.md Section 4 / MASTER_README.md Section 6):
  1. Receive a transcribed user utterance.
  2. Call Groq (openai/gpt-oss-20b) to decide whether an optional generic
     delayed tool is needed (or answer directly).
  3. Call the optional tool through the generic tool client.
  4. Pass tool result + original request back to Groq to draft a spoken-answer
     text response.
  5. Emit llm.response_drafted { fence_token, response_text } per CONTRACTS.md
     Section 2.
  6. Validate the drafted response against the active task fence.
  7. Pass the response text to the voice client for spoken output.

Wiring:
  - Reads GROQ_API_KEY from .env (python-dotenv). Never hardcodes a key.
  - Uses TaskManager (real) or stub_task_client for task_id + fence_token.
  - Uses the generic delayed stub tool when a tool client is not injected.
  - Uses LiveKitRimeVoiceClient, stub_voice_client, or similar for speech.
  - Real modules are the default; pass explicit stubs for isolated evaluation.

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
from typing import Any, Callable, Optional, Protocol

from dotenv import load_dotenv
from groq import AsyncGroq

from backend.orchestration.stub_task_client import StubTaskClient, Task, TaskEvent
from backend.orchestration.stub_tool_client import StubToolClient
from backend.orchestration.tool_contract import ToolRequest, ToolResponse
from backend.orchestration.stub_voice_client import StubVoiceClient, SpeechEvent
from backend.state.task_manager import TaskManager

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


class TaskClientProtocol(Protocol):
    def create_task(self, request_text: str) -> Any: ...
    def check_fence(self, task_id: str, fence_token: str) -> str: ...
    def check_llm_response(self, llm_response: dict) -> str: ...
    def complete_task(self, task_id: str) -> None: ...
    def on_event(self, listener: EventListener) -> None: ...
    def off_event(self, listener: EventListener) -> None: ...


class ToolClientProtocol(Protocol):
    async def call_tool(self, request: ToolRequest) -> ToolResponse: ...


class VoiceClientProtocol(Protocol):
    async def speak(self, text: str, task_id: str) -> str: ...
    def on_event(self, listener: EventListener) -> None: ...
    def off_event(self, listener: EventListener) -> None: ...


# ---------------------------------------------------------------------------
# Tool definitions passed to Groq for tool-selection
# ---------------------------------------------------------------------------

_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "delayed_demo_work",
            "description": (
                "Runs a neutral delayed demonstration workload. Use only when "
                "the user explicitly asks to run the delayed demonstration."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Optional label for the demonstration workload.",
                    },
                },
                "required": [],
            },
        },
    },
]

_SYSTEM_PROMPT = """\
You are REVIA, a voice-native conversational intelligence focused on reliable
full-duplex task switching. You can answer general knowledge questions and
converse naturally and thoughtfully on any topic.

Delivery & "Writing for the Ear" Guidelines:
1. Write for the ear, not the eye: Use natural spoken contractions ("it's", "that's", "you'll", "don't").
2. Short breath groups: Keep sentences short, rhythmic, and easy to speak (under 15 words per clause).
3. Spoken rhythm & punctuation: Use commas and periods to pace natural breathing pauses. Avoid semicolons, parentheses, dashes, or brackets.
4. Natural transitions: Sound organic and human with conversational connectors ("Well,", "Sure thing,", "Alright,").
5. Strictly no formatting: Never output markdown, asterisks, bullet points, numbers as lists, emojis, or code blocks.
6. Keep spoken answers concise: Deliver 2 to 4 punchy, natural sentences unless more detail is explicitly requested.
7. Use the optional delayed demonstration tool only when the user explicitly asks for that demonstration workload.
8. Keep the conversation honest about what tools and information are available.
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

    Wires: task client -> tool client -> Groq -> voice client.

    Each call to run() or run_headless() is for a single task. If fencing rejects
    the tool or LLM result mid-flight, it returns early with aborted=True and
    never updates conversation state or passes anything to voice output.
    """

    def __init__(
        self,
        task_client: Optional[TaskClientProtocol] = None,
        tool_client: Optional[ToolClientProtocol] = None,
        voice_client: Optional[VoiceClientProtocol] = None,
        groq_model: Optional[str] = None,
        use_stubs: bool = False,
    ) -> None:
        """
        Args:
            task_client:  Task Manager. Defaults to real TaskManager unless use_stubs.
            tool_client:  Tool client. Defaults to the generic delayed stub unless injected.
            voice_client: Voice client. Defaults to StubVoiceClient unless provided.
            groq_model:   Groq model name. Reads GROQ_MODEL from .env if None.
            use_stubs:    When True, wire stub task/tool clients for isolated tests.
        """
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY not set. Add it to your .env file. "
                "Never hardcode API keys."
            )
        self._groq = AsyncGroq(api_key=api_key)
        self._model = groq_model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        if not os.environ.get("GROQ_MODEL") and not groq_model:
            logger.warning("GROQ_MODEL not set. Defaulting to openai/gpt-oss-20b.")

        if use_stubs:
            self._task_client: Any = task_client or StubTaskClient()
            self._tool_client: Any = tool_client or StubToolClient()
        else:
            self._task_client = task_client or TaskManager()
            self._tool_client = tool_client or StubToolClient(delay_s=0)
        self._voice_client: Any = voice_client or StubVoiceClient()

        self._persona: str = "signature"
        self._language: str = "eng"
        self._conversation_history: list[dict[str, str]] = []
        self._conversation_turns: dict[int, dict[str, Optional[str]]] = {}
        self._next_turn_sequence = 0
        self._listeners: list[EventListener] = []
        self._event_log: list[Any] = []

        # Wire sub-client events into our unified log
        self._task_client.on_event(self._record_event)
        self._voice_client.on_event(self._record_event)

    def set_persona(self, persona: str) -> None:
        """Update persona preset (signature, concierge, dispatcher, copilot)."""
        self._persona = persona.lower().strip()

    def set_language(self, language: str) -> None:
        """Update language preference (eng, spa, fra, ger, hin, auto)."""
        self._language = language.lower().strip()

    def _get_system_prompt(self) -> str:
        prompt = _SYSTEM_PROMPT

        if self._persona == "concierge":
            prompt += (
                "\nActive Persona: Empathetic Concierge. Speak with warm, reassuring, patient, and polite phrasing. "
                "Prioritize comfort and gentle clarity."
            )
        elif self._persona == "dispatcher":
            prompt += (
                "\nActive Persona: Telephony Dispatcher. Speak with crisp, concise, high-efficiency phrasing. "
                "Confirm details immediately and maintain swift call handling etiquette."
            )
        elif self._persona == "copilot":
            prompt += (
                "\nActive Persona: Technical Co-Pilot. Provide sharp, technically accurate answers with zero filler. "
                "Prioritize actionable logic and direct technical truth."
            )

        if self._language in ("eng", "en"):
            prompt += (
                "\nSTRICT LANGUAGE ENFORCEMENT: English.\n"
                "You MUST respond exclusively in natural, fluent spoken English.\n"
                "Even if previous conversation turns, context, or user inputs were in Hindi, Spanish, French, or German, "
                "switch completely, immediately, and unconditionally back to English. Do not output foreign or mixed-language words."
            )
        elif self._language in ("hin", "hi"):
            prompt += (
                "\nSTRICT LANGUAGE ENFORCEMENT: Hindi (हिंदी / Hinglish as natural for voice).\n"
                "You MUST respond in natural, polite spoken Hindi. "
                "Keep sentences clean, natural, and easy to understand for speech synthesis. Do not output English sentences unless technical terms."
            )
        elif self._language in ("spa", "es"):
            prompt += (
                "\nSTRICT LANGUAGE ENFORCEMENT: Spanish (Español).\n"
                "You MUST respond exclusively in natural, conversational spoken Spanish. Maintain spoken contractions and rhythm."
            )
        elif self._language in ("fra", "fr"):
            prompt += (
                "\nSTRICT LANGUAGE ENFORCEMENT: French (Français).\n"
                "You MUST respond exclusively in natural, conversational spoken French. Maintain spoken contractions and rhythm."
            )
        elif self._language in ("ger", "de"):
            prompt += (
                "\nSTRICT LANGUAGE ENFORCEMENT: German (Deutsch).\n"
                "You MUST respond exclusively in natural, conversational spoken German. Maintain clear, spoken rhythm."
            )
        elif self._language == "auto":
            prompt += (
                "\nLANGUAGE DIRECTIVE: Dynamic Multilingual.\n"
                "Automatically detect the user's spoken language and respond fluently in that exact same language. "
                "If the user switches languages, switch your response language immediately and completely."
            )

        return prompt

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_event(self, listener: EventListener) -> None:
        """Register a listener for all events emitted during a run."""
        self._listeners.append(listener)

    @property
    def task_client(self) -> Any:
        return self._task_client

    @property
    def tool_client(self) -> Any:
        return self._tool_client

    @property
    def voice_client(self) -> Any:
        return self._voice_client

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Return a copy of the conversation history."""
        self._refresh_conversation_history()
        return list(self._conversation_history)

    def clear_conversation_history(self) -> None:
        """Clear conversation history."""
        self._conversation_turns.clear()
        self._conversation_history.clear()

    def _start_conversation_turn(self, request_text: str) -> int:
        """Record a user turn independently from execution completion."""
        self._next_turn_sequence += 1
        sequence = self._next_turn_sequence
        self._conversation_turns[sequence] = {
            "user": request_text,
            "assistant": None,
        }
        self._refresh_conversation_history()
        return sequence

    def _refresh_conversation_history(self) -> None:
        """Materialize conversation entries in input order."""
        history: list[dict[str, str]] = []
        for sequence in sorted(self._conversation_turns):
            turn = self._conversation_turns[sequence]
            user_text = turn.get("user")
            assistant_text = turn.get("assistant")
            if user_text is not None:
                history.append({"role": "user", "content": user_text})
            if assistant_text is not None:
                history.append({"role": "assistant", "content": assistant_text})
        self._conversation_history = history

    def _history_before_turn(self, sequence: int) -> list[dict[str, str]]:
        """Return committed/pending prior turns, excluding the current user turn."""
        history: list[dict[str, str]] = []
        for turn_sequence in sorted(self._conversation_turns):
            if turn_sequence >= sequence:
                break
            turn = self._conversation_turns[turn_sequence]
            user_text = turn.get("user")
            assistant_text = turn.get("assistant")
            if user_text is not None:
                history.append({"role": "user", "content": user_text})
            if assistant_text is not None:
                history.append({"role": "assistant", "content": assistant_text})
        return history

    def _commit_assistant_response(self, sequence: int, response_text: str) -> None:
        """Commit one already-authorized assistant response exactly once."""
        turn = self._conversation_turns.get(sequence)
        if turn is None or turn.get("assistant") is not None:
            return
        turn["assistant"] = response_text
        self._refresh_conversation_history()

    def _is_status_query(self, text: str) -> bool:
        """Check if user query is asking for task status."""
        normalized = text.lower().strip()
        status_triggers = [
            "are you still working",
            "are you still working on that",
            "what is the status",
            "what's the status",
            "what are you doing",
            "is it done yet",
            "any update",
            "status update",
        ]
        return any(t in normalized for t in status_triggers)

    def _is_cancellation_query(self, text: str) -> bool:
        """Check if user query is requesting cancellation."""
        normalized = text.lower().strip()
        cancel_triggers = [
            "cancel that",
            "cancel the request",
            "cancel task",
            "stop that",
            "never mind",
            "nevermind",
            "forget it",
            "abort that",
        ]
        return any(t in normalized for t in cancel_triggers)

    def _should_consult_tool_router(self, text: str) -> bool:
        """Route only explicit delayed-demo requests through tool selection."""
        normalized = " ".join(text.lower().split())
        return any(
            phrase in normalized
            for phrase in (
                "delayed_demo_work",
                "delayed demo",
                "delayed demonstration",
                "delayed operation",
            )
        )

    async def run_headless(self, request_text: str) -> RunResult:
        """
        Process one user utterance end-to-end, but DO NOT pass to voice client.
        Useful when the caller (like agent.py) manages its own voice output.
        """
        run_events: list[Any] = []
        turn_sequence = self._start_conversation_turn(request_text)

        def _capture(event: Any) -> None:
            run_events.append(event)
            self._record_event(event)

        self._task_client.on_event(_capture)

        try:
            # Handle cancellation if requested
            if self._is_cancellation_query(request_text):
                if hasattr(self._task_client, "cancel_active_task"):
                    self._task_client.cancel_active_task("user_cancelled")
                task = self._task_client.create_task(request_text)
                task_id = task.task_id
                fence_token = task.fence_token
                response_text = "I have cancelled that request. What else can I help you with?"
                self._commit_assistant_response(turn_sequence, response_text)
                return RunResult(
                    task_id=task_id,
                    fence_token=fence_token,
                    request_text=request_text,
                    tool_name=None,
                    tool_result=None,
                    response_text=response_text,
                    speech_id=None,
                    events=run_events,
                    aborted=False,
                )

            # Handle status inquiry
            if self._is_status_query(request_text):
                active_t = getattr(self._task_client, "get_active_task", lambda: None)()
                status_str = getattr(active_t, "status", None)
                if status_str and str(status_str).endswith("TOOL_RUNNING"):
                    response_text = "I am still working on retrieving your data."
                elif status_str and str(status_str).endswith("CANCELLED"):
                    response_text = "That request was cancelled."
                elif status_str and str(status_str).endswith("COMPLETED"):
                    response_text = "I have already finished that request."
                else:
                    response_text = "I am ready and listening. How can I help you?"
                task = self._task_client.create_task(request_text)
                task_id = task.task_id
                fence_token = task.fence_token
                return RunResult(
                    task_id=task_id,
                    fence_token=fence_token,
                    request_text=request_text,
                    tool_name=None,
                    tool_result=None,
                    response_text=response_text,
                    speech_id=None,
                    events=run_events,
                    aborted=False,
                )

            task = self._task_client.create_task(request_text)
            task_id = task.task_id
            fence_token = task.fence_token
            logger.info(
                "[Brain] run_headless START  task_id=%s  fence=%s  request=%r",
                task_id, fence_token, request_text[:80],
            )

            if self._should_consult_tool_router(request_text):
                tool_name, tool_args = await self._decide_tool(request_text, turn_sequence)
            else:
                tool_name, tool_args = None, None
            logger.info(
                "[Brain] tool decision  task_id=%s  tool=%s  args=%s",
                task_id, tool_name, tool_args,
            )

            tool_result: Optional[dict] = None
            if tool_name is not None:
                if hasattr(self._task_client, "start_tool_running"):
                    self._task_client.start_tool_running(task_id, tool_name)

                tool_req = ToolRequest(
                    task_id=task_id,
                    fence_token=fence_token,
                    tool_name=tool_name,
                    args=tool_args or {},
                )
                try:
                    tool_resp = await self._tool_client.call_tool(tool_req)
                except asyncio.CancelledError:
                    logger.warning(
                        "[Brain] tool call cancelled  task_id=%s  tool=%s",
                        task_id, tool_name,
                    )
                    return RunResult(
                        task_id=task_id,
                        fence_token=fence_token,
                        request_text=request_text,
                        tool_name=tool_name,
                        tool_result=None,
                        response_text="",
                        speech_id=None,
                        events=run_events,
                        aborted=True,
                        abort_reason="tool_call_cancelled",
                    )

                fence_status = self._task_client.check_fence(
                    tool_resp.task_id,
                    tool_resp.fence_token,
                )
                if fence_status != "accepted":
                    logger.warning(
                        "[Brain] STALE RESULT REJECTED  task_id=%s  fence=%s  status=%s",
                        task_id, tool_resp.fence_token, fence_status,
                    )
                    return RunResult(
                        task_id=task_id,
                        fence_token=fence_token,
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
                    task_id, tool_name,
                )

            if hasattr(self._task_client, "start_generating"):
                self._task_client.start_generating(task_id)

            response_text = await self._draft_response(
                request_text=request_text,
                tool_name=tool_name,
                tool_result=tool_result,
                turn_sequence=turn_sequence,
            )
            logger.info(
                "[Brain] response drafted  task_id=%s  text=%r",
                task_id, response_text[:120],
            )

            drafted_event = LLMResponseDraftedEvent(
                task_id=task_id,
                fence_token=fence_token,
                response_text=response_text,
            )
            _capture(drafted_event)
            logger.info(
                "[Brain] llm.response_drafted  task_id=%s  fence=%s",
                task_id, fence_token,
            )

            llm_payload = {
                "task_id": task_id,
                "fence_token": fence_token,
                "response_text": response_text,
            }
            llm_status = self._task_client.check_llm_response(llm_payload)
            if llm_status != "accepted":
                logger.warning(
                    "[Brain] STALE LLM RESPONSE REJECTED  task_id=%s  fence=%s  status=%s",
                    task_id, fence_token, llm_status,
                )
                return RunResult(
                    task_id=task_id,
                    fence_token=fence_token,
                    request_text=request_text,
                    tool_name=tool_name,
                    tool_result=tool_result,
                    response_text="",
                    speech_id=None,
                    events=run_events,
                    aborted=True,
                    abort_reason="stale_llm_response_rejected",
                )

            # The user turn was recorded at input time; commit only the
            # assistant response after the existing authority check succeeds.
            self._commit_assistant_response(turn_sequence, response_text)

            return RunResult(
                task_id=task_id,
                fence_token=fence_token,
                request_text=request_text,
                tool_name=tool_name,
                tool_result=tool_result,
                response_text=response_text,
                speech_id=None,
                events=run_events,
                aborted=False,
            )

        finally:
            self._task_client.off_event(_capture)

    async def run(self, request_text: str) -> RunResult:
        """
        Process one user utterance end-to-end.

        Steps:
          1. Create task (task_id + fence_token).
          2. Call Groq to decide which tool to use (with conversation history).
          3. Call the tool (with fence_token).
          4. Check fence (rejects stale tokens).
          5. Call Groq to draft spoken answer.
          6. Emit llm.response_drafted.
          7. Validate llm.response_drafted against the active task fence.
          8. Pass text to voice client.

        Returns RunResult. If fencing rejects (aborted=True), no speech occurs.
        """
        run_events: list[Any] = []
        turn_sequence = self._start_conversation_turn(request_text)

        def _capture(event: Any) -> None:
            run_events.append(event)
            self._record_event(event)

        self._task_client.on_event(_capture)
        self._voice_client.on_event(_capture)

        try:
            # Handle cancellation
            if self._is_cancellation_query(request_text):
                if hasattr(self._task_client, "cancel_active_task"):
                    self._task_client.cancel_active_task("user_cancelled")
                task = self._task_client.create_task(request_text)
                task_id = task.task_id
                fence_token = task.fence_token
                response_text = "I have cancelled that request. What else can I help you with?"
                speech_id = await self._voice_client.speak(text=response_text, task_id=task_id)
                self._task_client.complete_task(task_id)
                self._commit_assistant_response(turn_sequence, response_text)
                return RunResult(
                    task_id=task_id,
                    fence_token=fence_token,
                    request_text=request_text,
                    tool_name=None,
                    tool_result=None,
                    response_text=response_text,
                    speech_id=speech_id,
                    events=run_events,
                    aborted=False,
                )

            # Handle status inquiry
            if self._is_status_query(request_text):
                active_t = getattr(self._task_client, "get_active_task", lambda: None)()
                status_str = getattr(active_t, "status", None)
                if status_str and str(status_str).endswith("TOOL_RUNNING"):
                    response_text = "I am still working on retrieving your data."
                elif status_str and str(status_str).endswith("CANCELLED"):
                    response_text = "That request was cancelled."
                elif status_str and str(status_str).endswith("COMPLETED"):
                    response_text = "I have already finished that request."
                else:
                    response_text = "I am ready and listening. How can I help you?"
                task = self._task_client.create_task(request_text)
                task_id = task.task_id
                fence_token = task.fence_token
                speech_id = await self._voice_client.speak(text=response_text, task_id=task_id)
                self._task_client.complete_task(task_id)
                return RunResult(
                    task_id=task_id,
                    fence_token=fence_token,
                    request_text=request_text,
                    tool_name=None,
                    tool_result=None,
                    response_text=response_text,
                    speech_id=speech_id,
                    events=run_events,
                    aborted=False,
                )

            task = self._task_client.create_task(request_text)
            task_id = task.task_id
            fence_token = task.fence_token
            logger.info(
                "[Brain] run START  task_id=%s  fence=%s  request=%r",
                task_id, fence_token, request_text[:80],
            )

            if self._should_consult_tool_router(request_text):
                tool_name, tool_args = await self._decide_tool(request_text, turn_sequence)
            else:
                tool_name, tool_args = None, None
            logger.info(
                "[Brain] tool decision  task_id=%s  tool=%s  args=%s",
                task_id, tool_name, tool_args,
            )

            tool_result: Optional[dict] = None
            if tool_name is not None:
                if hasattr(self._task_client, "start_tool_running"):
                    self._task_client.start_tool_running(task_id, tool_name)

                tool_req = ToolRequest(
                    task_id=task_id,
                    fence_token=fence_token,
                    tool_name=tool_name,
                    args=tool_args or {},
                )
                try:
                    tool_resp = await self._tool_client.call_tool(tool_req)
                except asyncio.CancelledError:
                    logger.warning(
                        "[Brain] tool call cancelled  task_id=%s  tool=%s",
                        task_id, tool_name,
                    )
                    return RunResult(
                        task_id=task_id,
                        fence_token=fence_token,
                        request_text=request_text,
                        tool_name=tool_name,
                        tool_result=None,
                        response_text="",
                        speech_id=None,
                        events=run_events,
                        aborted=True,
                        abort_reason="tool_call_cancelled",
                    )

                fence_status = self._task_client.check_fence(
                    tool_resp.task_id,
                    tool_resp.fence_token,
                )
                if fence_status != "accepted":
                    logger.warning(
                        "[Brain] STALE RESULT REJECTED  task_id=%s  fence=%s  status=%s",
                        task_id, tool_resp.fence_token, fence_status,
                    )
                    return RunResult(
                        task_id=task_id,
                        fence_token=fence_token,
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
                    task_id, tool_name,
                )

            if hasattr(self._task_client, "start_generating"):
                self._task_client.start_generating(task_id)

            response_text = await self._draft_response(
                request_text=request_text,
                tool_name=tool_name,
                tool_result=tool_result,
                turn_sequence=turn_sequence,
            )
            logger.info(
                "[Brain] response drafted  task_id=%s  text=%r",
                task_id, response_text[:120],
            )

            drafted_event = LLMResponseDraftedEvent(
                task_id=task_id,
                fence_token=fence_token,
                response_text=response_text,
            )
            _capture(drafted_event)
            logger.info(
                "[Brain] llm.response_drafted  task_id=%s  fence=%s",
                task_id, fence_token,
            )

            llm_payload = {
                "task_id": task_id,
                "fence_token": fence_token,
                "response_text": response_text,
            }
            llm_status = self._task_client.check_llm_response(llm_payload)
            if llm_status != "accepted":
                logger.warning(
                    "[Brain] STALE LLM RESPONSE REJECTED  task_id=%s  fence=%s  status=%s",
                    task_id, fence_token, llm_status,
                )
                return RunResult(
                    task_id=task_id,
                    fence_token=fence_token,
                    request_text=request_text,
                    tool_name=tool_name,
                    tool_result=tool_result,
                    response_text="",
                    speech_id=None,
                    events=run_events,
                    aborted=True,
                    abort_reason="stale_llm_response_rejected",
                )

            if hasattr(self._task_client, "start_speaking"):
                self._task_client.start_speaking(task_id, f"speech-{task_id}")

            speech_id = await self._voice_client.speak(
                text=response_text,
                task_id=task_id,
            )

            # Speech can yield to an interruption. Re-check before allowing
            # the assistant response to enter conversational context.
            final_context_status = self._task_client.check_llm_response(llm_payload)
            if final_context_status != "accepted":
                logger.warning(
                    "[Brain] STALE CONTEXT RESPONSE REJECTED  task_id=%s fence=%s status=%s",
                    task_id,
                    fence_token,
                    final_context_status,
                )
            else:
                self._task_client.complete_task(task_id)
                self._commit_assistant_response(turn_sequence, response_text)

            return RunResult(
                task_id=task_id,
                fence_token=fence_token,
                request_text=request_text,
                tool_name=tool_name,
                tool_result=tool_result,
                response_text=response_text,
                speech_id=speech_id,
                events=run_events,
                aborted=False,
            )

        finally:
            self._task_client.off_event(_capture)
            self._voice_client.off_event(_capture)

    # ------------------------------------------------------------------
    # Internal -- Groq calls
    # ------------------------------------------------------------------

    async def _decide_tool(
        self, request_text: str, turn_sequence: Optional[int] = None
    ) -> tuple[Optional[str], Optional[dict]]:
        """
        Ask Groq which tool to call for *request_text* with conversational history.

        Returns (tool_name, args) or (None, None) if no tool is needed.
        """
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        # Include the complete valid session context in input order.
        history = (
            self._history_before_turn(turn_sequence)
            if turn_sequence is not None
            else self._conversation_history
        )
        messages.extend(history)
        messages.append({"role": "user", "content": request_text})

        try:
            response = await self._groq.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=_TOOL_DEFINITIONS,
                tool_choice="auto",
                max_tokens=256,
                temperature=0.0,
            )

            choice = response.choices[0]
            msg = choice.message

            if msg.tool_calls:
                tc = msg.tool_calls[0]
                tool_name = tc.function.name
                # Validate against supported tools
                valid_tools = {t["function"]["name"] for t in _TOOL_DEFINITIONS}
                if tool_name not in valid_tools:
                    logger.warning("[Brain] Unrecognized tool name %s, falling back to None", tool_name)
                    return None, None
                try:
                    tool_args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_args = {}
                return tool_name, tool_args
        except Exception as exc:
            logger.warning("[Brain] _decide_tool failed: %s; falling back to direct conversation", exc)

        return None, None

    async def _draft_response(
        self,
        request_text: str,
        tool_name: Optional[str],
        tool_result: Optional[dict],
        turn_sequence: Optional[int] = None,
    ) -> str:
        """
        Ask Groq to draft a spoken-answer text response using context and data.
        """
        if tool_result is not None:
            clean_result = {k: v for k, v in tool_result.items() if k != "_stub"} if isinstance(tool_result, dict) else tool_result
            data_context = (
                f"Tool called: {tool_name}\n"
                f"Data returned: {json.dumps(clean_result, indent=2)}"
            )
            user_message = (
                f"The user asked: {request_text}\n\n"
                f"Here is the result returned by the tool:\n{data_context}\n\n"
                "Provide a concise spoken answer using this result. "
                "No markdown, no lists -- natural spoken language only."
            )
        else:
            user_message = request_text

        messages = [{"role": "system", "content": self._get_system_prompt()}]
        history = (
            self._history_before_turn(turn_sequence)
            if turn_sequence is not None
            else self._conversation_history
        )
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        content = None
        try:
            response = await self._groq.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
            )
            content = response.choices[0].message.content
        except Exception as exc:
            logger.warning("[Brain] _draft_response primary call failed: %s; retrying with plain prompt", exc)
            try:
                retry_response = await self._groq.chat.completions.create(
                    model=self._model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                f"{self._get_system_prompt()}\n"
                                "Do not output JSON, tool calls, or markdown formatting."
                            ),
                        },
                        *history,
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=1024,
                    temperature=0.3,
                )
                content = retry_response.choices[0].message.content
            except Exception as exc2:
                logger.error("[Brain] _draft_response fallback call also failed: %s", exc2)
                content = None

        if not content or not content.strip():
            logger.warning("[Brain] _draft_response: model returned empty content, using fallback")
            if tool_result is not None:
                content = "The delayed operation completed for your request."
            else:
                content = "I understand. How else can I assist you?"
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
            use_stubs=True,
            tool_client=StubToolClient(delay_s=1.0),
            voice_client=StubVoiceClient(speech_duration_s=2.0),
        )

        all_events: list[Any] = []
        brain.on_event(all_events.append)

        # --- Test 1: explicit delayed demonstration workload ---
        print("\n--- Test 1: tool-calling question ---")
        result = await brain.run("Please run the delayed demonstration workload.")
        print(f"\nTask ID:       {result.task_id}")
        print(f"Fence token:   {result.fence_token}")
        print(f"Tool called:   {result.tool_name}")
        print(f"Response text: {result.response_text}")
        print(f"Speech ID:     {result.speech_id}")
        print(f"Aborted:       {result.aborted}")
        print(f"Event count:   {len(result.events)}")
        assert not result.aborted
        assert result.tool_name == "delayed_demo_work"
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
