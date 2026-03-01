"""Extract and download images referenced in a README."""

import re
from pathlib import Path

import httpx

OUTPUT_DIR = Path("/output/images")
MAX_IMAGES = 5


def extract_images(readme: str, repo_url: str) -> list[dict]:
    """Find images in README markdown/HTML and download up to 5.

    Returns a list of dicts with url, alt_text, local_path, and source.
    """
    if not readme:
        return []

    raw_base = _raw_base_url(repo_url)
    urls = _find_image_urls(readme, raw_base)

    results: list[dict] = []
    for alt_text, url in urls[:MAX_IMAGES]:
        local_path = _download_image(url, len(results))
        if local_path:
            results.append({
                "url": url,
                "alt_text": alt_text,
                "local_path": str(local_path),
                "source": "readme",
            })
    return results


def _raw_base_url(repo_url: str) -> str:
    """Build the raw.githubusercontent.com base URL for resolving relative paths."""
    parts = repo_url.rstrip("/").replace(".git", "").split("/")
    owner = parts[-2]
    repo = parts[-1]
    return f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/"


def _find_image_urls(readme: str, raw_base: str) -> list[tuple[str, str]]:
    """Return (alt_text, absolute_url) pairs from markdown and HTML img tags."""
    found: list[tuple[str, str]] = []

    # Markdown: ![alt](url)
    for match in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", readme):
        alt, url = match.group(1), match.group(2)
        found.append((alt, _resolve_url(url, raw_base)))

    # HTML: <img src="url" alt="alt" ...>
    for match in re.finditer(
        r'<img\s[^>]*src=["\']([^"\']+)["\'][^>]*>', readme, re.IGNORECASE
    ):
        url = match.group(1)
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0))
        alt = alt_match.group(1) if alt_match else ""
        found.append((alt, _resolve_url(url, raw_base)))

    return found


def _resolve_url(url: str, raw_base: str) -> str:
    """Resolve a potentially relative URL to an absolute one."""
    if url.startswith(("http://", "https://")):
        return url
    return raw_base + url.lstrip("/")


def _download_image(url: str, index: int) -> Path | None:
    """Download a single image. Returns local path on success, None on failure."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        ext = _guess_extension(resp.headers.get("content-type", ""), url)
        local_path = OUTPUT_DIR / f"image_{index}{ext}"
        local_path.write_bytes(resp.content)
        return local_path
    except Exception:
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
