"""
backend/evaluation/evidence_generator.py
==========================================
Runs Scenario A and Scenario B, then prints a PASS/FAIL checklist in the
exact format of RIME_EVIDENCE.md Section 4 (Acceptance Test).

Exits 0 if every applicable check passes. Exits 1 if any check fails.

Every output line is labelled [STUB TEST -- not real evidence] when running
against stub modules. Do NOT paste these results into RIME_EVIDENCE.md as
real evidence -- that file is only updated with confirmed real-integration runs.

Usage:
    python -m backend.evaluation.evidence_generator

Owner: shlok (backend/evaluation/).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from backend.evaluation.scenarios import (
    ScenarioResult,
    run_scenario_a,
    run_scenario_b,
)
from backend.evaluation.metrics import MetricsCollector, MetricsReport
from backend.orchestration.stub_task_client import TaskEvent
from backend.orchestration.stub_voice_client import SpeechEvent

logger = logging.getLogger(__name__)

_STUB_TAG = "[STUB TEST -- not real evidence]"
_REAL_TAG = "[REAL RUN]"


# ---------------------------------------------------------------------------
# Checklist rendering -- matches RIME_EVIDENCE.md Section 4 / 7 format
# ---------------------------------------------------------------------------

_CHECK_LABELS = [
    ("old_task_invalidated",                "old task invalidated"),
    ("old_speech_stopped_interrupted",      "old speech stopped if speaking"),
    ("new_task_created",                    "new task created"),
    ("new_task_becomes_active",             "new task becomes active"),
    ("stale_result_rejected",               "stale result rejected"),
    ("stale_result_not_spoken",             "stale result not spoken"),
    ("active_state_not_overwritten",        "active state not overwritten"),
    ("final_answer_matches_latest_request", "final answer matches latest request"),
    ("events_recorded_in_timeline",         "events recorded in timeline"),
    ("measurable_evidence_captured",        "measurable evidence captured (logs/metrics attached)"),
]


def _render_checklist(result: ScenarioResult, report: MetricsReport) -> list[str]:
    """
    Render the 10-item PASS/FAIL checklist for one scenario.

    Matches the format in RIME_EVIDENCE.md Section 7:
        [PASS] old task invalidated
        [FAIL] stale result rejected
        [N/A ] old speech stopped if speaking
    """
    lines = []
    for attr, label in _CHECK_LABELS:
        value: Optional[bool] = getattr(result, attr)
        if value is True:
            marker = "PASS"
        elif value is False:
            marker = "FAIL"
        else:
            marker = "N/A "
        lines.append(f"  [{marker}] {label}")
    return lines


def _render_metrics_block(report: MetricsReport) -> list[str]:
    """Render the metrics evidence block for one scenario."""
    def fmt(val: Optional[float], unit: str = "ms") -> str:
        return f"{val:.0f}{unit}" if val is not None else "N/A"

    def fmt_rate(val: Optional[float]) -> str:
        return f"{val:.1%}" if val is not None else "N/A"

    lines = [
        "  Measured metrics (from actual event timestamps):",
        f"    interruption_count          = {report.interruption_count}",
        f"    stale_result_rejection_rate = {fmt_rate(report.stale_result_rejection_rate)}",
        f"    time_to_first_audio_ms      = {fmt(report.time_to_first_audio_ms)}",
        f"    recovery_time_ms            = {fmt(report.recovery_time_ms)}",
    ]
    return lines


def _render_scenario_block(
    result: ScenarioResult,
    report: MetricsReport,
) -> list[str]:
    """Render the full evidence block for one scenario."""
    tag = _STUB_TAG if result.stub_run else _REAL_TAG
    status = "PASS" if result.passed else "FAIL"
    title = (
        "Scenario A -- Interrupt while speaking"
        if result.scenario == "A"
        else "Scenario B -- Interrupt during tool execution"
    )

    lines: list[str] = []
    lines.append("")
    lines.append(f"**{title}**  [{status}]  {tag}")

    # Provenance
    if result.scenario == "A" and result.t1_speech_stopped_reason:
        lines.append(
            f"  T1 speech stopped: reason={result.t1_speech_stopped_reason}"
            f"  ms_spoken={result.t1_speech_ms_spoken}"
        )
    if result.scenario == "B" and result.t1_run_result:
        lines.append(
            f"  T1 abort reason: {result.t1_run_result.abort_reason}"
            f"  (aborted={result.t1_run_result.aborted})"
        )
    if result.t1_task_id:
        lines.append(f"  T1 task_id: {result.t1_task_id}")
    if result.t2_task_id:
        lines.append(f"  T2 task_id: {result.t2_task_id}")
    if result.interrupt_fired_at_s is not None:
        lines.append(f"  Interrupt fired at: {result.interrupt_fired_at_s:.2f}s")
    if result.scenario == "B" and result.t1_tool_returned_at_s is not None:
        lines.append(f"  T1 tool returned at: {result.t1_tool_returned_at_s:.2f}s")

    lines.append("")
    lines.append("  PASS checklist (per RIME_EVIDENCE.md Section 7):")
    lines.extend(_render_checklist(result, report))
    lines.append("")
    lines.extend(_render_metrics_block(report))

    # Event timeline summary
    if result.events:
        lines.append("")
        lines.append(f"  Event timeline ({len(result.events)} events recorded):")
        for entry in result.events:
            e = entry["event"]
            ts = entry["ts"]
            if isinstance(e, TaskEvent):
                lines.append(
                    f"    t={ts:5.2f}s  {e.event:<22}  task_id={e.task_id}"
                )
            elif isinstance(e, SpeechEvent):
                extra = ""
                if e.stopped_reason:
                    extra = f"  reason={e.stopped_reason}  ms={e.ms_spoken}"
                lines.append(
                    f"    t={ts:5.2f}s  {e.event:<22}  task_id={e.task_id}{extra}"
                )

    return lines


# ---------------------------------------------------------------------------
# Main evidence generation runner
# ---------------------------------------------------------------------------

async def generate_evidence(
    scenario_a_kwargs: Optional[dict] = None,
    scenario_b_kwargs: Optional[dict] = None,
) -> tuple[list[str], bool]:
    """
    Run both scenarios and generate the full evidence report.

    Args:
        scenario_a_kwargs: Override parameters for run_scenario_a().
        scenario_b_kwargs: Override parameters for run_scenario_b().

    Returns:
        (lines, all_passed) where lines is the full report as a list of strings
        and all_passed is True iff every applicable check PASS'd.
    """
    a_kwargs = scenario_a_kwargs or {}
    b_kwargs = scenario_b_kwargs or {}

    collector = MetricsCollector()
    lines: list[str] = []
    all_passed = True

    # ---- Header ----
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("=" * 68)
    lines.append("REVIA -- Evidence Generator")
    lines.append(f"Generated: {run_ts}")
    lines.append("One mechanism, two demonstrations (MASTER_README.md Section 2)")
    lines.append("=" * 68)
    lines.append("")
    lines.append("WARNING: Running against STUB modules.")
    lines.append(f"         Every result below is {_STUB_TAG}.")
    lines.append("         Do NOT write these results into RIME_EVIDENCE.md.")
    lines.append("         Re-run with real modules when available (see PROGRESS.md).")

    # ---- Scenario A ----
    lines.append("")
    lines.append("-" * 68)
    print("[evidence_generator] Running Scenario A ...", flush=True)
    result_a = await run_scenario_a(**a_kwargs)
    report_a = collector.compute(result_a)

    if not result_a.passed:
        all_passed = False

    lines.extend(_render_scenario_block(result_a, report_a))

    # ---- Scenario B ----
    lines.append("")
    lines.append("-" * 68)
    print("[evidence_generator] Running Scenario B ...", flush=True)
    result_b = await run_scenario_b(**b_kwargs)
    report_b = collector.compute(result_b)

    if not result_b.passed:
        all_passed = False

    lines.extend(_render_scenario_block(result_b, report_b))

    # ---- Summary ----
    lines.append("")
    lines.append("=" * 68)
    lines.append("SUMMARY")
    lines.append("=" * 68)

    a_status = "PASS" if result_a.passed else "FAIL"
    b_status = "PASS" if result_b.passed else "FAIL"
    overall = "PASS" if all_passed else "FAIL"

    lines.append(f"  Scenario A (interrupt while speaking):         [{a_status}]")
    lines.append(f"  Scenario B (interrupt during tool execution):  [{b_status}]")
    lines.append("")
    lines.append(f"  OVERALL: [{overall}]  {_STUB_TAG}")
    lines.append("")

    # Key evidence sentences (suitable for RIME_EVIDENCE.md when real)
    lines.append("  Key evidence (STUB values -- replace with real run data):")
    lines.append("")
    lines.append("  Scenario A:")
    if result_a.t1_speech_stopped_reason == "interrupted":
        lines.append(
            f"    - Rime audio stopped in {result_a.t1_speech_ms_spoken} ms "
            f"after interrupt (stopped_reason=interrupted)"
        )
    lines.append(
        f"    - Recovery time (interrupt -> new speech): "
        f"{report_a.recovery_time_ms:.0f} ms"
        if report_a.recovery_time_ms is not None
        else "    - Recovery time: N/A"
    )
    lines.append(
        f"    - Time to first audio (T1 task.active -> speech.started): "
        f"{report_a.time_to_first_audio_ms:.0f} ms"
        if report_a.time_to_first_audio_ms is not None
        else "    - Time to first audio: N/A"
    )
    lines.append("")
    lines.append("  Scenario B:")
    if result_b.t1_run_result and result_b.t1_run_result.abort_reason == "stale_result_rejected":
        lines.append(
            "    - Stale tool result (fence_token mismatch) was REJECTED "
            "and never reached speech"
        )
    lines.append(
        f"    - Stale result rejection rate: "
        f"{report_b.stale_result_rejection_rate:.1%}"
        if report_b.stale_result_rejection_rate is not None
        else "    - Stale result rejection rate: N/A"
    )
    lines.append(
        f"    - Interrupt fired at {result_b.interrupt_fired_at_s:.2f}s, "
        f"tool returned at {result_b.t1_tool_returned_at_s:.2f}s "
        f"({result_b.t1_tool_returned_at_s - result_b.interrupt_fired_at_s:.2f}s after interrupt)"
        if (result_b.interrupt_fired_at_s is not None and result_b.t1_tool_returned_at_s is not None)
        else "    - Tool timing: N/A"
    )
    lines.append("")
    lines.append("=" * 68)

    return lines, all_passed


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Run evidence generation and print the full report to stdout."""
    import sys as _sys
    logging.basicConfig(
        level=logging.ERROR,    # suppress all but errors; STALE RESULT log is INFO
        format="[%(name)s] %(message)s",
        stream=_sys.stdout,     # route to stdout to avoid PowerShell NativeCommandError
    )

    async def _run() -> bool:
        lines, all_passed = await generate_evidence(
            scenario_a_kwargs={
                "speech_duration_s": 4.0,
                "tool_delay_s": 1.0,
                "interrupt_after_speech_s": 1.0,
            },
            scenario_b_kwargs={
                "tool_delay_s": 5.0,
                "interrupt_after_s": 2.0,
            },
        )
        print("\n".join(lines))
        return all_passed

    all_passed = asyncio.run(_run())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
