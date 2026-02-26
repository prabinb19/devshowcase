"""Tests for the ingest node and GitHub client service."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.github_client import (
    extract_readme_images,
    fetch_config_files,
    fetch_file_tree,
    fetch_readme,
    fetch_repo_metadata,
    parse_github_url,
)


# ── URL parsing tests ──


class TestParseGithubUrl:
    def test_valid_url(self) -> None:
        assert parse_github_url("https://github.com/owner/repo") == ("owner", "repo")

    def test_valid_url_with_git_suffix(self) -> None:
        assert parse_github_url("https://github.com/owner/repo.git") == (
            "owner",
            "repo",
        )

    def test_valid_url_trailing_slash(self) -> None:
        assert parse_github_url("https://github.com/owner/repo/") == ("owner", "repo")

    def test_valid_url_http(self) -> None:
        assert parse_github_url("http://github.com/owner/repo") == ("owner", "repo")

    def test_valid_url_with_dots_and_hyphens(self) -> None:
        assert parse_github_url("https://github.com/my-org/my.repo") == (
            "my-org",
            "my.repo",
        )

    def test_invalid_url_no_repo(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub"):
            parse_github_url("https://github.com/owner")

    def test_invalid_url_empty(self) -> None:
        with pytest.raises(ValueError):
            parse_github_url("")

    def test_invalid_url_non_github(self) -> None:
        with pytest.raises(ValueError, match="Only github.com"):
            parse_github_url("https://gitlab.com/owner/repo")

    def test_invalid_url_with_extra_path(self) -> None:
        with pytest.raises(ValueError, match="Invalid GitHub"):
            parse_github_url("https://github.com/owner/repo/tree/main")


# ── SSRF prevention tests ──


class TestSSRFPrevention:
    def test_rejects_localhost(self) -> None:
        with pytest.raises(ValueError, match="Only github.com"):
            parse_github_url("https://localhost/owner/repo")

    def test_rejects_private_ip(self) -> None:
        with pytest.raises(ValueError, match="Only github.com"):
            parse_github_url("https://192.168.1.1/owner/repo")

    def test_rejects_loopback_ip(self) -> None:
        with pytest.raises(ValueError, match="Only github.com"):
            parse_github_url("https://127.0.0.1/owner/repo")

    def test_rejects_other_hosts(self) -> None:
        with pytest.raises(ValueError, match="Only github.com"):
            parse_github_url("https://evil.com/owner/repo")


# ── Metadata fetch tests ──


class TestFetchRepoMetadata:
    async def test_returns_metadata(self) -> None:
        mock_resp = httpx.Response(
            200,
            json={
                "name": "myrepo",
                "description": "A cool project",
                "stargazers_count": 42,
                "forks_count": 5,
                "language": "Python",
                "topics": ["web", "api"],
                "html_url": "https://github.com/owner/myrepo",
                "default_branch": "main",
            },
            request=httpx.Request("GET", "https://api.github.com/repos/owner/myrepo"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_repo_metadata("owner", "myrepo")

        assert result["name"] == "myrepo"
        assert result["description"] == "A cool project"
        assert result["stars"] == 42
        assert result["forks"] == 5
        assert result["language"] == "Python"
        assert result["topics"] == ["web", "api"]
        assert result["default_branch"] == "main"

    async def test_returns_non_standard_default_branch(self) -> None:
        mock_resp = httpx.Response(
            200,
            json={
                "name": "myrepo",
                "description": "A project with develop branch",
                "stargazers_count": 10,
                "forks_count": 1,
                "language": "Go",
                "topics": [],
                "html_url": "https://github.com/owner/myrepo",
                "default_branch": "develop",
            },
            request=httpx.Request("GET", "https://api.github.com/repos/owner/myrepo"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_repo_metadata("owner", "myrepo")

        assert result["default_branch"] == "develop"


# ── README fetch tests ──


class TestFetchReadme:
    async def test_returns_decoded_readme(self) -> None:
        content = base64.b64encode(b"# Hello World\nThis is a README.").decode()
        mock_resp = httpx.Response(
            200,
            json={"content": content, "encoding": "base64"},
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/readme"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_readme("o", "r")

        assert result == "# Hello World\nThis is a README."

    async def test_returns_empty_on_404(self) -> None:
        mock_resp = httpx.Response(
            404,
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/readme"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_readme("o", "r")

        assert result == ""


# ── File tree tests ──


class TestFetchFileTree:
    async def test_returns_paths(self) -> None:
        tree_items = [{"path": f"file{i}.py"} for i in range(5)]
        mock_resp = httpx.Response(
            200,
            json={"tree": tree_items},
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/git/trees/main"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_file_tree("o", "r", "main")

        assert result == [f"file{i}.py" for i in range(5)]

    async def test_caps_at_10k(self) -> None:
        tree_items = [{"path": f"file{i}.py"} for i in range(15_000)]
        mock_resp = httpx.Response(
            200,
            json={"tree": tree_items},
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/git/trees/main"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_file_tree("o", "r", "main")

        assert len(result) == 10_000

    async def test_fallback_to_master(self) -> None:
        not_found = httpx.Response(
            404,
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/git/trees/main"),
        )
        master_resp = httpx.Response(
            200,
            json={"tree": [{"path": "README.md"}]},
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/git/trees/master"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[not_found, master_resp])
            mock_get_client.return_value = client

            result = await fetch_file_tree("o", "r", "main")

        assert result == ["README.md"]


# ── Config file tests ──


class TestFetchConfigFiles:
    async def test_fetches_present_files(self) -> None:
        content = base64.b64encode(b'{"name": "myapp"}').decode()
        mock_resp = httpx.Response(
            200,
            json={"content": content, "encoding": "base64", "size": 100},
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/contents/package.json"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_config_files(
                "o", "r", ["package.json", "src/main.py", "README.md"]
            )

        assert "package.json" in result
        assert result["package.json"] == '{"name": "myapp"}'

    async def test_skips_absent_files(self) -> None:
        """Files not in the tree are not fetched."""
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock()
            mock_get_client.return_value = client

            result = await fetch_config_files(
                "o", "r", ["src/main.py", "README.md"]
            )

        assert result == {}
        client.get.assert_not_called()

    async def test_skips_oversized_files(self) -> None:
        """Files > 50 KB are skipped."""
        mock_resp = httpx.Response(
            200,
            json={"content": "big", "encoding": "base64", "size": 60_000},
            request=httpx.Request("GET", "https://api.github.com/repos/o/r/contents/package.json"),
        )
        with patch(
            "app.services.github_client._get_client"
        ) as mock_get_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = client

            result = await fetch_config_files("o", "r", ["package.json"])

        assert result == {}


# ── Image extraction tests ──


class TestExtractReadmeImages:
    def test_markdown_images(self) -> None:
        md = "![logo](https://example.com/logo.png) and ![alt](img.jpg)"
        result = extract_readme_images(md)
        assert result == ["https://example.com/logo.png", "img.jpg"]

    def test_html_img_tags(self) -> None:
        md = '<img src="https://example.com/pic.png" width="200">'
        result = extract_readme_images(md)
        assert result == ["https://example.com/pic.png"]

    def test_mixed_and_deduplication(self) -> None:
        md = (
            "![logo](https://example.com/logo.png)\n"
            '<img src="https://example.com/logo.png">\n'
            '<img src="other.png">'
        )
        result = extract_readme_images(md)
        assert result == ["https://example.com/logo.png", "other.png"]

    def test_strips_title_text(self) -> None:
        md = '![logo](https://example.com/logo.png "Project Logo")'
        result = extract_readme_images(md)
        assert result == ["https://example.com/logo.png"]

    def test_no_images(self) -> None:
        assert extract_readme_images("Just text, no images.") == []


# ── Ingest node integration test ──


class TestIngestNode:
    async def test_successful_ingest(self) -> None:
        """Full ingest node returns assembled repo_context."""
        from app.nodes.ingest import ingest

        state = {"repo_url": "https://github.com/owner/myrepo"}

        readme_b64 = base64.b64encode(
            b"# My Repo\n![screenshot](https://img.example.com/shot.png)"
        ).decode()

        metadata_resp = httpx.Response(
            200,
            json={
                "name": "myrepo",
                "description": "desc",
                "stargazers_count": 10,
                "forks_count": 2,
                "language": "Python",
                "topics": [],
                "html_url": "https://github.com/owner/myrepo",
            },
            request=httpx.Request("GET", "https://api.github.com/repos/owner/myrepo"),
        )
        readme_resp = httpx.Response(
            200,
            json={"content": readme_b64, "encoding": "base64"},
            request=httpx.Request("GET", "https://api.github.com/repos/owner/myrepo/readme"),
        )
        tree_resp = httpx.Response(
            200,
            json={"tree": [{"path": "README.md"}, {"path": "requirements.txt"}]},
            request=httpx.Request("GET", "https://api.github.com/repos/owner/myrepo/git/trees/main"),
        )
        config_resp = httpx.Response(
            200,
            json={
                "content": base64.b64encode(b"flask>=2.0").decode(),
                "encoding": "base64",
                "size": 10,
            },
            request=httpx.Request("GET", "https://api.github.com/repos/owner/myrepo/contents/requirements.txt"),
        )

        with (
            patch(
                "app.services.github_client._get_client"
            ) as mock_get_client,
            patch("app.nodes.ingest.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.get = AsyncMock(
                side_effect=[metadata_resp, readme_resp, tree_resp, config_resp]
            )
            mock_get_client.return_value = client
            mock_writer.return_value = lambda x: None

            result = await ingest(state)

        assert "error" not in result
        ctx = result["repo_context"]
        assert ctx["url"] == "https://github.com/owner/myrepo"
        assert ctx["metadata"]["name"] == "myrepo"
        assert "My Repo" in ctx["readme"]
        assert "README.md" in ctx["file_tree"]
        assert "requirements.txt" in ctx["config_files"]
        assert "https://img.example.com/shot.png" in ctx["images_in_readme"]

    async def test_invalid_url_returns_error(self) -> None:
        """Ingest node sets error on invalid URL."""
        from app.nodes.ingest import ingest

        state = {"repo_url": "https://gitlab.com/owner/repo"}

        with patch("app.nodes.ingest.get_stream_writer") as mock_writer:
            mock_writer.return_value = lambda x: None
            result = await ingest(state)

        assert "error" in result
        assert "Invalid repository URL" in result["error"]

    async def test_404_returns_error(self) -> None:
        """Ingest node sets error when repo is not found."""
        from app.nodes.ingest import ingest

        state = {"repo_url": "https://github.com/owner/nonexistent"}

        resp_404 = httpx.Response(
            404,
            request=httpx.Request("GET", "https://api.github.com/repos/owner/nonexistent"),
        )

        with (
            patch(
                "app.services.github_client._get_client"
            ) as mock_get_client,
            patch("app.nodes.ingest.get_stream_writer") as mock_writer,
        ):
            client = AsyncMock()
            client.get = AsyncMock(return_value=resp_404)
            mock_get_client.return_value = client
            mock_writer.return_value = lambda x: None

            result = await ingest(state)

        assert "error" in result
        assert "not found" in result["error"]
