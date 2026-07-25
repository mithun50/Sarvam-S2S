"""Run the Sarvam S2S Web Demo server — Real-time streaming with interrupt."""

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR / "src"))
os.chdir(ROOT_DIR)

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

import asyncio
import base64
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.llm import LLMEngine

app = FastAPI(title="Sarvam S2S Web Demo")
STATIC_DIR = ROOT_DIR / "demos" / "web_demo" / "static"

SENTENCE_ENDERS = (".", "!", "?", "\n", ",", ";", ":")


@app.get("/")
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health():
    api_key = os.environ.get("SARVAM_API_KEY", "")
    return {"status": "ok", "api_key_set": bool(api_key)}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """Real-time chat with interrupt support."""
    await websocket.accept()

    api_key = os.environ.get("SARVAM_API_KEY", "")
    if not api_key:
        await websocket.send_json({"type": "error", "message": "SARVAM_API_KEY not set"})
        await websocket.close()
        return

    config = SarvamS2SConfig(
        api_key=api_key,
        llm_system_prompt=(
            "You are a helpful voice assistant. Respond concisely in English. "
            "Keep responses to 1-2 sentences max. Be natural and conversational."
        ),
        llm_model="sarvam-105b",
        llm_max_tokens=200,
        llm_max_history_turns=20,
        stt_language="en-IN",
        tts_language="en-IN",
        tts_speaker="aditya",
    )
    llm = LLMEngine(config)
    interrupted = False  # Flag to cancel current generation

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "text":
                user_text = data.get("text", "").strip()
                language = data.get("language", "en-IN")
                speaker = data.get("speaker", "aditya")
                context = data.get("context", "")
                system_prompt = data.get("system_prompt", "")

                if not user_text:
                    continue

                if context:
                    config.llm_context = context
                if system_prompt:
                    config.llm_system_prompt = system_prompt
                config.tts_language = language
                config.tts_speaker = speaker

                llm.add_user_message(user_text)
                interrupted = False

                # Stream response with interrupt checking
                full_response = ""
                sentence_buffer = ""
                await websocket.send_json({"type": "stream_start"})

                try:
                    async for token in llm.generate_stream():
                        # Check for interrupt between tokens
                        if interrupted:
                            break

                        # Check if client sent an interrupt
                        try:
                            # Non-blocking check for incoming messages
                            msg = await asyncio.wait_for(
                                websocket.receive_json(), timeout=0.001
                            )
                            if msg.get("type") == "interrupt":
                                interrupted = True
                                break
                            elif msg.get("type") == "text":
                                # New message while generating = interrupt + new request
                                interrupted = True
                                # Put it back by processing after break
                                data = msg
                                break
                        except asyncio.TimeoutError:
                            pass  # No message waiting, continue generating

                        full_response += token
                        sentence_buffer += token
                        await websocket.send_json({"type": "token", "token": token})

                        # TTS per sentence
                        if sentence_buffer.rstrip().endswith(SENTENCE_ENDERS) and len(sentence_buffer.strip()) >= 8:
                            sentence = sentence_buffer.strip()
                            audio_b64 = await _generate_tts(sentence, language, speaker, api_key)
                            if audio_b64 and not interrupted:
                                await websocket.send_json({"type": "audio_chunk", "audio": audio_b64})
                            sentence_buffer = ""

                except Exception as e:
                    if not interrupted:
                        await websocket.send_json({"type": "error", "message": f"LLM error: {str(e)}"})
                    if llm.memory._history and llm.memory._history[-1]["role"] == "user":
                        llm.memory._history.pop()
                    continue

                if interrupted:
                    # Discard partial response, don't save to memory
                    if llm.memory._history and llm.memory._history[-1]["role"] == "user":
                        llm.memory._history.pop()
                    await websocket.send_json({"type": "response_complete", "text": "[interrupted]"})
                    # If we got a new text message during interrupt, process it
                    if data.get("type") == "text" and data.get("text", "").strip():
                        # Loop will handle it on next iteration
                        continue
                    continue

                # Flush remaining
                if sentence_buffer.strip():
                    audio_b64 = await _generate_tts(sentence_buffer.strip(), language, speaker, api_key)
                    if audio_b64:
                        await websocket.send_json({"type": "audio_chunk", "audio": audio_b64})

                llm.add_assistant_message(full_response)
                await websocket.send_json({"type": "response_complete", "text": full_response})

            elif data["type"] == "interrupt":
                interrupted = True

            elif data["type"] == "clear":
                llm.clear_history()
                await websocket.send_json({"type": "cleared"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


async def _generate_tts(text: str, language: str, speaker: str, api_key: str) -> str | None:
    """Generate TTS audio via Sarvam HTTP Streaming API."""
    import httpx

    if not text.strip():
        return None

    try:
        # Try streaming endpoint first
        url = "https://api.sarvam.ai/text-to-speech/stream"
        headers = {"api-subscription-key": api_key, "Content-Type": "application/json"}
        payload = {
            "input": text[:2500],
            "target_language_code": language,
            "speaker": speaker,
            "model": "bulbul:v3",
        }
        audio_bytes = bytearray()
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    return await _tts_rest(text, language, speaker, api_key)
                async for chunk in resp.aiter_bytes():
                    audio_bytes.extend(chunk)

        if audio_bytes:
            return base64.b64encode(bytes(audio_bytes)).decode("utf-8")
        return None
    except Exception:
        return await _tts_rest(text, language, speaker, api_key)


async def _tts_rest(text: str, language: str, speaker: str, api_key: str) -> str | None:
    """Fallback REST TTS."""
    import httpx

    try:
        url = "https://api.sarvam.ai/text-to-speech"
        headers = {"api-subscription-key": api_key, "Content-Type": "application/json"}
        payload = {"inputs": [text[:2500]], "target_language_code": language, "speaker": speaker, "model": "bulbul:v3"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            audios = resp.json().get("audios", [])
            return audios[0] if audios else None
    except Exception:
        return None


if __name__ == "__main__":
    import uvicorn
    print()
    print("=" * 50)
    print("  Sarvam S2S Web Demo")
    print("=" * 50)
    has_key = bool(os.environ.get("SARVAM_API_KEY"))
    print(f"  API Key: {'SET' if has_key else 'NOT SET'}")
    print("  Open: http://localhost:8000")
    print("=" * 50)
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
