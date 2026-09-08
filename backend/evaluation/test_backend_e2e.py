"""
Comprehensive 12-Scenario Acceptance Test Suite for REVIA Backend.

Covers:
TEST 01 — Normal conversation
TEST 02 — Multi-turn context
TEST 03 — Generic delayed tool
TEST 04 — Interrupt during Rime speech
TEST 05 — Interrupt during tool execution
TEST 06 — Change request during tool execution
TEST 07 — Multiple interruptions
TEST 08 — Status during tool execution
TEST 09 — Cancellation
TEST 10 — Context preserved after cancellation/refinement
TEST 11 — Switch from delayed work to normal conversation
TEST 12 — Late stale result rejection
"""

import asyncio
import ast
import inspect
import os
import sys
from types import SimpleNamespace
from pathlib import Path
import pytest
from dotenv import load_dotenv

from backend.orchestration.agent_brain import AgentBrain, RunResult
from backend.state.task import TaskStatus, Task
from backend.state.task_manager import TaskManager
from backend.state.fencing import validate_tool_result, validate_llm_response
from backend.orchestration.stub_tool_client import StubToolClient
from backend.orchestration.stub_voice_client import StubVoiceClient
from backend.orchestration.tool_contract import ToolRequest

VOICE_IO_DIR = Path(__file__).resolve().parents[1] / "voice_io"
if str(VOICE_IO_DIR) not in sys.path:
    sys.path.insert(0, str(VOICE_IO_DIR))

from agent import ReviaVoiceAgent, _has_active_rime_playback
from backend.rime.events import RimePlaybackController


def test_livekit_text_chat_is_disabled_without_changing_transcript_path():
    """RoomIO chat text must not invoke native generate_reply()."""
    import agent as voice_agent
    from livekit.agents.voice.room_io import RoomOptions

    entrypoint_source = inspect.getsource(voice_agent.entrypoint)
    entrypoint_tree = ast.parse(entrypoint_source)
    start_calls = [
        node
        for node in ast.walk(entrypoint_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "start"
    ]

    assert len(start_calls) == 1
    room_options = next(
        keyword.value
        for keyword in start_calls[0].keywords
        if keyword.arg == "room_options"
    )
    assert isinstance(room_options, ast.Call)
    assert isinstance(room_options.func, ast.Name)
    assert room_options.func.id == "RoomOptions"
    assert [keyword.arg for keyword in room_options.keywords] == ["text_input"]
    assert isinstance(room_options.keywords[0].value, ast.Constant)
    assert room_options.keywords[0].value.value is False
    assert RoomOptions(text_input=False).get_text_input_options() is None

    assert 'session.on("user_input_transcribed")' in entrypoint_source
    assert "agent_instance.process_transcript" in entrypoint_source

load_dotenv()


def test_user_speaking_gate_uses_only_active_rime_playback():
    class _Handle:
        def __init__(self):
            self.interrupted = False

        def done(self):
            return self.interrupted

        def interrupt(self, force=False):
            self.interrupted = True

    controller = RimePlaybackController()
    assert not _has_active_rime_playback(controller)
    assert controller.interrupt_on_new_user_speech() == []

    handle = _Handle()
    controller.start_playback("task-active", handle)
    assert _has_active_rime_playback(controller)
    events = controller.interrupt_on_new_user_speech()
    assert [event["event"] for event in events] == ["interrupt", "speech.stopped"]
    assert events[-1]["stopped_reason"] == "interrupted"
    assert not _has_active_rime_playback(controller)


def test_tool_router_is_skipped_for_normal_conversation():
    """Ordinary conversation goes directly to response drafting."""
    async def _run():
        brain = AgentBrain()
        router_calls = []

        async def record_router(*args, **kwargs):
            router_calls.append((args, kwargs))
            return "delayed_demo_work", {}

        async def draft_response(request_text, tool_name, tool_result, turn_sequence=None):
            return "A direct conversational response."

        brain._decide_tool = record_router
        brain._draft_response = draft_response

        result = await brain.run_headless("What is Python?")

        assert not result.aborted
        assert result.tool_name is None
        assert router_calls == []

    asyncio.run(_run())


def test_explicit_delayed_demo_routes_consistently_in_headless_and_run():
    """Both public execution paths consult the router for explicit demo work."""
    async def run_one(brain, request_text):
        router_calls = []

        async def record_router(*args, **kwargs):
            router_calls.append((args, kwargs))
            return "delayed_demo_work", {}

        async def draft_response(request_text, tool_name, tool_result, turn_sequence=None):
            return "The delayed operation completed."

        brain._decide_tool = record_router
        brain._draft_response = draft_response
        return await brain.run_headless(request_text), router_calls

    async def _run():
        headless_result, headless_calls = await run_one(
            AgentBrain(), "Run the delayed demonstration."
        )
        assert not headless_result.aborted
        assert headless_result.tool_name == "delayed_demo_work"
        assert len(headless_calls) == 1

        brain = AgentBrain(voice_client=StubVoiceClient(speech_duration_s=0.01))
        router_calls = []

        async def record_router(*args, **kwargs):
            router_calls.append((args, kwargs))
            return "delayed_demo_work", {}

        async def draft_response(request_text, tool_name, tool_result, turn_sequence=None):
            return "The delayed operation completed."

        brain._decide_tool = record_router
        brain._draft_response = draft_response
        result = await brain.run("Start a delayed operation for me.")

        assert not result.aborted
        assert result.tool_name == "delayed_demo_work"
        assert len(router_calls) == 1

    asyncio.run(_run())

def test_01_normal_conversation():
    """TEST 01 — Normal conversational generation (GPT mode, no tools)."""
    async def _run():
        brain = AgentBrain()
        res = await brain.run_headless("Hello Revia, can you give me a 1-sentence greeting?")
        assert not res.aborted
        assert res.tool_name is None
        assert len(res.response_text) > 0
    asyncio.run(_run())


def test_02_multi_turn_context():
    """TEST 02 — Multi-turn context memory across turns."""
    async def _run():
        brain = AgentBrain()
        # Turn 1
        res1 = await brain.run_headless("My favorite color is emerald green.")
        assert not res1.aborted
        # Turn 2
        res2 = await brain.run_headless("What is my favorite color?")
        assert not res2.aborted
        assert "emerald" in res2.response_text.lower() or "green" in res2.response_text.lower()
    asyncio.run(_run())


def test_03_generic_delayed_tool():
    """TEST 03 — Generic delayed tool contract and execution."""
    async def _run():
        client = StubToolClient(delay_s=0)
        request = ToolRequest("task-a", "fence-a", "delayed_demo_work", {})
        response = await client.call_tool(request)
        assert response.task_id == request.task_id
        assert response.fence_token == request.fence_token
        assert response.result == {"message": "Delayed operation completed."}
    asyncio.run(_run())


def test_04_interrupt_during_speech():
    """TEST 04 — Interrupt during speech playback invalidates old task and stops audio."""
    tm = TaskManager()
    t1 = tm.create_task("Run the delayed demonstration workload.")
    tm.start_generating(t1.task_id)
    tm.start_speaking(t1.task_id, "speech-1")
    assert t1.status == TaskStatus.SPEAKING

    # Interrupt arrives
    t2 = tm.create_task("Wait, change the delayed workload request")
    assert t1.status == TaskStatus.OBSOLETE
    assert t1.fence_token == ""
    assert t2.status == TaskStatus.ACTIVE
    assert t2.parent_task_id == t1.task_id


def test_05_interrupt_during_tool_execution():
    """TEST 05 — Interrupt during slow tool execution fences old task and rejects late result."""
    tm = TaskManager()
    tc = StubToolClient(delay_s=0)

    # Task 1 starts tool
    t1 = tm.create_task("Run delayed work")
    t1_fence = t1.fence_token
    tm.start_tool_running(t1.task_id, "delayed_demo_work")
    assert t1.status == TaskStatus.TOOL_RUNNING

    # Interrupt arrives while tool is running
    t2 = tm.create_task("Actually, change that request")
    assert t1.status == TaskStatus.OBSOLETE
    assert t1.fence_token == ""
    assert t2.status == TaskStatus.ACTIVE

    # Tool 1 finishes late with old fence token
    late_response = asyncio.run(tc.call_tool(ToolRequest(
        task_id=t1.task_id,
        fence_token=t1_fence,
        tool_name="delayed_demo_work",
        args={},
    )))
    validation = validate_tool_result(tm.get_active_task(), {
        "task_id": late_response.task_id,
        "fence_token": late_response.fence_token,
        "tool_name": late_response.tool_name,
        "result": late_response.result,
    })
    assert validation["status"] == "rejected_stale"


def test_06_change_request_during_tool_execution():
    """TEST 06 — Change / refine request during tool execution."""
    async def _run():
        brain = AgentBrain(tool_client=StubToolClient(delay_s=1))
        async def delayed_tool(request_text, turn_sequence=None):
            return "delayed_demo_work", {}
        brain._decide_tool = delayed_tool
        
        # Task 1 in flight in background
        t1_task = asyncio.create_task(brain.run_headless("Please run the delayed demonstration workload."))
        await asyncio.sleep(0.1) # Let T1 start

        # User interrupts and changes request
        t2_res = await brain.run_headless("Actually, run the delayed demonstration instead.")
        assert not t2_res.aborted
        assert t2_res.tool_name == "delayed_demo_work"

        # T1 result returns and is rejected
        t1_res = await t1_task
        assert t1_res.aborted
        assert t1_res.abort_reason == "stale_result_rejected"
    asyncio.run(_run())


def test_07_multiple_interruptions():
    """TEST 07 — Multiple successive interruptions (T1 -> T2 -> T3)."""
    tm = TaskManager()
    t1 = tm.create_task("Request 1")
    t1_id = t1.task_id
    t1_fence = t1.fence_token

    t2 = tm.create_task("Request 2")
    t2_id = t2.task_id
    t2_fence = t2.fence_token

    t3 = tm.create_task("Request 3")
    t3_id = t3.task_id

    assert tm.get_task(t1_id).status == TaskStatus.OBSOLETE
    assert tm.get_task(t2_id).status == TaskStatus.OBSOLETE
    assert tm.get_active_task().task_id == t3_id
    assert tm.get_active_task().status == TaskStatus.ACTIVE

    # Fencing check for late results from both T1 and T2
    assert tm.check_fence(t1_id, t1_fence) == "rejected_stale"
    assert tm.check_fence(t2_id, t2_fence) == "rejected_stale"
    assert tm.check_fence(
        tm.get_active_task().task_id,
        tm.get_active_task().fence_token,
    ) == "accepted"


def test_08_status_during_tool_execution():
    """TEST 08 — Status query ('Are you still working?') returns live status."""
    async def _run():
        brain = AgentBrain()
        # Mock active task in TOOL_RUNNING
        task = brain.task_client.create_task("Slow query")
        brain.task_client.start_tool_running(task.task_id, "delayed_demo_work")

        res = await brain.run_headless("Are you still working?")
        assert not res.aborted
        assert "still working" in res.response_text.lower()
    asyncio.run(_run())


def test_09_cancellation():
    """TEST 09 — Explicit cancellation invalidates active task and stops speech."""
    async def _run():
        brain = AgentBrain()
        t1 = brain.task_client.create_task("Slow analysis")
        brain.task_client.start_tool_running(t1.task_id, "delayed_demo_work")
        t1_fence = t1.fence_token

        res = await brain.run_headless("Cancel that")
        assert not res.aborted
        assert "cancel" in res.response_text.lower()
        assert t1.status in (TaskStatus.CANCELLED, TaskStatus.OBSOLETE)
        assert brain.task_client.check_fence(t1.task_id, t1_fence) == "rejected_stale"
    asyncio.run(_run())


def test_10_context_preserved_after_cancellation():
    """TEST 10 — Conversational context preserved after cancellation or refinement."""
    async def _run():
        brain = AgentBrain()
        await brain.run_headless("We are analyzing our North American regional performance.")
        await brain.run_headless("Cancel that")
        res = await brain.run_headless("Which region were we talking about?")
        assert not res.aborted
        assert "north" in res.response_text.lower() or "american" in res.response_text.lower()
    asyncio.run(_run())


def test_11_switch_from_delayed_work_to_general_conversation():
    """TEST 11 — Seamless topic switch from delayed work to conversation."""
    async def _run():
        brain = AgentBrain(tool_client=StubToolClient(delay_s=0))
        async def delayed_tool(request_text, turn_sequence=None):
            if "delayed" in request_text.lower():
                return "delayed_demo_work", {}
            return None, None
        brain._decide_tool = delayed_tool
        res1 = await brain.run_headless("Please run the delayed demonstration workload.")
        assert res1.tool_name == "delayed_demo_work"

        res2 = await brain.run_headless("Now explain quantum computing in one sentence.")
        assert res2.tool_name is None
        assert len(res2.response_text) > 0
        assert "quantum" in res2.response_text.lower() or "qubit" in res2.response_text.lower() or "physics" in res2.response_text.lower() or "computer" in res2.response_text.lower()
    asyncio.run(_run())


def test_12_late_stale_result_rejection():
    """TEST 12 — Late stale result rejection on LLM response gate."""
    tm = TaskManager()
    t1 = tm.create_task("First question")
    llm_payload = {
        "task_id": t1.task_id,
        "fence_token": t1.fence_token,
        "response_text": "Late answer"
    }

    # Interruption occurs
    t2 = tm.create_task("Second question")
    assert tm.check_llm_response(llm_payload) == "rejected_stale"


def test_14_tool_result_requires_matching_task_id_and_fence():
    """A tool result must match both the active task ID and fence token."""
    tm = TaskManager()
    active = tm.create_task("Current request")

    assert tm.check_fence("wrong-task", active.fence_token) == "rejected_stale"
    assert tm.check_fence(active.task_id, active.fence_token) == "accepted"


def _deterministic_brain(monkeypatch):
    """Build an AgentBrain whose model decisions/responses never use the network."""
    monkeypatch.setenv("GROQ_API_KEY", "deterministic-test-key")
    brain = AgentBrain(task_client=TaskManager(), use_stubs=True)

    async def no_tool(_request_text, _turn_sequence=None):
        return None, None

    async def draft_response(request_text, tool_name, tool_result, turn_sequence=None):
        return f"response for: {request_text}"

    brain._decide_tool = no_tool
    brain._draft_response = draft_response
    return brain


def test_15_context_records_user_turns_and_assistants_once(monkeypatch):
    """Normal context uses input order and does not duplicate entries."""
    async def _run():
        brain = _deterministic_brain(monkeypatch)
        await brain.run_headless("My project is called REVIA.")
        await brain.run_headless("What is my project called?")

        assert brain.get_conversation_history() == [
            {"role": "user", "content": "My project is called REVIA."},
            {"role": "assistant", "content": "response for: My project is called REVIA."},
            {"role": "user", "content": "What is my project called?"},
            {"role": "assistant", "content": "response for: What is my project called?"},
        ]
    asyncio.run(_run())


def test_16_context_survives_task_invalidation(monkeypatch):
    """Invalidating a task does not erase already-established context."""
    async def _run():
        brain = _deterministic_brain(monkeypatch)
        await brain.run_headless("My project is called REVIA.")
        task = brain.task_client.create_task("obsolete follow-up")
        brain.task_client.obsolete_active_task()

        assert task.status == TaskStatus.OBSOLETE
        assert brain.get_conversation_history() == [
            {"role": "user", "content": "My project is called REVIA."},
            {"role": "assistant", "content": "response for: My project is called REVIA."},
        ]
    asyncio.run(_run())


def test_17_interrupted_user_turn_is_kept_but_stale_assistant_is_not(monkeypatch):
    """An interrupted durable user utterance remains without stale assistant text."""
    async def _run():
        brain = _deterministic_brain(monkeypatch)
        draft_started = asyncio.Event()
        release_draft = asyncio.Event()

        async def delayed_draft(request_text, tool_name, tool_result, turn_sequence=None):
            if request_text.startswith("I am going from Mumbai"):
                draft_started.set()
                await release_draft.wait()
            return f"response for: {request_text}"

        brain._draft_response = delayed_draft
        task_a_run = asyncio.create_task(
            brain.run_headless("I am going from Mumbai to Nagpur.")
        )
        await draft_started.wait()

        task_a = brain.task_client.get_active_task()
        assert task_a is not None
        task_b_run = asyncio.create_task(
            brain.run_headless("Actually, change that to Pune.")
        )
        task_b_result = await task_b_run
        assert not task_b_result.aborted

        release_draft.set()
        task_a_result = await task_a_run
        assert task_a_result.aborted
        assert task_a_result.abort_reason == "stale_llm_response_rejected"
        assert task_a.status == TaskStatus.OBSOLETE

        assert brain.get_conversation_history() == [
            {"role": "user", "content": "I am going from Mumbai to Nagpur."},
            {"role": "user", "content": "Actually, change that to Pune."},
            {"role": "assistant", "content": "response for: Actually, change that to Pune."},
        ]
    asyncio.run(_run())


def test_18_concurrent_turns_preserve_input_order(monkeypatch):
    """A later completion cannot reorder user context or commit stale A output."""
    async def _run():
        brain = _deterministic_brain(monkeypatch)
        draft_started = asyncio.Event()
        release_first = asyncio.Event()

        async def out_of_order_draft(request_text, tool_name, tool_result, turn_sequence=None):
            if request_text == "Task A":
                draft_started.set()
                await release_first.wait()
            return f"response for: {request_text}"

        brain._draft_response = out_of_order_draft
        task_a_run = asyncio.create_task(brain.run_headless("Task A"))
        await draft_started.wait()
        task_b_result = await brain.run_headless("Task B")
        assert not task_b_result.aborted

        release_first.set()
        task_a_result = await task_a_run
        assert task_a_result.aborted

        assert brain.get_conversation_history() == [
            {"role": "user", "content": "Task A"},
            {"role": "user", "content": "Task B"},
            {"role": "assistant", "content": "response for: Task B"},
        ]
    asyncio.run(_run())


def test_19_refinement_context_uses_latest_input(monkeypatch):
    """A refinement preserves prior context and records the latest request after it."""
    async def _run():
        brain = _deterministic_brain(monkeypatch)
        prompt_history = []

        async def record_prompt(request_text, tool_name, tool_result, turn_sequence=None):
            prompt_history.append((request_text, brain._history_before_turn(turn_sequence)))
            return f"response for: {request_text}"

        brain._draft_response = record_prompt
        await brain.run_headless("I am going from Mumbai to Nagpur.")
        await brain.run_headless("Actually, change that to Pune.")

        assert prompt_history[1][1] == [
            {"role": "user", "content": "I am going from Mumbai to Nagpur."},
            {"role": "assistant", "content": "response for: I am going from Mumbai to Nagpur."},
        ]
        assert brain.get_conversation_history()[-2:] == [
            {"role": "user", "content": "Actually, change that to Pune."},
            {"role": "assistant", "content": "response for: Actually, change that to Pune."},
        ]
    asyncio.run(_run())


def test_26_long_session_context_reaches_groq_in_order(monkeypatch):
    """Context beyond six messages remains available to both Groq requests."""
    class CapturingGroq:
        def __init__(self):
            self.calls = []

            class Completions:
                def __init__(self, owner):
                    self.owner = owner

                async def create(self, **kwargs):
                    self.owner.calls.append(kwargs)
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(tool_calls=None, content="context response")
                            )
                        ]
                    )

            self.chat = SimpleNamespace(completions=Completions(self))

    async def _run():
        monkeypatch.setenv("GROQ_API_KEY", "deterministic-test-key")
        brain = AgentBrain(task_client=TaskManager(), use_stubs=True)
        groq = CapturingGroq()
        brain._groq = groq

        await brain.run_headless("My project is called REVIA.")
        for index in range(4):
            await brain.run_headless(f"Unrelated completed turn {index + 1}.")
        await brain.run_headless("What is my project called?")

        final_calls = groq.calls[-2:]
        for call in final_calls:
            contents = [message["content"] for message in call["messages"]]
            assert "My project is called REVIA." in contents

        assert brain.get_conversation_history() == [
            item
            for index, user_text in enumerate(
                [
                    "My project is called REVIA.",
                    "Unrelated completed turn 1.",
                    "Unrelated completed turn 2.",
                    "Unrelated completed turn 3.",
                    "Unrelated completed turn 4.",
                    "What is my project called?",
                ]
            )
            for item in (
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": "context response"},
            )
        ]

    asyncio.run(_run())


def test_27_draft_fallback_preserves_session_context(monkeypatch):
    """The plain-prompt draft retry retains valid session history."""
    class FailingPrimaryGroq:
        def __init__(self):
            self.calls = []

            class Completions:
                def __init__(self, owner):
                    self.owner = owner

                async def create(self, **kwargs):
                    self.owner.calls.append(kwargs)
                    if len(self.owner.calls) == 2:
                        raise RuntimeError("simulated primary draft failure")
                    return SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(tool_calls=None, content="fallback response")
                            )
                        ]
                    )

            self.chat = SimpleNamespace(completions=Completions(self))

    async def _run():
        monkeypatch.setenv("GROQ_API_KEY", "deterministic-test-key")
        brain = AgentBrain(task_client=TaskManager(), use_stubs=True)
        groq = FailingPrimaryGroq()
        brain._groq = groq

        await brain.run_headless("My project is called REVIA.")
        result = await brain.run_headless("Which project did I mention?")

        assert not result.aborted
        fallback_call = groq.calls[-1]
        contents = [message["content"] for message in fallback_call["messages"]]
        assert "My project is called REVIA." in contents
        assert contents[-1] == "Which project did I mention?"

    asyncio.run(_run())


def test_20_delayed_tool_task_switch_rejects_late_result(monkeypatch):
    """Task B can finish while Task A's uncancelled delayed tool is pending."""
    class GatedToolClient:
        def __init__(self):
            self.first_request = None
            self.first_tool_started = asyncio.Event()
            self.first_tool_completed = asyncio.Event()
            self.release_first_tool = asyncio.Event()
            self.second_tool_started = asyncio.Event()
            self.release_second_tool = asyncio.Event()
            self.cancelled = False
            self.calls = []

        async def call_tool(self, request):
            self.calls.append(request)
            if self.first_request is None:
                self.first_request = request
                self.first_tool_started.set()
                try:
                    await self.release_first_tool.wait()
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
                self.first_tool_completed.set()
            else:
                self.second_tool_started.set()
                await self.release_second_tool.wait()

            return type("ToolResponse", (), {
                "task_id": request.task_id,
                "fence_token": request.fence_token,
                "tool_name": request.tool_name,
                "result": {"answer": request.args.get("destination", "ok")},
                "error": None,
            })()

    async def _run():
        monkeypatch.setenv("GROQ_API_KEY", "deterministic-test-key")
        task_manager = TaskManager()
        tool_client = GatedToolClient()
        brain = AgentBrain(
            task_client=task_manager,
            tool_client=tool_client,
            use_stubs=True,
        )

        task_b_decision_started = asyncio.Event()
        draft_calls = []

        async def decide_tool(request_text, turn_sequence=None):
            if request_text == "Actually, run the delayed demonstration for Pune instead.":
                task_b_decision_started.set()
            return "delayed_demo_work", {"label": request_text}

        async def draft_response(request_text, tool_name, tool_result, turn_sequence=None):
            draft_calls.append(request_text)
            return f"authoritative response for: {request_text}"

        brain._decide_tool = decide_tool
        brain._draft_response = draft_response

        fence_checks = []
        original_check_fence = task_manager.check_fence

        def record_fence_check(task_id, fence_token):
            status = original_check_fence(task_id, fence_token)
            fence_checks.append((task_id, fence_token, status))
            return status

        task_manager.check_fence = record_fence_check

        task_a_run = asyncio.create_task(
            brain.run_headless("Run the delayed demonstration for the first request.")
        )
        await tool_client.first_tool_started.wait()

        task_a = task_manager.get_active_task()
        assert task_a is not None
        task_a_id = task_a.task_id
        task_a_fence = task_a.fence_token
        assert task_a.status == TaskStatus.TOOL_RUNNING
        assert not tool_client.first_tool_completed.is_set()

        task_b_run = asyncio.create_task(
            brain.run_headless("Actually, run the delayed demonstration for Pune instead.")
        )
        await task_b_decision_started.wait()
        await tool_client.second_tool_started.wait()

        task_b = task_manager.get_active_task()
        assert task_b is not None
        assert task_b.task_id != task_a_id
        assert task_a.status == TaskStatus.OBSOLETE
        assert task_b.status == TaskStatus.TOOL_RUNNING
        assert not tool_client.first_tool_completed.is_set()

        tool_client.release_second_tool.set()
        task_b_result = await task_b_run
        assert not task_b_result.aborted
        assert task_b_result.task_id == task_b.task_id
        assert task_b_result.response_text == (
            "authoritative response for: Actually, run the delayed demonstration for Pune instead."
        )
        assert task_b.status == TaskStatus.GENERATING

        # Task A is deliberately not cancelled. Its tool is released only now.
        tool_client.release_first_tool.set()
        task_a_result = await task_a_run

        assert tool_client.first_tool_completed.is_set()
        assert tool_client.cancelled is False
        assert task_a_result.aborted
        assert task_a_result.abort_reason == "stale_result_rejected"

        # The production path supplied both identifiers from Task A's result.
        assert (task_a_id, task_a_fence, "rejected_stale") in fence_checks
        assert draft_calls == [
            "Actually, run the delayed demonstration for Pune instead."
        ]

        assert brain.get_conversation_history() == [
                {"role": "user", "content": "Run the delayed demonstration for the first request."},
                {"role": "user", "content": "Actually, run the delayed demonstration for Pune instead."},
                {
                    "role": "assistant",
                    "content": "authoritative response for: Actually, run the delayed demonstration for Pune instead.",
                },
        ]

    asyncio.run(_run())


def test_21_fence_provenance_snapshot_survives_task_obsolescence(monkeypatch):
    """Obsolescence clears task state but not the run's original fence provenance."""
    async def _run():
        monkeypatch.setenv("GROQ_API_KEY", "deterministic-test-key")
        task_manager = TaskManager()
        brain = AgentBrain(task_client=task_manager, use_stubs=True)
        draft_started = asyncio.Event()
        release_draft = asyncio.Event()

        async def no_tool(request_text, turn_sequence=None):
            return None, None

        async def delayed_draft(request_text, tool_name, tool_result, turn_sequence=None):
            draft_started.set()
            await release_draft.wait()
            return "late Task A response"

        brain._decide_tool = no_tool
        brain._draft_response = delayed_draft

        task_run = asyncio.create_task(brain.run_headless("Task A"))
        await draft_started.wait()

        task_a = task_manager.get_active_task()
        assert task_a is not None
        original_task_id = task_a.task_id
        original_fence = task_a.fence_token
        assert original_fence

        task_manager.obsolete_active_task()
        assert task_a.fence_token == ""

        release_draft.set()
        result = await task_run
        drafted_event = next(
            event
            for event in result.events
            if getattr(event, "event", None) == "llm.response_drafted"
        )

        assert drafted_event.task_id == original_task_id
        assert drafted_event.fence_token == original_fence
        assert result.task_id == original_task_id
        assert result.fence_token == original_fence
        assert result.aborted
        assert result.abort_reason == "stale_llm_response_rejected"
        assert task_manager.check_llm_response(
            {
                "task_id": original_task_id,
                "fence_token": original_fence,
                "response_text": "late Task A response",
            }
        ) == "rejected_stale"

    asyncio.run(_run())


def test_22_session_teardown_skips_rime_speech(monkeypatch):
    """A detached transcript task exits cleanly after session closure."""
    class FakeTaskClient:
        def check_llm_response(self, payload):
            return "accepted"

    class DelayedBrain:
        def __init__(self):
            self.task_client = FakeTaskClient()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def run_headless(self, request_text):
            self.started.set()
            await self.release.wait()
            return RunResult(
                task_id="task-session-close",
                fence_token="fence-session-close",
                request_text=request_text,
                tool_name=None,
                tool_result=None,
                response_text="late response",
                speech_id=None,
            )

    class FakeSession:
        closed = False

        def __init__(self):
            self.say_calls = 0

        def say(self, text, **kwargs):
            self.say_calls += 1
            raise AssertionError("session.say() must not run after teardown")

    async def _run():
        brain = DelayedBrain()
        session = FakeSession()
        agent = ReviaVoiceAgent(brain, RimePlaybackController())
        transcript_task = asyncio.create_task(
            agent.process_transcript("late request", session)
        )
        await brain.started.wait()

        session.closed = True
        agent.mark_session_closed()
        brain.release.set()
        await transcript_task

        assert session.say_calls == 0

    asyncio.run(_run())


def test_23_session_say_teardown_race_is_contained(monkeypatch):
    """The LiveKit teardown RuntimeError does not escape process_transcript()."""
    import agent as agent_module

    class FakeTaskClient:
        def check_llm_response(self, payload):
            return "accepted"

    class ImmediateBrain:
        task_client = FakeTaskClient()

        async def run_headless(self, request_text):
            return RunResult(
                task_id="task-race",
                fence_token="fence-race",
                request_text=request_text,
                tool_name=None,
                tool_result=None,
                response_text="race response",
                speech_id=None,
            )

    class FakeSession:
        closed = False

        def __init__(self):
            self.say_calls = 0

        def say(self, text, **kwargs):
            self.say_calls += 1
            raise RuntimeError("AgentSession isn't running")

    async def _run():
        session = FakeSession()
        agent = ReviaVoiceAgent(ImmediateBrain(), RimePlaybackController())
        monkeypatch.setattr(
            agent_module,
            "queue_rime_speech",
            lambda current_session, text: current_session.say(text),
        )

        await agent.process_transcript("race request", session)
        assert session.say_calls == 1

    asyncio.run(_run())


def test_24_session_closing_say_race_is_contained(monkeypatch):
    """The LiveKit closing RuntimeError does not escape process_transcript()."""
    import agent as agent_module

    class FakeTaskClient:
        def check_llm_response(self, payload):
            return "accepted"

    class ImmediateBrain:
        task_client = FakeTaskClient()

        async def run_headless(self, request_text):
            return RunResult(
                task_id="task-closing-race",
                fence_token="fence-closing-race",
                request_text=request_text,
                tool_name=None,
                tool_result=None,
                response_text="closing race response",
                speech_id=None,
            )

    class FakeSession:
        closed = False

        def say(self, text, **kwargs):
            raise RuntimeError("AgentSession is closing, cannot use say()")

    async def _run():
        session = FakeSession()
        agent = ReviaVoiceAgent(ImmediateBrain(), RimePlaybackController())
        monkeypatch.setattr(
            agent_module,
            "queue_rime_speech",
            lambda current_session, text: current_session.say(text),
        )

        await agent.process_transcript("closing race request", session)

    asyncio.run(_run())


def test_25_unrelated_rime_runtime_error_propagates(monkeypatch):
    """Unrelated RuntimeErrors must not be swallowed by teardown handling."""
    import agent as agent_module

    class FakeTaskClient:
        def check_llm_response(self, payload):
            return "accepted"

    class ImmediateBrain:
        task_client = FakeTaskClient()

        async def run_headless(self, request_text):
            return RunResult(
                task_id="task-unrelated-error",
                fence_token="fence-unrelated-error",
                request_text=request_text,
                tool_name=None,
                tool_result=None,
                response_text="unrelated error response",
                speech_id=None,
            )

    class FakeSession:
        closed = False

        def say(self, text, **kwargs):
            raise RuntimeError("unrelated Rime failure")

    async def _run():
        session = FakeSession()
        agent = ReviaVoiceAgent(ImmediateBrain(), RimePlaybackController())
        monkeypatch.setattr(
            agent_module,
            "queue_rime_speech",
            lambda current_session, text: current_session.say(text),
        )

        with pytest.raises(RuntimeError, match="unrelated Rime failure"):
            await agent.process_transcript("unrelated error request", session)

    asyncio.run(_run())


def test_13_stale_response_is_not_queued_to_rime():
    """A response invalidated before the speech boundary must not call session.say()."""
    class RecordingSession:
        def __init__(self):
            self.say_calls = []

        def say(self, text, **kwargs):
            self.say_calls.append((text, kwargs))
            raise AssertionError("stale response reached session.say()")

    class FakeBrain:
        def __init__(self):
            self.task_client = TaskManager()
            task = self.task_client.create_task("Task A")
            self.result = RunResult(
                task_id=task.task_id,
                fence_token=task.fence_token,
                request_text=task.request_text,
                tool_name=None,
                tool_result=None,
                response_text="Task A response",
                speech_id=None,
            )

        async def run_headless(self, request_text):
            return self.result

    async def _run():
        brain = FakeBrain()
        session = RecordingSession()
        agent = ReviaVoiceAgent(brain, RimePlaybackController())

        returned_result = await brain.run_headless("Task A")
        assert returned_result is brain.result
        brain.task_client.obsolete_active_task()
        await agent.process_transcript("Task A", session)

        assert session.say_calls == []
        assert brain.task_client.check_llm_response(
            {
                "task_id": brain.result.task_id,
                "fence_token": brain.result.fence_token,
                "response_text": brain.result.response_text,
            }
        ) == "rejected_stale"

    asyncio.run(_run())


if __name__ == "__main__":
    test_01_normal_conversation()
    test_02_multi_turn_context()
    test_03_generic_delayed_tool()
    test_04_interrupt_during_speech()
    test_05_interrupt_during_tool_execution()
    test_06_change_request_during_tool_execution()
    test_07_multiple_interruptions()
    test_08_status_during_tool_execution()
    test_09_cancellation()
    test_10_context_preserved_after_cancellation()
    test_11_switch_from_delayed_work_to_general_conversation()
    test_12_late_stale_result_rejection()
    print("\nALL 12 TESTS PASSED PERFECTLY!")
