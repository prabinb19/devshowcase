"""Background graph execution for pipeline runs."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.database import async_session
from app.graph import compiled_graph
from app.models import Run, RunStatus

logger = logging.getLogger(__name__)


async def execute_graph(
    run_id: uuid.UUID, user_id: uuid.UUID, repo_url: str
) -> None:
    """Execute the LangGraph pipeline for a run. Called via asyncio.create_task()."""
    if compiled_graph is None:
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
        final_state = await compiled_graph.ainvoke(initial_state, config)

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

            await session.commit()

    except Exception:
        logger.exception("Unhandled error in run %s", run_id)
        async with async_session() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = RunStatus.failed
                run.error = "Internal pipeline error"
                await session.commit()
