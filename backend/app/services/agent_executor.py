"""Agent executor — manages E2B sandboxes running the DevShowcase agent."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from e2b_desktop import Sandbox as DesktopSandbox

from app.config import settings
from app.database import async_session
from app.models import Run, RunStatus

logger = logging.getLogger(__name__)

# In-memory state for active agent sessions
_agent_events: dict[str, asyncio.Queue[dict[str, Any]]] = {}
_agent_sandboxes: dict[str, DesktopSandbox] = {}
_pending_questions: dict[str, dict[str, Any]] = {}

# Map agent progress stages to RunStatus values
def _start_stream(sandbox: DesktopSandbox) -> str | None:
    """Start desktop stream and return the view-only URL, or None on failure."""
    if not settings.e2b_enable_stream:
        return None
    try:
        sandbox.stream.start(require_auth=True)
        auth_key = sandbox.stream.get_auth_key()
        return sandbox.stream.get_url(auth_key=auth_key, view_only=True)
    except Exception as exc:
        logger.warning("Failed to start desktop stream: %s", exc)
        return None


_STAGE_TO_STATUS: dict[str, RunStatus] = {
    "exploring": RunStatus.agent_exploring,
    "extracting_images": RunStatus.agent_exploring,
    "generating": RunStatus.agent_generating,
    "portfolio": RunStatus.agent_updating_portfolio,
}


async def start_agent_run(run_id: uuid.UUID, user_id: uuid.UUID, repo_url: str) -> None:
    """Launch an agent sandbox and monitor its progress."""
    rid = str(run_id)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _agent_events[rid] = queue

    try:
        # Update run status
        await _update_run_status(run_id, RunStatus.agent_starting)
        queue.put_nowait({"stage": "agent_starting", "message": "Starting secure sandbox..."})

        # Create E2B desktop sandbox (sync SDK — run off event loop)
        sandbox = await asyncio.to_thread(
            DesktopSandbox.create,
            template=settings.e2b_template_id or None,
            timeout=settings.agent_sandbox_timeout,
            resolution=(1280, 800),
            envs={"CI": "true"},
            api_key=settings.e2b_api_key,
        )
        _agent_sandboxes[rid] = sandbox

        stream_url = await asyncio.to_thread(_start_stream, sandbox)
        if stream_url:
            queue.put_nowait({
                "stage": "agent_starting",
                "message": "Sandbox ready — live view active",
                "stream_url": stream_url,
            })

        # Write mission file
        mission = {
            "repo_url": repo_url,
            "gemini_api_key": settings.gemini_api_key,
            "github_token": settings.github_token,
            "portfolio_repo": settings.portfolio_repo,
            "portfolio_owner": settings.portfolio_owner,
        }
        await asyncio.to_thread(
            sandbox.files.write, "/comms/mission.json", json.dumps(mission)
        )

        # Start the agent process
        await asyncio.to_thread(
            sandbox.commands.run, "python3 /agent/main.py", background=True
        )

        # Monitor the agent
        await _monitor_agent(run_id, sandbox, queue)

    except Exception as exc:
        logger.exception("Agent run %s failed", run_id)
        await _update_run_status(run_id, RunStatus.failed, error=str(exc))
        queue.put_nowait({"stage": "error", "message": str(exc)})
    finally:
        _cleanup(rid)


async def _monitor_agent(
    run_id: uuid.UUID,
    sandbox: DesktopSandbox,
    queue: asyncio.Queue[dict[str, Any]],
) -> None:
    """Poll sandbox files for progress updates."""
    rid = str(run_id)
    last_progress_stage = ""
    last_question_id = ""

    while True:
        await asyncio.sleep(2)

        try:
            # Check status (sync SDK calls off event loop)
            try:
                status_raw = await asyncio.to_thread(
                    sandbox.files.read, "/comms/status.json"
                )
                status_data = json.loads(status_raw)
            except Exception:
                continue

            if status_data.get("status") == "completed":
                # Read final result
                try:
                    result_raw = await asyncio.to_thread(
                        sandbox.files.read, "/output/result.json"
                    )
                    result = json.loads(result_raw)
                except Exception:
                    result = {}

                await _save_agent_output(run_id, result)
                await _update_run_status(run_id, RunStatus.completed)
                queue.put_nowait({"stage": "completed", "message": "Agent completed successfully"})
                return

            if status_data.get("status") == "failed":
                error_msg = status_data.get("error", "Agent failed")
                await _update_run_status(run_id, RunStatus.failed, error=error_msg)
                queue.put_nowait({"stage": "error", "message": error_msg})
                return

            # Check progress
            try:
                progress_raw = await asyncio.to_thread(
                    sandbox.files.read, "/comms/progress.json"
                )
                progress = json.loads(progress_raw)
                stage = progress.get("stage", "")
                if stage and stage != last_progress_stage:
                    last_progress_stage = stage
                    message = progress.get("message", stage)
                    # Update run status
                    run_status = _STAGE_TO_STATUS.get(stage, RunStatus.agent_exploring)
                    await _update_run_status(run_id, run_status)
                    queue.put_nowait({"stage": stage, "message": message})
            except Exception:
                pass

            # Check for questions
            try:
                question_raw = await asyncio.to_thread(
                    sandbox.files.read, "/comms/question.json"
                )
                question = json.loads(question_raw)
                qid = question.get("question_id", "")
                if qid and qid != last_question_id:
                    last_question_id = qid
                    _pending_questions[rid] = question
                    await _update_run_status(run_id, RunStatus.agent_awaiting_answer)
                    queue.put_nowait({
                        "stage": "awaiting_answer",
                        "message": question.get("text", "Agent has a question"),
                        "question": question,
                    })
            except Exception:
                pass

        except Exception as exc:
            logger.warning("Monitor error for run %s: %s", run_id, exc)
            continue


async def submit_answer(run_id: str, answer_text: str) -> None:
    """Write an answer to the sandbox for the agent to read."""
    sandbox = _agent_sandboxes.get(run_id)
    question = _pending_questions.pop(run_id, None)
    if not sandbox or not question:
        return

    answer = {
        "question_id": question["question_id"],
        "text": answer_text,
    }
    await asyncio.to_thread(
        sandbox.files.write, "/comms/answer.json", json.dumps(answer)
    )


def get_event_queue(run_id: str) -> asyncio.Queue[dict[str, Any]] | None:
    """Get the SSE event queue for a run."""
    return _agent_events.get(run_id)


def _cleanup(run_id: str) -> None:
    """Clean up all in-memory state for a run."""
    _agent_events.pop(run_id, None)
    _pending_questions.pop(run_id, None)
    sandbox = _agent_sandboxes.pop(run_id, None)
    if sandbox:
        try:
            sandbox.kill()
        except Exception:
            pass


async def _update_run_status(
    run_id: uuid.UUID, status: RunStatus, *, error: str | None = None
) -> None:
    """Update run status in the database."""
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            if error is not None:
                run.error = error
            await session.commit()


async def _save_agent_output(run_id: uuid.UUID, output: dict) -> None:
    """Save agent output to the database."""
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(select(Run).where(Run.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.agent_output = output
            # Also populate post_draft for backward compat with review page
            if "post_draft" in output:
                run.post_draft = output["post_draft"]
            await session.commit()
