"""Analyze node — determines project type, tech stack, and build strategy."""

from __future__ import annotations

from typing import Any

from langgraph.config import get_stream_writer

from app.state import AgentState


async def analyze(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    writer({"stage": "analyzing", "message": "Analyzing project structure…"})

    # Stub: return placeholder analysis
    return {
        "current_stage": "analyzing",
        "analysis": {
            "project_type": "web",
            "summary": "Stub analysis",
            "tech_stack": ["python"],
            "key_features": [],
            "run_command": "python main.py",
            "install_command": "pip install -r requirements.txt",
            "expected_port": 8000,
            "has_dockerfile": False,
            "visual_type": "web",
            "screenshot_strategy": "browser",
        },
    }
