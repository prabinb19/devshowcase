"""Tests for the generate node and its helper functions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


from app.nodes.generate import (
    _build_tool_schema,
    _build_user_message,
    generate,
)


# ── Tool schema tests ──


class TestBuildToolSchema:
    def test_has_expected_fields(self) -> None:
        schema = _build_tool_schema()
        assert schema["name"] == "generate_linkedin_post"
        props = schema["input_schema"]["properties"]
        assert "body" in props
        assert "first_comment" in props
        assert "alt_texts" in props

    def test_excludes_programmatic_fields(self) -> None:
        schema = _build_tool_schema()
        props = schema["input_schema"]["properties"]
        assert "platform" not in props
        assert "status" not in props
        assert "screenshot_urls" not in props
        required = schema["input_schema"].get("required", [])
        assert "platform" not in required
        assert "status" not in required
        assert "screenshot_urls" not in required


# ── User message tests ──


def _sample_analysis() -> dict:
    return {
        "project_type": "web",
        "summary": "A real-time dashboard for monitoring IoT devices.",
        "tech_stack": ["React", "FastAPI", "PostgreSQL"],
        "key_features": ["Live data streaming", "Alert rules", "Device management"],
    }


def _sample_screenshots() -> list[dict]:
    return [
        {
            "url": "https://cdn.example.com/shot1.png",
            "alt_text": "Dashboard overview",
            "source": "sandbox",
        },
        {
            "url": "https://cdn.example.com/shot2.png",
            "alt_text": "",
            "source": "readme",
        },
    ]


def _sample_repo_context() -> dict:
    return {
        "url": "https://github.com/owner/iot-dash",
        "metadata": {
            "name": "iot-dash",
            "description": "IoT monitoring dashboard",
            "language": "TypeScript",
            "stars": 120,
            "topics": ["iot", "dashboard"],
        },
        "readme": "# IoT Dashboard",
        "file_tree": ["README.md", "src/App.tsx"],
        "config_files": {},
        "images_in_readme": [],
    }


class TestBuildUserMessage:
    def test_includes_project_info(self) -> None:
        msg = _build_user_message(_sample_analysis(), [], _sample_repo_context())
        assert "iot-dash" in msg
        assert "real-time dashboard" in msg
        assert "React" in msg
        assert "FastAPI" in msg

    def test_includes_repo_url(self) -> None:
        msg = _build_user_message(_sample_analysis(), [], _sample_repo_context())
        assert "https://github.com/owner/iot-dash" in msg

    def test_includes_screenshots(self) -> None:
        msg = _build_user_message(
            _sample_analysis(), _sample_screenshots(), _sample_repo_context()
        )
        assert "2 available" in msg
        assert "Dashboard overview" in msg

    def test_includes_key_features(self) -> None:
        msg = _build_user_message(_sample_analysis(), [], _sample_repo_context())
        assert "Live data streaming" in msg
        assert "Alert rules" in msg


# ── Generate node integration tests ──


def _make_tool_response(tool_input: dict) -> MagicMock:
    """Create a mock Anthropic response with a tool_use content block."""
    tool_block = SimpleNamespace(type="tool_use", input=tool_input)
    response = MagicMock()
    response.content = [tool_block]
    return response


class TestGenerateNode:
    async def test_successful_generation(self) -> None:
        tool_output = {
            "body": "I built an IoT monitoring dashboard that updates in real time.",
            "first_comment": "https://github.com/owner/iot-dash\n\nStar it if you find it useful!",
            "alt_texts": ["Dashboard with live charts", "Device management panel"],
        }
        mock_response = _make_tool_response(tool_output)

        with (
            patch("app.nodes.generate.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.generate.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {
                "analysis": _sample_analysis(),
                "screenshots": _sample_screenshots(),
                "repo_context": _sample_repo_context(),
            }
            result = await generate(state)

        assert "error" not in result
        draft = result["post_draft"]
        assert draft["platform"] == "linkedin"
        assert draft["status"] == "draft"
        assert "IoT monitoring dashboard" in draft["body"]
        assert "github.com/owner/iot-dash" in draft["first_comment"]
        assert len(draft["alt_texts"]) == 2
        # screenshot_urls come from state, not LLM
        assert draft["screenshot_urls"] == [
            "https://cdn.example.com/shot1.png",
            "https://cdn.example.com/shot2.png",
        ]

    async def test_missing_analysis_returns_error(self) -> None:
        with patch("app.nodes.generate.get_stream_writer") as mock_writer:
            mock_writer.return_value = lambda x: None
            result = await generate({"screenshots": []})

        assert "error" in result
        assert "No analysis" in result["error"]

    async def test_missing_screenshots_returns_error(self) -> None:
        with patch("app.nodes.generate.get_stream_writer") as mock_writer:
            mock_writer.return_value = lambda x: None
            result = await generate({"analysis": _sample_analysis()})

        assert "error" in result
        assert "No screenshots" in result["error"]

    async def test_api_error_returns_error(self) -> None:
        with (
            patch("app.nodes.generate.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.generate.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(
                side_effect=Exception("API rate limit exceeded")
            )
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {
                "analysis": _sample_analysis(),
                "screenshots": _sample_screenshots(),
                "repo_context": _sample_repo_context(),
            }
            result = await generate(state)

        assert "error" in result
        assert "API rate limit exceeded" in result["error"]

    async def test_no_tool_use_block_returns_error(self) -> None:
        text_block = SimpleNamespace(type="text", text="I cannot generate a post.")
        response = MagicMock()
        response.content = [text_block]

        with (
            patch("app.nodes.generate.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.generate.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {
                "analysis": _sample_analysis(),
                "screenshots": _sample_screenshots(),
                "repo_context": _sample_repo_context(),
            }
            result = await generate(state)

        assert "error" in result
        assert "did not return structured data" in result["error"]


# ── Content validation tests ──


class TestContentValidation:
    async def test_body_truncated_to_max(self) -> None:
        long_body = "x" * 4000
        tool_output = {
            "body": long_body,
            "first_comment": "https://github.com/owner/repo",
            "alt_texts": [],
        }
        mock_response = _make_tool_response(tool_output)

        with (
            patch("app.nodes.generate.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.generate.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {
                "analysis": _sample_analysis(),
                "screenshots": [],
                "repo_context": _sample_repo_context(),
            }
            result = await generate(state)

        assert len(result["post_draft"]["body"]) <= 3000

    async def test_alt_texts_truncated_to_max(self) -> None:
        long_alt = "A" * 200
        tool_output = {
            "body": "Short post.",
            "first_comment": "https://github.com/owner/repo",
            "alt_texts": [long_alt, "Short alt"],
        }
        mock_response = _make_tool_response(tool_output)

        with (
            patch("app.nodes.generate.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.generate.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {
                "analysis": _sample_analysis(),
                "screenshots": _sample_screenshots(),
                "repo_context": _sample_repo_context(),
            }
            result = await generate(state)

        alt_texts = result["post_draft"]["alt_texts"]
        assert all(len(alt) <= 125 for alt in alt_texts)

    async def test_empty_screenshots_produces_empty_urls(self) -> None:
        tool_output = {
            "body": "Check out this project.",
            "first_comment": "https://github.com/owner/repo",
            "alt_texts": [],
        }
        mock_response = _make_tool_response(tool_output)

        with (
            patch("app.nodes.generate.get_anthropic_client") as mock_client_fn,
            patch("app.nodes.generate.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.messages.create = AsyncMock(return_value=mock_response)
            mock_client_fn.return_value = client
            mock_writer.return_value = lambda x: None

            state = {
                "analysis": _sample_analysis(),
                "screenshots": [],
                "repo_context": _sample_repo_context(),
            }
            result = await generate(state)

        assert result["post_draft"]["screenshot_urls"] == []
