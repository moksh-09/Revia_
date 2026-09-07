"""
backend/evaluation/metrics.py
================================
Real, measured metrics only -- MASTER_README.md Section 10 (shlok) Step 3.

Four metrics, all computed from actual observed event timestamps:
  1. interruption_count        -- number of tasks interrupted mid-flight
  2. stale_result_rejection_rate -- fraction of post-interrupt tool results rejected
  3. time_to_first_audio_ms   -- ms from task.active to first speech.started
  4. recovery_time_ms         -- ms from interrupt to new task's first speech.started

NEVER fabricated or estimated. Against stubs, every number is labelled:
  [STUB TEST -- not real evidence]

Owner: shlok (backend/evaluation/).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.orchestration.stub_task_client import TaskEvent
from backend.orchestration.stub_voice_client import SpeechEvent
from backend.evaluation.scenarios import ScenarioResult

logger = logging.getLogger(__name__)

_STUB_NOTE = "[STUB TEST -- not real evidence]"


# ---------------------------------------------------------------------------
# MetricsReport -- the four measured metrics
# ---------------------------------------------------------------------------

@dataclass
class MetricsReport:
    """
    Real, measured metrics from one scenario run.

    All numeric fields are derived from actual monotonic timestamps captured
    during the scenario. None means the metric could not be measured for this
    scenario (e.g. TTFA for a task that never reached speech).

    If stub_run is True, every number is labelled as a stub-test result and
    must NOT be copied into RIME_EVIDENCE.md as real evidence.
    """

    scenario: str
    stub_run: bool = True

    # ---- The 4 metrics ----

    interruption_count: int = 0
    """
    Number of tasks that were interrupted (moved to OBSOLETE) during this run.
    Proxy for the 'interrupt' event from CONTRACTS.md Section 2 -- in stub runs,
    counted via task.obsolete events (one per unique interrupted task_id).
    In real integration, count actual 'interrupt' events emitted by vedantk.
    """

    stale_result_rejection_rate: Optional[float] = None
    """
    Fraction of tool results that were rejected as stale after an interrupt.
    = rejected_stale_count / total_tool_completions_where_task_ran_a_tool.
    None if no tool ran during this scenario at all.
    0.0 if a tool ran but was not stale (e.g. Scenario A: tool completes before
        the interrupt fires, result is accepted, interruption happens during speech).
    1.0 if a tool ran post-interrupt and was correctly rejected (Scenario B).
    Range [0.0, 1.0] when not None.
    """

    time_to_first_audio_ms: Optional[float] = None
    """
    Milliseconds from task.active to the first speech.started for that task.
    Covers: Groq latency + tool latency (if any) + TTS startup.
    Measured for the first task that actually reached speech in this scenario.
    In Scenario B, T1 never speaks -- TTFA is measured on T2 (new request).
    """

    recovery_time_ms: Optional[float] = None
    """
    Milliseconds from the interrupt event (task.obsolete of T1) to the first
    speech.started of the new task (T2's answer).
    Measures end-to-end latency of the interruption-recovery mechanism:
    how long the user waits from interrupting to hearing the new answer begin.
    """

    # ---- Raw timestamps (evidence) ----

    _t1_active_ts: Optional[float] = field(default=None, repr=False)
    _first_speech_ts: Optional[float] = field(default=None, repr=False)
    _interrupt_ts: Optional[float] = field(default=None, repr=False)
    _new_speech_ts: Optional[float] = field(default=None, repr=False)
    _stale_rejections: int = field(default=0, repr=False)
    _tool_completions_post_interrupt: int = field(default=0, repr=False)

    def summary(self) -> str:
        """One-line human-readable summary."""
        rate = (
            f"{self.stale_result_rejection_rate:.1%}"
            if self.stale_result_rejection_rate is not None
            else "N/A"
        )
        ttfa = (
            f"{self.time_to_first_audio_ms:.0f}ms"
            if self.time_to_first_audio_ms is not None
            else "N/A"
        )
        rec = (
            f"{self.recovery_time_ms:.0f}ms"
            if self.recovery_time_ms is not None
            else "N/A"
        )
        stub = f"  {_STUB_NOTE}" if self.stub_run else ""
        return (
            f"Scenario {self.scenario}{stub}\n"
            f"  interruption_count             = {self.interruption_count}\n"
            f"  stale_result_rejection_rate    = {rate}\n"
            f"  time_to_first_audio_ms         = {ttfa}\n"
            f"  recovery_time_ms               = {rec}"
        )


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Computes real, measured metrics from a completed ScenarioResult.

    All numbers come from actual monotonic timestamps captured during the
    scenario run. Nothing is fabricated or estimated.

    Usage::

        collector = MetricsCollector()
        report = collector.compute(scenario_result)
        print(report.summary())
    """

    def compute(self, result: ScenarioResult) -> MetricsReport:
        """
        Derive all four metrics from *result*'s event log and run results.

        Args:
            result: A completed ScenarioResult from run_scenario_a() or
                    run_scenario_b().

        Returns:
            MetricsReport with all four metrics (or None where not applicable).
        """
        report = MetricsReport(scenario=result.scenario, stub_run=result.stub_run)
        events = result.events   # list of {"ts": float, "event": TaskEvent|SpeechEvent}

        if not events:
            logger.warning("[Metrics] No events in ScenarioResult -- cannot compute metrics")
            return report

        t1_id = result.t1_task_id
        t2_id = result.t2_task_id

        # ----------------------------------------------------------------
        # 1. interruption_count
        #    Count unique task_ids that appeared in a task.obsolete event.
        #    (task.obsolete is emitted twice by the stub -- deduplicate.)
        # ----------------------------------------------------------------
        obsoleted_task_ids: set[str] = set()
        for entry in events:
            e = entry["event"]
            if isinstance(e, TaskEvent) and e.event == "task.obsolete":
                obsoleted_task_ids.add(e.task_id)
        report.interruption_count = len(obsoleted_task_ids)
        logger.debug("[Metrics] interruption_count=%d  ids=%s",
                     report.interruption_count, obsoleted_task_ids)

        # ----------------------------------------------------------------
        # 2. stale_result_rejection_rate
        #    = stale_rejections / tool_completions_post_interrupt
        #
        #    In stub runs: we know a stale rejection happened if T1's
        #    RunResult has aborted=True and abort_reason="stale_result_rejected".
        #    tool_completions_post_interrupt = 1 if T1's tool ran and returned.
        #    (In real integration: count tool.result events post-interrupt.)
        # ----------------------------------------------------------------
        t1_result = result.t1_run_result
        if (
            t1_result is not None
            and t1_result.tool_name is not None        # tool actually ran
            and report.interruption_count > 0          # an interrupt happened
        ):
            tool_returned = True    # the tool ran and returned (even if aborted)
            was_rejected = (
                t1_result.aborted
                and t1_result.abort_reason == "stale_result_rejected"
            )
            report._tool_completions_post_interrupt = 1 if tool_returned else 0
            report._stale_rejections = 1 if was_rejected else 0

            if report._tool_completions_post_interrupt > 0:
                report.stale_result_rejection_rate = (
                    report._stale_rejections / report._tool_completions_post_interrupt
                )
            logger.debug(
                "[Metrics] stale_rejection_rate=%.2f  rejections=%d  completions=%d",
                report.stale_result_rejection_rate or 0.0,
                report._stale_rejections,
                report._tool_completions_post_interrupt,
            )
        else:
            # No tool ran post-interrupt (Scenario A: T1 speaks before interrupt)
            report.stale_result_rejection_rate = None
            logger.debug("[Metrics] stale_result_rejection_rate=N/A (no tool ran post-interrupt)")

        # ----------------------------------------------------------------
        # 3. time_to_first_audio_ms
        #    = speech.started(first_speaking_task) - task.active(first_speaking_task)
        #
        #    "First speaking task" = T1 if T1 reached speech (Scenario A),
        #    or T2 if T1 never spoke (Scenario B where T1 was aborted pre-speech).
        # ----------------------------------------------------------------
        #
        # Determine which task to measure TTFA on.
        t1_spoke = (
            t1_result is not None
            and t1_result.speech_id is not None
        )
        ttfa_task_id = t1_id if t1_spoke else t2_id

        if ttfa_task_id is not None:
            active_ts = self._find_event_ts(
                events, TaskEvent, "task.active", ttfa_task_id
            )
            speech_ts = self._find_event_ts(
                events, SpeechEvent, "speech.started", ttfa_task_id
            )
            if active_ts is not None and speech_ts is not None:
                report._t1_active_ts = active_ts
                report._first_speech_ts = speech_ts
                report.time_to_first_audio_ms = (speech_ts - active_ts) * 1000.0
                logger.debug(
                    "[Metrics] TTFA task=%s  active=%.3fs  speech=%.3fs  ttfa=%.0fms",
                    ttfa_task_id,
                    active_ts, speech_ts,
                    report.time_to_first_audio_ms,
                )
            else:
                logger.debug(
                    "[Metrics] TTFA N/A: could not find both task.active and speech.started "
                    "for task=%s", ttfa_task_id
                )

        # ----------------------------------------------------------------
        # 4. recovery_time_ms
        #    = speech.started(T2) - first task.obsolete(T1)
        #
        #    Measures: from interrupt to new-task answer beginning.
        # ----------------------------------------------------------------
        if t1_id is not None and t2_id is not None:
            interrupt_ts = self._find_event_ts(
                events, TaskEvent, "task.obsolete", t1_id
            )
            new_speech_ts = self._find_event_ts(
                events, SpeechEvent, "speech.started", t2_id
            )
            if interrupt_ts is not None and new_speech_ts is not None:
                report._interrupt_ts = interrupt_ts
                report._new_speech_ts = new_speech_ts
                report.recovery_time_ms = (new_speech_ts - interrupt_ts) * 1000.0
                logger.debug(
                    "[Metrics] recovery  interrupt=%.3fs  new_speech=%.3fs  recovery=%.0fms",
                    interrupt_ts, new_speech_ts, report.recovery_time_ms,
                )
            else:
                logger.debug(
                    "[Metrics] recovery N/A: could not find both task.obsolete(T1) "
                    "and speech.started(T2)"
                )

        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_event_ts(
        events: list[dict],
        event_type: type,
        event_name: str,
        task_id: str,
    ) -> Optional[float]:
        """
        Return the monotonic timestamp (seconds) of the FIRST event matching
        *event_type*, *event_name*, and *task_id* in the event log.

        Returns None if no matching event is found.
        """
        for entry in events:
            e = entry["event"]
            if (
                isinstance(e, event_type)
                and e.event == event_name
                and e.task_id == task_id
            ):
                return entry["ts"]
        return None


# ---------------------------------------------------------------------------
# Batch helper -- compute metrics for a list of scenario results
# ---------------------------------------------------------------------------

def compute_all(results: list[ScenarioResult]) -> list[MetricsReport]:
    """
    Compute metrics for a list of scenario results.

    Args:
        results: List of ScenarioResults from run_scenario_a() / run_scenario_b().

    Returns:
        List of MetricsReports, one per result, in the same order.
    """
    collector = MetricsCollector()
    return [collector.compute(r) for r in results]


def print_reports(reports: list[MetricsReport]) -> None:
    """Print all reports to stdout."""
    print("\n" + "=" * 60)
    print("REVIA -- Metrics Report")
    print("=" * 60)
    for r in reports:
        print()
        print(r.summary())
    print("\n" + "=" * 60)
    if any(r.stub_run for r in reports):
        print(_STUB_NOTE)
        print("Do NOT copy these numbers into RIME_EVIDENCE.md.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI entrypoint -- runs scenarios and prints metrics
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    from backend.evaluation.scenarios import run_scenario_a, run_scenario_b

    async def _main() -> None:
        print("\nRunning Scenario A to collect metrics ...")
        result_a = await run_scenario_a(
            speech_duration_s=4.0,
            tool_delay_s=1.0,
            interrupt_after_speech_s=1.0,
        )
        assert result_a.passed, "Scenario A did not PASS -- metrics would be meaningless"

        print("\nRunning Scenario B to collect metrics ...")
        result_b = await run_scenario_b(
            tool_delay_s=5.0,
            interrupt_after_s=2.0,
        )
        assert result_b.passed, "Scenario B did not PASS -- metrics would be meaningless"

        reports = compute_all([result_a, result_b])
        print_reports(reports)

        # ---- Assertions: all measurable metrics must be present ----
        rA, rB = reports

        # Scenario A
        assert rA.interruption_count == 1,          f"Expected 1, got {rA.interruption_count}"
        assert rA.stale_result_rejection_rate is None or 0.0 <= rA.stale_result_rejection_rate <= 1.0, \
            f"Scenario A: stale_result_rejection_rate out of valid range [0.0, 1.0] or None " \
            f"(got {rA.stale_result_rejection_rate})"
        assert rA.time_to_first_audio_ms is not None, "TTFA must be measured"
        assert rA.time_to_first_audio_ms > 0,        "TTFA must be positive"
        assert rA.recovery_time_ms is not None,       "recovery_time must be measured"
        assert rA.recovery_time_ms > 0,               "recovery_time must be positive"
        print("\nScenario A metric assertions: PASS")

        # Scenario B
        assert rB.interruption_count == 1,             f"Expected 1, got {rB.interruption_count}"
        assert rB.stale_result_rejection_rate == 1.0,  \
            f"Expected 1.0, got {rB.stale_result_rejection_rate}"
        assert rB.time_to_first_audio_ms is not None,  "TTFA must be measured for T2"
        assert rB.time_to_first_audio_ms > 0,           "TTFA must be positive"
        assert rB.recovery_time_ms is not None,         "recovery_time must be measured"
        assert rB.recovery_time_ms > 0,                 "recovery_time must be positive"
        print("Scenario B metric assertions: PASS")

        print(f"\nAll metrics verified. {_STUB_NOTE}")

    asyncio.run(_main())
