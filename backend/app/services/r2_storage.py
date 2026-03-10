"""Cloudflare R2 storage client — lazy singleton boto3 S3 client."""

from __future__ import annotations

import hashlib
import logging

import boto3

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_r2_client():
    """Lazy singleton boto3 S3 client for Cloudflare R2."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
    return _client


def upload_image(
    image_bytes: bytes,
    run_id: str,
    filename: str,
    content_type: str = "image/png",
) -> str:
    """Upload image to R2 and return the public URL.

    Key format: screenshots/{run_id}/{content_hash}_{filename}
    Content-hash provides free deduplication.
    """
    content_hash = hashlib.sha256(image_bytes).hexdigest()[:12]
    key = f"screenshots/{run_id}/{content_hash}_{filename}"

    client = _get_r2_client()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=image_bytes,
        ContentType=content_type,
    )

    # Return a backend-proxy URL so images load without R2 public access.
    # Frontend proxies /api/backend/* → backend /api/*, so store the full
    # frontend-accessible path.
    proxy_url = f"/api/backend/images/{run_id}/{content_hash}_{filename}"
    logger.info("Uploaded %s to R2: %s", filename, proxy_url)
    return proxy_url


def download_image(key: str) -> bytes | None:
    """Download an image from R2 by key. Returns bytes or None."""
    try:
        client = _get_r2_client()
        response = client.get_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
        )
        return response["Body"].read()
    except Exception:
        logger.exception("Failed to download from R2: %s", key)
        return None
