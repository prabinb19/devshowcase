"""Extract and download images referenced in a README."""

import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/output/images")
REPO_DIR = Path("/workspace/repo")
MAX_IMAGES = 5

# Badge / shield hosts whose images are tiny SVGs, not useful screenshots
_BADGE_HOSTS = frozenset({
    "img.shields.io",
    "badge.fury.io",
    "badges.gitter.im",
    "badgen.net",
    "flat.badgen.net",
    "codecov.io",
    "coveralls.io",
    "travis-ci.org",
    "travis-ci.com",
    "ci.appveyor.com",
    "circleci.com",
    "github.com",  # GitHub workflow badge URLs contain /actions/workflows/
})

# URL path patterns that indicate badges even on general hosts
_BADGE_PATH_PATTERNS = (
    "/badge/",
    "/badges/",
    "/actions/workflows/",  # GitHub Actions badges
)


def _is_badge_url(url: str) -> bool:
    """Return True if the URL looks like a small badge/shield image."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Known badge hosts (except github.com which needs path check)
    if host in _BADGE_HOSTS and host != "github.com":
        return True

    # Check path patterns on any host
    path_lower = parsed.path.lower()
    for pattern in _BADGE_PATH_PATTERNS:
        if pattern in path_lower:
            return True

    # SVG files are almost always badges in READMEs
    if path_lower.endswith(".svg"):
        return True

    return False


def extract_images(
    readme: str, repo_url: str, default_branch: str = "main"
) -> list[dict]:
    """Find images in README markdown/HTML and download up to 5.

    Filters out badge/shield images that are not useful as screenshots.
    Returns a list of dicts with url, alt_text, local_path, and source.
    """
    if not readme:
        logger.info("No README content — skipping image extraction")
        return []

    raw_base = _raw_base_url(repo_url, default_branch)
    logger.info("Raw base URL for relative images: %s", raw_base)
    urls = _find_image_urls(readme, raw_base)

    logger.info("Found %d image URLs in README", len(urls))

    # Separate content images from badges, prioritize content images
    content_urls = [(alt, url, raw) for alt, url, raw in urls if not _is_badge_url(url)]
    badge_urls = [(alt, url, raw) for alt, url, raw in urls if _is_badge_url(url)]
    prioritized = content_urls + badge_urls

    logger.info(
        "%d content images, %d badge images", len(content_urls), len(badge_urls)
    )

    results: list[dict] = []
    for alt_text, url, raw_path in prioritized[:MAX_IMAGES]:
        local_path = _copy_or_download_image(url, raw_path, len(results))
        if local_path:
            results.append({
                "url": url,
                "alt_text": alt_text,
                "local_path": str(local_path),
                "source": "readme",
            })
        else:
            logger.warning("Failed to get image: %s", url)

    logger.info("Successfully extracted %d images", len(results))
    return results


def _raw_base_url(repo_url: str, default_branch: str = "main") -> str:
    """Build the raw.githubusercontent.com base URL for resolving relative paths."""
    parts = repo_url.rstrip("/").replace(".git", "").split("/")
    owner = parts[-2]
    repo = parts[-1]
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/"


def _find_image_urls(
    readme: str, raw_base: str
) -> list[tuple[str, str, str]]:
    """Return (alt_text, absolute_url, original_path) tuples.

    original_path is the raw path from the README (relative or absolute).
    Used to resolve images from the local clone when available.
    """
    found: list[tuple[str, str, str]] = []

    # Markdown: ![alt](url)
    for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", readme):
        alt, raw_url = match.group(1), match.group(2)
        found.append((alt, _resolve_url(raw_url, raw_base), raw_url))

    # HTML: <img src="url" alt="alt" ...>
    for match in re.finditer(
        r'<img\s[^>]*src=["\']([^"\']+)["\'][^>]*>', readme, re.IGNORECASE
    ):
        raw_url = match.group(1)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0))
        alt = alt_match.group(1) if alt_match else ""
        found.append((alt, _resolve_url(raw_url, raw_base), raw_url))

    return found


def _resolve_url(url: str, raw_base: str) -> str:
    """Resolve a potentially relative URL to an absolute one."""
    if url.startswith(("http://", "https://")):
        return url
    return raw_base + url.lstrip("/")


def _copy_or_download_image(url: str, raw_path: str, index: int) -> Path | None:
    """Try to copy from local clone first, then fall back to HTTP download."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # For relative paths, try local clone first
    if not raw_path.startswith(("http://", "https://")):
        local_file = REPO_DIR / raw_path.lstrip("./")
        if local_file.is_file():
            ext = _guess_extension("", raw_path)
            out_path = OUTPUT_DIR / f"image_{index}{ext}"
            import shutil
            shutil.copy2(local_file, out_path)
            logger.info(
                "Copied local image %d: %s (%d bytes)",
                index, local_file, out_path.stat().st_size,
            )
            return out_path
        logger.info("Local file not found at %s, trying HTTP", local_file)

    # Fall back to HTTP download
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "")
        ext = _guess_extension(ct, url)
        out_path = OUTPUT_DIR / f"image_{index}{ext}"
        out_path.write_bytes(resp.content)
        logger.info(
            "Downloaded image %d: %s (%s, %d bytes)",
            index, url, ct, len(resp.content),
        )
        return out_path
    except Exception as exc:
        logger.warning("Image download failed for %s: %s", url, exc)
        return None


def _guess_extension(content_type: str, url: str) -> str:
    """Guess a file extension from content-type or URL."""
    ct_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
              "image/webp": ".webp", "image/svg+xml": ".svg"}
    for ct, ext in ct_map.items():
        if ct in content_type:
            return ext
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
        if url.lower().endswith(ext):
            return ext
    return ".png"
