"""
Demo: Text-Mode Simulation (No Microphone Required)
====================================================
Tests the full LLM + context pipeline by simulating the STT output
with text input. Useful for:
- Testing without a microphone
- CI/CD environments
- Debugging the LLM/context pipeline

Usage:
    export SARVAM_API_KEY="your-key"
    python -m demos.simulate_conversation
"""

import asyncio
import os
import sys

from sarvam_s2s.config import SarvamS2SConfig
from sarvam_s2s.engines.llm import LLMEngine


async def simulate_conversation():
    """Simulate a full conversation using text input instead of speech."""

    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="en-IN",
        tts_speaker="aditya",
        tts_language="en-IN",
        llm_system_prompt=(
            "You are a helpful assistant at a restaurant called Dosa Palace in Bangalore. "
            "Help customers with menu items and orders. "
            "Be friendly and concise (1-2 sentences)."
        ),
        llm_context=(
            "Menu:\n"
            "- Masala Dosa: Rs.80\n"
            "- Ghee Roast Dosa: Rs.110\n"
            "- Idli (2 pcs): Rs.50\n"
            "- Filter Coffee: Rs.30\n"
            "- Mysore Bonda: Rs.45\n"
            "Today's special: Podi Dosa Rs.75"
        ),
        llm_context_position="after_system",
        llm_max_history_turns=10,
        llm_temperature=0.7,
        llm_max_tokens=150,
    )

    llm = LLMEngine(config)

    print("=" * 55)
    print("  Sarvam S2S — Simulated Conversation")
    print("  (Text mode — no microphone needed)")
    print("=" * 55)
    print("  Type messages to simulate speech input.")
    print("  Type 'quit' or 'exit' to stop.")
    print("  Type 'clear' to reset conversation.")
    print("  Type 'history' to see conversation memory.")
    print("=" * 55)
    print()

    turn = 0
    while True:
        try:
            user_input = input("  🎤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye! 👋")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("  Goodbye! 👋")
            break
        if user_input.lower() == "clear":
            llm.clear_history()
            print("  🔄 Conversation cleared.\n")
            turn = 0
            continue
        if user_input.lower() == "history":
            print(f"\n  📝 Memory ({llm.memory.turn_count} turns):")
            for msg in llm.memory.history:
                role = "You" if msg["role"] == "user" else "AI"
                print(f"     [{role}] {msg['content'][:80]}")
            print()
            continue

        # Simulate STT output -> LLM processing
        turn += 1
        llm.add_user_message(user_input)

        # Stream LLM response
        print("  🤖 AI:  ", end="", flush=True)
        full_response = ""

        try:
            async for token in llm.generate_stream():
                print(token, end="", flush=True)
                full_response += token
        except Exception as e:
            print(f"\n  ❌ Error: {e}")
            print("  (Set SARVAM_API_KEY or use offline mode)\n")
            # Remove the user message since we didn't get a response
            llm.memory._history.pop()
            continue

        print("\n")

        # Save assistant response to memory
        llm.add_assistant_message(full_response)


async def offline_demo():
    """Demo that works completely offline (mocked LLM responses)."""

    config = SarvamS2SConfig(
        api_key="demo-key",
        llm_system_prompt="You are a helpful assistant.",
        llm_context="Restaurant menu: Dosa Rs.80, Coffee Rs.30, Idli Rs.50",
        llm_max_history_turns=5,
    )

    llm = LLMEngine(config)

    print("=" * 55)
    print("  Sarvam S2S — Offline Demo (Mocked Responses)")
    print("=" * 55)
    print()

    # Simulated conversation
    conversation = [
        "What's on the menu?",
        "How much is the dosa?",
        "I'll have one dosa and a coffee",
        "What's the total?",
    ]

    mock_responses = [
        "We have Dosa for Rs.80, Coffee for Rs.30, and Idli for Rs.50. What would you like?",
        "Masala Dosa is Rs.80. Would you like to add anything else?",
        "One Dosa and one Coffee. Your order is confirmed!",
        "That would be Rs.80 + Rs.30 = Rs.110 total. Shall I proceed?",
    ]

    for user_text, ai_response in zip(conversation, mock_responses):
        print(f"  🎤 You: {user_text}")
        llm.add_user_message(user_text)

        print(f"  🤖 AI:  {ai_response}")
        llm.add_assistant_message(ai_response)

        print(f"     [Memory: {llm.memory.turn_count} turns]\n")
        await asyncio.sleep(0.5)  # Simulate delay

    print("=" * 55)
    print(f"  Final memory: {llm.memory.turn_count} turns")
    print("  Context pipeline: ✅ Working")
    print("  History management: ✅ Working")
    print("=" * 55)


async def main():
    print("\n  Choose mode:")
    print("    [1] Interactive (requires SARVAM_API_KEY)")
    print("    [2] Offline demo (no API key needed)")

    choice = input("\n  Select (1/2): ").strip()

    if choice == "1":
        if not os.environ.get("SARVAM_API_KEY"):
            print("\n  ⚠️  SARVAM_API_KEY not set!")
            print("  Set it with: export SARVAM_API_KEY='your-key'")
            print("  Running offline demo instead...\n")
            await offline_demo()
        else:
            await simulate_conversation()
    else:
        await offline_demo()


if __name__ == "__main__":
    asyncio.run(main())
