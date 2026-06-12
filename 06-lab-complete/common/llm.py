"""LLM helpers for the Day 8 A2A runtime."""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


def llm_enabled() -> bool:
    """Return whether the runtime should attempt live LLM calls."""
    if os.getenv("DAY08_DISABLE_LLM", "").lower() in {"1", "true", "yes"}:
        return False
    return bool(os.getenv("OPENROUTER_API_KEY"))


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client pointed at OpenRouter."""
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4-5"),
        temperature=0.3,
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "1000")),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
    )

