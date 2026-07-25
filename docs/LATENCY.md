---
layout: default
title: Latency Optimization
---


# Latency Optimization Guide

This document explains the techniques used in the Sarvam S2S SDK to achieve ~500-1000ms end-to-end latency (user stops speaking → first audio byte plays).

---

## Latency Budget

| Stage | What Happens | Target | Optimization |
|-------|-------------|--------|-------------|
| Audio → STT | 32ms audio chunks streamed continuously | ~32ms | Small chunk size, no buffering |
| STT → Transcript | VAD detects speech end, final transcript produced | ~100-200ms | High VAD sensitivity |
| Transcript → LLM request | HTTP request initiated | ~50ms | Connection reuse (httpx) |
| LLM first token | Model generates first output token | ~200-400ms | `reasoning_effort: null` |
| LLM → TTS | First phrase sent to TTS | ~0ms | Pipelined (phrase detection) |
| TTS first audio | Audio bytes begin streaming | ~100-200ms | HTTP streaming, low buffer |
| **Total** | | **~500-1000ms** | |

---

## Technique 1: `reasoning_effort: null`

The single biggest latency win. By setting `reasoning_effort` to `null` in the Sarvam LLM request, the model skips its internal chain-of-thought step and outputs tokens immediately.

```python
payload = {
    "model": "sarvam-105b",
    "messages": [...],
    "reasoning_effort": None,  # Disables thinking — instant tokens
    "stream": True,
}
```

**Impact**: Reduces LLM first-token latency from ~1-2s (with reasoning) to ~200-400ms.

**Trade-off**: Slightly lower quality on complex reasoning tasks. For voice assistants with short, conversational responses, this is an excellent trade-off.

---

## Technique 2: Phrase-Level Streaming to TTS

Instead of waiting for the full LLM response, the SDK detects phrase boundaries and sends text to TTS immediately:

```python
PHRASE_ENDERS = (".", "!", "?", "।", "॥", "\n", ",", ";", ":")
MIN_PHRASE_LENGTH = 10  # Avoid sending tiny fragments

# In the streaming loop:
if text.rstrip().endswith(PHRASE_ENDERS) and len(text.strip()) >= MIN_PHRASE_LENGTH:
    send_to_tts(text)
    text = ""
```

**Impact**: TTS synthesis begins while LLM is still generating the rest of the response. For a 3-sentence response, the user hears the first sentence ~500ms earlier than waiting for the full response.

**Why commas and semicolons?** For voice output, natural pause points (commas, semicolons) are valid places to split. The TTS model handles these fragments well and it reduces perceived latency.

---

## Technique 3: HTTP Streaming TTS

The SDK uses `POST https://api.sarvam.ai/text-to-speech/stream` which returns audio bytes via chunked transfer encoding:

```python
async with client.stream("POST", url, headers=headers, json=payload) as resp:
    async for chunk in resp.aiter_bytes():
        play(chunk)  # Play immediately as bytes arrive
```

**Impact**: Audio playback begins before the full TTS response is generated. First audio byte arrives ~100-200ms after request (vs ~500ms+ for REST which returns the complete audio).

**Fallback chain**: WebSocket → HTTP Streaming → REST (each progressively more reliable but higher latency).

---

## Technique 4: Small Audio Chunks (32ms)

Audio is captured in 32ms chunks (512 samples at 16kHz):

```python
audio_chunk_ms: int = 32  # 512 samples at 16kHz
```

**Why 32ms?** Balances between:
- Smaller chunks = lower latency (audio reaches STT faster)
- Larger chunks = less overhead (fewer WebSocket messages)

32ms is optimal for real-time conversation. Going smaller (16ms) adds overhead without meaningful latency improvement due to STT server-side buffering.

---

## Technique 5: Persistent STT WebSocket

The STT WebSocket stays open for the entire conversation session:

```python
# Connected once at session start
await stt.connect()

# Audio streams continuously (no reconnect overhead per utterance)
async for chunk in capture.stream():
    await stt.send_audio(chunk)
```

**Impact**: Eliminates ~100-200ms WebSocket handshake per utterance. In a multi-turn conversation, this saves significant cumulative latency.

---

## Technique 6: VAD-Based Endpoint Detection

Instead of using fixed silence duration to detect speech end, the SDK relies on Sarvam's server-side VAD:

```python
stt_vad_sensitivity: bool = True   # High sensitivity for conversational speech
stt_vad_signals: bool = True       # Receive speech_start/speech_end events
```

**Impact**: Faster and more accurate endpoint detection than client-side silence counting. Server VAD uses model-aware signal processing.

---

## Technique 7: Low `max_tokens` for Voice

Voice responses should be short and conversational:

```python
llm_max_tokens: int = 200  # ~50-100 words
```

**Impact**: Model generates faster (fewer tokens = less time), and responses are naturally suited for spoken output. A 200-token response takes ~2-3 seconds to generate vs ~10+ seconds for 1000 tokens.

---

## Technique 8: Connection Reuse with httpx

The SDK uses `httpx.AsyncClient` for LLM and TTS HTTP requests, which supports connection pooling:

```python
async with httpx.AsyncClient(timeout=30.0) as client:
    async with client.stream("POST", url, ...) as resp:
        ...
```

**Impact**: TCP connection reuse eliminates ~50-100ms of TLS handshake on subsequent requests within the same session.

---

## Technique 9: Immediate Barge-In

When the user interrupts, the SDK takes immediate action:

1. Stop audio playback (flush buffer)
2. Disconnect TTS (stop synthesis)
3. Cancel LLM generation (HTTP stream closed)
4. Return to LISTENING state

**Impact**: The user's new utterance is processed without waiting for the old response to finish. Perceived responsiveness matches natural conversation.

---

## Measuring Latency

To measure end-to-end latency in your deployment:

```python
import time

config = SarvamS2SConfig(...)

# Track pipeline timing
async with SarvamS2S(config) as s2s:
    t_speech_end = None
    t_first_audio = None
    
    def on_transcript(text):
        nonlocal t_speech_end
        t_speech_end = time.monotonic()
    
    def on_first_audio():
        nonlocal t_first_audio
        t_first_audio = time.monotonic()
        if t_speech_end:
            print(f"Latency: {(t_first_audio - t_speech_end)*1000:.0f}ms")
    
    s2s.on_transcript(on_transcript)
    # ... hook into player for first audio timing
```

---

## Latency vs. Quality Trade-offs

| Setting | Lower Latency | Higher Quality |
|---------|--------------|---------------|
| `reasoning_effort` | `null` | `"medium"` or omit |
| `llm_max_tokens` | 100-200 | 500-1000 |
| `llm_model` | `sarvam-30b` | `sarvam-105b` |
| `tts_min_buffer_size` | 20-50 | 100-200 |
| Phrase splitting | Aggressive (commas) | Conservative (periods only) |

For voice assistants, optimize for latency. For read-aloud or non-interactive use cases, optimize for quality.

---

## Network Considerations

- **Deploy close to Sarvam servers** (India): Reduces RTT by 50-200ms vs. international
- **Use HTTP/2 or keep-alive**: Connection reuse across requests
- **Prefer wired/WiFi over mobile**: Reduces jitter and packet loss
- **Monitor P95 latency**: Average latency hides tail spikes
