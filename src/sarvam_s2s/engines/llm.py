"""LLM Engine — Streaming chat completion with context management."""

from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from sarvam_s2s.config import SarvamS2SConfig

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manages conversation history with token/turn limits.

    Features:
    - Sliding window over conversation turns
    - Approximate token counting for context budget
    - Injection of static context and RAG-retrieved context
    - Few-shot example support
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self._history: list[dict[str, str]] = []

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self._history.append({"role": role, "content": content})
        self._trim_history()

    def clear(self) -> None:
        """Clear all conversation history."""
        self._history.clear()

    def get_messages(self, current_user_text: str = "") -> list[dict[str, str]]:
        """Build the full message list for the LLM.

        Order:
        1. System prompt
        2. Static context (if configured)
        3. RAG-retrieved context (if retriever configured)
        4. Few-shot examples (if any)
        5. Conversation history
        """
        messages: list[dict[str, str]] = []

        # 1. System prompt
        messages.append({"role": "system", "content": self.config.llm_system_prompt})

        # 2. Static context (after system by default)
        if self.config.llm_context:
            ctx_msg = {
                "role": "system",
                "content": f"[Context]\n{self.config.llm_context}",
            }
            if self.config.llm_context_position == "before_system":
                messages.insert(0, ctx_msg)
            elif self.config.llm_context_position == "after_system":
                messages.append(ctx_msg)
            # "before_user" is handled below

        # 3. RAG-retrieved context
        if self.config.llm_context_retriever and current_user_text:
            try:
                retrieved = self.config.llm_context_retriever(current_user_text)
                if retrieved:
                    messages.append({
                        "role": "system",
                        "content": f"[Retrieved Context]\n{retrieved}",
                    })
            except Exception as e:
                logger.warning(f"Context retriever failed: {e}")

        # 4. Few-shot examples
        for example in self.config.llm_few_shot_examples:
            messages.append(example)

        # 5. Insert static context before user messages if configured
        if (
            self.config.llm_context
            and self.config.llm_context_position == "before_user"
        ):
            messages.append({
                "role": "system",
                "content": f"[Context]\n{self.config.llm_context}",
            })

        # 6. Conversation history
        messages.extend(self._history)

        return messages

    @property
    def history(self) -> list[dict[str, str]]:
        """Read-only access to conversation history."""
        return list(self._history)

    @property
    def turn_count(self) -> int:
        """Number of user turns in history."""
        return sum(1 for m in self._history if m["role"] == "user")

    def _trim_history(self) -> None:
        """Trim history to stay within turn and token limits."""
        # Trim by turns
        max_turns = self.config.llm_max_history_turns
        if max_turns > 0:
            user_turns = [i for i, m in enumerate(self._history) if m["role"] == "user"]
            if len(user_turns) > max_turns:
                # Keep only the last N turns (pairs of user+assistant)
                cutoff_idx = user_turns[-max_turns]
                self._history = self._history[cutoff_idx:]

        # Trim by approximate token count
        max_tokens = self.config.llm_max_history_tokens
        if max_tokens > 0:
            while self._estimate_tokens() > max_tokens and len(self._history) > 2:
                # Remove oldest pair
                self._history.pop(0)
                if self._history and self._history[0]["role"] == "assistant":
                    self._history.pop(0)

    def _estimate_tokens(self) -> int:
        """Rough token estimate (~4 chars per token for English, ~2 for Devanagari)."""
        total_chars = sum(len(m["content"]) for m in self._history)
        return total_chars // 3  # Conservative estimate for multilingual


class LLMEngine:
    """Streaming LLM inference engine with context management.

    Features:
    - Conversation memory with sliding window
    - Static context injection (persona, knowledge base)
    - RAG-ready: plug in a retriever callback
    - Few-shot examples
    - Multi-provider: Sarvam, OpenAI, or any compatible API
    """

    def __init__(self, config: SarvamS2SConfig) -> None:
        self.config = config
        self.memory = ConversationMemory(config)

    async def generate_stream(
        self, conversation_history: list[dict[str, str]] | None = None
    ) -> AsyncIterator[str]:
        """Stream tokens from LLM.

        Args:
            conversation_history: If provided, uses this directly.
                Otherwise uses internal memory.

        Yields:
            Individual tokens/chunks as strings
        """
        if conversation_history is not None:
            # Legacy mode: build messages from provided history
            messages = [{"role": "system", "content": self.config.llm_system_prompt}]
            if self.config.llm_context:
                messages.append({"role": "system", "content": f"[Context]\n{self.config.llm_context}"})
            messages.extend(conversation_history)
        else:
            # New mode: use internal memory with full context management
            messages = self.memory.get_messages()

        if self.config.llm_provider == "sarvam":
            async for token in self._stream_sarvam(messages):
                yield token
        elif self.config.llm_provider == "openai":
            async for token in self._stream_openai(messages):
                yield token
        elif self.config.llm_provider == "custom":
            async for token in self._stream_custom(messages):
                yield token

    def add_user_message(self, text: str) -> None:
        """Add a user message to memory."""
        self.memory.add_message("user", text)

    def add_assistant_message(self, text: str) -> None:
        """Add an assistant response to memory."""
        self.memory.add_message("assistant", text)

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.memory.clear()

    def inject_context(self, context: str) -> None:
        """Dynamically update the static context."""
        self.config.llm_context = context

    async def _stream_sarvam(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream from Sarvam chat completion API."""
        import httpx

        url = f"{self.config.base_url}/v1/chat/completions"
        headers = {
            "api-subscription-key": self.config.api_key,
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.llm_model,
            "messages": messages,
            "max_tokens": self.config.llm_max_tokens,
            "temperature": self.config.llm_temperature,
            "reasoning_effort": None,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0]["delta"]
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def _stream_openai(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream from OpenAI API."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.config.llm_api_key or self.config.api_key)
        stream = await client.chat.completions.create(
            model=self.config.llm_model,
            messages=messages,  # type: ignore
            max_tokens=self.config.llm_max_tokens,
            temperature=self.config.llm_temperature,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def _stream_custom(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Stream from any OpenAI-compatible endpoint."""
        import httpx

        base_url = self.config.llm_base_url or self.config.base_url
        url = f"{base_url}/chat/completions"
        api_key = self.config.llm_api_key or self.config.api_key

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.llm_model,
            "messages": messages,
            "max_tokens": self.config.llm_max_tokens,
            "temperature": self.config.llm_temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
