"""Download, validate, and upload README images."""

from __future__ import annotations

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.services.image_processor import (
    get_dimensions,
    process_image,
    validate_image,
)
from app.services.r2_storage import upload_image

logger = logging.getLogger(__name__)

# Hosts that must never be contacted (cloud metadata endpoints, localhost, etc.)
_BLOCKED_HOSTS = frozenset(
    {
        "metadata.google.internal",
        "169.254.169.254",
        "metadata.azure.com",
        "100.100.100.200",
    }
)


def _validate_image_url(url: str) -> None:
    """Reject URLs that point to private/internal networks or metadata endpoints.

    Raises ValueError if the URL is unsafe.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("No hostname in URL")

    if hostname in _BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname}")

    # Resolve DNS and reject private IPs
    try:
        for info in socket.getaddrinfo(
            hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        ):
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError(f"URL resolves to private/reserved IP: {addr}")
    except socket.gaierror as exc:
        raise ValueError(f"DNS resolution failed for {hostname}: {exc}") from exc


_MAX_IMAGES = 3
_DOWNLOAD_TIMEOUT = 15.0
_MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _resolve_github_url(image_url: str, repo_url: str) -> str:
    """Resolve relative image URLs to raw.githubusercontent.com.

    Handles:
    - Absolute URLs (returned as-is)
    - Relative URLs (resolved against raw GitHub content URL)
    - GitHub blob URLs (converted to raw URLs)
    """
    parsed = urlparse(image_url)
    if parsed.scheme in ("http", "https"):
        # Convert github.com blob URLs to raw URLs
        if "github.com" in parsed.netloc and "/blob/" in parsed.path:
            return image_url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )
        return image_url

    # Relative URL — resolve against raw.githubusercontent.com
    repo_parsed = urlparse(repo_url)
    # repo_url like https://github.com/owner/repo
    path_parts = repo_parsed.path.strip("/").split("/")
    if len(path_parts) >= 2:
        owner, repo = path_parts[0], path_parts[1]
        raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/"
        return urljoin(raw_base, image_url.lstrip("./"))

    return image_url


def capture_readme_images(
    image_urls: list[str],
    repo_url: str,
    run_id: str,
) -> list[dict]:
    """Download up to 3 README images, validate, process, and upload to R2.

    Silently skips invalid, oversized, or failed downloads.
    Returns list of Screenshot dicts.
    """
    screenshots: list[dict] = []

    for url in image_urls[:_MAX_IMAGES]:
        try:
            resolved_url = _resolve_github_url(url, repo_url)
            _validate_image_url(resolved_url)  # SSRF prevention
            logger.info("Downloading README image: %s", resolved_url)

            with httpx.Client(
                timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True
            ) as client:
                resp = client.get(resolved_url)
                resp.raise_for_status()

            raw_bytes = resp.content
            if len(raw_bytes) > _MAX_DOWNLOAD_BYTES:
                logger.warning(
                    "Skipping oversized image: %s (%d bytes)", url, len(raw_bytes)
                )
                continue

            if not validate_image(raw_bytes):
                logger.warning("Skipping invalid image: %s", url)
                continue

            processed = process_image(raw_bytes)
            width, height = get_dimensions(processed)

            # Derive filename from URL
            filename = urlparse(resolved_url).path.split("/")[-1] or "readme_image.png"
            if "." not in filename:
                filename += ".png"

            public_url = upload_image(processed, run_id, filename)

            screenshots.append(
                {
                    "url": public_url,
                    "alt_text": f"README image: {filename}",
                    "source": "readme",
                    "width": width,
                    "height": height,
                }
            )

        except Exception:
            logger.exception("Failed to process README image: %s", url)
            continue

    return screenshots
