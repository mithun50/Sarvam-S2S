# Changelog

## 0.1.1 (2026-07-25)

### Fixes
- Fix README links to use absolute URLs (no more 404s on PyPI)
- Add author email to package metadata
- Add Documentation and Changelog URLs to PyPI sidebar
- Add badges (PyPI version, Python versions, license, stars, issues, downloads)
- Add GitHub Pages documentation site

## 0.1.0 (2026-07-23)

### Features
- Real-time Speech-to-Speech pipeline (STT -> LLM -> TTS)
- Sarvam STT (Saaras v3) via WebSocket with VAD signals
- Sarvam TTS (Bulbul v3) with 3 transport options (WebSocket, HTTP stream, REST)
- Sarvam LLM (sarvam-105b) with reasoning disabled for instant tokens
- Multi-provider LLM support (Sarvam, OpenAI, any OpenAI-compatible)
- Conversation memory with sliding window and token budget
- Context management (static, RAG retriever, few-shot examples)
- Barge-in / interruption support
- 11 Indian language support
- 40+ TTS voices
- Web demo with real-time streaming UI
- Sentence-level TTS streaming (audio plays as sentences complete)
- Echo prevention (mic disabled during AI speech)
- Phrase-level splitting for lower latency

### Models
- STT: `saaras:v3` (22 languages, VAD, streaming)
- LLM: `sarvam-105b` (128K context, `reasoning_effort: null`)
- TTS: `bulbul:v3` (40+ speakers, streaming)
