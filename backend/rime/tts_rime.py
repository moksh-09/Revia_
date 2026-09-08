"""Locked Rime TTS configuration and LiveKit playback for REVIA."""

import asyncio
import os

from dotenv import load_dotenv
from livekit.agents import AgentSession
from livekit.agents.utils import http_context
from livekit.plugins import rime


RIME_MODEL = "coda"
RIME_VOICE = "lyra"
RIME_LANGUAGE = "eng"
RIME_BASE_URL = "wss://users-ws.rime.ai"
RIME_ENDPOINT = f"{RIME_BASE_URL}/ws3"
RIME_AUDIO_FORMAT = "pcm"
RIME_SAMPLE_RATE = 16000


def create_rime_tts() -> rime.TTS:
    """Create Rime TTS with REVIA's frozen configuration."""
    if not os.getenv("RIME_API_KEY"):
        raise RuntimeError("RIME_API_KEY is required in .env")

    return rime.TTS(
        base_url=RIME_BASE_URL,
        model=RIME_MODEL,
        speaker=RIME_VOICE,
        lang=RIME_LANGUAGE,
        sample_rate=RIME_SAMPLE_RATE,
        use_websocket=True,
    )


def queue_rime_speech(session: AgentSession, text: str):
    """Queue Rime-generated speech for playback in the active LiveKit room."""
    return session.say(
        text,
        allow_interruptions=False,
        add_to_chat_ctx=False,
    )


async def verify_rime_synthesis() -> None:
    """Make one real Rime request and verify PCM audio frames are returned."""
    frame_count = 0
    byte_count = 0

    async with http_context.open():
        tts = create_rime_tts()

        try:
            async with tts.stream() as stream:
                stream.push_text("REVIA Rime configuration verification.")
                stream.end_input()

                async for event in stream:
                    frame_count += 1
                    byte_count += len(event.frame.data)
        finally:
            await tts.aclose()

    if frame_count == 0 or byte_count == 0:
        raise RuntimeError("Rime returned no PCM audio frames.")

    print(
        "RIME VERIFIED: "
        f"model={RIME_MODEL} voice={RIME_VOICE} "
        f"endpoint={RIME_ENDPOINT} format={RIME_AUDIO_FORMAT} "
        f"sample_rate={RIME_SAMPLE_RATE} frames={frame_count} bytes={byte_count}"
    )


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(verify_rime_synthesis())