"""API endpoints for user preferences/settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.deps import get_or_create_user
from app.schemas.settings import UserSettings, UserSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> UserSettingsResponse:
    """Get user preferences."""
    user = await get_or_create_user(x_github_id, x_github_username, session)
    prefs = user.preferences or {}
    return UserSettingsResponse(
        default_tone=prefs.get("default_tone", "professional"),
        hashtags=prefs.get("hashtags", []),
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    body: UserSettings,
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> UserSettingsResponse:
    """Update user preferences."""
    user = await get_or_create_user(x_github_id, x_github_username, session)
    user.preferences = {
        "default_tone": body.default_tone,
        "hashtags": body.hashtags,
    }
    await session.commit()
    await session.refresh(user)
    prefs = user.preferences or {}
    return UserSettingsResponse(
        default_tone=prefs.get("default_tone", "professional"),
        hashtags=prefs.get("hashtags", []),
    )
