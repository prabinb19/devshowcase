"""Capture node — takes screenshots of the running project."""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from app.state import AgentState


async def capture(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    writer({"stage": "capturing", "message": "Capturing screenshots…"})

    # Stub: return placeholder screenshots
    return {
        "current_stage": "capturing",
        "screenshots": [
            {
                "url": "https://placeholder.dev/screenshot.png",
                "alt_text": "Stub screenshot",
                "source": "stub",
                "width": 1280,
                "height": 720,
            }
        ],
    }
