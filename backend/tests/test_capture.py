"""Tests for capture node, image processor, R2 storage, and screenshot services."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.nodes.capture import capture
from app.services.image_processor import get_dimensions, process_image, validate_image
from app.services.r2_storage import upload_image
from app.services.screenshot.project_card import generate_project_card
from app.services.screenshot.readme_images import (
    _resolve_github_url,
    capture_readme_images,
)
from app.services.screenshot.sandbox import capture_sandbox_screenshot


# ── Helpers ──


def _make_png(width: int = 100, height: int = 100, mode: str = "RGB") -> bytes:
    """Create a minimal valid PNG image."""
    img = Image.new(mode, (width, height), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_rgba_png(width: int = 100, height: int = 100) -> bytes:
    """Create a valid RGBA PNG image."""
    return _make_png(width, height, mode="RGBA")


def _sample_analysis(strategy: str = "project_card") -> dict:
    return {
        "project_type": "web",
        "summary": "A cool web app.",
        "tech_stack": ["React", "TypeScript"],
        "key_features": ["Dashboard", "Charts"],
        "run_command": "npm start",
        "install_command": "npm install",
        "expected_port": 3000,
        "has_dockerfile": False,
        "visual_type": "web",
        "screenshot_strategy": strategy,
    }


def _sample_repo_context(images: list[str] | None = None) -> dict:
    return {
        "url": "https://github.com/owner/myrepo",
        "metadata": {
            "name": "myrepo",
            "description": "A cool project",
            "language": "Python",
            "stars": 42,
            "topics": ["web"],
        },
        "readme": "# My Repo\nA web app.",
        "file_tree": ["README.md", "main.py"],
        "config_files": {},
        "images_in_readme": images or [],
    }


# ══════════════════════════════════════════════════════════════
#  Image Processor
# ══════════════════════════════════════════════════════════════


class TestValidateImage:
    def test_valid_png(self) -> None:
        assert validate_image(_make_png()) is True

    def test_invalid_bytes(self) -> None:
        assert validate_image(b"not an image") is False

    def test_empty_bytes(self) -> None:
        assert validate_image(b"") is False


class TestGetDimensions:
    def test_returns_width_height(self) -> None:
        w, h = get_dimensions(_make_png(200, 150))
        assert (w, h) == (200, 150)


class TestProcessImage:
    def test_resize_large_image(self) -> None:
        big = _make_png(2400, 1800)
        result = process_image(big, max_width=1200, max_height=1200)
        w, h = get_dimensions(result)
        assert w <= 1200
        assert h <= 1200

    def test_preserves_aspect_ratio(self) -> None:
        # 2000x1000 → max 1200 → should become 1200x600
        big = _make_png(2000, 1000)
        result = process_image(big, max_width=1200, max_height=1200)
        w, h = get_dimensions(result)
        assert w == 1200
        assert h == 600

    def test_small_image_not_upscaled(self) -> None:
        small = _make_png(100, 50)
        result = process_image(small, max_width=1200, max_height=1200)
        w, h = get_dimensions(result)
        assert (w, h) == (100, 50)

    def test_rgba_to_rgb_for_jpeg(self) -> None:
        rgba = _make_rgba_png()
        result = process_image(rgba, output_format="JPEG")
        img = Image.open(io.BytesIO(result))
        assert img.mode == "RGB"

    def test_output_is_valid_image(self) -> None:
        result = process_image(_make_png(800, 600))
        assert validate_image(result) is True


# ══════════════════════════════════════════════════════════════
#  R2 Storage
# ══════════════════════════════════════════════════════════════


class TestUploadImage:
    @patch("app.services.r2_storage._get_r2_client")
    @patch("app.services.r2_storage.settings")
    def test_calls_put_object(self, mock_settings: MagicMock, mock_get_client: MagicMock) -> None:
        mock_settings.r2_bucket_name = "test-bucket"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        data = b"fake image bytes"
        url = upload_image(data, "run-123", "screenshot.png")

        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"].startswith("screenshots/run-123/")
        assert call_kwargs["Key"].endswith("_screenshot.png")
        assert call_kwargs["ContentType"] == "image/png"

    @patch("app.services.r2_storage._get_r2_client")
    @patch("app.services.r2_storage.settings")
    def test_returns_public_url(self, mock_settings: MagicMock, mock_get_client: MagicMock) -> None:
        mock_settings.r2_bucket_name = "test-bucket"
        mock_get_client.return_value = MagicMock()

        url = upload_image(b"image data", "run-456", "img.png")
        assert "test-bucket.r2.dev" in url
        assert "run-456" in url

    @patch("app.services.r2_storage._get_r2_client")
    @patch("app.services.r2_storage.settings")
    def test_content_hash_dedup(self, mock_settings: MagicMock, mock_get_client: MagicMock) -> None:
        mock_settings.r2_bucket_name = "bucket"
        mock_get_client.return_value = MagicMock()

        # Same content → same hash in key
        url1 = upload_image(b"same data", "run-1", "a.png")
        url2 = upload_image(b"same data", "run-1", "a.png")
        assert url1 == url2

        # Different content → different hash
        url3 = upload_image(b"different data", "run-1", "a.png")
        assert url3 != url1


# ══════════════════════════════════════════════════════════════
#  README Images
# ══════════════════════════════════════════════════════════════


class TestResolveGithubUrl:
    def test_absolute_url_unchanged(self) -> None:
        url = "https://example.com/img.png"
        assert _resolve_github_url(url, "https://github.com/o/r") == url

    def test_relative_url_resolved(self) -> None:
        result = _resolve_github_url("docs/logo.png", "https://github.com/owner/repo")
        assert result == "https://raw.githubusercontent.com/owner/repo/HEAD/docs/logo.png"

    def test_github_blob_url_converted(self) -> None:
        blob_url = "https://github.com/owner/repo/blob/main/assets/img.png"
        result = _resolve_github_url(blob_url, "https://github.com/owner/repo")
        assert "raw.githubusercontent.com" in result
        assert "/blob/" not in result

    def test_dot_slash_relative(self) -> None:
        result = _resolve_github_url("./images/screenshot.png", "https://github.com/o/r")
        assert "raw.githubusercontent.com" in result
        assert "screenshot.png" in result


class TestCaptureReadmeImages:
    @patch("app.services.screenshot.readme_images.upload_image")
    @patch("app.services.screenshot.readme_images.httpx.Client")
    def test_happy_path(self, mock_client_cls: MagicMock, mock_upload: MagicMock) -> None:
        png_bytes = _make_png()
        mock_resp = MagicMock()
        mock_resp.content = png_bytes
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        mock_upload.return_value = "https://bucket.r2.dev/screenshots/run/hash_img.png"

        result = capture_readme_images(
            ["https://example.com/img.png"],
            "https://github.com/o/r",
            "run-1",
        )

        assert len(result) == 1
        assert result[0]["source"] == "readme"
        assert result[0]["url"].startswith("https://")

    @patch("app.services.screenshot.readme_images.upload_image")
    @patch("app.services.screenshot.readme_images.httpx.Client")
    def test_skips_invalid_image(self, mock_client_cls: MagicMock, mock_upload: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.content = b"not an image"
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        result = capture_readme_images(
            ["https://example.com/bad.txt"],
            "https://github.com/o/r",
            "run-1",
        )

        assert len(result) == 0
        mock_upload.assert_not_called()

    @patch("app.services.screenshot.readme_images.upload_image")
    @patch("app.services.screenshot.readme_images.httpx.Client")
    def test_caps_at_three(self, mock_client_cls: MagicMock, mock_upload: MagicMock) -> None:
        png_bytes = _make_png()
        mock_resp = MagicMock()
        mock_resp.content = png_bytes
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        mock_upload.return_value = "https://bucket.r2.dev/img.png"

        urls = [f"https://example.com/img{i}.png" for i in range(5)]
        result = capture_readme_images(urls, "https://github.com/o/r", "run-1")

        assert len(result) == 3

    @patch("app.services.screenshot.readme_images.httpx.Client")
    def test_handles_download_failure(self, mock_client_cls: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client_cls.return_value = mock_client

        result = capture_readme_images(
            ["https://example.com/broken.png"],
            "https://github.com/o/r",
            "run-1",
        )

        assert len(result) == 0


# ══════════════════════════════════════════════════════════════
#  Project Card
# ══════════════════════════════════════════════════════════════


class TestGenerateProjectCard:
    @patch("app.services.screenshot.project_card.upload_image")
    def test_generates_valid_png(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = "https://bucket.r2.dev/card.png"

        result = generate_project_card(
            name="MyProject",
            description="A great project",
            tech_stack=["Python", "FastAPI"],
            stars=100,
            language="Python",
            key_features=["Fast", "Reliable"],
            run_id="run-1",
        )

        assert len(result) == 1
        assert result[0]["source"] == "project_card"
        assert result[0]["width"] == 1200
        assert result[0]["height"] == 630

        # Verify upload was called with valid PNG bytes
        upload_call = mock_upload.call_args
        uploaded_bytes = upload_call[0][0]
        assert validate_image(uploaded_bytes) is True

    @patch("app.services.screenshot.project_card.upload_image")
    def test_handles_missing_fields(self, mock_upload: MagicMock) -> None:
        mock_upload.return_value = "https://bucket.r2.dev/card.png"

        result = generate_project_card(
            name="Minimal",
            description="",
            tech_stack=[],
            stars=0,
            language="",
            key_features=[],
            run_id="run-1",
        )

        assert len(result) == 1
        assert result[0]["source"] == "project_card"


# ══════════════════════════════════════════════════════════════
#  Sandbox (E2B Desktop)
# ══════════════════════════════════════════════════════════════

_SANDBOX_CARD_KWARGS = {
    "name": "WebApp",
    "description": "A web app",
    "tech_stack": ["React"],
    "stars": 50,
    "language": "TypeScript",
    "key_features": ["SPA"],
    "run_id": "run-1",
}

_SANDBOX_FULL_KWARGS = {
    **_SANDBOX_CARD_KWARGS,
    "repo_url": "https://github.com/owner/repo",
    "run_command": "npm start",
    "install_command": "npm install",
    "expected_port": 3000,
}


class TestCaptureSandboxScreenshot:
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_missing_repo_url_falls_back(self, mock_card: MagicMock) -> None:
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]
        result = capture_sandbox_screenshot(**{**_SANDBOX_FULL_KWARGS, "repo_url": ""})
        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"

    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_missing_run_command_falls_back(self, mock_card: MagicMock) -> None:
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]
        result = capture_sandbox_screenshot(**{**_SANDBOX_FULL_KWARGS, "run_command": ""})
        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"

    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_missing_expected_port_falls_back(self, mock_card: MagicMock) -> None:
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]
        result = capture_sandbox_screenshot(**{**_SANDBOX_FULL_KWARGS, "expected_port": None})
        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_missing_api_key_falls_back(self, mock_card: MagicMock, mock_settings: MagicMock) -> None:
        mock_settings.e2b_api_key = ""
        mock_settings.github_token = ""
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]
        result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)
        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_import_error_falls_back(self, mock_card: MagicMock, mock_settings: MagicMock) -> None:
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]

        import builtins
        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "e2b_desktop":
                raise ImportError("No module named 'e2b_desktop'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_happy_path(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"

        png_bytes = _make_png(1280, 800)

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        assert len(result) == 1
        assert result[0]["source"] == "sandbox"
        assert result[0]["url"] == "https://r2.dev/sandbox.png"
        assert result[0]["width"] > 0
        assert result[0]["height"] > 0
        mock_card.assert_not_called()
        mock_desktop.kill.assert_called_once()

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_sandbox_exception_falls_back(self, mock_card: MagicMock, mock_settings: MagicMock) -> None:
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.side_effect = RuntimeError("Sandbox creation failed")

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"

    @patch("app.services.screenshot.sandbox.time")
    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_port_never_ready_falls_back(
        self, mock_card: MagicMock, mock_settings: MagicMock, mock_time: MagicMock,
    ) -> None:
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]
        mock_time.sleep = MagicMock()

        # Clone/install succeed, but curl always returns 000 (port not ready)
        clone_result = MagicMock(exit_code=0, stderr="")
        install_result = MagicMock(exit_code=0, stderr="")
        curl_result = MagicMock(exit_code=1, stdout="000", stderr="")

        mock_commands = MagicMock()
        mock_commands.run.side_effect = [clone_result, install_result, MagicMock()] + [curl_result] * 25

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        mock_card.assert_called_once()
        assert result[0]["source"] == "project_card"
        mock_desktop.kill.assert_called_once()

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_stream_callback_invoked(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        """Verify on_stream_url callback is called with the stream URL."""
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"
        png_bytes = _make_png(1280, 800)

        mock_stream = MagicMock()
        mock_stream.get_auth_key.return_value = "auth-key-123"
        mock_stream.get_url.return_value = "https://e2b.dev/stream?auth=auth-key-123"

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.stream = mock_stream
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        callback = MagicMock()

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS, on_stream_url=callback)

        callback.assert_called_once_with("https://e2b.dev/stream?auth=auth-key-123")
        mock_stream.start.assert_called_once_with(require_auth=True)
        assert result[0]["source"] == "sandbox"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_stream_failure_nonfatal(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        """Verify stream failure doesn't prevent screenshot capture."""
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"
        png_bytes = _make_png(1280, 800)

        mock_stream = MagicMock()
        mock_stream.start.side_effect = RuntimeError("Stream failed")

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.stream = mock_stream
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        callback = MagicMock()

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS, on_stream_url=callback)

        callback.assert_not_called()
        assert len(result) == 1
        assert result[0]["source"] == "sandbox"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_no_callback_skips_streaming(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        """Verify stream.start() is never called when on_stream_url is None."""
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"
        png_bytes = _make_png(1280, 800)

        mock_stream = MagicMock()

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.stream = mock_stream
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            result = capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        mock_stream.start.assert_not_called()
        assert result[0]["source"] == "sandbox"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_custom_template_passed_to_sandbox(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        """Verify Sandbox.create() receives template when e2b_template_id is set."""
        mock_settings.e2b_api_key = "test-key"
        mock_settings.e2b_template_id = "custom-tpl"
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"
        png_bytes = _make_png(1280, 800)

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        call_kwargs = mock_sandbox_cls.create.call_args[1]
        assert call_kwargs["template"] == "custom-tpl"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_no_template_uses_default(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        """Verify Sandbox.create() has no template key when e2b_template_id is empty."""
        mock_settings.e2b_api_key = "test-key"
        mock_settings.e2b_template_id = ""
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"
        png_bytes = _make_png(1280, 800)

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        call_kwargs = mock_sandbox_cls.create.call_args[1]
        assert "template" not in call_kwargs

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.upload_image")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_env_vars_passed_to_sandbox(
        self, mock_card: MagicMock, mock_upload: MagicMock, mock_settings: MagicMock,
    ) -> None:
        """Verify envs dict is passed to Sandbox.create()."""
        mock_settings.e2b_api_key = "test-key"
        mock_settings.e2b_template_id = ""
        mock_settings.github_token = ""
        mock_upload.return_value = "https://r2.dev/sandbox.png"
        png_bytes = _make_png(1280, 800)

        mock_commands = MagicMock()
        mock_commands.run.return_value = MagicMock(exit_code=0, stdout="200", stderr="")

        mock_desktop = MagicMock()
        mock_desktop.commands = mock_commands
        mock_desktop.screenshot.return_value = png_bytes

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        call_kwargs = mock_sandbox_cls.create.call_args[1]
        assert call_kwargs["envs"]["CI"] == "true"
        assert call_kwargs["envs"]["BROWSER"] == "none"

    @patch("app.services.screenshot.sandbox.settings")
    @patch("app.services.screenshot.sandbox.generate_project_card")
    def test_cleanup_called_on_exception(self, mock_card: MagicMock, mock_settings: MagicMock) -> None:
        mock_settings.e2b_api_key = "test-key"
        mock_settings.github_token = ""
        mock_card.return_value = [{"url": "https://r2/card.png", "source": "project_card"}]

        mock_desktop = MagicMock()
        mock_desktop.commands.run.side_effect = RuntimeError("Clone exploded")

        mock_sandbox_cls = MagicMock()
        mock_sandbox_cls.create.return_value = mock_desktop

        with patch.dict("sys.modules", {"e2b_desktop": MagicMock(Sandbox=mock_sandbox_cls)}):
            capture_sandbox_screenshot(**_SANDBOX_FULL_KWARGS)

        mock_desktop.kill.assert_called_once()


# ══════════════════════════════════════════════════════════════
#  Capture Node
# ══════════════════════════════════════════════════════════════


class TestCaptureNode:
    async def test_routes_to_project_card(self) -> None:
        with (
            patch("app.nodes.capture.get_stream_writer") as mock_writer,
            patch("app.nodes.capture.generate_project_card") as mock_card,
        ):
            mock_writer.return_value = lambda x: None
            mock_card.return_value = [
                {"url": "https://r2/card.png", "source": "project_card", "width": 1200, "height": 630}
            ]

            state = {
                "analysis": _sample_analysis("project_card"),
                "repo_context": _sample_repo_context(),
                "run_id": "run-1",
            }
            result = await capture(state)

        assert "error" not in result
        assert len(result["screenshots"]) == 1
        assert result["screenshots"][0]["source"] == "project_card"

    async def test_routes_to_sandbox(self) -> None:
        with (
            patch("app.nodes.capture.get_stream_writer") as mock_writer,
            patch("app.nodes.capture.capture_sandbox_screenshot") as mock_sandbox,
        ):
            mock_writer.return_value = lambda x: None
            mock_sandbox.return_value = [
                {"url": "https://r2/card.png", "source": "project_card", "width": 1200, "height": 630}
            ]

            state = {
                "analysis": _sample_analysis("sandbox"),
                "repo_context": _sample_repo_context(),
                "run_id": "run-1",
            }
            result = await capture(state)

        assert "error" not in result
        mock_sandbox.assert_called_once()
        # Verify sandbox kwargs are forwarded from analysis/repo_context
        call_kwargs = mock_sandbox.call_args[1]
        assert call_kwargs["repo_url"] == "https://github.com/owner/myrepo"
        assert call_kwargs["run_command"] == "npm start"
        assert call_kwargs["install_command"] == "npm install"
        assert call_kwargs["expected_port"] == 3000

    async def test_sandbox_fallback_to_card(self) -> None:
        with (
            patch("app.nodes.capture.get_stream_writer") as mock_writer,
            patch("app.nodes.capture.capture_sandbox_screenshot") as mock_sandbox,
            patch("app.nodes.capture.generate_project_card") as mock_card,
        ):
            mock_writer.return_value = lambda x: None
            mock_sandbox.return_value = []  # Empty = sandbox failed
            mock_card.return_value = [
                {"url": "https://r2/card.png", "source": "project_card", "width": 1200, "height": 630}
            ]

            state = {
                "analysis": _sample_analysis("sandbox"),
                "repo_context": _sample_repo_context(),
                "run_id": "run-1",
            }
            result = await capture(state)

        assert "error" not in result
        assert result["screenshots"][0]["source"] == "project_card"
        mock_card.assert_called_once()

    async def test_routes_to_readme_images(self) -> None:
        with (
            patch("app.nodes.capture.get_stream_writer") as mock_writer,
            patch("app.nodes.capture.capture_readme_images") as mock_readme,
        ):
            mock_writer.return_value = lambda x: None
            mock_readme.return_value = [
                {"url": "https://r2/img.png", "source": "readme", "width": 800, "height": 600}
            ]

            state = {
                "analysis": _sample_analysis("readme_images"),
                "repo_context": _sample_repo_context(images=["https://example.com/img.png"]),
                "run_id": "run-1",
            }
            result = await capture(state)

        assert "error" not in result
        assert result["screenshots"][0]["source"] == "readme"

    async def test_readme_fallback_to_card(self) -> None:
        with (
            patch("app.nodes.capture.get_stream_writer") as mock_writer,
            patch("app.nodes.capture.capture_readme_images") as mock_readme,
            patch("app.nodes.capture.generate_project_card") as mock_card,
        ):
            mock_writer.return_value = lambda x: None
            mock_readme.return_value = []  # No valid images captured
            mock_card.return_value = [
                {"url": "https://r2/card.png", "source": "project_card", "width": 1200, "height": 630}
            ]

            state = {
                "analysis": _sample_analysis("readme_images"),
                "repo_context": _sample_repo_context(images=["https://example.com/bad.txt"]),
                "run_id": "run-1",
            }
            result = await capture(state)

        assert "error" not in result
        assert result["screenshots"][0]["source"] == "project_card"

    async def test_capture_node_emits_stream_url(self) -> None:
        """Verify capture node emits stream_url via writer when sandbox callback is invoked."""
        written: list[dict] = []

        def fake_writer(data: dict) -> None:
            written.append(data)

        def fake_sandbox(**kwargs: object) -> list[dict]:
            # Simulate the sandbox invoking the callback
            cb = kwargs.get("on_stream_url")
            if cb:
                cb("https://e2b.dev/stream?auth=xyz")
            return [{"url": "https://r2/sandbox.png", "source": "sandbox", "width": 1280, "height": 800}]

        with (
            patch("app.nodes.capture.get_stream_writer") as mock_writer,
            patch("app.nodes.capture.capture_sandbox_screenshot", side_effect=fake_sandbox) as mock_sandbox,
        ):
            mock_writer.return_value = fake_writer

            state = {
                "analysis": _sample_analysis("sandbox"),
                "repo_context": _sample_repo_context(),
                "run_id": "run-1",
            }
            result = await capture(state)

        assert "error" not in result
        # Check that stream_url was emitted
        stream_events = [w for w in written if w.get("stream_url") is not None]
        assert len(stream_events) >= 1
        assert stream_events[0]["stream_url"] == "https://e2b.dev/stream?auth=xyz"
        # Check that stream_url=None was emitted to signal teardown
        teardown_events = [w for w in written if "stream_url" in w and w["stream_url"] is None]
        assert len(teardown_events) >= 1

    async def test_missing_analysis_returns_error(self) -> None:
        with patch("app.nodes.capture.get_stream_writer") as mock_writer:
            mock_writer.return_value = lambda x: None
            result = await capture({"repo_context": _sample_repo_context()})

        assert "error" in result
        assert "No analysis" in result["error"]

    async def test_missing_repo_context_returns_error(self) -> None:
        with patch("app.nodes.capture.get_stream_writer") as mock_writer:
            mock_writer.return_value = lambda x: None
            result = await capture({"analysis": _sample_analysis()})

        assert "error" in result
        assert "No repo context" in result["error"]
