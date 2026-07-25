"""
Demo 3: Custom LLM Provider
============================
Use OpenAI GPT-4o or Groq Llama instead of Sarvam's LLM,
while still using Sarvam's STT and TTS.

Usage:
    export SARVAM_API_KEY="your-sarvam-key"
    export OPENAI_API_KEY="sk-..."
    python -m demos.custom_llm
"""

import asyncio
import os

from sarvam_s2s import SarvamS2S, SarvamS2SConfig


async def run_with_openai():
    """Use OpenAI GPT-4o-mini as the brain."""
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="en-IN",
        tts_speaker="aditya",
        tts_language="en-IN",
        # LLM: OpenAI
        llm_provider="openai",
        llm_api_key=os.environ.get("OPENAI_API_KEY", ""),
        llm_model="gpt-4o-mini",
        llm_system_prompt=(
            "You are a knowledgeable assistant speaking to an Indian user. "
            "Respond in English with an Indian conversational style. "
            "Keep responses to 2-3 sentences max."
        ),
    )

    print("  Using: OpenAI GPT-4o-mini + Sarvam STT/TTS")
    return config


async def run_with_groq():
    """Use Groq's fast Llama as the brain."""
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="en-IN",
        tts_speaker="aditya",
        tts_language="en-IN",
        # LLM: Groq (OpenAI-compatible)
        llm_provider="custom",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_api_key=os.environ.get("GROQ_API_KEY", ""),
        llm_model="llama-3.1-70b-versatile",
        llm_system_prompt=(
            "You are a fast, helpful assistant. "
            "Respond concisely in English. 1-2 sentences."
        ),
    )

    print("  Using: Groq Llama-3.1-70B + Sarvam STT/TTS")
    return config


async def main():
    print("=" * 50)
    print("  Sarvam S2S — Custom LLM Demo")
    print("=" * 50)
    print("\n  Choose LLM provider:")
    print("    [1] OpenAI GPT-4o-mini")
    print("    [2] Groq Llama-3.1-70B")
    print("    [3] Sarvam-105B (default)")

    choice = input("\n  Select (1/2/3): ").strip()

    if choice == "1":
        config = await run_with_openai()
    elif choice == "2":
        config = await run_with_groq()
    else:
        config = SarvamS2SConfig(
            api_key=os.environ.get("SARVAM_API_KEY", ""),
            stt_language="en-IN",
            tts_speaker="aditya",
            tts_language="en-IN",
        )
        print("  Using: Sarvam-105B (default)")

    print(f"\n  Speak in English. Press Ctrl+C to stop.\n{'=' * 50}\n")

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
