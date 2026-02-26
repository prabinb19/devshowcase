"""LinkedIn API client — OAuth, image upload, post creation, commenting."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_VERSION = "202502"
SCOPES = "w_member_social openid profile"

_MAX_RETRIES = 3
_BASE_DELAY = 1.0


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Execute an HTTP request with exponential backoff for 5xx/429."""
    for attempt in range(_MAX_RETRIES):
        response = await client.request(method, url, **kwargs)
        if response.status_code < 500 and response.status_code != 429:
            return response
        if attempt < _MAX_RETRIES - 1:
            delay = _BASE_DELAY * (2 ** attempt)
            logger.warning(
                "LinkedIn API %s %s returned %d, retrying in %.1fs (attempt %d/%d)",
                method, url, response.status_code, delay, attempt + 1, _MAX_RETRIES,
            )
            await asyncio.sleep(delay)
    return response


def build_auth_url(state: str) -> str:
    """Build the LinkedIn OAuth2 authorization URL."""
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": SCOPES,
    }
    return f"{LINKEDIN_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for access/refresh tokens.

    Returns dict with keys: access_token, refresh_token, expires_in.
    """
    async with httpx.AsyncClient() as client:
        response = await _request_with_retry(
            client,
            "POST",
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linkedin_redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token.

    Returns dict with keys: access_token, refresh_token, expires_in.
    """
    async with httpx.AsyncClient() as client:
        response = await _request_with_retry(
            client,
            "POST",
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


def _api_headers(access_token: str) -> dict[str, str]:
    """Common headers for LinkedIn REST API calls."""
    return {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }


async def get_linkedin_profile(access_token: str) -> str:
    """Get the authenticated user's person URN."""
    async with httpx.AsyncClient() as client:
        response = await _request_with_retry(
            client,
            "GET",
            f"{LINKEDIN_API_BASE}/v2/userinfo",
            headers=_api_headers(access_token),
        )
        response.raise_for_status()
        data = response.json()
        return f"urn:li:person:{data['sub']}"


async def upload_image(
    access_token: str, author_urn: str, image_url: str
) -> str:
    """Upload an image to LinkedIn via the 2-step process.

    1. Initialize the upload to get an upload URL and image URN.
    2. Download the image from image_url, then PUT it to LinkedIn.

    Returns the image URN for use in posts.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Step 1: Initialize upload
        init_response = await _request_with_retry(
            client,
            "POST",
            f"{LINKEDIN_API_BASE}/rest/images?action=initializeUpload",
            headers={**_api_headers(access_token), "Content-Type": "application/json"},
            json={
                "initializeUploadRequest": {
                    "owner": author_urn,
                }
            },
        )
        init_response.raise_for_status()
        init_data = init_response.json()
        upload_url = init_data["value"]["uploadUrl"]
        image_urn = init_data["value"]["image"]

        # Step 2: Download image from source URL
        img_response = await client.get(image_url)
        img_response.raise_for_status()
        image_bytes = img_response.content

        # Step 3: PUT image to LinkedIn upload URL
        put_response = await _request_with_retry(
            client,
            "PUT",
            upload_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/octet-stream",
            },
            content=image_bytes,
        )
        put_response.raise_for_status()

        logger.info("Uploaded image to LinkedIn: %s", image_urn)
        return image_urn


async def create_post(
    access_token: str,
    author_urn: str,
    body: str,
    image_urns: list[str] | None = None,
) -> dict:
    """Create a LinkedIn post via the Posts API.

    Returns the full response dict including the post URN.
    """
    post_data: dict = {
        "author": author_urn,
        "commentary": body,
        "visibility": "PUBLIC",
        "lifecycleState": "PUBLISHED",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
        },
    }

    if image_urns:
        if len(image_urns) == 1:
            post_data["content"] = {
                "media": {
                    "id": image_urns[0],
                }
            }
        else:
            post_data["content"] = {
                "multiImage": {
                    "images": [{"id": urn} for urn in image_urns],
                }
            }

    async with httpx.AsyncClient() as client:
        response = await _request_with_retry(
            client,
            "POST",
            f"{LINKEDIN_API_BASE}/rest/posts",
            headers={**_api_headers(access_token), "Content-Type": "application/json"},
            json=post_data,
        )
        response.raise_for_status()

        # Posts API returns 201 with x-restli-id header containing the post URN
        post_urn = response.headers.get("x-restli-id", "")
        return {"post_urn": post_urn, "status_code": response.status_code}


async def create_comment(
    access_token: str, post_urn: str, text: str
) -> dict:
    """Create a comment on a LinkedIn post (e.g. first comment with GitHub link)."""
    async with httpx.AsyncClient() as client:
        response = await _request_with_retry(
            client,
            "POST",
            f"{LINKEDIN_API_BASE}/rest/socialActions/{urllib.parse.quote(post_urn, safe='')}/comments",
            headers={**_api_headers(access_token), "Content-Type": "application/json"},
            json={
                "actor": post_urn.split(":")[3] if "person" in post_urn else post_urn,
                "message": {"text": text},
            },
        )
        response.raise_for_status()
        return response.json()
