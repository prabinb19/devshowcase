"""Ingest node — fetches repo metadata, README, file tree."""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from app.state import AgentState


async def ingest(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    writer({"stage": "ingesting", "message": "Fetching repository data…"})

    # Stub: return placeholder context
    return {
        "current_stage": "ingesting",
        "repo_context": {
            "url": state.get("repo_url", ""),
            "metadata": {"name": "stub-repo", "description": "Stub data"},
            "readme": "# Stub README",
            "file_tree": ["README.md", "src/main.py"],
            "config_files": {},
            "images_in_readme": [],
        },
    }
