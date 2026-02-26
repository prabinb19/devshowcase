"""Tests for the analyze node and its helper functions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.nodes.analyze import (
    _build_tool_schema,
    _cap_file_tree,
    _determine_screenshot_strategy,
    _redact_secrets,
    _truncate_readme,
    analyze,
)


# ── Secret redaction tests ──


class TestRedactSecrets:
    def test_redacts_aws_key(self) -> None:
        text = "key = AKIAIOSFODNN7EXAMPLE"
        result = _redact_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED_AWS_KEY]" in result

    def test_redacts_github_pat(self) -> None:
        token = "ghp_" + "A" * 40
        text = f"GITHUB_TOKEN={token}"
        result = _redact_secrets(text)
        assert token not in result
        assert "[REDACTED_GITHUB_TOKEN]" in result

    def test_redacts_openai_key(self) -> None:
        text = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456"
        result = _redact_secrets(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[REDACTED_OPENAI_KEY]" in result

    def test_redacts_pem_key(self) -> None:
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIBogIBAAJBALRiMLAH...fake\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = _redact_secrets(text)
        assert "BEGIN RSA PRIVATE KEY" not in result
        assert "[REDACTED_PEM_KEY]" in result

    def test_redacts_generic_api_key(self) -> None:
        text = 'api_key = "super_secret_value_1234"'
        result = _redact_secrets(text)
        assert "super_secret_value_1234" not in result
        assert "[REDACTED]" in result

    def test_preserves_normal_text(self) -> None:
        text = "This is a normal README with no secrets."
        assert _redact_secrets(text) == text


# ── README truncation tests ──


class TestTruncateReadme:
    def test_short_readme_unchanged(self) -> None:
        short = "# Hello\nThis is short."
        assert _truncate_readme(short) == short

    def test_long_readme_truncated(self) -> None:
        long_readme = "x" * 40_000
        result = _truncate_readme(long_readme)
        assert len(result) < 40_000
        assert result.endswith("[… truncated …]")


# ── File tree capping tests ──


class TestCapFileTree:
    def test_under_limit_unchanged(self) -> None:
        tree = [f"file{i}.py" for i in range(100)]
        assert _cap_file_tree(tree) == tree

    def test_over_limit_capped(self) -> None:
        tree = [f"file{i}.py" for i in range(1000)]
        result = _cap_file_tree(tree)
        assert len(result) == 500


# ── Screenshot strategy tests ──


class TestDetermineScreenshotStrategy:
    def test_web_returns_sandbox(self) -> None:
        assert _determine_screenshot_strategy("web", False, []) == "sandbox"

    def test_has_images_returns_readme_images(self) -> None:
        assert (
            _determine_screenshot_strategy("cli", False, ["img.png"])
            == "readme_images"
        )

    def test_fallback_returns_project_card(self) -> None:
        assert _determine_screenshot_strategy("none", False, []) == "project_card"

    def test_web_takes_priority_over_images(self) -> None:
        assert (
            _determine_screenshot_strategy("web", True, ["img.png"]) == "sandbox"
        )


# ── Tool schema tests ──


class TestBuildToolSchema:
    def test_has_required_fields(self) -> None:
        schema = _build_tool_schema()
        assert schema["name"] == "extract_project_analysis"
        props = schema["input_schema"]["properties"]
        assert "project_type" in props
        assert "summary" in props
        assert "tech_stack" in props
        assert "key_features" in props
        assert "visual_type" in props

    def test_excludes_screenshot_strategy(self) -> None:
        schema = _build_tool_schema()
        props = schema["input_schema"]["properties"]
        assert "screenshot_strategy" not in props
        required = schema["input_schema"].get("required", [])
        assert "screenshot_strategy" not in required


# ── Analyze node integration tests ──


def _make_tool_response(tool_input: dict) -> MagicMock:
    """Create a mock Anthropic response with a tool_use content block."""
    tool_block = SimpleNamespace(type="tool_use", input=tool_input)
    response = MagicMock()
    response.content = [tool_block]
    return response


def _sample_repo_context() -> dict:
    return {
        "url": "https://github.com/owner/myrepo",
        "metadata": {
            "name": "myrepo",
            "description": "A cool project",
            "language": "Python",
            "stars": 42,
            "topics": ["web"],
        },
        "readme": "# My Repo\nA web app built with FastAPI.",
        "file_tree": ["README.md", "main.py", "requirements.txt"],
        "config_files": {"requirements.txt": "fastapi>=0.100"},
        "images_in_readme": [],
    }


class TestAnalyzeNode:
    async def test_successful_analysis(self) -> None:
        tool_output = {
            "project_type": "api",
            "summary": "A FastAPI web service for managing tasks.",
            "tech_stack": ["FastAPI", "Python 3.11", "Uvicorn"],
            "key_features": ["REST API", "Async support", "Auto docs"],
            "run_command": "uvicorn main:app",
            "install_command": "pip install -r requirements.txt",
            "expected_port": 8000,
            "has_dockerfile": False,
            "visual_type": "none",
        }
        mock_response = _make_tool_response(tool_output)

        with (
            patch("app.nodes.analyze.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.analyze.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {"repo_context": _sample_repo_context()}
            result = await analyze(state)

        assert "error" not in result
        analysis = result["analysis"]
        assert analysis["project_type"] == "api"
        assert analysis["summary"] == "A FastAPI web service for managing tasks."
        assert "FastAPI" in analysis["tech_stack"]
        assert analysis["screenshot_strategy"] == "project_card"

    async def test_missing_repo_context_returns_error(self) -> None:
        with patch("app.nodes.analyze.get_stream_writer") as mock_writer:
            mock_writer.return_value = lambda x: None
            result = await analyze({})

        assert "error" in result
        assert "No repo context" in result["error"]

    async def test_api_error_returns_error(self) -> None:
        with (
            patch("app.nodes.analyze.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.analyze.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {"repo_context": _sample_repo_context()}
            result = await analyze(state)

        assert "error" in result
        assert "API rate limit exceeded" in result["error"]

    async def test_no_tool_use_block_returns_error(self) -> None:
        text_block = SimpleNamespace(type="text", text="Sorry, I can't do that.")
        response = MagicMock()
        response.content = [text_block]

        with (
            patch("app.nodes.analyze.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.analyze.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {"repo_context": _sample_repo_context()}
            result = await analyze(state)

        assert "error" in result
        assert "did not return structured data" in result["error"]

    async def test_web_visual_type_gets_sandbox_strategy(self) -> None:
        tool_output = {
            "project_type": "web",
            "summary": "A React dashboard.",
            "tech_stack": ["React", "TypeScript"],
            "key_features": ["Dashboard", "Charts"],
            "run_command": "npm start",
            "install_command": "npm install",
            "expected_port": 3000,
            "has_dockerfile": False,
            "visual_type": "web",
        }
        mock_response = _make_tool_response(tool_output)

        with (
            patch("app.nodes.analyze.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.analyze.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {"repo_context": _sample_repo_context()}
            result = await analyze(state)

        assert result["analysis"]["screenshot_strategy"] == "sandbox"
