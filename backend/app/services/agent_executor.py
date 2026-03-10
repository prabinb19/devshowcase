"""Agent executor — manages E2B sandboxes running the DevShowcase agent."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from e2b_desktop import Sandbox as DesktopSandbox
from e2b.sandbox.commands.command_handle import CommandExitException

from app.config import settings
from app.database import async_session
from app.models import Run, RunStatus
from app.services.image_processor import validate_image, process_image
from app.services.r2_storage import upload_image

# Agent source files live alongside this repo
_AGENT_SRC_DIR = Path(__file__).resolve().parents[3] / "e2b-agent" / "agent"

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


_AGENT_STARTUP_TIMEOUT = 120  # seconds to wait for status.json before failing


async def _provision_agent(
    sandbox: DesktopSandbox, queue: asyncio.Queue[dict[str, Any]]
) -> None:
    """Upload agent source files and ensure Python deps are installed."""
    queue.put_nowait(
        {"stage": "agent_starting", "message": "Provisioning agent code..."}
    )

    # Create required directories (world-writable so agent process can write)
    await asyncio.to_thread(
        sandbox.commands.run,
        "mkdir -p /agent /comms /output/images /workspace && chmod 777 /agent /comms /output /output/images /workspace",
        user="root",
    )

    # Upload each agent source file
    for src_file in _AGENT_SRC_DIR.iterdir():
        if src_file.is_file():
            content = src_file.read_text()
            await asyncio.to_thread(
                sandbox.files.write, f"/agent/{src_file.name}", content
            )

    # Set git identity for portfolio commits
    await asyncio.to_thread(
        sandbox.commands.run,
        'git config --global user.name "DevShowcase Agent" && '
        'git config --global user.email "agent@devshowcase.app"',
    )

    # Install Python deps (no-op if already in template)
    dep_result = await asyncio.to_thread(
        sandbox.commands.run,
        "pip3 install -q google-genai==1.14.0 httpx==0.28.1",
    )
    if dep_result.exit_code != 0:
        logger.warning(
            "pip install failed (exit %d): %s", dep_result.exit_code, dep_result.stderr
        )


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
        queue.put_nowait(
            {"stage": "agent_starting", "message": "Starting secure sandbox..."}
        )

        # Create E2B desktop sandbox (sync SDK — run off event loop)
        sandbox = await asyncio.to_thread(
            DesktopSandbox.create,
            template=settings.e2b_template_id or None,
            timeout=settings.agent_sandbox_timeout,
            resolution=(1280, 800),
            envs={
                "CI": "true",
                "GEMINI_API_KEY": settings.gemini_api_key,
                "GITHUB_TOKEN": settings.github_token,
            },
            api_key=settings.e2b_api_key,
        )
        _agent_sandboxes[rid] = sandbox

        stream_url = await asyncio.to_thread(_start_stream, sandbox)
        if stream_url:
            queue.put_nowait(
                {
                    "stage": "agent_starting",
                    "message": "Sandbox ready — live view active",
                    "stream_url": stream_url,
                }
            )

        # Upload agent code and install deps (works with any template)
        await _provision_agent(sandbox, queue)

        # Write mission file
        mission = {
            "repo_url": repo_url,
            "portfolio_repo": settings.portfolio_repo,
            "portfolio_owner": settings.portfolio_owner,
        }
        await asyncio.to_thread(
            sandbox.files.write, "/comms/mission.json", json.dumps(mission)
        )

        # Launch agent in a separate task (not background=True which is unreliable)
        async def _run_agent() -> None:
            try:
                result = await asyncio.to_thread(
                    sandbox.commands.run,
                    "cd /agent && python3 main.py 2>&1 | tee /comms/agent.log",
                )
                logger.info("Agent process exited %d", result.exit_code)
            except CommandExitException as exc:
                logger.error("Agent process failed: %s", exc)
            except Exception:
                logger.exception("Agent process crashed")

        agent_task = asyncio.create_task(_run_agent())

        # Best-effort visible terminal for desktop stream
        try:
            await asyncio.to_thread(
                sandbox.commands.run,
                'DISPLAY=:0 xterm -T "DevShowcase Agent" -fa Monospace -fs 13 '
                '-bg black -fg white -e "tail -f /comms/agent.log" &',
                background=True,
            )
        except Exception:
            pass  # Desktop visibility is optional

        # Monitor the agent (runs concurrently with agent_task)
        await _monitor_agent(run_id, sandbox, queue)

        # Cancel the agent task if monitor finished first (e.g., completed/failed)
        agent_task.cancel()

    except Exception:
        logger.exception("Agent run %s failed", run_id)
        await _update_run_status(
            run_id, RunStatus.failed, error="Agent run failed unexpectedly"
        )
        queue.put_nowait({"stage": "error", "message": "Agent run failed unexpectedly"})
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
    startup_polls = 0

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
                # Agent hasn't written status.json yet — check startup timeout
                startup_polls += 1
                elapsed = startup_polls * 2

                # Every 10s, try to read agent.log for early crash diagnostics
                if elapsed % 10 == 0:
                    try:
                        log_content = await asyncio.to_thread(
                            sandbox.files.read, "/comms/agent.log"
                        )
                        if log_content.strip():
                            logger.info(
                                "Run %s: agent.log after %ds:\n%s",
                                run_id,
                                elapsed,
                                log_content[-2000:],
                            )
                    except Exception:
                        logger.info("Run %s: no agent.log after %ds", run_id, elapsed)

                if elapsed > _AGENT_STARTUP_TIMEOUT:
                    # Try to read agent log for final error context
                    agent_log = ""
                    try:
                        agent_log = await asyncio.to_thread(
                            sandbox.files.read, "/comms/agent.log"
                        )
                    except Exception:
                        pass
                    error_msg = "Agent failed to start within timeout"
                    if agent_log.strip():
                        logger.error(
                            "Run %s startup timeout — log tail: %s",
                            run_id,
                            agent_log.strip()[-500:],
                        )
                    else:
                        logger.error(
                            "Run %s startup timeout — no agent.log found", run_id
                        )
                    await _update_run_status(run_id, RunStatus.failed, error=error_msg)
                    queue.put_nowait({"stage": "error", "message": error_msg})
                    return
                continue

            startup_polls = 0  # Agent is alive, reset timeout counter

            if status_data.get("status") == "completed":
                # Read final result
                try:
                    result_raw = await asyncio.to_thread(
                        sandbox.files.read, "/output/result.json"
                    )
                    result = json.loads(result_raw)
                except Exception:
                    result = {}

                # Upload extracted images from sandbox to R2
                result = await _upload_agent_images(sandbox, run_id, result)

                await _save_agent_output(run_id, result)
                await _update_run_status(run_id, RunStatus.completed)
                queue.put_nowait(
                    {"stage": "completed", "message": "Agent completed successfully"}
                )
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
                    queue.put_nowait(
                        {
                            "stage": "awaiting_answer",
                            "message": question.get("text", "Agent has a question"),
                            "question": question,
                        }
                    )
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


async def _upload_agent_images(
    sandbox: DesktopSandbox, run_id: uuid.UUID, result: dict
) -> dict:
    """Download images from sandbox /output/images/ and upload to R2.

    Replaces screenshot_urls in result with public R2 URLs.
    """
    images = result.get("images", [])
    if not images:
        return result

    r2_urls: list[str] = []
    for img in images:
        local_path = img.get("local_path", "")
        if not local_path:
            continue
        try:
            raw_bytes = await asyncio.to_thread(
                sandbox.files.read, local_path, format="bytes"
            )
            if not raw_bytes or not validate_image(raw_bytes):
                logger.warning("Invalid image from sandbox: %s", local_path)
                continue
            processed = process_image(raw_bytes, max_width=1200, max_height=1200)
            filename = Path(local_path).name
            url = upload_image(processed, str(run_id), filename)
            r2_urls.append(url)
            logger.info("Uploaded agent image to R2: %s", url)
        except Exception:
            logger.exception("Failed to upload agent image %s", local_path)

    if r2_urls and "post_draft" in result:
        result["post_draft"]["screenshot_urls"] = r2_urls
        # Keep alt_texts aligned — trim to match R2 URL count
        alt_texts = result["post_draft"].get("alt_texts", [])
        result["post_draft"]["alt_texts"] = alt_texts[: len(r2_urls)]

    return result


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
