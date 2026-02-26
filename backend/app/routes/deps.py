"""Reusable FastAPI dependencies."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_or_create_user(
    github_id: str, github_username: str, session: AsyncSession
) -> User:
    """Look up User by github_id, create if not found, return User record."""
    result = await session.execute(
        select(User).where(User.github_id == github_id)
    )
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(github_id=github_id, github_username=github_username)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
