"""Pillow-based image utilities for screenshot processing."""

from __future__ import annotations

import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image(image_bytes: bytes) -> bool:
    """Return True if bytes represent a valid image."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        return True
    except Exception:
        return False


def get_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Return (width, height) of an image."""
    img = Image.open(io.BytesIO(image_bytes))
    return img.size


def process_image(
    image_bytes: bytes,
    max_width: int = 1200,
    max_height: int = 1200,
    output_format: str = "PNG",
) -> bytes:
    """Resize image preserving aspect ratio and compress.

    Converts RGBA to RGB when output format is JPEG.
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA → RGB for JPEG output
    if output_format.upper() in ("JPEG", "JPG") and img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background

    # Resize if exceeding max dimensions
    if img.width > max_width or img.height > max_height:
        img.thumbnail((max_width, max_height), Image.LANCZOS)

    buf = io.BytesIO()
    save_format = "JPEG" if output_format.upper() == "JPG" else output_format.upper()
    img.save(buf, format=save_format, optimize=True)
    return buf.getvalue()
