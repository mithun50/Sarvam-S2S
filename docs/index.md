---
layout: default
title: Home
---

[Home](index.html) | [Architecture](ARCHITECTURE.html) | [API Reference](API.html) | [Latency Guide](LATENCY.html)

---

# Sarvam S2S

Real-time Speech-to-Speech SDK for Indian languages, powered by [Sarvam AI](https://sarvam.ai).

Build voice AI assistants with Sarvam's STT + LLM + TTS stack, optimized for 11 Indian languages with sub-second latency.

## Install

```bash
pip install sarvam-s2s
```

## Quick Start

```python
import asyncio
from sarvam_s2s import SarvamS2S, SarvamS2SConfig

async def main():
    config = SarvamS2SConfig(
        api_key="your-sarvam-api-key",
        stt_language="hi-IN",
        tts_speaker="aditya",
        llm_system_prompt="You are a friendly Hindi assistant.",
    )

    async with SarvamS2S(config) as s2s:
        s2s.on_transcript(lambda t: print(f"You: {t}"))
        s2s.on_response(lambda r: print(f"AI: {r}"))
        await s2s.start()
        await s2s.wait_until_done()

asyncio.run(main())
```

## Features

- **Real-time Streaming** - Audio in, audio out with ~500-1000ms latency. All three stages stream simultaneously.
- **Barge-in Support** - Interrupt the AI mid-sentence naturally. VAD detects speech and instantly stops playback.
- **11 Indian Languages** - Hindi, Tamil, Telugu, Kannada, Bengali, Malayalam, Marathi, Gujarati, Punjabi, Odia, English (Indian).
- **LLM-agnostic** - Sarvam-105B/30B, OpenAI GPT-4o, Groq Llama, or any OpenAI-compatible endpoint.
- **16+ Natural Voices** - Bulbul v3 TTS with voices like Aditya, Priya, Kavitha, Anushka, Rahul, and more.
- **Context Management** - RAG callbacks, few-shot examples, static knowledge bases, and conversation memory with sliding window.

## Architecture

```
Mic -> [STT WebSocket] -> Transcript -> [LLM Stream] -> Text -> [TTS Stream] -> Speaker
         (Saaras v3)                    (Sarvam-105B)           (Bulbul v3)
```

All three stages stream simultaneously. Phrase-level splitting sends text to TTS as soon as a boundary is detected.

## Changing the LLM Provider

The SDK supports three LLM providers out of the box. Switch between them with a single config change.

### Sarvam (Default)

Uses Sarvam's own LLM endpoint. No extra API key needed.

```python
config = SarvamS2SConfig(
    api_key="your-sarvam-key",
    llm_provider="sarvam",
    llm_model="sarvam-105b",  # or "sarvam-30b" for faster responses
)
```

### OpenAI

Use GPT-4o, GPT-4o-mini, or any OpenAI model.

```python
config = SarvamS2SConfig(
    api_key="your-sarvam-key",       # still needed for STT/TTS
    llm_provider="openai",
    llm_api_key="sk-...",            # your OpenAI API key
    llm_model="gpt-4o-mini",
)
```

### Custom (Groq, Together, Local, or any OpenAI-compatible API)

Point to any endpoint that follows the OpenAI chat completions format.

```python
# Groq
config = SarvamS2SConfig(
    api_key="your-sarvam-key",
    llm_provider="custom",
    llm_base_url="https://api.groq.com/openai/v1",
    llm_api_key="gsk_...",
    llm_model="llama-3.1-70b-versatile",
)

# Together AI
config = SarvamS2SConfig(
    api_key="your-sarvam-key",
    llm_provider="custom",
    llm_base_url="https://api.together.xyz/v1",
    llm_api_key="your-together-key",
    llm_model="meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
)

# Local (Ollama, vLLM, etc.)
config = SarvamS2SConfig(
    api_key="your-sarvam-key",
    llm_provider="custom",
    llm_base_url="http://localhost:11434/v1",
    llm_api_key="not-needed",
    llm_model="llama3.1",
)
```

### LLM Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `llm_provider` | `"sarvam"` | Provider: `"sarvam"`, `"openai"`, or `"custom"` |
| `llm_model` | `"sarvam-105b"` | Model name to use |
| `llm_api_key` | `""` | API key for the LLM provider (if different from Sarvam key) |
| `llm_base_url` | `""` | Base URL for custom endpoints |
| `llm_max_tokens` | `200` | Max tokens per response (lower = faster for voice) |
| `llm_temperature` | `0.7` | Sampling temperature |
| `llm_stream` | `True` | Enable streaming (always recommended for voice) |

## Context Management

### Static Context (Knowledge Base, Persona)

```python
config = SarvamS2SConfig(
    api_key="your-key",
    llm_context="Menu: Dosa Rs.80, Coffee Rs.30, Idli Rs.50",
    llm_system_prompt="You are a restaurant assistant.",
    llm_max_history_turns=10,
)
```

### RAG Retriever

Plug in your own vector search or knowledge retrieval function.

```python
def my_retriever(query: str) -> str:
    # Your vector search here
    return relevant_context

config = SarvamS2SConfig(
    api_key="your-key",
    llm_context_retriever=my_retriever,
)
```

### Few-shot Examples

```python
config = SarvamS2SConfig(
    api_key="your-key",
    llm_few_shot_examples=[
        {"role": "user", "content": "What is dosa?"},
        {"role": "assistant", "content": "Dosa is a thin crispy crepe made from fermented rice and lentil batter."},
    ],
)
```

### Context Pipeline Order

Messages sent to the LLM are constructed in this order:

1. System prompt
2. Static context (configurable position)
3. RAG-retrieved context
4. Few-shot examples
5. Conversation history (sliding window)

## Supported Languages

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
| Odia | `or-IN` |

## Available TTS Voices

`aditya`, `priya`, `rahul`, `neha`, `anushka`, `kavitha`, `karun`, `hitesh`, `ritu`, `rohan`, `simran`, `kavya`, `amit`, `dev`, `ishita`, `shreya`

## Pricing

Approximately Rs.4.50 per 5-minute conversation:

- STT (Saaras v3): Rs.30/hour
- TTS (Bulbul v3): Rs.30/10K characters
- LLM (Sarvam-105B): ~Rs.0.50/conversation

## Demos

| Demo | Description | Command |
|------|-------------|---------|
| Web Demo | Browser-based streaming chat | `python run_web_demo.py` |
| Basic Hindi | Microphone conversation | `python -m demos.basic_hindi` |
| Multilingual | 6 language options | `python -m demos.multilingual` |
| Custom LLM | OpenAI/Groq/Sarvam choice | `python -m demos.custom_llm` |
| With Context | Restaurant bot, RAG, tutor | `python -m demos.with_context` |
| Simulate | Text mode (no mic needed) | `python -m demos.simulate_conversation` |

## Documentation

- [Architecture](ARCHITECTURE.html) - System design, state machine, streaming pipeline, barge-in handling
- [API Reference](API.html) - Configuration options, methods, events, type definitions
- [Latency Guide](LATENCY.html) - Optimization techniques for sub-second time-to-first-audio

## Setup

1. Get an API key from [dashboard.sarvam.ai](https://dashboard.sarvam.ai)
2. Clone and install:

```bash
git clone https://github.com/mithun50/Sarvam-S2S
cd Sarvam-S2S
pip install -e .
```

3. Add your key:

```bash
cp .env.example .env
# Edit .env and add your SARVAM_API_KEY
```

4. Run the web demo:

```bash
pip install fastapi uvicorn python-dotenv httpx
python run_web_demo.py
# Open http://localhost:8000
```

## License

MIT
