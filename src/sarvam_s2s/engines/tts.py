"""TTS Engine — Sarvam Text-to-Speech with multiple transport options."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator

from sarvam_s2s.config import SarvamS2SConfig

logger = logging.getLogger(__name__)


class TTSEngine:
    """Sarvam TTS engine with WebSocket, HTTP Streaming, and REST fallback.

    Priority order for lowest latency:
    1. WebSocket (persistent connection, lowest TTFB for multi-sentence)
    2. HTTP Streaming (low TTFB, simpler setup)
    3. REST (highest latency, most reliable fallback)
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self._ws: object | None = None
        self._connected = False

    # ─── WebSocket Mode ─────────────────────────────────

    async def connect(self) -> None:
        """Open WebSocket connection and send config."""
        try:
            import websockets

            url = (
                f"{self.config.tts_ws_url}"
                f"?model={self.config.tts_model}"
                f"&send_completion_event=true"
            )
            headers = {"api-subscription-key": self.config.api_key}
            self._ws = await websockets.connect(url, additional_headers=headers)
            self._connected = True

            config_msg = json.dumps({
                "type": "config",
                "data": {
                    "speaker": self.config.tts_speaker,
                    "target_language_code": self.config.tts_language,
                    "pace": self.config.tts_pace,
                    "min_buffer_size": self.config.tts_min_buffer_size,
                    "max_chunk_length": self.config.tts_max_chunk_length,
                    "output_audio_codec": self.config.tts_audio_codec,
                },
            })
            await self._ws.send(config_msg)  # type: ignore
            logger.info(f"TTS WebSocket connected: speaker={self.config.tts_speaker}")
        except Exception as e:
            logger.warning(f"TTS WebSocket connect failed: {e}, will use HTTP streaming")
            self._connected = False

    async def disconnect(self) -> None:
        """Close the TTS WebSocket."""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()  # type: ignore
            except Exception:
                pass
            self._ws = None

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text to audio chunks. Uses best available transport.

        Args:
            text: Text to synthesize

        Yields:
            Raw audio bytes
        """
        if not text.strip():
            return

        if self._ws and self._connected:
            async for chunk in self._ws_synthesize(text):
                yield chunk
        else:
            async for chunk in self._http_stream_synthesize(text):
                yield chunk

    async def _ws_synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize via WebSocket (lowest latency for multi-turn)."""
        if not self._ws or not self._connected:
            return

        text_msg = json.dumps({"type": "text", "data": {"text": text}})
        await self._ws.send(text_msg)  # type: ignore

        flush_msg = json.dumps({"type": "flush"})
        await self._ws.send(flush_msg)  # type: ignore

        while self._connected:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=5.0)  # type: ignore
                message = json.loads(raw)

                if message.get("type") == "audio":
                    audio_b64 = message.get("data", {}).get("audio", "")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                elif message.get("type") == "event":
                    if message.get("data", {}).get("event_type") == "final":
                        break
            except asyncio.TimeoutError:
                break
            except Exception as e:
                if self._connected:
                    logger.error(f"TTS WS error: {e}")
                break

    # ─── HTTP Streaming Mode (lower latency than REST) ──

    async def _http_stream_synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize via HTTP Streaming endpoint."""
        import httpx

        url = "https://api.sarvam.ai/text-to-speech/stream"
        headers = {
            "api-subscription-key": self.config.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "input": text[:2500],
            "target_language_code": self.config.tts_language,
            "speaker": self.config.tts_speaker,
            "model": self.config.tts_model,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        # Fallback to REST
                        async for chunk in self._rest_synthesize(text):
                            yield chunk
                        return
                    async for chunk in resp.aiter_bytes():
                        if chunk:
                            yield chunk
        except Exception as e:
            logger.warning(f"TTS HTTP stream error: {e}, falling back to REST")
            async for chunk in self._rest_synthesize(text):
                yield chunk

    # ─── REST Fallback ──────────────────────────────────

    async def _rest_synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize via REST API (highest latency, most reliable)."""
        import httpx

        url = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "api-subscription-key": self.config.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": [text[:2500]],
            "target_language_code": self.config.tts_language,
            "speaker": self.config.tts_speaker,
            "model": self.config.tts_model,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()
                audios = result.get("audios", [])
                if audios:
                    yield base64.b64decode(audios[0])
        except Exception as e:
            logger.error(f"TTS REST error: {e}")

    # ─── One-shot helper (for simple use cases) ─────────

    async def synthesize(self, text: str) -> bytes | None:
        """Synthesize text and return full audio bytes (non-streaming)."""
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)
        return b"".join(chunks) if chunks else None
