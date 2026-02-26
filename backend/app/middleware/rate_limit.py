"""DB-backed rate limiting middleware for run creation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from sqlalchemy import func, select

from app.config import settings
from app.database import async_session
from app.models import Run


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limits POST /api/runs to N per hour per user (via X-GitHub-Id header)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method != "POST" or request.url.path != "/api/runs":
            return await call_next(request)

        github_id = request.headers.get("X-GitHub-Id")
        if not github_id:
            return await call_next(request)

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        async with async_session() as session:
            # Count recent runs by looking up the user's UUID from github_id
            from app.models import User
            user_result = await session.execute(
                select(User.id).where(User.github_id == github_id)
            )
            user_id = user_result.scalar_one_or_none()
            if not user_id:
                # New user — no runs yet, allow
                return await call_next(request)

            result = await session.execute(
                select(func.count(Run.id)).where(
                    Run.user_id == user_id,
                    Run.created_at >= one_hour_ago,
                )
            )
            count = result.scalar_one()

        if count >= settings.rate_limit_runs_per_hour:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded: max {settings.rate_limit_runs_per_hour} runs per hour"
                },
            )

        return await call_next(request)
