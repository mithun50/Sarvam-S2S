"""
Demo 1: Basic Hindi Conversation
================================
The simplest possible S2S setup. Speak in Hindi, get spoken responses.

Usage:
    export SARVAM_API_KEY="your-key"
    python -m demos.basic_hindi
"""

import asyncio
import os

from sarvam_s2s import SarvamS2S, SarvamS2SConfig


async def main():
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="hi-IN",
        tts_speaker="aditya",
        tts_language="hi-IN",
        llm_system_prompt="तुम एक मददगार हिंदी सहायक हो। हमेशा हिंदी में जवाब दो। छोटे और सीधे जवाब दो।",
    )

    print("=" * 50)
    print("  Sarvam S2S — Basic Hindi Conversation")
    print("=" * 50)
    print("  Speak in Hindi. Press Ctrl+C to stop.")
    print("=" * 50)
    print()

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
