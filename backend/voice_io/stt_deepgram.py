"""Deepgram STT configuration for the REVIA LiveKit agent."""

import os

from livekit.plugins import deepgram


def create_stt() -> deepgram.STT:
    """Create the realtime Deepgram recognizer used for user speech."""
    if not os.getenv("DEEPGRAM_API_KEY"):
        raise RuntimeError("DEEPGRAM_API_KEY is required in .env")

    return deepgram.STT(
        model="nova-3",
        language="en",
    )