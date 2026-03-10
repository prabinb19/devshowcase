"""Image proxy — serves R2-stored images through the backend."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.services.r2_storage import download_image

router = APIRouter(prefix="/images", tags=["images"])
logger = logging.getLogger(__name__)

# Only allow safe filenames: hex hash + underscore + image filename
_SAFE_FILENAME = re.compile(r"^[a-f0-9]+_image_\d+\.\w+$")


@router.get("/{run_id}/{filename}")
async def proxy_image(run_id: str, filename: str) -> Response:
    """Serve an image from R2 storage."""
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(400, "Invalid filename")

    key = f"screenshots/{run_id}/{filename}"
    data = download_image(key)
    if data is None:
        raise HTTPException(404, "Image not found")

    # Guess content type from extension
    ext = filename.rsplit(".", 1)[-1].lower()
    content_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    ct = content_types.get(ext, "image/png")

    return Response(
        content=data,
        media_type=ct,
        headers={"Cache-Control": "public, max-age=86400"},
    )
