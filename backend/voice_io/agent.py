"""LiveKit STT agent with stub tasks, Rime playback, and speech events."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    UserStateChangedEvent,
    cli,
)

from stt_deepgram import create_stt
from stub_task_client import StubTaskManager


RIME_DIRECTORY = Path(__file__).resolve().parents[1] / "rime"
if str(RIME_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(RIME_DIRECTORY))

from events import RimePlaybackController
from tts_rime import create_rime_tts, queue_rime_speech


REQUIRED_ENVIRONMENT_VARIABLES = (
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "DEEPGRAM_API_KEY",
    "RIME_API_KEY",
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
        task_manager: StubTaskManager,
        playback_controller: RimePlaybackController,
    ) -> None:
        super().__init__(
            instructions="Transcribe user speech and play a Rime acknowledgement.",
        )
        self._task_manager = task_manager
        self._playback_controller = playback_controller

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """Create one task after the user's complete turn is committed."""
        transcript = new_message.text_content.strip()
        if not transcript:
            return

        task = self._task_manager.create_task(transcript)
        print(
            f"TASK: task_id={task.task_id} status={task.status}",
            flush=True,
        )

        response_text = (
            "I received your request. Rime audio playback is working. "
            "You can interrupt me by saying stop."
        )

        handle = queue_rime_speech(self.session, response_text)
        speech_started_event = self._playback_controller.start_playback(
            task.task_id,
            handle,
        )

        print(
            f"EVENT: {json.dumps(speech_started_event)}",
            flush=True,
        )
        print(f"RIME PLAYBACK QUEUED: task_id={task.task_id}", flush=True)

        await handle

        stopped_reason = "interrupted" if handle.interrupted else "completed"
        speech_stopped_event = self._playback_controller.finish_playback(
            task.task_id,
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
                f"RIME PLAYBACK STOPPED: task_id={task.task_id} "
                "reason=interrupted",
                flush=True,
            )
        elif handle.exception() is None:
            print(
                f"RIME PLAYBACK FINISHED: task_id={task.task_id}",
                flush=True,
            )
        else:
            print(
                f"RIME PLAYBACK FAILED: task_id={task.task_id} "
                f"error={handle.exception()}",
                flush=True,
            )


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
            "endpointing": {
                "mode": "fixed",
                "min_delay": 0.9,
                "max_delay": 3.0,
            },
            "interruption": {
                "enabled": True,
                "min_duration": 0.35,
                "min_words": 1,
                "false_interruption_timeout": 1.0,
                "resume_false_interruption": True,
            },
        },
    )

    task_manager = StubTaskManager()
    playback_controller = RimePlaybackController()

    @session.on("user_state_changed")
    def on_user_state_changed(event: UserStateChangedEvent) -> None:
        if event.new_state != "speaking":
            return

        interruption_events = playback_controller.interrupt_on_new_user_speech()
        for interruption_event in interruption_events:
            print(
                f"EVENT: {json.dumps(interruption_event)}",
                flush=True,
            )

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: object) -> None:
        if getattr(event, "is_final", False):
            transcript = getattr(event, "transcript", "").strip()
            if transcript:
                print(f"TRANSCRIPT: {transcript}", flush=True)

    await session.start(
        room=ctx.room,
        agent=ReviaVoiceAgent(task_manager, playback_controller),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)