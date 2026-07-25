"""Configuration for the Sarvam S2S SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal


@dataclass
class SarvamS2SConfig:
    """Configuration for a Speech-to-Speech session.

    Provides sensible defaults for Hindi conversation. Override as needed.
    """

    # ─── API ───────────────────────────────────────────────
    api_key: str = ""
    base_url: str = "https://api.sarvam.ai"

    # ─── STT (Speech-to-Text) ──────────────────────────────
    stt_model: str = "saaras:v3"
    stt_language: str = "hi-IN"
    stt_mode: Literal["transcribe", "translate", "verbatim", "translit", "codemix"] = "transcribe"
    stt_sample_rate: int = 16000
    stt_vad_sensitivity: bool = True
    stt_vad_signals: bool = True

    # ─── LLM ──────────────────────────────────────────────
    llm_provider: Literal["sarvam", "openai", "custom"] = "sarvam"
    llm_model: str = "sarvam-105b"  # Options: "sarvam-30b", "sarvam-105b"
    llm_api_key: str = ""  # If different from api_key (e.g. OpenAI)
    llm_base_url: str = ""  # Custom endpoint
    llm_system_prompt: str = "You are a helpful assistant. Respond concisely in the same language the user speaks."
    llm_max_tokens: int = 200  # Lower = faster response for voice
    llm_temperature: float = 0.7
    llm_stream: bool = True

    # ─── LLM Context Management ───────────────────────────
    llm_context: str = ""  # Static context injected before conversation (e.g. knowledge base, persona)
    llm_context_position: Literal["before_system", "after_system", "before_user"] = "after_system"
    llm_max_history_turns: int = 20  # Max conversation turns to keep (0 = unlimited)
    llm_max_history_tokens: int = 4000  # Approx max tokens for history (0 = unlimited)
    llm_context_retriever: Callable[[str], str] | None = None  # RAG callback: query -> context
    llm_few_shot_examples: list[dict[str, str]] = field(default_factory=list)  # Few-shot examples

    # ─── TTS (Text-to-Speech) ──────────────────────────────
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "aditya"
    tts_language: str = "hi-IN"
    tts_pace: float = 1.0
    tts_audio_codec: str = "linear16"
    tts_sample_rate: int = 16000
    tts_min_buffer_size: int = 50
    tts_max_chunk_length: int = 200

    # ─── Behavior ─────────────────────────────────────────
    enable_barge_in: bool = True
    sentence_buffer_chars: int = 50
    max_response_chars: int = 500
    idle_timeout_seconds: int = 300
    reconnect_max_attempts: int = 5
    reconnect_base_delay: float = 0.5

    # ─── Audio I/O ─────────────────────────────────────────
    input_device: int | None = None  # None = system default
    output_device: int | None = None
    audio_chunk_ms: int = 32  # 32ms chunks = 512 samples at 16kHz

    @property
    def audio_chunk_samples(self) -> int:
        """Number of samples per audio chunk."""
        return int(self.stt_sample_rate * self.audio_chunk_ms / 1000)

    @property
    def stt_ws_url(self) -> str:
        """WebSocket URL for STT streaming."""
        return "wss://api.sarvam.ai/speech-to-text/ws"

    @property
    def tts_ws_url(self) -> str:
        """WebSocket URL for TTS streaming."""
        return "wss://api.sarvam.ai/text-to-speech/ws"
