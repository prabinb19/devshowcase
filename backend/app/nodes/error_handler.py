"""Error handler node — records failure in the database."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.config import get_stream_writer
from sqlalchemy import select

from app.database import async_session
from app.models import Run, RunStatus
from app.state import AgentState

logger = logging.getLogger(__name__)


async def handle_error(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    error_msg = state.get("error", "Unknown error")
    run_id = state.get("run_id")

    writer({"stage": "error", "message": error_msg})
    logger.error("Run %s failed: %s", run_id, error_msg)

    if run_id:
        async with async_session() as session:
            result = await session.execute(select(Run).where(Run.id == run_id))
            run = result.scalar_one_or_none()
            if run:
                run.status = RunStatus.failed
                run.error = error_msg
                await session.commit()

    return {"current_stage": "failed"}
