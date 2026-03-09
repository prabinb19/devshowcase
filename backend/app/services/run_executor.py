"""Background graph execution for pipeline runs."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select

from app.database import async_session
import app.graph
from app.models import Run, RunStatus
from app.nodes.generate import generate

logger = logging.getLogger(__name__)


async def execute_graph(run_id: uuid.UUID, user_id: uuid.UUID, repo_url: str) -> None:
    """Execute the LangGraph pipeline for a run. Called via asyncio.create_task()."""
    if app.graph.compiled_graph is None:
        logger.error("Graph not initialized — cannot execute run %s", run_id)
        return

    # Mark run as ingesting
    async with async_session() as session:
        result = await session.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            logger.error("Run %s not found in DB", run_id)
            return
        run.status = RunStatus.ingesting
        await session.commit()

    initial_state = {
        "repo_url": repo_url,
        "run_id": str(run_id),
        "user_id": str(user_id),
    }
    config = {"configurable": {"thread_id": str(run_id)}}

    try:
        final_state = await app.graph.compiled_graph.ainvoke(initial_state, config)

        # Update run with results
        async with async_session() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if not run:
                return

            if final_state.get("error"):
                run.status = RunStatus.failed
                run.error = final_state["error"]
            else:
                run.status = RunStatus.completed
                run.repo_context = final_state.get("repo_context")
                run.analysis = final_state.get("analysis")
                run.screenshots = final_state.get("screenshots")
                run.post_draft = final_state.get("post_draft")

            await session.commit()

    except Exception:
        logger.exception("Unhandled error in run %s", run_id)
        async with async_session() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = RunStatus.failed
                run.error = "Pipeline execution failed unexpectedly"
                await session.commit()


async def execute_graph_from_generate(
    run_id: uuid.UUID,
    repo_context: dict[str, Any] | None,
    analysis: dict[str, Any] | None,
    screenshots: list[dict[str, Any]] | None,
    user_feedback: str,
) -> None:
    """Re-run only the generate node with user feedback. Called via asyncio.create_task()."""
    state = {
        "run_id": str(run_id),
        "repo_context": repo_context or {},
        "analysis": analysis or {},
        "screenshots": screenshots or [],
        "user_feedback": user_feedback,
    }

    try:
        result = await generate(state)

        async with async_session() as session:
            db_result = await session.execute(select(Run).where(Run.id == run_id))
            run = db_result.scalar_one_or_none()
            if not run:
                return

            if result.get("error"):
                run.status = RunStatus.failed
                run.error = result["error"]
            else:
                run.status = RunStatus.completed
                run.post_draft = result.get("post_draft")

            await session.commit()

    except Exception:
        logger.exception("Unhandled error in regenerate run %s", run_id)
        async with async_session() as session:
            db_result = await session.execute(select(Run).where(Run.id == run_id))
            run = db_result.scalar_one_or_none()
            if run:
                run.status = RunStatus.failed
                run.error = "Post regeneration failed unexpectedly"
                await session.commit()
