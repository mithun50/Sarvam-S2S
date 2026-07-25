# Contributing

## Development Setup

```bash
git clone https://github.com/your-org/sarvam-s2s
cd sarvam-s2s
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Code Style

- Formatted with `ruff` (line length 100)
- Type hints required (checked with `mypy --strict`)
- Docstrings for all public methods

```bash
ruff check src/
mypy src/
```

## Project Structure

```
src/sarvam_s2s/
├── __init__.py        # Public API exports
├── config.py          # SarvamS2SConfig dataclass
├── session.py         # Main orchestrator + state machine
├── engines/
│   ├── stt.py         # STT WebSocket client
│   ├── tts.py         # TTS (WebSocket + HTTP stream + REST)
│   └── llm.py         # LLM streaming + ConversationMemory
└── audio/
    ├── capture.py     # Microphone input (sounddevice)
    └── player.py      # Audio output with barge-in stop
```

## Adding a New LLM Provider

1. Add the provider name to `llm_provider` Literal in `config.py`
2. Add a `_stream_<name>` method in `engines/llm.py`
3. Add routing in `generate_stream()`

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code change without feature/fix
