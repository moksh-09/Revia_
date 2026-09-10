"""Tests for REVIA voice identity, multilingual routing, and telephony profiles."""

import pytest
from backend.orchestration.agent_brain import AgentBrain, _SYSTEM_PROMPT
from backend.rime.tts_rime import (
    create_rime_tts,
    RIME_MODEL,
    RIME_VOICE,
    RIME_LANGUAGE,
    RIME_SAMPLE_RATE,
)


def test_agent_brain_persona_and_multilingual_prompt():
    brain = AgentBrain(use_stubs=True)
    default_prompt = brain._get_system_prompt()
    assert "Writing for the Ear" in default_prompt

    # Test Concierge persona
    brain.set_persona("concierge")
    assert "Active Persona: Empathetic Concierge" in brain._get_system_prompt()

    # Test Dispatcher persona
    brain.set_persona("dispatcher")
    assert "Active Persona: Telephony Dispatcher" in brain._get_system_prompt()

    # Test Copilot persona
    brain.set_persona("copilot")
    assert "Active Persona: Technical Co-Pilot" in brain._get_system_prompt()

    # Test Multilingual
    brain.set_language("spa")
    assert "Spanish (Español)" in brain._get_system_prompt()

    brain.set_language("fra")
    assert "French (Français)" in brain._get_system_prompt()

    brain.set_language("ger")
    assert "German (Deutsch)" in brain._get_system_prompt()

    brain.set_language("hin")
    assert "Hindi" in brain._get_system_prompt()

    brain.set_language("auto")
    assert "Automatically detect" in brain._get_system_prompt()

    # Test switching from Hindi back to English enforces strict English
    brain.set_language("hin")
    assert "Hindi" in brain._get_system_prompt()
    brain.set_language("eng")
    eng_prompt = brain._get_system_prompt()
    assert "STRICT LANGUAGE ENFORCEMENT: English" in eng_prompt
    assert "switch completely, immediately, and unconditionally back to English" in eng_prompt


def test_create_rime_tts_parameterization():
    from dotenv import load_dotenv
    load_dotenv()
    # Verify default call works
    tts_default = create_rime_tts()
    assert tts_default._opts.model == RIME_MODEL
    assert tts_default._opts.speaker == RIME_VOICE
    assert tts_default.sample_rate == RIME_SAMPLE_RATE

    # Verify telephony sample rate 8000
    tts_telephony = create_rime_tts(sample_rate=8000, speed_alpha=1.15)
    assert tts_telephony.sample_rate == 8000

    # Verify multilingual
    tts_multilingual = create_rime_tts(speaker="lyra", lang="spa", speed_alpha=0.95)
    opts = tts_multilingual._opts.coda_options or tts_multilingual._opts.mist_options
    assert opts.lang == "spa"
