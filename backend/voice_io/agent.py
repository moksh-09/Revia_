"""LiveKit STT agent with stub tasks, Rime playback, and speech events."""

import asyncio
import json
import os
import sys
import logging
from pathlib import Path
from typing import Any, Optional

# Configure robust UTF-8 logging for Windows environments
sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from livekit import rtc
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


async def _publish_event(room, event_dict: dict) -> None:
    """
    Publish a task/speech event over the LiveKit data channel.
    This is a minimal, additive bridge — purely for browser observability.
    Backend task authority and fence logic remain unchanged.
    """
    try:
        await room.local_participant.publish_data(
            json.dumps(event_dict).encode(),
            reliable=True,
        )
    except Exception as exc:
        logger.warning("data channel publish failed: %s", exc)


class ReviaVoiceAgent(Agent):
    """Creates tasks and manages Rime speech lifecycle events."""

    def __init__(
        self,
        brain: AgentBrain,
        playback_controller: RimePlaybackController,
        room: Any = None,
    ) -> None:
        super().__init__(
            instructions="Transcribe user speech and play a Rime acknowledgement.",
        )
        self._brain = brain
        self._playback_controller = playback_controller
        self._room = room
        self._session_closed = False

    def set_room(self, room: Any) -> None:
        self._room = room

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

        # Publish llm.response_drafted to data channel for frontend conversation
        target_room = self._room or getattr(session, "_room", None)
        if target_room is not None:
            asyncio.create_task(_publish_event(target_room, {
                "event": "llm.response_drafted",
                "task_id": result.task_id,
                "fence_token": result.fence_token,
                "response_text": response_text,
            }))

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

        if hasattr(self._brain.task_client, "start_speaking"):
            self._brain.task_client.start_speaking(
                result.task_id,
                speech_started_event.get("speech_id", ""),
            )

        print(
            f"EVENT: {json.dumps(speech_started_event)}",
            flush=True,
        )
        print(f"RIME PLAYBACK QUEUED: task_id={result.task_id}", flush=True)
        if target_room is not None:
            asyncio.create_task(_publish_event(target_room, speech_started_event))

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
            if target_room is not None:
                asyncio.create_task(_publish_event(target_room, speech_stopped_event))

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
                # Tight min_delay so interruption is detected fast (~150 ms after speech)
                "min_delay": 0.15,
                "max_delay": 1.2,
            },
            "interruption": {
                # Let LiveKit also interrupt natively — this is the fastest path.
                # Our _interrupt_playback() also fires on user_input_transcribed as
                # a belt-and-suspenders safety net.
                "enabled": True,
                "discard_audio_if_uninterruptible": True,
                "min_duration": 0.2,
                "min_words": 1,
                "false_interruption_timeout": 0.3,
                "resume_false_interruption": False,
            },
        },
    )

    brain = AgentBrain()
    playback_controller = RimePlaybackController()

    agent_instance = ReviaVoiceAgent(brain, playback_controller, room=ctx.room)

    # Wire TaskManager timeline → data channel for browser observability.
    # Flatten timeline events so the frontend receives them with top-level event name and payload fields.
    def _on_task_event(event: dict) -> None:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        flat_event = {
            "event": event.get("event_name") or event.get("event"),
            "task_id": event.get("task_id"),
            "timestamp": event.get("timestamp"),
            **payload,
        }
        asyncio.create_task(_publish_event(ctx.room, flat_event))

    brain.task_client.on_event(_on_task_event)

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket) -> None:
        try:
            raw = json.loads(data_packet.data.decode("utf-8"))
            if raw.get("event") == "config.update":
                persona = raw.get("persona", "signature")
                language = raw.get("language", "eng")
                speed_alpha = float(raw.get("speed_alpha", 1.0))
                telephony = bool(raw.get("telephony_mode", False))

                brain.set_persona(persona)
                brain.set_language(language)

                rime_model = "mistv2" if persona == "concierge" else "coda"
                rime_voice = "cove" if persona == "concierge" else "lyra"
                rime_lang = "eng"
                stt_lang = "multi"
                if language in ("eng", "en"):
                    rime_lang = "eng"
                    stt_lang = "en"
                elif language in ("spa", "es"):
                    rime_lang = "spa"
                    stt_lang = "es"
                elif language in ("fra", "fr"):
                    rime_lang = "fra"
                    stt_lang = "fr"
                elif language in ("ger", "de"):
                    rime_lang = "ger"
                    stt_lang = "de"
                elif language in ("hin", "hi"):
                    rime_lang = "hin"
                    stt_lang = "hi"
                elif language == "auto":
                    stt_lang = "multi"

                sample_rate = 8000 if telephony else 16000

                new_tts = create_rime_tts(
                    model=rime_model,
                    speaker=rime_voice,
                    lang=rime_lang,
                    sample_rate=sample_rate,
                    speed_alpha=speed_alpha,
                )
                session._tts = new_tts
                session._stt = create_stt(language=stt_lang)

                # Flush any audio still buffered from the previous language/TTS instance
                # so we don't get English words bleeding out after a language switch.
                try:
                    session.interrupt(force=True)
                except Exception as exc:
                    logger.debug("TTS language switch flush: %s", exc)
                if hasattr(session, "output") and getattr(session.output, "audio", None):
                    try:
                        session.output.audio.clear_buffer()
                    except Exception:
                        pass

                ack_event = {
                    "event": "config.applied",
                    "persona": persona,
                    "language": language,
                    "speed_alpha": speed_alpha,
                    "telephony_mode": telephony,
                    "rime_model": rime_model,
                    "rime_voice": rime_voice,
                    "sample_rate": sample_rate,
                }
                asyncio.create_task(_publish_event(ctx.room, ack_event))
                logger.info("Config applied: %s", ack_event)
        except Exception as exc:
            logger.warning("Failed to apply config.update: %s", exc)

    def _interrupt_playback() -> None:
        if not _has_active_rime_playback(playback_controller):
            return
        # No elapsed-time guard — interrupt immediately as soon as the user speaks.
        brain.task_client.obsolete_active_task()
        interruption_events = playback_controller.interrupt_on_new_user_speech()
        for interruption_event in interruption_events:
            print(f"EVENT: {json.dumps(interruption_event)}", flush=True)
            asyncio.create_task(_publish_event(ctx.room, interruption_event))
        try:
            session.interrupt(force=True)
        except Exception as exc:
            logger.debug("session.interrupt: %s", exc)
        if hasattr(session, "output") and getattr(session.output, "audio", None):
            try:
                session.output.audio.clear_buffer()
            except Exception:
                pass

    @session.on("close")
    def on_session_closed(_event: object) -> None:
        agent_instance.mark_session_closed()
        try:
            ctx.shutdown(reason="session closed")
        except Exception as exc:
            logger.debug("ctx.shutdown error: %s", exc)


    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: object) -> None:
        # Extract transcript and final flag
        is_final = getattr(event, "is_final", False)
        transcript = getattr(event, "transcript", "").strip()
        if not transcript:
            return

        # Publish interim transcript to browser so user sees live captions.
        # Do NOT call _interrupt_playback() here — LiveKit's own VAD
        # (interruption.enabled=True) already handles the fast-path interrupt.
        # Calling it on every partial word causes triple-interrupt collisions.
        if not is_final:
            asyncio.create_task(_publish_event(ctx.room, {
                "event": "transcript",
                "transcript": transcript,
                "is_final": False,
            }))

        # For final transcripts, interrupt as a safety net (belt-and-suspenders)
        # then forward the completed utterance to the agent brain.
        if is_final:
            _interrupt_playback()
            print(f"TRANSCRIPT: {transcript}", flush=True)
            # Also publish final transcript to browser
            asyncio.create_task(_publish_event(ctx.room, {
                "event": "transcript",
                "transcript": transcript,
                "is_final": True,
            }))
            asyncio.create_task(agent_instance.process_transcript(transcript, session))

    await session.start(
        room=ctx.room,
        agent=agent_instance,
        room_options=RoomOptions(text_input=False),
    )
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
