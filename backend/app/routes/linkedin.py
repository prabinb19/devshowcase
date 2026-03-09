"""API endpoints for LinkedIn OAuth and publishing."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Draft, DraftStatus, Token
from app.routes.deps import AuthenticatedUser, verify_auth
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
from app.services.audit_log import log_publish_event, log_token_event
from app.services.token_encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/linkedin", tags=["linkedin"])

# --- OAuth state store (CSRF protection) ---
_STATE_TTL = 600  # 10 minutes
_state_lock = threading.Lock()
_state_store: dict[str, tuple[float, str]] = {}  # state -> (expires_at, github_id)


def _store_state(state: str, github_id: str) -> None:
    """Store an OAuth state value with a TTL and user binding."""
    with _state_lock:
        # Prune expired entries
        now = time.time()
        expired = [k for k, (exp, _) in _state_store.items() if exp < now]
        for k in expired:
            del _state_store[k]
        _state_store[state] = (now + _STATE_TTL, github_id)


def _consume_state(state: str, github_id: str) -> bool:
    """Validate and consume an OAuth state value. Returns True if valid."""
    with _state_lock:
        entry = _state_store.pop(state, None)
    if entry is None:
        return False
    expires_at, bound_id = entry
    if time.time() > expires_at:
        return False
    if bound_id != github_id:
        return False
    return True


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
async def get_auth_url(
    auth: AuthenticatedUser = Depends(verify_auth),
) -> LinkedInAuthURLResponse:
    """Return the LinkedIn OAuth2 authorization URL."""
    state = uuid.uuid4().hex
    _store_state(state, auth.github_id)
    auth_url = build_auth_url(state)
    return LinkedInAuthURLResponse(auth_url=auth_url)


@router.post("/callback", response_model=LinkedInTokenStatus)
async def handle_callback(
    body: LinkedInCallbackRequest,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> LinkedInTokenStatus:
    """Exchange authorization code for tokens and store them."""
    # Validate OAuth state (CSRF protection)
    if not _consume_state(body.state, auth.github_id):
        raise HTTPException(400, "Invalid or expired OAuth state")

    user = auth.db_user

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
    log_token_event(action="store", github_id=auth.github_id)
    return LinkedInTokenStatus(connected=True, expires_at=expires_at.isoformat())


@router.get("/status", response_model=LinkedInTokenStatus)
async def get_status(
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> LinkedInTokenStatus:
    """Check if the user has a valid LinkedIn connection."""
    user = auth.db_user
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
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> PublishResponse:
    """Publish a draft to LinkedIn."""
    user = auth.db_user
    token = await _get_user_token(user.id, session)

    if not token:
        raise HTTPException(401, "LinkedIn not connected")

    access_token = await _ensure_valid_token(token, session)

    # Fetch the draft
    result = await session.execute(
        select(Draft).where(Draft.id == body.draft_id)
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")

    # Ownership check
    if draft.user_id != user.id:
        raise HTTPException(403, "Not authorized to publish this draft")

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

        log_publish_event(github_id=auth.github_id, draft_id=str(body.draft_id), success=True)
        return PublishResponse(success=True, post_url=post_url)

    except Exception as exc:
        logger.error("Failed to publish draft %s: %s", body.draft_id, exc)
        log_publish_event(github_id=auth.github_id, draft_id=str(body.draft_id), success=False, error=str(exc))
        return PublishResponse(success=False, error="Failed to publish to LinkedIn. Please try again.")


@router.delete("/disconnect", status_code=204)
async def disconnect(
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Remove stored LinkedIn tokens."""
    user = auth.db_user
    token = await _get_user_token(user.id, session)
    if token:
        await session.delete(token)
        await session.commit()
        log_token_event(action="delete", github_id=auth.github_id)
