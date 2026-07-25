"""
Web Demo — Browser-based Speech-to-Speech
==========================================
A FastAPI server that serves a web UI for testing the S2S pipeline.
Uses browser's Web Speech API or MediaRecorder for audio capture,
sends to server which runs STT -> LLM -> TTS and streams audio back.

Usage:
    pip install fastapi uvicorn python-dotenv
    python -m demos.web_demo.server
    Open http://localhost:8000
"""

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.llm import LLMEngine
from sarvam_s2s.engines.tts import TTSEngine

app = FastAPI(title="Sarvam S2S Web Demo")

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/")
async def index():
    """Serve the main web UI."""
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/config")
async def get_config():
    """Return available voices and languages."""
    return {
        "languages": [
            {"code": "hi-IN", "name": "Hindi"},
            {"code": "en-IN", "name": "English (Indian)"},
            {"code": "ta-IN", "name": "Tamil"},
            {"code": "te-IN", "name": "Telugu"},
            {"code": "kn-IN", "name": "Kannada"},
            {"code": "bn-IN", "name": "Bengali"},
            {"code": "ml-IN", "name": "Malayalam"},
            {"code": "mr-IN", "name": "Marathi"},
            {"code": "gu-IN", "name": "Gujarati"},
        ],
        "speakers": [
            {"id": "aditya", "name": "Aditya (Male)"},
            {"id": "priya", "name": "Priya (Female)"},
            {"id": "kavitha", "name": "Kavitha (Female)"},
            {"id": "anushka", "name": "Anushka (Female)"},
            {"id": "rahul", "name": "Rahul (Male)"},
            {"id": "neha", "name": "Neha (Female)"},
            {"id": "karun", "name": "Karun (Male)"},
            {"id": "hitesh", "name": "Hitesh (Male)"},
        ],
    }


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat.
    
    Protocol:
    - Client sends: {"type": "text", "text": "...", "language": "hi-IN", "speaker": "aditya"}
    - Server responds: {"type": "response", "text": "...", "audio": "<base64>"}
    """
    await websocket.accept()

    api_key = os.environ.get("SARVAM_API_KEY", "")
    if not api_key:
        await websocket.send_json({"type": "error", "message": "SARVAM_API_KEY not set"})
        await websocket.close()
        return

    # Create LLM engine with session memory
    config = SarvamS2SConfig(
        api_key=api_key,
        llm_system_prompt="You are a helpful assistant. Respond concisely in the same language the user speaks. Keep responses to 1-2 sentences.",
        llm_max_history_turns=20,
        llm_model="sarvam-105b",
        llm_max_tokens=200,
    )
    llm = LLMEngine(config)

    try:
        while True:
            data = await websocket.receive_json()

            if data["type"] == "text":
                user_text = data.get("text", "")
                language = data.get("language", "hi-IN")
                speaker = data.get("speaker", "aditya")
                context = data.get("context", "")

                if not user_text:
                    continue

                # Update config for this request
                config.tts_language = language
                config.tts_speaker = speaker
                if context:
                    config.llm_context = context

                # Add user message to memory
                llm.add_user_message(user_text)

                # Stream LLM response
                full_response = ""
                await websocket.send_json({"type": "stream_start"})

                try:
                    async for token in llm.generate_stream():
                        full_response += token
                        await websocket.send_json({
                            "type": "token",
                            "token": token,
                        })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"LLM error: {str(e)}",
                    })
                    continue

                # Save to memory
                llm.add_assistant_message(full_response)

                # Generate TTS audio
                try:
                    audio_data = await generate_tts_audio(
                        full_response, language, speaker, api_key
                    )
                    await websocket.send_json({
                        "type": "response_complete",
                        "text": full_response,
                        "audio": audio_data,
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "response_complete",
                        "text": full_response,
                        "audio": None,
                        "tts_error": str(e),
                    })

            elif data["type"] == "clear":
                llm.clear_history()
                await websocket.send_json({"type": "cleared"})

    except WebSocketDisconnect:
        pass


async def generate_tts_audio(text: str, language: str, speaker: str, api_key: str) -> str | None:
    """Generate TTS audio using Sarvam REST API (simpler for web demo)."""
    import httpx

    url = "https://api.sarvam.ai/text-to-speech"
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": [text],
        "target_language_code": language,
        "speaker": speaker,
        "model": "bulbul:v3",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        # Returns base64 wav audio
        audios = result.get("audios", [])
        if audios:
            return audios[0]
    return None


if __name__ == "__main__":
    import uvicorn
    print("\n  🚀 Starting Sarvam S2S Web Demo...")
    print("  Open http://localhost:8000 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
