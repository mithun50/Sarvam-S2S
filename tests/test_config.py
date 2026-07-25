"""Basic tests for the Sarvam S2S SDK."""

import pytest
from sarvam_s2s.config import SarvamS2SConfig


def test_default_config():
    """Test that default config has sensible values."""
    config = SarvamS2SConfig(api_key="test-key")
    assert config.stt_model == "saaras:v3"
    assert config.tts_model == "bulbul:v3"
    assert config.llm_model == "sarvam-105b"
    assert config.tts_speaker == "aditya"
    assert config.llm_max_tokens == 200
    assert config.stt_language == "hi-IN"
    assert config.enable_barge_in is True
    assert config.audio_chunk_samples == 512  # 32ms at 16kHz


def test_audio_chunk_samples():
    """Test audio chunk calculation."""
    config = SarvamS2SConfig(api_key="test", stt_sample_rate=8000, audio_chunk_ms=64)
    assert config.audio_chunk_samples == 512  # 8000 * 64 / 1000


def test_ws_urls():
    """Test WebSocket URL generation."""
    config = SarvamS2SConfig(api_key="test")
    assert "speech-to-text/ws" in config.stt_ws_url
    assert "text-to-speech/ws" in config.tts_ws_url


def test_custom_llm_provider():
    """Test custom LLM provider configuration."""
    config = SarvamS2SConfig(
        api_key="test",
        llm_provider="custom",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_api_key="gsk_test",
        llm_model="llama-3.1-70b-versatile",
    )
    assert config.llm_provider == "custom"
    assert config.llm_base_url == "https://api.groq.com/openai/v1"
