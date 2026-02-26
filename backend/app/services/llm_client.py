"""Anthropic API client — lazy singleton for Claude LLM calls."""

from __future__ import annotations

import anthropic

from app.config import settings

# ── Module-level client (lazy singleton) ──

_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    """Return a shared async Anthropic client, creating on first call."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client
