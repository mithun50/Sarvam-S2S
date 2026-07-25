# Sarvam S2S - Speech-to-Speech SDK

[![PyPI version](https://img.shields.io/pypi/v/sarvam-s2s.svg)](https://pypi.org/project/sarvam-s2s/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/sarvam-s2s.svg)](https://pypi.org/project/sarvam-s2s/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/mithun50/Sarvam-S2S/blob/master/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/mithun50/Sarvam-S2S.svg)](https://github.com/mithun50/Sarvam-S2S/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/mithun50/Sarvam-S2S.svg)](https://github.com/mithun50/Sarvam-S2S/issues)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://mithun50.github.io/Sarvam-S2S/)

Real-time conversational AI SDK for Indian languages, powered by [Sarvam AI](https://sarvam.ai).

> Build voice AI assistants with Sarvam's STT + LLM + TTS stack, optimized for 11 Indian languages with sub-second latency.

## Features

- Real-time streaming - Audio in, audio out with ~500-1000ms latency
- 11 Indian languages - Hindi, Tamil, Telugu, Kannada, Bengali, and more
- Barge-in support - Interrupt the AI mid-sentence naturally
- LLM-agnostic - Sarvam-105B/30B, OpenAI, Groq, or any compatible endpoint
- Context management - RAG, few-shot examples, conversation memory
- 16+ voices - Natural speech with Bulbul v3 (aditya, priya, kavitha, anushka, rahul, neha, and more)
- Simple SDK - 5 lines to start a conversation

## Quick Start

```bash
pip install sarvam-s2s
```

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

## Setup

1. Get an API key from [dashboard.sarvam.ai](https://dashboard.sarvam.ai)
2. Copy `.env.example` to `.env` and add your key:
   ```bash
   cp .env.example .env
   # Edit .env and add your SARVAM_API_KEY
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   ```

## Web Demo

Try the SDK in your browser with real-time streaming and interrupt support:

```bash
pip install fastapi uvicorn python-dotenv httpx
python run_web_demo.py
# Open http://localhost:8000
```

The web demo supports:
- Real-time LLM streaming (token-by-token)
- Sentence-level TTS (audio plays as sentences complete)
- Interrupt support (send a new message to cancel current response)
- Multiple speakers and languages

## Architecture

```
Mic -> [STT WebSocket] -> Transcript -> [LLM Stream] -> Text -> [TTS Stream] -> Speaker
         (Saaras v3)                    (Sarvam-105B)           (Bulbul v3)
```

All three stages stream simultaneously. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## Models & Endpoints

| Component | Model | Endpoint |
|-----------|-------|----------|
| STT | Saaras v3 | `wss://api.sarvam.ai/speech-to-text/ws` |
| LLM | Sarvam-105B (default) | `POST https://api.sarvam.ai/v1/chat/completions` |
| TTS | Bulbul v3 | `wss://api.sarvam.ai/text-to-speech/ws` |
| TTS (HTTP) | Bulbul v3 | `POST https://api.sarvam.ai/text-to-speech/stream` |

## Available TTS Speakers

aditya, priya, rahul, neha, anushka, kavitha, karun, hitesh, ritu, rohan, simran, kavya, amit, dev, ishita, shreya

## Using Other LLMs

```python
# OpenAI
config = SarvamS2SConfig(
    api_key="sarvam-key",
    llm_provider="openai",
    llm_api_key="sk-...",
    llm_model="gpt-4o-mini",
)

# Groq / Together / Local
config = SarvamS2SConfig(
    api_key="sarvam-key",
    llm_provider="custom",
    llm_base_url="https://api.groq.com/openai/v1",
    llm_api_key="gsk_...",
    llm_model="llama-3.1-70b-versatile",
)
```

## Context Management

```python
# Static context (knowledge base, persona)
config = SarvamS2SConfig(
    api_key="your-key",
    llm_context="Menu: Dosa Rs.80, Coffee Rs.30, Idli Rs.50",
    llm_system_prompt="You are a restaurant assistant.",
    llm_max_history_turns=10,
)

# RAG retriever
def my_retriever(query: str) -> str:
    # Your vector search here
    return relevant_context

config = SarvamS2SConfig(
    api_key="your-key",
    llm_context_retriever=my_retriever,
)
```

## Demos

| Demo | Description | Command |
|------|-------------|---------|
| Web Demo | Browser-based streaming chat | `python run_web_demo.py` |
| Basic Hindi | Microphone conversation | `python -m demos.basic_hindi` |
| Multilingual | 6 language options | `python -m demos.multilingual` |
| Custom LLM | OpenAI/Groq/Sarvam choice | `python -m demos.custom_llm` |
| With Context | Restaurant bot, RAG, tutor | `python -m demos.with_context` |
| Simulate | Text mode (no mic needed) | `python -m demos.simulate_conversation` |

## Supported Languages

Hindi, English (Indian), Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Odia

## Latency

Target: ~500-1000ms from user silence to first audio byte. See [docs/LATENCY.md](docs/LATENCY.md) for optimization techniques.

## Pricing

~₹4.50 per 5-minute conversation (STT ₹30/hr + TTS ₹30/10K chars + LLM ~₹0.50)

## Project Structure

```
sarvam-s2s/
├── src/sarvam_s2s/
│   ├── config.py            # Configuration (defaults: sarvam-105b, aditya)
│   ├── session.py           # Main orchestrator
│   ├── engines/
│   │   ├── stt.py           # Sarvam STT WebSocket
│   │   ├── tts.py           # Sarvam TTS (WebSocket + HTTP streaming)
│   │   └── llm.py           # LLM streaming + context management
│   └── audio/
│       ├── capture.py       # Microphone input
│       └── player.py        # Speaker output
├── demos/
│   ├── web_demo/            # Browser-based demo
│   ├── basic_hindi.py
│   ├── multilingual.py
│   ├── custom_llm.py
│   ├── with_context.py
│   └── simulate_conversation.py
├── run_web_demo.py          # Quick-start web demo
├── .env.example             # Environment template
└── docs/
    ├── ARCHITECTURE.md      # System architecture
    └── LATENCY.md           # Latency optimization guide
```

## Development

```bash
git clone https://github.com/mithun50/Sarvam-S2S
cd sarvam-s2s
pip install -e ".[dev]"
pytest
```

## License

MIT
