"""Generate node — creates the social media post draft."""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from app.state import AgentState


async def generate(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    writer({"stage": "generating", "message": "Generating post draft…"})

    # Stub: return placeholder draft
    return {
        "current_stage": "generating",
        "post_draft": {
            "platform": "linkedin",
            "body": "Check out this project!",
            "first_comment": "",
            "screenshot_urls": [],
            "alt_texts": [],
            "status": "draft",
        },
    }
