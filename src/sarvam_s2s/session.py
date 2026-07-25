"""Session orchestrator — the main entry point for the S2S SDK."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto
from typing import Any, Callable

from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.stt import STTEngine
from sarvam_s2s.engines.tts import TTSEngine
from sarvam_s2s.engines.llm import LLMEngine
from sarvam_s2s.audio.capture import AudioCapture
from sarvam_s2s.audio.player import AudioPlayer

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """State machine for the conversation session."""

    IDLE = auto()
    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()


class SarvamS2S:
    """Real-time Speech-to-Speech conversation manager.

    Usage:
        async with SarvamS2S(config) as s2s:
            await s2s.start()
            await s2s.wait_until_done()
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self.state = SessionState.IDLE
        self._conversation_history: list[dict[str, str]] = []
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []

        # Engines (initialized in __aenter__)
        self._stt: STTEngine | None = None
        self._tts: TTSEngine | None = None
        self._llm: LLMEngine | None = None
        self._capture: AudioCapture | None = None
        self._player: AudioPlayer | None = None

        # Callbacks
        self._on_transcript: Callable[[str], None] | None = None
        self._on_response: Callable[[str], None] | None = None
        self._on_state_change: Callable[[SessionState], None] | None = None

    async def __aenter__(self) -> "SarvamS2S":
        """Initialize all engines and connections."""
        self._stt = STTEngine(self.config)
        self._tts = TTSEngine(self.config)
        self._llm = LLMEngine(self.config)
        self._capture = AudioCapture(self.config)
        self._player = AudioPlayer(self.config)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        """Clean up all connections."""
        await self.stop()

    async def start(self) -> None:
        """Start the conversation session."""
        if self.state != SessionState.IDLE:
            raise RuntimeError(f"Cannot start session in state {self.state}")

        logger.info("Starting S2S session...")
        assert self._stt and self._tts and self._llm and self._capture and self._player

        # Connect STT WebSocket
        await self._stt.connect()

        # Start audio capture and processing loop
        self._set_state(SessionState.LISTENING)
        self._tasks.append(asyncio.create_task(self._audio_capture_loop()))
        self._tasks.append(asyncio.create_task(self._stt_receive_loop()))

        logger.info("S2S session started. Listening...")

    async def stop(self) -> None:
        """Stop the session and clean up."""
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._stt:
            await self._stt.disconnect()
        if self._tts:
            await self._tts.disconnect()
        if self._player:
            await self._player.stop()
        if self._capture:
            await self._capture.stop()

        self._set_state(SessionState.IDLE)
        logger.info("S2S session stopped.")

    async def wait_until_done(self) -> None:
        """Block until the session is stopped."""
        await self._stop_event.wait()

    # ─── Event Hooks ─────────────────────────────────────────

    def on_transcript(self, callback: Callable[[str], None]) -> None:
        """Register callback for when user speech is transcribed."""
        self._on_transcript = callback

    def on_response(self, callback: Callable[[str], None]) -> None:
        """Register callback for when LLM generates a response."""
        self._on_response = callback

    def on_state_change(self, callback: Callable[[SessionState], None]) -> None:
        """Register callback for state transitions."""
        self._on_state_change = callback

    # ─── Internal Loops ──────────────────────────────────────

    async def _audio_capture_loop(self) -> None:
        """Continuously capture audio from microphone and send to STT."""
        assert self._capture and self._stt
        async for chunk in self._capture.stream():
            if self._stop_event.is_set():
                break
            await self._stt.send_audio(chunk)

    async def _stt_receive_loop(self) -> None:
        """Receive transcriptions and VAD signals from STT."""
        assert self._stt
        async for event in self._stt.events():
            if self._stop_event.is_set():
                break

            if event.type == "speech_start" and self.state == SessionState.SPEAKING:
                await self._handle_barge_in()
            elif event.type == "speech_end":
                pass  # VAD detected end of speech
            elif event.type == "transcript":
                await self._handle_transcript(event.text)

    async def _handle_barge_in(self) -> None:
        """Handle user interruption during TTS playback."""
        if not self.config.enable_barge_in:
            return

        logger.info("Barge-in detected! Stopping current response.")
        assert self._player and self._tts

        # 1. Stop audio playback immediately
        await self._player.stop()

        # 2. Close TTS connection to stop generation
        await self._tts.disconnect()

        # 3. Return to listening state
        self._set_state(SessionState.LISTENING)

    async def _handle_transcript(self, text: str) -> None:
        """Process a completed transcript from STT."""
        if not text.strip():
            return

        logger.info(f"User said: {text}")
        if self._on_transcript:
            self._on_transcript(text)

        # Transition to processing
        self._set_state(SessionState.PROCESSING)

        # Generate response via LLM and stream to TTS
        await self._generate_and_speak(text)

    async def _generate_and_speak(self, user_text: str) -> None:
        """Stream LLM response sentence-by-sentence to TTS for audio output.
        
        Latency optimizations:
        - Splits on commas/semicolons too (not just periods)
        - Sends to TTS as soon as a phrase boundary is detected
        - TTS uses HTTP streaming for low TTFB
        """
        assert self._llm and self._tts and self._player

        # Connect TTS for this response
        await self._tts.connect()
        self._set_state(SessionState.SPEAKING)

        full_response = ""
        sentence_buffer = ""

        # Use internal memory-based generation
        self._llm.add_user_message(user_text)

        async for token in self._llm.generate_stream():
            # Check for barge-in
            if self.state != SessionState.SPEAKING:
                break

            full_response += token
            sentence_buffer += token

            # Send to TTS at phrase boundaries for lower latency
            if self._is_phrase_boundary(sentence_buffer):
                text_to_speak = sentence_buffer.strip()
                if text_to_speak:
                    async for audio_chunk in self._tts.synthesize_stream(text_to_speak):
                        if self.state != SessionState.SPEAKING:
                            break
                        await self._player.play_chunk(audio_chunk)
                sentence_buffer = ""

        # Flush remaining text
        if sentence_buffer.strip() and self.state == SessionState.SPEAKING:
            async for audio_chunk in self._tts.synthesize_stream(sentence_buffer.strip()):
                if self.state != SessionState.SPEAKING:
                    break
                await self._player.play_chunk(audio_chunk)

        # Save response to memory
        if full_response:
            self._llm.add_assistant_message(full_response)
            if self._on_response:
                self._on_response(full_response)

        # Return to listening
        if self.state == SessionState.SPEAKING:
            await self._tts.disconnect()
            self._set_state(SessionState.LISTENING)

    # ─── Helpers ─────────────────────────────────────────────

    def _set_state(self, new_state: SessionState) -> None:
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        if old_state != new_state:
            logger.debug(f"State: {old_state.name} → {new_state.name}")
            if self._on_state_change:
                self._on_state_change(new_state)

    @staticmethod
    def _is_sentence_boundary(text: str) -> bool:
        """Check if text ends with a sentence boundary."""
        sentence_enders = (".", "!", "?", "।", "॥", "\n")
        return text.rstrip().endswith(sentence_enders)

    @staticmethod
    def _is_phrase_boundary(text: str) -> bool:
        """Check if text ends with a phrase boundary (more aggressive splitting for low latency)."""
        phrase_enders = (".", "!", "?", "।", "॥", "\n", ",", ";", ":")
        return text.rstrip().endswith(phrase_enders) and len(text.strip()) >= 10
