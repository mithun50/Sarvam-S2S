"""Audio Capture — Microphone input with async streaming."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from sarvam_s2s.config import SarvamS2SConfig

logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures audio from microphone and yields chunks asynchronously.

    Output: 16-bit PCM, mono, at configured sample rate.
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._stream: object | None = None
        self._running = False

    async def start(self) -> None:
        """Start audio capture from microphone."""
        import sounddevice as sd
        import numpy as np

        self._running = True

        def _callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")
            if self._running:
                pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
                try:
                    self._queue.put_nowait(pcm)
                except asyncio.QueueFull:
                    pass

        self._stream = sd.InputStream(
            samplerate=self.config.stt_sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self.config.audio_chunk_samples,
            device=self.config.input_device,
            callback=_callback,
        )
        self._stream.start()  # type: ignore
        logger.info(f"Capture started: {self.config.stt_sample_rate}Hz")

    async def stop(self) -> None:
        """Stop audio capture."""
        self._running = False
        if self._stream:
            self._stream.stop()  # type: ignore
            self._stream.close()  # type: ignore
            self._stream = None

    async def stream(self) -> AsyncIterator[bytes]:
        """Yield audio chunks as captured.

        Yields:
            bytes: Raw PCM audio (16-bit, mono)
        """
        if not self._running:
            await self.start()

        while self._running:
            try:
                chunk = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield chunk
            except asyncio.TimeoutError:
                continue
