"""API endpoints for LinkedIn OAuth and publishing."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Draft, DraftStatus, Token
from app.routes.deps import get_or_create_user
from app.schemas.linkedin import (
    LinkedInAuthURLResponse,
    LinkedInCallbackRequest,
    LinkedInTokenStatus,
    PublishRequest,
    PublishResponse,
)
from app.services.linkedin_client import (
    build_auth_url,
    create_comment,
    create_post,
    exchange_code_for_tokens,
    get_linkedin_profile,
    refresh_access_token,
    upload_image,
)
from app.services.token_encryption import decrypt_token, encrypt_token

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


async def _get_user_token(
    user_id: uuid.UUID, session: AsyncSession
) -> Token | None:
    """Get the LinkedIn token for a user."""
    result = await session.execute(
        select(Token).where(Token.user_id == user_id, Token.platform == "linkedin")
    )
    return result.scalar_one_or_none()


async def _ensure_valid_token(
    token: Token, session: AsyncSession
) -> str:
    """Return a valid access token, refreshing if expired."""
    if token.expires_at and token.expires_at < datetime.now(timezone.utc):
        if not token.encrypted_refresh_token:
            raise HTTPException(401, "LinkedIn token expired and no refresh token available")
        refresh_tok = decrypt_token(token.encrypted_refresh_token)
        data = await refresh_access_token(refresh_tok)
        token.encrypted_access_token = encrypt_token(data["access_token"])
        if data.get("refresh_token"):
            token.encrypted_refresh_token = encrypt_token(data["refresh_token"])
        token.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=data.get("expires_in", 3600)
        )
        await session.commit()
    return decrypt_token(token.encrypted_access_token)


@router.get("/auth-url", response_model=LinkedInAuthURLResponse)
async def get_auth_url() -> LinkedInAuthURLResponse:
    """Return the LinkedIn OAuth2 authorization URL."""
    state = uuid.uuid4().hex
    auth_url = build_auth_url(state)
    return LinkedInAuthURLResponse(auth_url=auth_url)


@router.post("/callback", response_model=LinkedInTokenStatus)
async def handle_callback(
    body: LinkedInCallbackRequest,
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> LinkedInTokenStatus:
    """Exchange authorization code for tokens and store them."""
    user = await get_or_create_user(x_github_id, x_github_username, session)

    data = await exchange_code_for_tokens(body.code)
    access_token = data["access_token"]
    refresh_token = data.get("refresh_token")
    expires_in = data.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Upsert: update existing token or create new one
    existing = await _get_user_token(user.id, session)
    if existing:
        existing.encrypted_access_token = encrypt_token(access_token)
        existing.encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
        existing.expires_at = expires_at
    else:
        token = Token(
            user_id=user.id,
            platform="linkedin",
            encrypted_access_token=encrypt_token(access_token),
            encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
            expires_at=expires_at,
        )
        session.add(token)

    await session.commit()
    return LinkedInTokenStatus(connected=True, expires_at=expires_at.isoformat())


@router.get("/status", response_model=LinkedInTokenStatus)
async def get_status(
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> LinkedInTokenStatus:
    """Check if the user has a valid LinkedIn connection."""
    user = await get_or_create_user(x_github_id, x_github_username, session)
    token = await _get_user_token(user.id, session)

    if not token:
        return LinkedInTokenStatus(connected=False)

    # Try auto-refresh if expired
    try:
        await _ensure_valid_token(token, session)
    except Exception:
        return LinkedInTokenStatus(connected=False)

    expires_at_str = token.expires_at.isoformat() if token.expires_at else None
    return LinkedInTokenStatus(connected=True, expires_at=expires_at_str)


@router.post("/publish", response_model=PublishResponse)
async def publish_draft(
    body: PublishRequest,
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> PublishResponse:
    """Publish a draft to LinkedIn."""
    user = await get_or_create_user(x_github_id, x_github_username, session)
    token = await _get_user_token(user.id, session)

    if not token:
        raise HTTPException(401, "LinkedIn not connected")

    access_token = await _ensure_valid_token(token, session)

    # Fetch the draft
    result = await session.execute(
        select(Draft).where(Draft.id == uuid.UUID(body.draft_id))
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")

    try:
        # Get the user's LinkedIn profile URN
        author_urn = await get_linkedin_profile(access_token)

        # Upload images if present
        image_urns: list[str] = []
        if draft.screenshot_urls:
            for img_url in draft.screenshot_urls:
                urn = await upload_image(access_token, author_urn, img_url)
                image_urns.append(urn)

        # Create the post
        post_result = await create_post(
            access_token, author_urn, draft.body, image_urns or None
        )
        post_urn = post_result["post_urn"]

        # Auto-comment with first_comment if present
        if draft.first_comment and post_urn:
            await create_comment(access_token, post_urn, draft.first_comment)

        # Build the post URL
        post_url = f"https://www.linkedin.com/feed/update/{post_urn}" if post_urn else None

        # Update draft status
        draft.status = DraftStatus.published
        draft.published_url = post_url
        draft.published_at = datetime.now(timezone.utc)
        await session.commit()

        return PublishResponse(success=True, post_url=post_url)

    except Exception as exc:
        return PublishResponse(success=False, error=str(exc))


@router.delete("/disconnect", status_code=204)
async def disconnect(
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> None:
    """Remove stored LinkedIn tokens."""
    user = await get_or_create_user(x_github_id, x_github_username, session)
    token = await _get_user_token(user.id, session)
    if token:
        await session.delete(token)
        await session.commit()
