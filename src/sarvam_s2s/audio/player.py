"""Audio Player — Output audio with instant-stop for barge-in."""

from __future__ import annotations

import asyncio
import logging

from sarvam_s2s.config import SarvamS2SConfig

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Plays audio chunks with instant interruption support.

    Uses sounddevice for cross-platform audio output.
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self._stream: object | None = None
        self._playing = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize audio output stream."""
        import sounddevice as sd

        self._stream = sd.OutputStream(
            samplerate=self.config.tts_sample_rate,
            channels=1,
            dtype="int16",
            device=self.config.output_device,
        )
        self._stream.start()  # type: ignore
        self._playing = True
        logger.info(f"Player started: {self.config.tts_sample_rate}Hz")

    async def play_chunk(self, audio_bytes: bytes) -> None:
        """Play an audio chunk.

        Args:
            audio_bytes: Raw PCM audio (16-bit, mono)
        """
        if not self._playing:
            await self.start()
        if not self._stream:
            return
        import numpy as np

        audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
        self._stream.write(audio_array)  # type: ignore

    async def stop(self) -> None:
        """Immediately stop playback (for barge-in)."""
        async with self._lock:
            if self._stream:
                try:
                    self._stream.stop()  # type: ignore
                    self._stream.close()  # type: ignore
                except Exception:
                    pass
                self._stream = None
            self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing
