"""Capture node — routes to the appropriate screenshot strategy."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from app.services.screenshot import (
    capture_readme_images,
    capture_sandbox_screenshot,
    generate_project_card,
)
from app.state import AgentState

logger = logging.getLogger(__name__)


async def capture(state: AgentState) -> dict[str, Any]:
    """Route to the appropriate screenshot strategy based on analysis."""
    writer = get_stream_writer()
    writer({"stage": "capturing", "message": "Capturing screenshots…"})

    analysis = state.get("analysis")
    if not analysis:
        return {
            "error": "No analysis available — analyze may have failed.",
            "current_stage": "capturing",
        }

    repo_context = state.get("repo_context")
    if not repo_context:
        return {
            "error": "No repo context available — ingest may have failed.",
            "current_stage": "capturing",
        }

    try:
        metadata = repo_context.get("metadata", {})
        strategy = analysis.get("screenshot_strategy", "project_card")
        run_id = state.get("run_id", "unknown")

        # Common kwargs for project card / sandbox fallback
        card_kwargs = {
            "name": metadata.get("name", "Unknown Project"),
            "description": analysis.get("summary", metadata.get("description", "")),
            "tech_stack": analysis.get("tech_stack", []),
            "stars": metadata.get("stars", 0),
            "language": metadata.get("language", ""),
            "key_features": analysis.get("key_features", []),
            "run_id": run_id,
        }

        writer({
            "stage": "capturing",
            "message": f"Using {strategy} strategy…",
        })

        screenshots: list[dict] = []

        if strategy == "readme_images":
            image_urls = repo_context.get("images_in_readme", [])
            screenshots = capture_readme_images(image_urls, repo_context.get("url", ""), run_id)
            # Fallback to project card if no valid images were captured
            if not screenshots:
                logger.info("No valid README images, falling back to project card")
                screenshots = generate_project_card(**card_kwargs)

        elif strategy == "sandbox":
            def _emit_stream_url(url: str) -> None:
                writer({"stage": "capturing", "message": "Live sandbox preview available", "stream_url": url})

            sandbox_kwargs = {
                **card_kwargs,
                "repo_url": repo_context.get("url", ""),
                "run_command": analysis.get("run_command", ""),
                "install_command": analysis.get("install_command", ""),
                "expected_port": analysis.get("expected_port"),
                "on_stream_url": _emit_stream_url,
            }
            screenshots = capture_sandbox_screenshot(**sandbox_kwargs)
            writer({"stage": "capturing", "message": "Screenshot captured", "stream_url": None})
            if not screenshots:
                logger.info("Sandbox capture returned no screenshots, falling back to project card")
                screenshots = generate_project_card(**card_kwargs)

        else:  # "project_card" or any default
            screenshots = generate_project_card(**card_kwargs)

        return {
            "screenshots": screenshots,
            "current_stage": "capturing",
        }

    except Exception as exc:
        logger.error("Capture failed: %s", exc)
        return {
            "error": f"Capture failed: {exc}",
            "current_stage": "capturing",
        }
