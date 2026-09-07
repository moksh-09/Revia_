"""
backend/evaluation/scenarios.py
==================================
One mechanism, two demonstrations -- MASTER_README.md Section 2.

The single mechanism: task IDs + fencing + stale-result rejection.

Scenario A -- Interrupt while Rime is speaking.
  User interrupts mid-answer. Queued Rime audio stops immediately, the old task
  is invalidated, a new task takes over and its answer is spoken.

Scenario B -- Interrupt during tool execution.
  User interrupts (or changes their request) while a background analytics call
  is still in flight. The stale result must never update state and must never
  be spoken, even if the tool call cannot be physically cancelled.

These are NEVER described as "two problems" -- they are two demonstrations of
the same mechanism. See MASTER_README.md Section 2 rationale.

Owner: shlok (backend/evaluation/).
Runs against stub modules until real modules are logged DONE in PROGRESS.md.
All results are marked [STUB TEST -- not real evidence] where applicable.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.orchestration.agent_brain import AgentBrain, LLMResponseDraftedEvent
from backend.orchestration.stub_task_client import StubTaskClient, Task, TaskEvent
from backend.orchestration.stub_tool_client import StubToolClient, ToolRequest, ToolResponse
from backend.orchestration.stub_voice_client import StubVoiceClient, SpeechEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ScenarioAwareTaskClient
# ---------------------------------------------------------------------------

class ScenarioAwareTaskClient(StubTaskClient):
    """
    StubTaskClient with real fence-token comparison for scenario testing.

    The base StubTaskClient.check_fence() always returns "accepted"
    (per CONTRACTS.md Section 5 stub spec -- no real fencing logic).
    This subclass overrides check_fence() to compare the given fence_token
    against the currently active task's fence_token, simulating exactly
    what vedantkhar's real backend/state/fencing.py will do.

    Used ONLY inside evaluation/scenarios.py.  The base stub is not modified.
    When vedantkhar's real module is ready, this class becomes unnecessary --
    swap the real fencing layer in agent_brain.py and delete this class.
    """

    def check_fence(self, fence_token: str) -> str:
        """
        Real fence check: reject if fence_token does not match the active task.

        Returns "accepted" or "rejected_stale".
        """
        active = self.get_active_task()
        if active is None or active.fence_token != fence_token:
            logger.info(
                "[ScenarioTaskClient] STALE  fence_token=%s  active_fence=%s",
                fence_token,
                active.fence_token if active else "None",
            )
            return "rejected_stale"
        logger.debug(
            "[ScenarioTaskClient] ACCEPTED  fence_token=%s", fence_token
        )
        return "accepted"


# ---------------------------------------------------------------------------
# ScenarioResult -- 10 checks per RIME_EVIDENCE.md Section 4 / 7
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    """
    Outcome of one scenario run.

    The 10 boolean checks match the PASS checklist in RIME_EVIDENCE.md Section 7.
    N/A items default to True so they do not block the overall pass.
    """

    scenario: str                       # "A" or "B"
    stub_run: bool = True               # always True until real modules land
    events: list[Any] = field(default_factory=list)

    # ---- The 10 RIME_EVIDENCE.md checks (True = PASS, None = N/A) ----
    old_task_invalidated: Optional[bool] = None
    old_speech_stopped_interrupted: Optional[bool] = None   # A only
    new_task_created: Optional[bool] = None
    new_task_becomes_active: Optional[bool] = None
    stale_result_rejected: Optional[bool] = None            # B only
    stale_result_not_spoken: Optional[bool] = None          # B only
    active_state_not_overwritten: Optional[bool] = None
    final_answer_matches_latest_request: Optional[bool] = None
    events_recorded_in_timeline: Optional[bool] = None
    measurable_evidence_captured: Optional[bool] = None

    # ---- Raw data for evidence ----
    t1_task_id: Optional[str] = None
    t2_task_id: Optional[str] = None    # task that answered new request
    t1_run_result: Optional[Any] = None
    t2_run_result: Optional[Any] = None
    interrupt_fired_at_s: Optional[float] = None
    t1_tool_returned_at_s: Optional[float] = None
    t1_speech_stopped_reason: Optional[str] = None
    t1_speech_ms_spoken: Optional[int] = None

    @property
    def passed(self) -> bool:
        """True only if every non-None check is True."""
        checks = [
            self.old_task_invalidated,
            self.old_speech_stopped_interrupted,
            self.new_task_created,
            self.new_task_becomes_active,
            self.stale_result_rejected,
            self.stale_result_not_spoken,
            self.active_state_not_overwritten,
            self.final_answer_matches_latest_request,
            self.events_recorded_in_timeline,
            self.measurable_evidence_captured,
        ]
        return all(c is True or c is None for c in checks)

    def check_value(self, check: Optional[bool]) -> str:
        """Format a check value for display."""
        if check is True:
            return "PASS"
        if check is False:
            return "FAIL"
        return "N/A "


# ---------------------------------------------------------------------------
# Scenario A -- Interrupt while Rime is speaking
# ---------------------------------------------------------------------------

async def run_scenario_a(
    request_text: str = "What are the total sales for Q1 2026?",
    new_request_text: str = "What are sales broken down by region?",
    speech_duration_s: float = 4.0,
    tool_delay_s: float = 1.0,
    interrupt_after_speech_s: float = 1.0,
) -> ScenarioResult:
    """
    Scenario A: Interrupt while Rime is speaking.

    Script:
      1. Run brain.run(request_text) -> T1 created, tool runs, Rime begins speaking.
      2. After interrupt_after_speech_s of speech, fire interrupt().
      3. Verify: speech.stopped with stopped_reason=interrupted, T1 -> OBSOLETE.
      4. Run brain.run(new_request_text) -> T2 created and ACTIVE, answer spoken.

    Args:
        request_text:            First user utterance (answered and spoken first).
        new_request_text:        Interrupting utterance (must be answered instead).
        speech_duration_s:       How long the stub speech lasts before auto-complete.
        tool_delay_s:            Stub tool latency for the first request (s).
        interrupt_after_speech_s: How long after speech starts to fire interrupt.
                                  Must be < speech_duration_s.
    """
    if interrupt_after_speech_s >= speech_duration_s:
        raise ValueError(
            "interrupt_after_speech_s must be less than speech_duration_s "
            "so that the interrupt actually fires before speech completes."
        )

    result = ScenarioResult(scenario="A", stub_run=True)
    all_events: list[Any] = []
    wall_start = time.monotonic()

    # --- Wire clients ---
    task_client = ScenarioAwareTaskClient()
    tool_client = StubToolClient(delay_s=tool_delay_s)
    voice_client = StubVoiceClient(speech_duration_s=speech_duration_s)
    brain = AgentBrain(
        task_client=task_client,
        tool_client=tool_client,
        voice_client=voice_client,
    )

    # --- Event capture ---
    speech_started_event = asyncio.Event()
    t1_task_id_holder: list[str] = []   # list so closure can write to it

    def on_task_event(e: TaskEvent) -> None:
        e_with_ts = {"ts": time.monotonic() - wall_start, "event": e}
        all_events.append(e_with_ts)
        # Capture T1 task_id from first task.created
        if e.event == "task.created" and not t1_task_id_holder:
            t1_task_id_holder.append(e.task_id)
        logger.debug("[ScenA] task_event: %s  task_id=%s", e.event, e.task_id)

    def on_speech_event(e: SpeechEvent) -> None:
        e_with_ts = {"ts": time.monotonic() - wall_start, "event": e}
        all_events.append(e_with_ts)
        if e.event == "speech.started":
            speech_started_event.set()
        logger.debug("[ScenA] speech_event: %s  task_id=%s", e.event, e.task_id)

    task_client.on_event(on_task_event)
    voice_client.on_event(on_speech_event)

    # --- Start T1 run in background ---
    logger.info("[ScenA] Starting T1 run: %r", request_text)
    t1_run = asyncio.create_task(
        brain.run(request_text), name="scenario-a-t1"
    )

    # --- Wait for speech to start ---
    try:
        await asyncio.wait_for(
            speech_started_event.wait(),
            timeout=tool_delay_s + 5.0,   # tool must complete before speech starts
        )
    except asyncio.TimeoutError:
        t1_run.cancel()
        logger.error("[ScenA] TIMEOUT: speech.started never fired")
        result.old_task_invalidated = False
        result.old_speech_stopped_interrupted = False
        result.new_task_created = False
        result.new_task_becomes_active = False
        result.active_state_not_overwritten = False
        result.final_answer_matches_latest_request = False
        result.events_recorded_in_timeline = False
        result.measurable_evidence_captured = False
        # N/A for Scenario A
        result.stale_result_rejected = None
        result.stale_result_not_spoken = None
        result.events = all_events
        return result

    # --- Sleep interrupt_after_speech_s, then fire interrupt ---
    await asyncio.sleep(interrupt_after_speech_s)
    result.interrupt_fired_at_s = time.monotonic() - wall_start

    assert t1_task_id_holder, "T1 task_id not captured"
    t1_id = t1_task_id_holder[0]
    result.t1_task_id = t1_id

    logger.info(
        "[ScenA] INTERRUPT at t=%.2fs  task_id=%s",
        result.interrupt_fired_at_s, t1_id,
    )

    # Stop Rime audio immediately (per CONTRACTS.md Section 3)
    voice_client.interrupt()

    # Task Manager: T1 -> OBSOLETE, T2 created
    task_client.interrupt(t1_id, new_request_text)

    # --- Wait for T1 run to complete ---
    result_t1 = await t1_run
    result.t1_run_result = result_t1

    # Extract speech info from T1's events
    for entry in all_events:
        e = entry["event"]
        if (
            isinstance(e, SpeechEvent)
            and e.event == "speech.stopped"
            and e.task_id == t1_id
        ):
            result.t1_speech_stopped_reason = e.stopped_reason
            result.t1_speech_ms_spoken = e.ms_spoken
            break

    # --- Run new request (T2) ---
    logger.info("[ScenA] Starting T2 run: %r", new_request_text)
    result_t2 = await brain.run(new_request_text)
    result.t2_run_result = result_t2
    result.t2_task_id = result_t2.task_id
    result.events = all_events

    # ================================================================
    # Evaluate the 10 checks
    # ================================================================

    # 1. old task invalidated
    t1_task = task_client.get_task(t1_id)
    result.old_task_invalidated = (
        t1_task is not None and t1_task.status == "OBSOLETE"
    )

    # 2. old speech stopped with interrupted reason
    result.old_speech_stopped_interrupted = (
        result.t1_speech_stopped_reason == "interrupted"
    )

    # 3. new task created -- a task.created event exists that is not T1
    new_task_ids = {
        entry["event"].task_id
        for entry in all_events
        if isinstance(entry["event"], TaskEvent)
        and entry["event"].event == "task.created"
        and entry["event"].task_id != t1_id
    }
    result.new_task_created = len(new_task_ids) > 0

    # 4. new task becomes active
    new_active_ids = {
        entry["event"].task_id
        for entry in all_events
        if isinstance(entry["event"], TaskEvent)
        and entry["event"].event == "task.active"
        and entry["event"].task_id != t1_id
    }
    result.new_task_becomes_active = len(new_active_ids) > 0

    # 5 & 6. stale result rejected / not spoken -- N/A for Scenario A
    result.stale_result_rejected = None
    result.stale_result_not_spoken = None

    # 7. active state not overwritten -- T2 eventually COMPLETED (not OBSOLETE)
    if result.t2_task_id:
        t2_task = task_client.get_task(result.t2_task_id)
        result.active_state_not_overwritten = (
            t2_task is not None
            and t2_task.status == "COMPLETED"
        )
    else:
        result.active_state_not_overwritten = False

    # 8. final answer matches latest request -- T2 run succeeded with a response
    result.final_answer_matches_latest_request = (
        result_t2 is not None
        and not result_t2.aborted
        and bool(result_t2.response_text)
    )

    # 9. events recorded in timeline
    result.events_recorded_in_timeline = len(all_events) >= 4

    # 10. measurable evidence captured
    result.measurable_evidence_captured = (
        result.interrupt_fired_at_s is not None
        and result.t1_speech_ms_spoken is not None
    )

    return result


# ---------------------------------------------------------------------------
# Scenario B -- Interrupt during tool execution
# ---------------------------------------------------------------------------

async def run_scenario_b(
    request_text: str = "What are the total sales for Q1 2026?",
    new_request_text: str = "Actually, show me the top products instead.",
    tool_delay_s: float = 5.0,
    interrupt_after_s: float = 2.0,
) -> ScenarioResult:
    """
    Scenario B: Interrupt during tool execution.

    Script:
      1. Run brain.run(request_text) -> T1 created, slow tool starts (tool_delay_s).
      2. After interrupt_after_s, fire interrupt() while tool is still running.
      3. T1 -> OBSOLETE, T2 created.
      4. When T1's tool finally returns (carrying T1's fence_token), the fence
         check finds a mismatch (active task is now T2) -> rejected_stale.
      5. T1's result is never spoken (brain.run returns aborted=True).
      6. Run brain.run(new_request_text) -> T2 (or new task) answers correctly.

    Args:
        request_text:      First user utterance (its tool call will be interrupted).
        new_request_text:  Interrupting utterance (must be answered instead).
        tool_delay_s:      Stub tool delay -- must be longer than interrupt_after_s
                           so the interrupt reliably fires before the tool completes.
        interrupt_after_s: Seconds after run() starts to fire the interrupt.
                           Must be < tool_delay_s.
    """
    if interrupt_after_s >= tool_delay_s:
        raise ValueError(
            "interrupt_after_s must be less than tool_delay_s "
            "so the interrupt fires while the tool is still running."
        )

    result = ScenarioResult(scenario="B", stub_run=True)
    all_events: list[Any] = []
    wall_start = time.monotonic()

    # --- Wire clients ---
    # ScenarioAwareTaskClient provides REAL fence-token comparison,
    # which is what makes this scenario's stale-result rejection possible.
    task_client = ScenarioAwareTaskClient()
    tool_client = StubToolClient(delay_s=tool_delay_s)
    voice_client = StubVoiceClient(speech_duration_s=2.0)
    brain = AgentBrain(
        task_client=task_client,
        tool_client=tool_client,
        voice_client=voice_client,
    )

    # --- Event capture ---
    t1_task_id_holder: list[str] = []

    def on_task_event(e: TaskEvent) -> None:
        e_with_ts = {"ts": time.monotonic() - wall_start, "event": e}
        all_events.append(e_with_ts)
        if e.event == "task.created" and not t1_task_id_holder:
            t1_task_id_holder.append(e.task_id)
        logger.debug("[ScenB] task_event: %s  task_id=%s", e.event, e.task_id)

    def on_speech_event(e: SpeechEvent) -> None:
        e_with_ts = {"ts": time.monotonic() - wall_start, "event": e}
        all_events.append(e_with_ts)
        logger.debug("[ScenB] speech_event: %s  task_id=%s", e.event, e.task_id)

    task_client.on_event(on_task_event)
    voice_client.on_event(on_speech_event)

    # --- Start T1 run in background ---
    logger.info("[ScenB] Starting T1 run (slow tool=%ss): %r", tool_delay_s, request_text)
    t1_run = asyncio.create_task(
        brain.run(request_text), name="scenario-b-t1"
    )

    # --- Wait until T1 task is created, then sleep until interrupt time ---
    # Give up to 2s for the first task.created event to arrive
    deadline = time.monotonic() + 2.0
    while not t1_task_id_holder and time.monotonic() < deadline:
        await asyncio.sleep(0.05)

    if not t1_task_id_holder:
        t1_run.cancel()
        logger.error("[ScenB] TIMEOUT: task.created never fired")
        result.events = all_events
        result.old_task_invalidated = False
        result.old_speech_stopped_interrupted = None
        result.new_task_created = False
        result.new_task_becomes_active = False
        result.stale_result_rejected = False
        result.stale_result_not_spoken = False
        result.active_state_not_overwritten = False
        result.final_answer_matches_latest_request = False
        result.events_recorded_in_timeline = False
        result.measurable_evidence_captured = False
        return result

    t1_id = t1_task_id_holder[0]
    result.t1_task_id = t1_id

    # Wait for the interrupt moment (while tool is still running)
    time_to_wait = max(0.0, interrupt_after_s - (time.monotonic() - wall_start))
    await asyncio.sleep(time_to_wait)
    result.interrupt_fired_at_s = time.monotonic() - wall_start

    logger.info(
        "[ScenB] INTERRUPT at t=%.2fs (tool has %.1fs remaining)  task_id=%s",
        result.interrupt_fired_at_s,
        tool_delay_s - interrupt_after_s,
        t1_id,
    )

    # Nothing is speaking yet (tool is still running), but we fire the sequence:
    # voice interrupt (no-op here) + task interrupt
    voice_client.interrupt()   # no-op if not speaking -- safe per stub spec
    task_client.interrupt(t1_id, new_request_text)

    # --- Wait for T1 run to complete ---
    # The tool will return after tool_delay_s total. By then:
    #   - T1 is OBSOLETE
    #   - Active task is the stub T2 created by interrupt()
    #   - check_fence(T1.fence_token) vs active(T2.fence_token) -> mismatch
    #   - brain.run() returns aborted=True, abort_reason="stale_result_rejected"
    result_t1 = await t1_run
    result.t1_run_result = result_t1
    result.t1_tool_returned_at_s = time.monotonic() - wall_start

    logger.info(
        "[ScenB] T1 run complete  aborted=%s  abort_reason=%s",
        result_t1.aborted, result_t1.abort_reason,
    )

    # --- Run new request (T2) ---
    logger.info("[ScenB] Starting T2 run: %r", new_request_text)
    result_t2 = await brain.run(new_request_text)
    result.t2_run_result = result_t2
    result.t2_task_id = result_t2.task_id
    result.events = all_events

    # ================================================================
    # Evaluate the 10 checks
    # ================================================================

    # 1. old task invalidated
    t1_task = task_client.get_task(t1_id)
    result.old_task_invalidated = (
        t1_task is not None and t1_task.status == "OBSOLETE"
    )

    # 2. old speech stopped interrupted -- N/A for Scenario B
    #    (nothing was speaking when interrupt fired)
    result.old_speech_stopped_interrupted = None

    # 3. new task created
    new_task_ids = {
        entry["event"].task_id
        for entry in all_events
        if isinstance(entry["event"], TaskEvent)
        and entry["event"].event == "task.created"
        and entry["event"].task_id != t1_id
    }
    result.new_task_created = len(new_task_ids) > 0

    # 4. new task becomes active
    new_active_ids = {
        entry["event"].task_id
        for entry in all_events
        if isinstance(entry["event"], TaskEvent)
        and entry["event"].event == "task.active"
        and entry["event"].task_id != t1_id
    }
    result.new_task_becomes_active = len(new_active_ids) > 0

    # 5. stale result rejected
    result.stale_result_rejected = (
        result_t1.aborted
        and result_t1.abort_reason == "stale_result_rejected"
    )

    # 6. stale result not spoken
    #    Verify: no speech.started event for T1's task_id
    t1_speech_events = [
        entry for entry in all_events
        if isinstance(entry["event"], SpeechEvent)
        and entry["event"].event == "speech.started"
        and entry["event"].task_id == t1_id
    ]
    result.stale_result_not_spoken = len(t1_speech_events) == 0

    # 7. active state not overwritten -- T2 eventually completed
    if result.t2_task_id:
        t2_task = task_client.get_task(result.t2_task_id)
        result.active_state_not_overwritten = (
            t2_task is not None
            and t2_task.status == "COMPLETED"
        )
    else:
        result.active_state_not_overwritten = False

    # 8. final answer matches latest request
    result.final_answer_matches_latest_request = (
        result_t2 is not None
        and not result_t2.aborted
        and bool(result_t2.response_text)
    )

    # 9. events recorded in timeline
    result.events_recorded_in_timeline = len(all_events) >= 4

    # 10. measurable evidence captured
    result.measurable_evidence_captured = (
        result.interrupt_fired_at_s is not None
        and result.t1_tool_returned_at_s is not None
        and result.t1_tool_returned_at_s > result.interrupt_fired_at_s
    )

    return result


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _print_result(result: ScenarioResult) -> None:
    """Print a scenario result to stdout in a readable format."""
    tag = "[STUB TEST -- not real evidence]" if result.stub_run else "[REAL RUN]"
    status = "PASS" if result.passed else "FAIL"

    print(f"\n{'='*60}")
    print(f"SCENARIO {result.scenario}  {status}  {tag}")
    print(f"{'='*60}")

    checks = [
        ("old task invalidated",                result.old_task_invalidated),
        ("old speech stopped (interrupted)",    result.old_speech_stopped_interrupted),
        ("new task created",                    result.new_task_created),
        ("new task becomes active",             result.new_task_becomes_active),
        ("stale result rejected",               result.stale_result_rejected),
        ("stale result not spoken",             result.stale_result_not_spoken),
        ("active state not overwritten",        result.active_state_not_overwritten),
        ("final answer matches latest request", result.final_answer_matches_latest_request),
        ("events recorded in timeline",         result.events_recorded_in_timeline),
        ("measurable evidence captured",        result.measurable_evidence_captured),
    ]

    for label, value in checks:
        symbol = result.check_value(value)
        print(f"  [{symbol}] {label}")

    print(f"\n  T1 task_id:     {result.t1_task_id}")
    print(f"  T2 task_id:     {result.t2_task_id}")

    if result.scenario == "A":
        print(f"  interrupt at:   {result.interrupt_fired_at_s:.2f}s")
        print(f"  speech stopped: {result.t1_speech_stopped_reason}  "
              f"({result.t1_speech_ms_spoken} ms spoken)")

    if result.scenario == "B":
        print(f"  interrupt at:        {result.interrupt_fired_at_s:.2f}s")
        if result.t1_tool_returned_at_s:
            print(f"  T1 tool returned at: {result.t1_tool_returned_at_s:.2f}s")
        if result.t1_run_result:
            print(f"  T1 aborted:          {result.t1_run_result.aborted}")
            print(f"  T1 abort reason:     {result.t1_run_result.abort_reason}")

    if result.t2_run_result:
        resp = result.t2_run_result.response_text
        print(f"  T2 response:    {resp[:100]!r}{'...' if len(resp) > 100 else ''}")

    print(f"\n  Event timeline ({len(result.events)} events):")
    for entry in result.events:
        e = entry["event"]
        ts = entry["ts"]
        if isinstance(e, TaskEvent):
            print(f"    t={ts:5.2f}s  {e.event:<22}  task_id={e.task_id}")
        elif isinstance(e, SpeechEvent):
            extra = ""
            if e.stopped_reason:
                extra = f"  reason={e.stopped_reason}  ms={e.ms_spoken}"
            print(f"    t={ts:5.2f}s  {e.event:<22}  task_id={e.task_id}{extra}")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    async def _main() -> None:
        print("\n" + "="*60)
        print("REVIA -- Evaluation Scenarios (STUB RUN)")
        print("One mechanism, two demonstrations")
        print("="*60)
        print("\nWARNING: All results below are [STUB TEST -- not real evidence].")
        print("         Do not copy numbers into RIME_EVIDENCE.md.")

        print("\n\nRunning Scenario A (interrupt while speaking) ...")
        result_a = await run_scenario_a(
            speech_duration_s=4.0,
            tool_delay_s=1.0,
            interrupt_after_speech_s=1.0,
        )
        _print_result(result_a)

        print("\n\nRunning Scenario B (interrupt during tool execution) ...")
        result_b = await run_scenario_b(
            tool_delay_s=5.0,
            interrupt_after_s=2.0,
        )
        _print_result(result_b)

        print("\n\n" + "="*60)
        overall = "PASS" if (result_a.passed and result_b.passed) else "FAIL"
        print(f"OVERALL: {overall}  [STUB TEST -- not real evidence]")
        print("="*60)

        if not result_a.passed or not result_b.passed:
            raise SystemExit(1)

    asyncio.run(_main())
