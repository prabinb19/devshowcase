"""Ingest node — fetches repo metadata, README, file tree from GitHub API."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from langgraph.config import get_stream_writer

from app.services.github_client import (
    extract_readme_images,
    fetch_config_files,
    fetch_file_tree,
    fetch_readme,
    fetch_repo_metadata,
    parse_github_url,
)
from app.state import AgentState

logger = logging.getLogger(__name__)


async def ingest(state: AgentState) -> dict[str, Any]:
    writer = get_stream_writer()
    writer({"stage": "ingesting", "message": "Fetching repository data…"})

    repo_url: str = state.get("repo_url", "")

    # ── Parse & validate URL ──
    try:
        owner, repo = parse_github_url(repo_url)
    except ValueError as exc:
        logger.warning("Invalid repo URL %s: %s", repo_url, exc)
        return {"error": f"Invalid repository URL: {exc}", "current_stage": "ingesting"}

    # ── Fetch data from GitHub ──
    try:
        writer({"stage": "ingesting", "message": "Fetching metadata…"})
        metadata = await fetch_repo_metadata(owner, repo)

        writer({"stage": "ingesting", "message": "Fetching README…"})
        readme = await fetch_readme(owner, repo)

        default_branch = metadata.get("default_branch", "main")
        writer({"stage": "ingesting", "message": "Fetching file tree…"})
        file_tree = await fetch_file_tree(owner, repo, default_branch)

        writer({"stage": "ingesting", "message": "Fetching config files…"})
        config_files = await fetch_config_files(owner, repo, file_tree)

        images_in_readme = extract_readme_images(readme)

    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 404:
            msg = f"Repository not found: {owner}/{repo}"
        elif status == 403:
            msg = "GitHub API rate limit exceeded or access denied"
        else:
            msg = f"GitHub API error (HTTP {status})"
        logger.error("GitHub API error for %s/%s: %s", owner, repo, exc)
        return {"error": msg, "current_stage": "ingesting"}

    except httpx.HTTPError as exc:
        logger.error("Network error fetching %s/%s: %s", owner, repo, exc)
        return {
            "error": f"Network error while fetching repository: {exc}",
            "current_stage": "ingesting",
        }

    return {
        "current_stage": "ingesting",
        "repo_context": {
            "url": repo_url,
            "metadata": metadata,
            "readme": readme,
            "file_tree": file_tree,
            "config_files": config_files,
            "images_in_readme": images_in_readme,
        },
    }
