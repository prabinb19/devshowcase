"""Reusable FastAPI dependencies — JWT auth + user resolution."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import User
from app.services.audit_log import log_auth_event

logger = logging.getLogger(__name__)


@dataclass
class AuthenticatedUser:
    """Verified identity extracted from a NextAuth JWT."""

    github_id: str
    github_username: str
    db_user: User


async def get_or_create_user(
    github_id: str, github_username: str, session: AsyncSession
) -> User:
    """Look up User by github_id, create if not found, return User record.

    Handles the race condition where two concurrent requests for the same
    github_id both pass the SELECT and attempt INSERT.
    """
    result = await session.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(github_id=github_id, github_username=github_username)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one()
        return user
    await session.refresh(user)
    return user


async def verify_auth(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedUser:
    """Decode the NextAuth JWT from the Authorization header and return an AuthenticatedUser.

    The frontend proxy re-encodes the NextAuth session token and sends it as
    ``Authorization: Bearer <jwt>``.  The JWT is signed with HS256 using the
    same ``NEXTAUTH_SECRET`` shared between Next.js and this backend.

    Raises 401 on missing / invalid / expired tokens.
    """
    client_ip = request.client.host if request.client else ""

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        log_auth_event(
            action="missing_header", success=False, reason="no bearer", ip=client_ip
        )
        raise HTTPException(401, "Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        log_auth_event(
            action="empty_token", success=False, reason="empty bearer", ip=client_ip
        )
        raise HTTPException(401, "Empty bearer token")

    secret = settings.nextauth_secret
    if not secret:
        logger.error("NEXTAUTH_SECRET is not configured on the backend")
        raise HTTPException(500, "Auth not configured")

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        log_auth_event(action="token_expired", success=False, ip=client_ip)
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        log_auth_event(action="invalid_token", success=False, ip=client_ip)
        raise HTTPException(401, "Invalid token")

    github_id = payload.get("githubId") or payload.get("github_id") or ""
    github_username = (
        payload.get("githubUsername") or payload.get("github_username") or ""
    )

    if not github_id:
        log_auth_event(
            action="missing_claim", success=False, reason="no githubId", ip=client_ip
        )
        raise HTTPException(401, "Token missing githubId claim")

    db_user = await get_or_create_user(str(github_id), str(github_username), session)
    return AuthenticatedUser(
        github_id=str(github_id),
        github_username=str(github_username),
        db_user=db_user,
    )
