"""LiveKit STT agent with stub tasks, Rime playback, and speech events."""

import json
import os
import sys
import logging
from pathlib import Path

# Configure robust UTF-8 logging for Windows environments
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    UserStateChangedEvent,
    cli,
)
from livekit.agents.voice.room_io import RoomOptions

from stt_deepgram import create_stt

# We need to make sure the root dir is in sys.path to import from backend
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.orchestration.agent_brain import AgentBrain
from backend.rime.events import RimePlaybackController
from backend.rime.tts_rime import create_rime_tts, queue_rime_speech


def _has_active_rime_playback(playback_controller: RimePlaybackController) -> bool:
    handle = playback_controller.active_speech_handle
    return (
        playback_controller.active_task_id is not None
        and handle is not None
        and playback_controller.active_speech_id is not None
        and playback_controller.active_started_at is not None
        and not handle.done()
    )


REQUIRED_ENVIRONMENT_VARIABLES = (
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "DEEPGRAM_API_KEY",
    "RIME_API_KEY",
    "GROQ_API_KEY",
)


def validate_environment() -> None:
    """Fail before joining a room when a required secret is absent."""
    missing = [name for name in REQUIRED_ENVIRONMENT_VARIABLES if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required .env values: {', '.join(missing)}")


class ReviaVoiceAgent(Agent):
    """Creates tasks and manages Rime speech lifecycle events."""

    def __init__(
        self,
        brain: AgentBrain,
        playback_controller: RimePlaybackController,
    ) -> None:
        super().__init__(
            instructions="Transcribe user speech and play a Rime acknowledgement.",
        )
        self._brain = brain
        self._playback_controller = playback_controller
        self._session_closed = False

    def mark_session_closed(self) -> None:
        """Record AgentSession teardown for detached transcript tasks."""
        self._session_closed = True

    def _session_is_live(self, session: AgentSession) -> bool:
        """Check session lifecycle immediately before queueing speech."""
        return not self._session_closed

    async def process_transcript(self, transcript: str, session: AgentSession) -> None:
        """Run the headless pipeline for the final transcribed speech."""
        if not transcript:
            return

        result = await self._brain.run_headless(transcript)
        if result.aborted:
            print(
                f"TASK ABORTED: task_id={result.task_id} reason={result.abort_reason}",
                flush=True,
            )
            return

        response_text = result.response_text

        final_speech_status = self._brain.task_client.check_llm_response(
            {
                "task_id": result.task_id,
                "fence_token": result.fence_token,
                "response_text": response_text,
            }
        )
        if final_speech_status != "accepted":
            logger.warning(
                "STALE RIME RESPONSE REJECTED: task_id=%s fence=%s status=%s",
                result.task_id,
                result.fence_token,
                final_speech_status,
            )
            return

        if not self._session_is_live(session):
            logger.warning(
                "RIME SPEECH SKIPPED: AgentSession is closed/closing task_id=%s",
                result.task_id,
            )
            return

        try:
            handle = queue_rime_speech(session, response_text)
        except RuntimeError as exc:
            if str(exc) in {
                "AgentSession isn't running",
                "AgentSession is closing, cannot use say()",
            }:
                logger.warning(
                    "RIME SPEECH SKIPPED: AgentSession teardown raced speech queue "
                    "task_id=%s error=%s",
                    result.task_id,
                    exc,
                )
                return
            raise
        speech_started_event = self._playback_controller.start_playback(
            result.task_id,
            handle,
        )

        print(
            f"EVENT: {json.dumps(speech_started_event)}",
            flush=True,
        )
        print(f"RIME PLAYBACK QUEUED: task_id={result.task_id}", flush=True)

        await handle

        stopped_reason = "interrupted" if handle.interrupted else "completed"
        speech_stopped_event = self._playback_controller.finish_playback(
            result.task_id,
            handle,
            stopped_reason,
        )

        if speech_stopped_event is not None:
            print(
                f"EVENT: {json.dumps(speech_stopped_event)}",
                flush=True,
            )

        if handle.interrupted:
            print(
                f"RIME PLAYBACK STOPPED: task_id={result.task_id} "
                "reason=interrupted",
                flush=True,
            )
        elif handle.exception() is None:
            print(
                f"RIME PLAYBACK FINISHED: task_id={result.task_id}",
                flush=True,
            )
            self._brain.task_client.complete_task(result.task_id)
        else:
            print(
                f"RIME PLAYBACK FAILED: task_id={result.task_id} "
                f"error={handle.exception()}",
                flush=True,
            )
            self._brain.task_client.complete_task(result.task_id)


load_dotenv()
server = AgentServer()


@server.rtc_session(agent_name="revia-stt")
async def entrypoint(ctx: JobContext) -> None:
    """Join a room and emit speech lifecycle and interrupt events."""
    validate_environment()
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=create_stt(),
        tts=create_rime_tts(),
        turn_handling={
            "turn_detection": "stt",
            "endpointing": {
                "mode": "fixed",
                "min_delay": 1.5,
                "max_delay": 3.0,
            },
            "interruption": {
                "enabled": False,
                "min_duration": 0.35,
                "min_words": 1,
                "false_interruption_timeout": 1.0,
                "resume_false_interruption": True,
            },
        },
    )

    brain = AgentBrain()
    playback_controller = RimePlaybackController()

    agent_instance = ReviaVoiceAgent(brain, playback_controller)

    @session.on("close")
    def on_session_closed(_event: object) -> None:
        agent_instance.mark_session_closed()

    @session.on("user_state_changed")
    def on_user_state_changed(event: UserStateChangedEvent) -> None:
        if event.new_state != "speaking":
            return
        if not _has_active_rime_playback(playback_controller):
            return

        brain.task_client.obsolete_active_task()

        # Removed automatic interruption on user_state_changed; keep only task obsolete

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: object) -> None:
        # Extract transcript and final flag
        is_final = getattr(event, "is_final", False)
        transcript = getattr(event, "transcript", "").strip()
        if not transcript:
            return

        # Interrupt on interim (non‑final) transcripts if playback is active
        if not is_final and _has_active_rime_playback(playback_controller):
            brain.task_client.obsolete_active_task()
            interruption_events = playback_controller.interrupt_on_new_user_speech()
            for interruption_event in interruption_events:
                print(f"EVENT: {json.dumps(interruption_event)}", flush=True)

        # For final transcripts, also interrupt if needed and forward to brain
        if is_final:
            if _has_active_rime_playback(playback_controller):
                brain.task_client.obsolete_active_task()
                interruption_events = playback_controller.interrupt_on_new_user_speech()
                for interruption_event in interruption_events:
                    print(f"EVENT: {json.dumps(interruption_event)}", flush=True)
            print(f"TRANSCRIPT: {transcript}", flush=True)
            import asyncio
            asyncio.create_task(agent_instance.process_transcript(transcript, session))

    await session.start(
        room=ctx.room,
        agent=agent_instance,
        room_options=RoomOptions(text_input=False),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
