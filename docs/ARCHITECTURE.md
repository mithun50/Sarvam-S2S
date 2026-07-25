---
layout: default
title: Architecture
---

[Home](index.html) | [Architecture](ARCHITECTURE.html) | [API Reference](API.html) | [Latency Guide](LATENCY.html)

---

# Sarvam Speech-to-Speech SDK - Architecture

## Vision
A Python SDK that delivers real-time conversational AI by orchestrating Sarvam AI's STT, LLM, and TTS APIs in a streaming pipeline. The user speaks and gets intelligent spoken responses with sub-second latency.

---

## High-Level Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Microphone │────▶│  STT Engine  │────▶│  LLM Engine    │────▶│  TTS Engine  │────▶│   Speaker   │
│  (16kHz PCM)│     │  (Saaras v3) │     │  (Sarvam-105B) │     │  (Bulbul v3) │     │  (Audio Out)│
└─────────────┘     │   WebSocket  │     │  HTTP Stream   │     │  WS + HTTP   │     └─────────────┘
                    └──────────────┘     └────────────────┘     └──────────────┘
                           │                     │                      │
                           ▼                     ▼                      ▼
                    ┌──────────────┐     ┌────────────────┐     ┌──────────────┐
                    │  VAD Events  │     │  Streaming     │     │  Audio Chunks│
                    │  speech_start│     │  Token-by-Token│     │  Progressive │
                    │  speech_end  │     │  Generation    │     │  Playback    │
                    └──────────────┘     └────────────────┘     └──────────────┘
```

---

## Core Design Principles

### 1. Streaming Everything
- **STT**: WebSocket connection stays open, continuously receiving audio chunks
- **LLM**: Streaming chat completion with `reasoning_effort: null` for instant token flow (no thinking overhead)
- **TTS**: WebSocket connection for persistent sessions + HTTP streaming for per-sentence synthesis
- **Result**: First audio byte plays while user just finished speaking (~500ms target)

### 2. Barge-In Support (Interruption Handling)
Natural interruption model inspired by human conversation:
1. STT detects `speech_start` (VAD signal) while TTS is playing
2. Immediately stop TTS playback (flush local audio buffer)
3. Close current TTS connection
4. Cancel in-flight LLM generation
5. Resume STT processing for the new user utterance
6. Open fresh TTS connection for next response

### 3. Echo Prevention
The SDK prevents TTS audio from being picked up by the microphone and re-processed:
- Audio player state is tracked. STT ignores signals during active playback
- VAD `speech_start` events during SPEAKING state trigger barge-in (not echo processing)
- Short silence gap after TTS completion before re-enabling transcript processing

### 4. Sentence-Level Streaming to TTS
Don't wait for the full LLM response. As soon as a phrase boundary is detected in the LLM stream:
- Send that sentence/phrase to TTS immediately
- TTS starts synthesizing while LLM continues generating
- Phrase boundaries include: `.`, `!`, `?`, `,`, `;`, `:`, `।`, `॥`
- Minimum 10 characters before triggering a phrase send (avoids tiny fragments)

### 5. Persistent Connections
- STT WebSocket: kept alive for entire conversation session
- TTS WebSocket: per-utterance (closed on barge-in or completion)
- TTS HTTP Streaming: alternative transport, one request per sentence
- LLM: HTTP streaming (new request per turn)

---

## Key Configuration Choices

### `reasoning_effort: null`
Setting `reasoning_effort` to `null` in the Sarvam LLM request disables the model's internal "thinking" step. This produces **instant token flow**, critical for voice latency where every 100ms matters. The model skips chain-of-thought and outputs tokens directly.

### HTTP Streaming TTS (Primary for Web)
The HTTP streaming endpoint (`POST https://api.sarvam.ai/text-to-speech/stream`) provides:
- Lower time-to-first-byte than REST
- Simpler setup than WebSocket for per-sentence synthesis
- Automatic chunked transfer encoding
- Fallback to REST (`POST https://api.sarvam.ai/text-to-speech`) if streaming fails

### TTS Transport Priority
1. **WebSocket** - Lowest latency for multi-sentence streaming within a single connection
2. **HTTP Streaming** - Low TTFB, simpler lifecycle, ideal for sentence-by-sentence
3. **REST** - Highest latency, most reliable fallback

---

## Component Architecture

### SarvamS2S (Session Orchestrator)
```python
class SarvamS2S:
    """Orchestrates the full conversation lifecycle"""
    - state: SessionState (IDLE | LISTENING | PROCESSING | SPEAKING)
    - config: SarvamS2SConfig
    
    async def start()           # Begin listening
    async def stop()            # End session
    async def wait_until_done() # Block until stopped
    
    # Internal pipeline
    async def _audio_capture_loop()    # Mic → STT
    async def _stt_receive_loop()      # STT → Transcript events
    async def _handle_barge_in()       # Interrupt handling
    async def _handle_transcript(text) # Transcript → LLM → TTS → Speaker
    async def _generate_and_speak(text) # Core pipeline execution
```

### STTEngine
```python
class STTEngine:
    """Manages Sarvam STT WebSocket connection"""
    - ws: WebSocket → wss://api.sarvam.ai/speech-to-text/ws
    - model: "saaras:v3"
    - vad_signals: True (for barge-in detection)
    - high_vad_sensitivity: True (for conversational use)
    
    async def connect()
    async def send_audio(chunk: bytes)
    async def events() -> AsyncIterator[STTEvent]
    async def disconnect()
```

### LLMEngine
```python
class LLMEngine:
    """Streaming LLM inference with full context management"""
    - model: "sarvam-105b" (default) | "sarvam-30b" | custom
    - memory: ConversationMemory (sliding window)
    - context pipeline: system prompt → static context → RAG → few-shot → history
    
    async def generate_stream() -> AsyncIterator[str]
    def add_user_message(text: str)
    def add_assistant_message(text: str)
    def clear_history()
```

### TTSEngine
```python
class TTSEngine:
    """Sarvam TTS with WebSocket + HTTP Streaming + REST fallback"""
    - model: "bulbul:v3"
    - speaker: "aditya" (default), 16 voices available
    - transports: WS > HTTP Stream > REST (priority order)
    
    async def connect()         # Open WebSocket
    async def synthesize_stream(text) -> AsyncIterator[bytes]
    async def disconnect()      # Close (for barge-in)
```

### AudioCapture / AudioPlayer
```python
class AudioCapture:
    """Microphone input - 16-bit PCM, mono, 16kHz, 32ms chunks"""
    async def stream() -> AsyncIterator[bytes]

class AudioPlayer:
    """Speaker output with instant stop for barge-in"""
    async def play_chunk(audio_bytes: bytes)
    async def stop()  # Immediate interruption
```

---

## State Machine

```
                    ┌──────────┐
                    │   IDLE   │
                    └────┬─────┘
                         │ start()
                         ▼
                    ┌──────────┐
              ┌────▶│LISTENING │◀────────────────────────┐
              │     └────┬─────┘                         │
              │          │ speech_end + transcript        │
              │          ▼                               │
              │     ┌──────────┐                         │
              │     │PROCESSING│ (LLM generating)        │
              │     └────┬─────┘                         │
              │          │ first phrase ready             │
              │          ▼                               │
              │     ┌──────────┐     barge-in            │
              │     │ SPEAKING │─────────────────────────┘
              │     └────┬─────┘
              │          │ TTS complete
              └──────────┘
```

---

## Interrupt Sequence (Barge-In)

```
User Speaking    STT Engine    Session Manager    LLM Engine    TTS Engine    Speaker
     │               │               │                │              │            │
     │──audio────────▶               │                │              │            │
     │               │──speech_start─▶               │              │            │
     │               │               │                │              │──STOP──────▶│
     │               │               │──cancel_llm────▶              │            │
     │               │               │──disconnect────────────────────▶            │
     │               │               │  state → LISTENING            │            │
     │               │               │                │              │            │
     │──more audio──▶│               │                │              │            │
     │               │──speech_end───▶               │                │            │
     │               │──transcript───▶               │                │            │
     │               │               │──generate─────▶│              │            │
     │               │               │                │──stream──────▶│            │
     │               │               │                │              │──audio─────▶│
```

---

## LLM Context Pipeline

Messages sent to the LLM are constructed in this order:

```
1. System prompt (always present)
2. Static context [configurable position: before_system | after_system | before_user]
3. RAG-retrieved context (if retriever callback is set)
4. Few-shot examples (if configured)
5. Conversation history (sliding window by turns + tokens)
```

The `ConversationMemory` class manages trimming:
- `llm_max_history_turns`: Max user turns to retain (default: 20)
- `llm_max_history_tokens`: Approximate token budget for history (default: 4000)

---

## Sarvam LLM API Request

```python
# POST https://api.sarvam.ai/v1/chat/completions
{
    "model": "sarvam-105b",        # or "sarvam-30b"
    "messages": [...],
    "max_tokens": 200,             # Low for voice (fast responses)
    "temperature": 0.7,
    "reasoning_effort": null,      # CRITICAL: disables thinking for instant tokens
    "stream": true
}
```

Headers:
- `api-subscription-key: <api_key>`
- `Authorization: Bearer <api_key>`
- `Content-Type: application/json`

---

## Latency Optimization Strategy

| Stage | Technique | Target Latency |
|-------|-----------|---------------|
| Audio Capture → STT | Continuous streaming, 32ms chunks | ~32ms per chunk |
| STT → Transcript | VAD-based endpoint detection | ~100-200ms after speech ends |
| Transcript → LLM | Immediate request on transcript | ~50ms |
| LLM First Token | `reasoning_effort: null` + streaming | ~200-400ms |
| LLM → TTS | Phrase boundary detection, immediate send | ~0ms (pipelined) |
| TTS First Audio | HTTP streaming, low min_buffer_size | ~100-200ms |
| **Total: User stops → First audio plays** | | **~500-1000ms** |

---

## Configuration

```python
@dataclass
class SarvamS2SConfig:
    # API Configuration
    api_key: str
    base_url: str = "https://api.sarvam.ai"
    
    # STT Configuration
    stt_model: str = "saaras:v3"
    stt_language: str = "hi-IN"
    stt_mode: str = "transcribe"
    stt_vad_sensitivity: bool = True
    stt_vad_signals: bool = True
    
    # LLM Configuration
    llm_provider: str = "sarvam"           # "sarvam" | "openai" | "custom"
    llm_model: str = "sarvam-105b"         # "sarvam-30b", "sarvam-105b"
    llm_max_tokens: int = 200              # Low for voice latency
    llm_temperature: float = 0.7
    llm_stream: bool = True
    
    # LLM Context
    llm_context: str = ""                  # Static context
    llm_context_retriever: Callable | None # RAG callback
    llm_few_shot_examples: list            # Example conversations
    llm_max_history_turns: int = 20
    llm_max_history_tokens: int = 4000
    
    # TTS Configuration
    tts_model: str = "bulbul:v3"
    tts_speaker: str = "aditya"
    tts_language: str = "hi-IN"
    tts_pace: float = 1.0
    tts_audio_codec: str = "linear16"
    tts_sample_rate: int = 16000
    
    # Behavior
    enable_barge_in: bool = True
    sentence_buffer_chars: int = 50
    max_response_chars: int = 500
    idle_timeout_seconds: int = 300
```

---

## Supported Languages

| Language | Code | STT | TTS |
|----------|------|-----|-----|
| Hindi | hi-IN | ✅ | ✅ |
| English (Indian) | en-IN | ✅ | ✅ |
| Bengali | bn-IN | ✅ | ✅ |
| Tamil | ta-IN | ✅ | ✅ |
| Telugu | te-IN | ✅ | ✅ |
| Kannada | kn-IN | ✅ | ✅ |
| Malayalam | ml-IN | ✅ | ✅ |
| Marathi | mr-IN | ✅ | ✅ |
| Gujarati | gu-IN | ✅ | ✅ |
| Punjabi | pa-IN | ✅ | ✅ |
| Odia | od-IN | ✅ | ✅ |

---

## Available TTS Speakers

| Speaker | Gender |
|---------|--------|
| aditya | Male |
| priya | Female |
| rahul | Male |
| neha | Female |
| anushka | Female |
| kavitha | Female |
| karun | Male |
| hitesh | Male |
| ritu | Female |
| rohan | Male |
| simran | Female |
| kavya | Female |
| amit | Male |
| dev | Male |
| ishita | Female |
| shreya | Female |

---

## Pricing Estimate (per conversation)

| Component | Rate | Estimate (5-min convo) |
|-----------|------|----------------------|
| STT (Saaras v3) | ₹30/hour | ~₹2.50 |
| TTS (Bulbul v3) | ₹30/10K chars | ~₹1.50 (500 chars response avg) |
| LLM (Sarvam-105B) | ₹2.5 input + ₹10 output / 1M tokens | ~₹0.50 |
| **Total** | | **~₹4.50 per 5-min conversation** |

---

## External LLM Support

The SDK is LLM-agnostic. While it defaults to Sarvam-105B, it supports:
- **Sarvam-105B / Sarvam-30B** (default, best for Indian languages)
- **OpenAI GPT-4o / GPT-4o-mini** (via OpenAI-compatible API)
- **Any OpenAI-compatible endpoint** (Groq, Together, local models)

Configuration:
```python
# Sarvam (default)
config = SarvamS2SConfig(api_key="sarvam-key")

# OpenAI
config = SarvamS2SConfig(
    api_key="sarvam-key",
    llm_provider="openai",
    llm_api_key="sk-...",
    llm_model="gpt-4o-mini",
)

# Custom (Groq, Together, etc.)
config = SarvamS2SConfig(
    api_key="sarvam-key",
    llm_provider="custom",
    llm_base_url="https://api.groq.com/openai/v1",
    llm_api_key="gsk_...",
    llm_model="llama-3.1-70b-versatile",
)
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Async Runtime | asyncio |
| WebSocket Client | websockets |
| Audio I/O | sounddevice (PortAudio) |
| Audio Format | PCM 16-bit, 16kHz, mono |
| HTTP Client | httpx (async, streaming) |
| Package Manager | pip / uv |
| Testing | pytest + pytest-asyncio |
| Web Framework | FastAPI + uvicorn (demos) |

---

## Web Demo Architecture

The `run_web_demo.py` server provides a browser-based interface:

```
Browser (JS)                    FastAPI Server
┌───────────────┐              ┌──────────────────────┐
│ Text Input    │──WebSocket──▶│ /ws/chat             │
│ Audio Playback│◀─────────────│   LLM Stream         │
│ Interrupt Btn │──interrupt──▶│   TTS per sentence   │
└───────────────┘              │   Interrupt support  │
                               └──────────────────────┘
```

Key features:
- Token-by-token LLM streaming to browser
- Per-sentence TTS audio generation (HTTP streaming endpoint)
- Interrupt support: client sends `{"type": "interrupt"}` to cancel in-flight generation
- Sentence boundary detection for progressive TTS (`.,!?;:` + min 8 chars)
