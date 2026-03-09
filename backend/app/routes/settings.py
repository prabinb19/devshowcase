"""API endpoints for user preferences/settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.deps import AuthenticatedUser, verify_auth
from app.schemas.settings import UserSettings, UserSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> UserSettingsResponse:
    """Get user preferences."""
    user = auth.db_user
    prefs = user.preferences or {}
    return UserSettingsResponse(
        default_tone=prefs.get("default_tone", "professional"),
        hashtags=prefs.get("hashtags", []),
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    body: UserSettings,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> UserSettingsResponse:
    """Update user preferences."""
    user = auth.db_user
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
