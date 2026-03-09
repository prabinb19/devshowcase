"""API endpoints for managing pipeline runs."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import get_session
from app.models import Run, RunStatus
from app.routes.deps import AuthenticatedUser, verify_auth
from app.schemas.runs import CreateRunRequest, RunDetailResponse, RunResponse
from app.services.agent_executor import get_event_queue, start_agent_run, submit_answer

router = APIRouter(prefix="/runs", tags=["runs"])
logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def _create_stream_token(run_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Create a short-lived JWT for authenticating SSE stream connections."""
    payload = {
        "run_id": str(run_id),
        "user_id": str(user_id),
        "purpose": "stream",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.nextauth_secret, algorithm="HS256")


def _track_task(task: asyncio.Task) -> None:
    """Add task to background set and register cleanup callback."""
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception():
            logger.error("Background task failed: %s", t.exception())

    task.add_done_callback(_on_done)


@router.post("", status_code=202, response_model=RunResponse)
async def create_run(
    body: CreateRunRequest,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """Create a new agent run for the given repository URL."""
    user = auth.db_user

    run = Run(
        user_id=user.id,
        repo_url=str(body.repo_url),
        status=RunStatus.pending,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    task = asyncio.create_task(start_agent_run(run.id, user.id, str(body.repo_url)))
    _track_task(task)

    stream_token = _create_stream_token(run.id, user.id)
    return RunResponse(run_id=run.id, status=run.status, stream_token=stream_token)


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: uuid.UUID,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> RunDetailResponse:
    """Get the current status and results of a run."""
    result = await session.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    if run.user_id != auth.db_user.id:
        raise HTTPException(403, "Not authorized to access this run")
    return RunDetailResponse.model_validate(run)


class AgentAnswer(BaseModel):
    text: str = Field(..., max_length=10_000)


@router.post("/{run_id}/answer", status_code=204)
async def answer_agent_question(
    run_id: uuid.UUID,
    body: AgentAnswer,
    auth: AuthenticatedUser = Depends(verify_auth),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Submit an answer to an agent's question."""
    result = await session.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    if run.user_id != auth.db_user.id:
        raise HTTPException(403, "Not authorized to interact with this run")
    await submit_answer(str(run_id), body.text)


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, token: str = Query(...)) -> EventSourceResponse:
    """SSE stream of agent progress events for a run.

    Requires a short-lived JWT stream token passed via ?token= query parameter.
    The token is returned by the create_run endpoint.
    """
    try:
        payload = jwt.decode(token, settings.nextauth_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Stream token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid stream token")

    if payload.get("purpose") != "stream":
        raise HTTPException(401, "Invalid token purpose")
    if payload.get("run_id") != str(run_id):
        raise HTTPException(403, "Token does not match this run")

    queue = get_event_queue(str(run_id))

    async def event_generator():
        if not queue:
            yield {"event": "error", "data": "No active agent session"}
            return

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keepalive"}
                continue

            event_type = "question" if "question" in event else "status"
            yield {"event": event_type, "data": json.dumps(event)}

            if event.get("stage") in ("completed", "error"):
                yield {"event": "done", "data": "complete"}
                return

    return EventSourceResponse(event_generator(), ping=15)
