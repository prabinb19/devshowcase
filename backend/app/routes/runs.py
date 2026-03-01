"""API endpoints for managing pipeline runs."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_session
from app.models import Run, RunStatus
from app.routes.deps import get_or_create_user
from app.schemas.runs import CreateRunRequest, RunDetailResponse, RunResponse
from app.services.agent_executor import get_event_queue, start_agent_run, submit_answer

router = APIRouter(prefix="/runs", tags=["runs"])
logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


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
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header(..., alias="X-GitHub-Username"),
) -> RunResponse:
    """Create a new agent run for the given repository URL."""
    user = await get_or_create_user(x_github_id, x_github_username, session)

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

    return RunResponse(run_id=run.id, status=run.status)


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RunDetailResponse:
    """Get the current status and results of a run."""
    result = await session.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    return RunDetailResponse.model_validate(run)


class AgentAnswer(BaseModel):
    text: str


@router.post("/{run_id}/answer", status_code=204)
async def answer_agent_question(
    run_id: uuid.UUID,
    body: AgentAnswer,
) -> None:
    """Submit an answer to an agent's question."""
    await submit_answer(str(run_id), body.text)


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID) -> EventSourceResponse:
    """SSE stream of agent progress events for a run."""
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
