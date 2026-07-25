---
layout: default
title: API Reference
---

[Home](index.html) | [Architecture](ARCHITECTURE.html) | [API Reference](API.html) | [Latency Guide](LATENCY.html)

---

# API Reference

## SarvamS2S

The main entry point for the Speech-to-Speech SDK. Manages the full conversation lifecycle.

```python
from sarvam_s2s import SarvamS2S, SarvamS2SConfig
```

### Constructor

```python
SarvamS2S(config: SarvamS2SConfig)
```

### Context Manager

```python
async with SarvamS2S(config) as s2s:
    await s2s.start()
    await s2s.wait_until_done()
```

### Methods

| Method | Description |
|--------|-------------|
| `await start()` | Start the conversation (connects STT, begins mic capture) |
| `await stop()` | Stop the session, close all connections |
| `await wait_until_done()` | Block until session ends |
| `on_transcript(callback)` | Register callback for user speech transcription |
| `on_response(callback)` | Register callback for AI response text |
| `on_state_change(callback)` | Register callback for state transitions |

### States

```python
from sarvam_s2s.session import SessionState

SessionState.IDLE        # Not started or stopped
SessionState.LISTENING   # Mic active, waiting for speech
SessionState.PROCESSING  # LLM generating response
SessionState.SPEAKING    # TTS playing audio
```

---

## SarvamS2SConfig

Configuration dataclass with all SDK options.

```python
from sarvam_s2s import SarvamS2SConfig
```

### API Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `""` | Sarvam API key (required) |
| `base_url` | `str` | `"https://api.sarvam.ai"` | Sarvam API base URL |

### STT (Speech-to-Text)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stt_model` | `str` | `"saaras:v3"` | STT model |
| `stt_language` | `str` | `"hi-IN"` | Input language code |
| `stt_mode` | `str` | `"transcribe"` | Mode: transcribe, translate, verbatim, translit, codemix |
| `stt_sample_rate` | `int` | `16000` | Audio sample rate (16000 or 8000) |
| `stt_vad_sensitivity` | `bool` | `True` | High VAD sensitivity (~64ms silence boundary) |
| `stt_vad_signals` | `bool` | `True` | Emit speech_start/speech_end events |

### LLM

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `llm_provider` | `str` | `"sarvam"` | Provider: sarvam, openai, custom |
| `llm_model` | `str` | `"sarvam-105b"` | Model ID |
| `llm_api_key` | `str` | `""` | Separate key for non-Sarvam LLMs |
| `llm_base_url` | `str` | `""` | Custom endpoint URL |
| `llm_system_prompt` | `str` | (helpful assistant) | System prompt |
| `llm_max_tokens` | `int` | `200` | Max output tokens |
| `llm_temperature` | `float` | `0.7` | Sampling temperature |
| `llm_stream` | `bool` | `True` | Enable streaming |

### LLM Context Management

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `llm_context` | `str` | `""` | Static context (knowledge base, persona) |
| `llm_context_position` | `str` | `"after_system"` | Where to inject: before_system, after_system, before_user |
| `llm_max_history_turns` | `int` | `20` | Max conversation turns to keep |
| `llm_max_history_tokens` | `int` | `4000` | Approx max tokens for history |
| `llm_context_retriever` | `Callable` | `None` | RAG callback: `(query: str) -> str` |
| `llm_few_shot_examples` | `list` | `[]` | Few-shot example messages |

### TTS (Text-to-Speech)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tts_model` | `str` | `"bulbul:v3"` | TTS model |
| `tts_speaker` | `str` | `"aditya"` | Voice speaker |
| `tts_language` | `str` | `"hi-IN"` | Output language |
| `tts_pace` | `float` | `1.0` | Speaking speed |
| `tts_audio_codec` | `str` | `"linear16"` | Audio format |
| `tts_sample_rate` | `int` | `16000` | Output sample rate |
| `tts_min_buffer_size` | `int` | `50` | Min chars before TTS flush |
| `tts_max_chunk_length` | `int` | `200` | Max sentence split length |

### Behavior

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_barge_in` | `bool` | `True` | Allow user interruptions |
| `sentence_buffer_chars` | `int` | `50` | Chars before sending to TTS |
| `max_response_chars` | `int` | `500` | Max response length |
| `idle_timeout_seconds` | `int` | `300` | Session timeout |
| `reconnect_max_attempts` | `int` | `5` | Max reconnection attempts |
| `reconnect_base_delay` | `float` | `0.5` | Base delay for exponential backoff |

### Audio I/O

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `input_device` | `int\|None` | `None` | Mic device (None = default) |
| `output_device` | `int\|None` | `None` | Speaker device (None = default) |
| `audio_chunk_ms` | `int` | `32` | Chunk size in ms |

### Available TTS Speakers

```
aditya, priya, rahul, neha, anushka, kavitha, karun, hitesh,
ritu, rohan, simran, kavya, amit, dev, ishita, shreya,
abhilash, manisha, vidya, arya, pooja, ratan, varun, manan,
sumit, roopa, kabir, aayan, ashutosh, advait, anand, tanya,
tarun, sunny, mani, gokul, vijay, shruti, suhani, mohit, rehan, soham, rupali
```

### Supported Languages

| Language | Code |
|----------|------|
| Hindi | `hi-IN` |
| English (Indian) | `en-IN` |
| Bengali | `bn-IN` |
| Tamil | `ta-IN` |
| Telugu | `te-IN` |
| Kannada | `kn-IN` |
| Malayalam | `ml-IN` |
| Marathi | `mr-IN` |
| Gujarati | `gu-IN` |
| Punjabi | `pa-IN` |
| Odia | `od-IN` |

---

## LLMEngine

Streaming LLM with context management.

```python
from sarvam_s2s.engines.llm import LLMEngine, ConversationMemory
```

### Methods

| Method | Description |
|--------|-------------|
| `generate_stream(history?)` | Async generator yielding tokens |
| `add_user_message(text)` | Add user message to memory |
| `add_assistant_message(text)` | Add AI response to memory |
| `clear_history()` | Clear conversation memory |
| `inject_context(text)` | Dynamically update static context |

### ConversationMemory

| Method | Description |
|--------|-------------|
| `add_message(role, content)` | Add a message |
| `get_messages(user_text?)` | Build full message list with context |
| `clear()` | Clear history |
| `history` | Read-only list of messages |
| `turn_count` | Number of user turns |

### Example: Standalone LLM Usage

```python
import asyncio
from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.llm import LLMEngine

async def main():
    config = SarvamS2SConfig(
        api_key="your-key",
        llm_context="Menu: Dosa Rs.80, Coffee Rs.30",
        llm_system_prompt="You are a restaurant assistant.",
    )
    llm = LLMEngine(config)
    llm.add_user_message("What's on the menu?")

    async for token in llm.generate_stream():
        print(token, end="", flush=True)

asyncio.run(main())
```

---

## TTSEngine

Text-to-Speech with WebSocket, HTTP streaming, and REST fallback.

```python
from sarvam_s2s.engines.tts import TTSEngine
```

### Methods

| Method | Description |
|--------|-------------|
| `await connect()` | Open WebSocket connection |
| `await disconnect()` | Close connection |
| `synthesize_stream(text)` | Async generator yielding audio bytes |
| `await synthesize(text)` | One-shot: returns full audio bytes |

### Transport Priority

1. **WebSocket** - Lowest latency for multi-sentence (persistent connection)
2. **HTTP Streaming** - Low TTFB, simpler (per-request)
3. **REST** - Highest latency, most reliable (fallback)

### Example: Standalone TTS

```python
import asyncio
from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.tts import TTSEngine

async def main():
    config = SarvamS2SConfig(
        api_key="your-key",
        tts_speaker="priya",
        tts_language="en-IN",
    )
    tts = TTSEngine(config)

    audio = await tts.synthesize("Hello, how are you?")
    with open("output.wav", "wb") as f:
        f.write(audio)

asyncio.run(main())
```

---

## STTEngine

Speech-to-Text WebSocket streaming with VAD.

```python
from sarvam_s2s.engines.stt import STTEngine, STTEvent
```

### Methods

| Method | Description |
|--------|-------------|
| `await connect()` | Open WebSocket connection |
| `await disconnect()` | Close connection |
| `await send_audio(chunk)` | Send PCM audio bytes |
| `await flush()` | Force immediate processing |
| `events()` | Async generator yielding STTEvents |

### STTEvent

```python
@dataclass
class STTEvent:
    type: str   # "speech_start" | "speech_end" | "transcript"
    text: str   # Transcript text (only for type="transcript")
```

### Example: Standalone STT

```python
import asyncio
from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.stt import STTEngine

async def main():
    config = SarvamS2SConfig(
        api_key="your-key",
        stt_language="en-IN",
    )
    stt = STTEngine(config)
    await stt.connect()

    # Send audio and receive events
    async for event in stt.events():
        if event.type == "speech_start":
            print("Speech detected...")
        elif event.type == "transcript":
            print(f"Transcript: {event.text}")
            break

    await stt.disconnect()

asyncio.run(main())
```

---

## AudioCapture

Microphone input with async streaming.

```python
from sarvam_s2s.audio import AudioCapture
```

### Methods

| Method | Description |
|--------|-------------|
| `await start()` | Start mic capture |
| `await stop()` | Stop capture |
| `stream()` | Async generator yielding PCM bytes |

---

## AudioPlayer

Audio output with instant-stop for barge-in.

```python
from sarvam_s2s.audio import AudioPlayer
```

### Methods

| Method | Description |
|--------|-------------|
| `await start()` | Init audio output |
| `await play_chunk(bytes)` | Play PCM audio |
| `await stop()` | Stop immediately (barge-in) |
| `is_playing` | Whether audio is active |

---

## Sarvam API Endpoints Used

| Component | Endpoint | Protocol |
|-----------|----------|----------|
| STT | `wss://api.sarvam.ai/speech-to-text/ws` | WebSocket |
| LLM | `POST https://api.sarvam.ai/v1/chat/completions` | HTTP SSE |
| TTS (stream) | `POST https://api.sarvam.ai/text-to-speech/stream` | HTTP Stream |
| TTS (websocket) | `wss://api.sarvam.ai/text-to-speech/ws` | WebSocket |
| TTS (rest) | `POST https://api.sarvam.ai/text-to-speech` | HTTP |

### Authentication

All endpoints accept:
- Header: `api-subscription-key: sk_xxx`
- Header: `Authorization: Bearer sk_xxx`

---

## Error Handling

The SDK raises standard exceptions:

| Exception | Cause |
|-----------|-------|
| `ImportError` | Missing optional dependency (sounddevice, openai) |
| `RuntimeError` | Invalid state transition |
| `httpx.HTTPStatusError` | API returned 4xx/5xx |
| `websockets.ConnectionClosed` | WebSocket disconnected |

Reconnection is handled automatically with exponential backoff (configurable via `reconnect_max_attempts` and `reconnect_base_delay`).
