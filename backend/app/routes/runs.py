"""API endpoints for managing pipeline runs."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_session
from app.graph import compiled_graph
from app.models import Run, RunStatus
from app.routes.deps import get_or_create_user
from app.schemas.runs import CreateRunRequest, RunDetailResponse, RunResponse
from app.services.run_executor import execute_graph, execute_graph_from_generate

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", status_code=202, response_model=RunResponse)
async def create_run(
    body: CreateRunRequest,
    session: AsyncSession = Depends(get_session),
    x_github_id: str = Header(..., alias="X-GitHub-Id"),
    x_github_username: str = Header("unknown", alias="X-GitHub-Username"),
) -> RunResponse:
    """Create a new pipeline run for the given repository URL."""
    if compiled_graph is None:
        raise HTTPException(503, "Pipeline not ready")

    user = await get_or_create_user(x_github_id, x_github_username, session)

    run = Run(
        user_id=user.id,
        repo_url=str(body.repo_url),
        status=RunStatus.pending,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    asyncio.create_task(execute_graph(run.id, user.id, str(body.repo_url)))

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


class RegenerateRequest(BaseModel):
    feedback: str


@router.post("/{run_id}/regenerate", status_code=202, response_model=RunResponse)
async def regenerate_run(
    run_id: uuid.UUID,
    body: RegenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    """Re-run the generate stage with user feedback."""
    result = await session.execute(select(Run).where(Run.id == run_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(404, "Original run not found")

    new_run = Run(
        user_id=original.user_id,
        repo_url=original.repo_url,
        status=RunStatus.generating,
        repo_context=original.repo_context,
        analysis=original.analysis,
        screenshots=original.screenshots,
    )
    session.add(new_run)
    await session.commit()
    await session.refresh(new_run)

    asyncio.create_task(
        execute_graph_from_generate(
            new_run.id,
            original.repo_context,
            original.analysis,
            original.screenshots,
            body.feedback,
        )
    )

    return RunResponse(run_id=new_run.id, status=new_run.status)


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID) -> EventSourceResponse:
    """SSE stream of pipeline progress events for a run."""
    if compiled_graph is None:
        raise HTTPException(503, "Pipeline not ready")

    config = {"configurable": {"thread_id": str(run_id)}}

    async def event_generator():
        try:
            async for chunk in compiled_graph.astream(
                None, config, stream_mode="custom"
            ):
                yield {"event": "status", "data": str(chunk)}
        except Exception as exc:
            yield {"event": "error", "data": str(exc)}
            return

        yield {"event": "done", "data": "complete"}

    return EventSourceResponse(event_generator(), ping=15)
