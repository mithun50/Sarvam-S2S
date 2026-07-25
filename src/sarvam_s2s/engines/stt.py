"""STT Engine — Manages Sarvam Speech-to-Text WebSocket streaming."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from sarvam_s2s.config import SarvamS2SConfig

logger = logging.getLogger(__name__)


@dataclass
class STTEvent:
    """Event from the STT engine."""

    type: str  # "speech_start" | "speech_end" | "transcript"
    text: str = ""


class STTEngine:
    """Manages a persistent WebSocket connection to Sarvam STT API.

    Streams audio in, receives VAD events and transcripts out.
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self._ws: object | None = None
        self._event_queue: asyncio.Queue[STTEvent] = asyncio.Queue()
        self._connected = False
        self._receive_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Open WebSocket connection to Sarvam STT."""
        import websockets

        params = {
            "model": self.config.stt_model,
            "language_code": self.config.stt_language,
            "mode": self.config.stt_mode,
            "sample_rate": str(self.config.stt_sample_rate),
            "high_vad_sensitivity": str(self.config.stt_vad_sensitivity).lower(),
            "vad_signals": str(self.config.stt_vad_signals).lower(),
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.config.stt_ws_url}?{query}"
        headers = {"api-subscription-key": self.config.api_key}

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info(f"STT connected: lang={self.config.stt_language}")

    async def disconnect(self) -> None:
        """Close the STT WebSocket."""
        self._connected = False
        if self._receive_task:
            self._receive_task.cancel()
            self._receive_task = None
        if self._ws:
            await self._ws.close()  # type: ignore
            self._ws = None

    async def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk to STT."""
        if not self._ws or not self._connected:
            return
        message = json.dumps({
            "type": "audio",
            "data": {
                "audio": base64.b64encode(chunk).decode("utf-8"),
                "encoding": "audio/wav",
                "sample_rate": self.config.stt_sample_rate,
            },
        })
        await self._ws.send(message)  # type: ignore

    async def flush(self) -> None:
        """Send flush signal for immediate processing."""
        if not self._ws or not self._connected:
            return
        await self._ws.send(json.dumps({"type": "flush"}))  # type: ignore

    async def events(self) -> AsyncIterator[STTEvent]:
        """Yield STT events as they arrive."""
        while self._connected:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue

    async def _receive_loop(self) -> None:
        """Receive messages from STT WebSocket."""
        assert self._ws
        try:
            async for raw_message in self._ws:  # type: ignore
                if not self._connected:
                    break
                try:
                    message = json.loads(raw_message)
                    event = self._parse_message(message)
                    if event:
                        await self._event_queue.put(event)
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            if self._connected:
                logger.error(f"STT receive error: {e}")

    def _parse_message(self, message: dict) -> STTEvent | None:
        """Parse WebSocket message into an STTEvent."""
        msg_type = message.get("type", "")
        if msg_type == "events":
            signal = message.get("data", {}).get("signal_type", "")
            if signal == "START_SPEECH":
                return STTEvent(type="speech_start")
            elif signal == "END_SPEECH":
                return STTEvent(type="speech_end")
        elif msg_type == "data":
            transcript = message.get("data", {}).get("transcript", "")
            if transcript:
                return STTEvent(type="transcript", text=transcript)
        return None
