"""Basic conversation example using Sarvam S2S SDK."""

import asyncio
import os
from sarvam_s2s import SarvamS2S, SarvamS2SConfig


async def main():
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="hi-IN",
        tts_speaker="aditya",
        llm_system_prompt=(
            "You are a friendly Hindi-speaking assistant. "
            "Keep responses brief and conversational (1-2 sentences)."
        ),
    )

    print("Starting Sarvam S2S conversation...")
    print("Speak in Hindi. Press Ctrl+C to stop.\n")

    async with SarvamS2S(config) as s2s:
        s2s.on_transcript(lambda t: print(f"  You: {t}"))
        s2s.on_response(lambda r: print(f"  AI:  {r}\n"))

        await s2s.start()

        try:
            await s2s.wait_until_done()
        except KeyboardInterrupt:
            print("\nStopping...")


if __name__ == "__main__":
    asyncio.run(main())
