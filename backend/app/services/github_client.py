"""GitHub API client — async httpx wrapper for repo data fetching."""

from __future__ import annotations

import base64
import ipaddress
import re
from urllib.parse import urlparse

import httpx

from app.config import settings

# ── Constants ──

_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)

_CONFIG_FILENAMES = frozenset(
    {
        "package.json",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "requirements.txt",
    }
)

_MAX_TREE_ENTRIES = 10_000
_MAX_CONFIG_SIZE = 50 * 1024  # 50 KB

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^\s)]+)")
_HTML_IMG_RE = re.compile(r'<img\s[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)

# ── Module-level client (lazy singleton) ──

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Return a shared async httpx client with GitHub auth headers."""
    global _client  # noqa: PLW0603
    if _client is None or _client.is_closed:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        _client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=30.0,
        )
    return _client


# ── URL parsing & validation ──


def parse_github_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Raises ValueError for malformed or non-GitHub URLs.
    """
    _validate_url(url)
    match = _GITHUB_URL_RE.match(url)
    if not match:
        raise ValueError(f"Invalid GitHub repository URL: {url}")
    return match.group("owner"), match.group("repo")


def _validate_url(url: str) -> None:
    """SSRF prevention — only allow github.com hosts."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if host not in ("github.com", "www.github.com"):
        raise ValueError(f"Only github.com URLs are accepted, got host: {host}")

    # Block private/loopback IPs even if someone passes a numeric IP
    try:
        addr = ipaddress.ip_address(host)
        if addr.is_private or addr.is_loopback or addr.is_reserved:
            raise ValueError(f"Private/loopback addresses are not allowed: {host}")
    except ValueError as exc:
        # Not an IP address (it's a hostname) — that's fine
        if "not allowed" in str(exc):
            raise


# ── Fetch functions ──


async def fetch_repo_metadata(owner: str, repo: str) -> dict:
    """GET /repos/{owner}/{repo} → RepoMetadata dict."""
    client = _get_client()
    resp = await client.get(f"/repos/{owner}/{repo}")
    resp.raise_for_status()
    data = resp.json()
    return {
        "name": data.get("name", ""),
        "description": data.get("description") or "",
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "language": data.get("language") or "",
        "topics": data.get("topics", []),
        "url": data.get("html_url", ""),
        "default_branch": data.get("default_branch", "main"),
    }


async def fetch_readme(owner: str, repo: str) -> str:
    """GET /repos/{owner}/{repo}/readme → decoded markdown string."""
    client = _get_client()
    resp = await client.get(f"/repos/{owner}/{repo}/readme")
    if resp.status_code == 404:
        return ""
    resp.raise_for_status()
    data = resp.json()
    content = data.get("content", "")
    encoding = data.get("encoding", "base64")
    if encoding == "base64" and content:
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return content


async def fetch_file_tree(
    owner: str, repo: str, default_branch: str = "main"
) -> list[str]:
    """GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1 → list of paths."""
    client = _get_client()
    resp = await client.get(
        f"/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
    )
    if resp.status_code == 404 and default_branch == "main":
        # Fallback to "master"
        resp = await client.get(
            f"/repos/{owner}/{repo}/git/trees/master",
            params={"recursive": "1"},
        )
    resp.raise_for_status()
    tree = resp.json().get("tree", [])
    return [item["path"] for item in tree[:_MAX_TREE_ENTRIES] if item.get("path")]


async def fetch_config_files(
    owner: str, repo: str, file_tree: list[str]
) -> dict[str, str]:
    """Fetch known config files if they exist in the tree (< 50 KB each)."""
    client = _get_client()
    present = [f for f in file_tree if f in _CONFIG_FILENAMES]
    configs: dict[str, str] = {}

    for filename in present:
        resp = await client.get(f"/repos/{owner}/{repo}/contents/{filename}")
        if resp.status_code != 200:
            continue
        data = resp.json()
        size = data.get("size", 0)
        if size > _MAX_CONFIG_SIZE:
            continue
        content = data.get("content", "")
        encoding = data.get("encoding", "base64")
        if encoding == "base64" and content:
            configs[filename] = base64.b64decode(content).decode(
                "utf-8", errors="replace"
            )
        else:
            configs[filename] = content

    return configs


def _is_badge_url(url: str) -> bool:
    """Return True if the URL looks like a badge/shield image (not a real screenshot)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path_lower = (parsed.path or "").lower()

    badge_hosts = {
        "img.shields.io",
        "badge.fury.io",
        "badges.gitter.im",
        "badgen.net",
        "flat.badgen.net",
        "codecov.io",
        "coveralls.io",
    }
    if host in badge_hosts:
        return True
    if "/badge/" in path_lower or "/badges/" in path_lower:
        return True
    if "/actions/workflows/" in path_lower:
        return True
    if path_lower.endswith(".svg"):
        return True
    return False


def extract_readme_images(readme_md: str) -> list[str]:
    """Extract image URLs from markdown, filtering badges and prioritizing content images."""
    md_images = _MD_IMAGE_RE.findall(readme_md)
    html_images = _HTML_IMG_RE.findall(readme_md)
    # Deduplicate while preserving order
    seen: set[str] = set()
    content: list[str] = []
    badges: list[str] = []
    for url in md_images + html_images:
        if url not in seen:
            seen.add(url)
            if _is_badge_url(url):
                badges.append(url)
            else:
                content.append(url)
    # Content images first, badges last (badges will likely be skipped by MAX_IMAGES)
    return content + badges
