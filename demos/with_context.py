"""
Demo 4: LLM Context Management
===============================
Demonstrates injecting context, RAG retrieval, few-shot examples,
and conversation memory management.

Usage:
    export SARVAM_API_KEY="your-key"
    python -m demos.with_context
"""

import asyncio
import os

from sarvam_s2s import SarvamS2S, SarvamS2SConfig


# ─── Example 1: Restaurant Menu Bot ────────────────────────

RESTAURANT_CONTEXT = """
Restaurant: Dosa Palace
Location: Koramangala, Bangalore
Timings: 7 AM - 11 PM

Menu:
- Masala Dosa: ₹80
- Rava Dosa: ₹90
- Ghee Roast: ₹110
- Idli (2 pcs): ₹50
- Vada (2 pcs): ₹60
- Filter Coffee: ₹30
- Butter Milk: ₹25

Today's Special: Mysore Masala Dosa ₹95
Offers: 10% off on orders above ₹300
"""


# ─── Example 2: Simple RAG retriever ──────────────────────

KNOWLEDGE_BASE = {
    "refund": "Refund policy: Full refund within 7 days of purchase. Partial refund (50%) within 30 days. No refund after 30 days.",
    "shipping": "Free shipping on orders above ₹499. Standard delivery: 5-7 days. Express delivery: 2-3 days (₹99 extra).",
    "payment": "We accept UPI, credit/debit cards, net banking, and COD. EMI available on orders above ₹3000.",
    "return": "Returns accepted within 15 days. Item must be unused and in original packaging. Pickup scheduled within 48 hours.",
    "contact": "Customer care: 1800-123-4567 (toll free). Email: help@store.example.com. Hours: 9 AM - 9 PM IST.",
}


def simple_retriever(query: str) -> str:
    """A simple keyword-based retriever (replace with real vector search)."""
    query_lower = query.lower()
    matches = []
    for key, value in KNOWLEDGE_BASE.items():
        if key in query_lower or any(word in query_lower for word in key.split()):
            matches.append(value)

    if matches:
        return "\n".join(matches)
    return ""


# ─── Example 3: Few-shot examples ─────────────────────────

FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "What time do you open?"},
    {"role": "assistant", "content": "We open at 7 AM and close at 11 PM. Would you like to place an order?"},
    {"role": "user", "content": "How much is coffee?"},
    {"role": "assistant", "content": "Filter coffee is ₹30. Would you like anything else with that?"},
]


async def restaurant_bot():
    """Restaurant ordering bot with menu context."""
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="en-IN",
        tts_speaker="aditya",
        tts_language="en-IN",
        llm_system_prompt=(
            "You are a friendly restaurant order assistant at Dosa Palace. "
            "Help customers with menu, prices, and take orders. "
            "Be warm and suggest items. Keep responses to 1-2 sentences."
        ),
        # Context: the menu
        llm_context=RESTAURANT_CONTEXT,
        llm_context_position="after_system",
        # Few-shot: teach response style
        llm_few_shot_examples=FEW_SHOT_EXAMPLES,
        # Memory: keep last 10 turns
        llm_max_history_turns=10,
    )
    return config, "Restaurant Order Bot (Dosa Palace)"


async def customer_support_bot():
    """Customer support bot with RAG retrieval."""
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="en-IN",
        tts_speaker="priya",
        tts_language="en-IN",
        llm_system_prompt=(
            "You are a helpful customer support agent. "
            "Answer questions using the provided context. "
            "If you don't know something, say so politely. "
            "Keep responses brief and helpful."
        ),
        # RAG: dynamic context retrieval based on user query
        llm_context_retriever=simple_retriever,
        # Memory: remember the full conversation
        llm_max_history_turns=20,
        llm_max_history_tokens=3000,
    )
    return config, "Customer Support Bot (with RAG)"


async def tutor_bot():
    """Math tutor with persona and history management."""
    config = SarvamS2SConfig(
        api_key=os.environ.get("SARVAM_API_KEY", ""),
        stt_language="hi-IN",
        tts_speaker="aditya",
        tts_language="hi-IN",
        llm_system_prompt=(
            "तुम एक गणित के शिक्षक हो। छात्र के स्तर पर समझाओ। "
            "कदम-दर-कदम समझाओ। प्रोत्साहन दो। "
            "हमेशा हिंदी में बोलो। 2-3 वाक्य में जवाब दो।"
        ),
        llm_context=(
            "Student level: Class 8\n"
            "Current topic: Algebra - Linear Equations\n"
            "Previous weak areas: Word problems, negative numbers"
        ),
        llm_context_position="after_system",
        llm_max_history_turns=15,
    )
    return config, "Math Tutor (Hindi, with student context)"


async def main():
    print("=" * 55)
    print("  Sarvam S2S — Context Management Demos")
    print("=" * 55)
    print("\n  Choose a demo:")
    print("    [1] Restaurant Order Bot (static context + few-shot)")
    print("    [2] Customer Support Bot (RAG retrieval)")
    print("    [3] Math Tutor (Hindi, persona + student context)")

    choice = input("\n  Select (1/2/3): ").strip()

    if choice == "1":
        config, name = await restaurant_bot()
    elif choice == "2":
        config, name = await customer_support_bot()
    else:
        config, name = await tutor_bot()

    print(f"\n  Starting: {name}")
    print(f"  Press Ctrl+C to stop.\n{'=' * 55}\n")

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
