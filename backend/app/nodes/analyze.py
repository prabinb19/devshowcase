"""Analyze node — calls Claude to produce a structured ProjectAnalysis."""

from __future__ import annotations

import logging
import re
from typing import Any

from langgraph.config import get_stream_writer

from app.config import settings
from app.prompts.analyze import ANALYZE_SYSTEM_PROMPT
from app.services.llm_client import get_anthropic_client
from app.state import AgentState, ProjectAnalysis

logger = logging.getLogger(__name__)

# ── Constants ──

_MAX_README_CHARS = 32_000  # ~8K tokens at 4 chars/token
_MAX_TREE_ENTRIES = 500

# ── Secret redaction patterns ──

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # AWS access key IDs (AKIA...)
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    # GitHub personal access tokens (ghp_, gho_, ghs_, ghr_)
    (re.compile(r"gh[poshru]_[A-Za-z0-9_]{36,255}"), "[REDACTED_GITHUB_TOKEN]"),
    # OpenAI API keys
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_OPENAI_KEY]"),
    # PEM private keys
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |DSA )?PRIVATE KEY-----"
        ),
        "[REDACTED_PEM_KEY]",
    ),
    # Generic key/password/token assignments (key = "...", password: '...')
    (
        re.compile(
            r"""(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['"][^'"]{8,}['"]"""
        ),
        r"\1=[REDACTED]",
    ),
]


# ── Helper functions ──


def _redact_secrets(text: str) -> str:
    """Remove potential secrets from text before sending to LLM."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _truncate_readme(readme: str) -> str:
    """Cap README at ~8K tokens to stay within context budget."""
    if len(readme) <= _MAX_README_CHARS:
        return readme
    return readme[:_MAX_README_CHARS] + "\n\n[… truncated …]"


def _cap_file_tree(tree: list[str]) -> list[str]:
    """Limit file tree to 500 entries."""
    return tree[:_MAX_TREE_ENTRIES]


def _determine_screenshot_strategy(
    visual_type: str,
    has_dockerfile: bool,
    images_in_readme: list[str],
) -> str:
    """Deterministic screenshot strategy — no LLM needed."""
    visual_type = visual_type.lower()
    if visual_type == "web":
        return "sandbox"
    if images_in_readme:
        return "readme_images"
    return "project_card"


def _build_tool_schema() -> dict[str, Any]:
    """Derive tool schema from ProjectAnalysis Pydantic model."""
    schema = ProjectAnalysis.model_json_schema()
    # Remove screenshot_strategy — set deterministically, not by LLM
    properties = {
        k: v
        for k, v in schema.get("properties", {}).items()
        if k != "screenshot_strategy"
    }
    required = [f for f in schema.get("required", []) if f != "screenshot_strategy"]
    return {
        "name": "extract_project_analysis",
        "description": "Extract structured project analysis from repo data.",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _build_user_message(repo_context: dict[str, Any]) -> str:
    """Assemble the user message from repo context components."""
    metadata = repo_context.get("metadata", {})
    readme = _redact_secrets(_truncate_readme(repo_context.get("readme", "")))
    tree = _cap_file_tree(repo_context.get("file_tree", []))
    configs = repo_context.get("config_files", {})

    parts: list[str] = []

    # Metadata section
    parts.append("## Repository Metadata")
    parts.append(f"- Name: {metadata.get('name', 'unknown')}")
    parts.append(f"- Description: {metadata.get('description', 'N/A')}")
    parts.append(f"- Language: {metadata.get('language', 'N/A')}")
    parts.append(f"- Stars: {metadata.get('stars', 0)}")
    topics = metadata.get("topics", [])
    if topics:
        parts.append(f"- Topics: {', '.join(topics)}")

    # README section
    if readme:
        parts.append("\n## README\n")
        parts.append(readme)

    # File tree section
    if tree:
        parts.append("\n## File Tree\n")
        parts.append("\n".join(tree))

    # Config files section
    if configs:
        parts.append("\n## Config Files\n")
        for filename, content in configs.items():
            redacted = _redact_secrets(content)
            parts.append(f"### {filename}\n```\n{redacted}\n```")

    return "\n".join(parts)


# ── Main node ──


async def analyze(state: AgentState) -> dict[str, Any]:
    """Analyze a repo with Claude and return a structured ProjectAnalysis."""
    writer = get_stream_writer()
    writer({"stage": "analyzing", "message": "Analyzing project structure…"})

    repo_context = state.get("repo_context")
    if not repo_context:
        return {
            "error": "No repo context available — ingest may have failed.",
            "current_stage": "analyzing",
        }

    try:
        client = get_anthropic_client()
        user_message = _build_user_message(repo_context)
        tool_schema = _build_tool_schema()

        writer({"stage": "analyzing", "message": "Calling Claude for analysis…"})

        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=ANALYZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": "extract_project_analysis"},
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
                "error": "Analysis failed: model did not return structured data.",
                "current_stage": "analyzing",
            }

        # Set screenshot_strategy deterministically
        tool_result["screenshot_strategy"] = _determine_screenshot_strategy(
            visual_type=tool_result.get("visual_type", "none"),
            has_dockerfile=tool_result.get("has_dockerfile", False),
            images_in_readme=repo_context.get("images_in_readme", []),
        )

        # Validate through Pydantic model
        analysis = ProjectAnalysis(**tool_result)

        return {
            "analysis": analysis.model_dump(),
            "current_stage": "analyzing",
        }

    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        return {
            "error": f"Analysis failed: {exc}",
            "current_stage": "analyzing",
        }
