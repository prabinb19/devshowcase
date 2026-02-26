"""Generate node — creates a LinkedIn post draft via Claude."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer

from app.prompts.generate import GENERATE_SYSTEM_PROMPT
from app.services.llm_client import get_anthropic_client
from app.state import AgentState, PostDraft

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-20250514"
_MAX_BODY_CHARS = 3000
_MAX_ALT_TEXT_CHARS = 125
_MAX_FIRST_COMMENT_CHARS = 500


# ── Helper functions ──


def _build_tool_schema() -> dict[str, Any]:
    """Derive tool schema from PostDraft, keeping only LLM-generated fields."""
    schema = PostDraft.model_json_schema()
    keep = {"body", "first_comment", "alt_texts"}
    properties = {
        k: v for k, v in schema.get("properties", {}).items() if k in keep
    }
    required = [f for f in schema.get("required", []) if f in keep]
    return {
        "name": "generate_linkedin_post",
        "description": "Generate a LinkedIn post draft for the given project.",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _build_user_message(
    analysis: dict[str, Any],
    screenshots: list[dict[str, Any]],
    repo_context: dict[str, Any],
) -> str:
    """Assemble the user message from analysis, screenshots, and repo context."""
    metadata = repo_context.get("metadata", {})
    repo_url = repo_context.get("url", metadata.get("url", ""))

    parts: list[str] = []

    # Project overview
    parts.append("## Project Overview")
    parts.append(f"- Name: {metadata.get('name', 'unknown')}")
    parts.append(f"- Summary: {analysis.get('summary', 'N/A')}")
    parts.append(f"- Type: {analysis.get('project_type', 'N/A')}")

    # Tech stack
    tech_stack = analysis.get("tech_stack", [])
    if tech_stack:
        parts.append(f"- Tech Stack: {', '.join(tech_stack)}")

    # Key features
    features = analysis.get("key_features", [])
    if features:
        parts.append("\n## Key Features")
        for feat in features:
            parts.append(f"- {feat}")

    # Screenshots
    if screenshots:
        parts.append(f"\n## Screenshots ({len(screenshots)} available)")
        for i, shot in enumerate(screenshots, 1):
            alt = shot.get("alt_text", "")
            source = shot.get("source", "")
            desc = alt or source or f"Screenshot {i}"
            parts.append(f"- Screenshot {i}: {desc}")

    # Repo URL for first comment
    if repo_url:
        parts.append(f"\n## Repository URL\n{repo_url}")

    return "\n".join(parts)


# ── Main node ──


async def generate(state: AgentState) -> dict[str, Any]:
    """Generate a LinkedIn post draft from analysis and screenshots."""
    writer = get_stream_writer()
    writer({"stage": "generating", "message": "Generating post draft…"})

    analysis = state.get("analysis")
    if not analysis:
        return {
            "error": "No analysis available — analyze may have failed.",
            "current_stage": "generating",
        }

    screenshots = state.get("screenshots")
    if screenshots is None:
        return {
            "error": "No screenshots available — capture may have failed.",
            "current_stage": "generating",
        }

    repo_context = state.get("repo_context", {})

    try:
        client = get_anthropic_client()
        user_message = _build_user_message(analysis, screenshots, repo_context)
        tool_schema = _build_tool_schema()

        writer({"stage": "generating", "message": "Calling Claude for draft…"})

        response = await client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=GENERATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": "generate_linkedin_post"},
        )

        # Extract the tool_use block
        tool_result: dict[str, Any] | None = None
        for block in response.content:
            if block.type == "tool_use":
                tool_result = block.input
                break

        if tool_result is None:
            logger.error("No tool_use block in Claude response")
            return {
                "error": "Generation failed: model did not return structured data.",
                "current_stage": "generating",
            }

        # Validate and clamp content lengths
        body = tool_result.get("body", "")
        if len(body) > _MAX_BODY_CHARS:
            body = body[:_MAX_BODY_CHARS]

        first_comment = tool_result.get("first_comment", "")
        if len(first_comment) > _MAX_FIRST_COMMENT_CHARS:
            first_comment = first_comment[:_MAX_FIRST_COMMENT_CHARS]

        alt_texts = [
            alt[:_MAX_ALT_TEXT_CHARS]
            for alt in tool_result.get("alt_texts", [])
        ]

        # Assemble PostDraft with programmatic fields
        screenshot_urls = [s.get("url", "") for s in screenshots]
        draft = PostDraft(
            platform="linkedin",
            body=body,
            first_comment=first_comment,
            screenshot_urls=screenshot_urls,
            alt_texts=alt_texts,
            status="draft",
        )

        return {
            "post_draft": draft.model_dump(),
            "current_stage": "generating",
        }

    except Exception as exc:
        logger.error("Generation failed: %s", exc)
        return {
            "error": f"Generation failed: {exc}",
            "current_stage": "generating",
        }
