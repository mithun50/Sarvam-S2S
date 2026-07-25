"""
Demo 2: Multilingual Conversation
==================================
Switch between languages dynamically. The SDK detects and responds
in multiple Indian languages.

Usage:
    export SARVAM_API_KEY="your-key"
    python -m demos.multilingual
"""

import asyncio
import os

from sarvam_s2s import SarvamS2S, SarvamS2SConfig

# Language configurations
LANGUAGES = {
    "hi": {"stt": "hi-IN", "tts": "hi-IN", "speaker": "aditya", "name": "Hindi"},
    "ta": {"stt": "ta-IN", "tts": "ta-IN", "speaker": "kavitha", "name": "Tamil"},
    "te": {"stt": "te-IN", "tts": "te-IN", "speaker": "kavitha", "name": "Telugu"},
    "kn": {"stt": "kn-IN", "tts": "kn-IN", "speaker": "kavitha", "name": "Kannada"},
    "bn": {"stt": "bn-IN", "tts": "bn-IN", "speaker": "priya", "name": "Bengali"},
    "en": {"stt": "en-IN", "tts": "en-IN", "speaker": "aditya", "name": "English"},
}


def get_language_choice() -> dict:
    """Let user pick a language."""
    print("\n  Available languages:")
    for code, info in LANGUAGES.items():
        print(f"    [{code}] {info['name']}")

    choice = input("\n  Select language (default: hi): ").strip().lower()
    return LANGUAGES.get(choice, LANGUAGES["hi"])


async def main():
    lang = get_language_choice()

    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language=lang["stt"],
        tts_speaker=lang["speaker"],
        tts_language=lang["tts"],
        llm_system_prompt=(
            f"You are a helpful assistant. Always respond in {lang['name']}. "
            "Keep responses brief — 1-2 sentences max."
        ),
    )

    print(f"\n{'=' * 50}")
    print(f"  Sarvam S2S — {lang['name']} Conversation")
    print(f"{'=' * 50}")
    print(f"  Speak in {lang['name']}. Press Ctrl+C to stop.")
    print(f"{'=' * 50}\n")

    async with SarvamS2S(config) as s2s:
        s2s.on_transcript(lambda t: print(f"  🎤 You: {t}"))
        s2s.on_response(lambda r: print(f"  🤖 AI:  {r}\n"))

        await s2s.start()
        try:
            await s2s.wait_until_done()
        except KeyboardInterrupt:
            print("\n  Goodbye! 👋")


if __name__ == "__main__":
    asyncio.run(main())
