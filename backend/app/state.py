"""LangGraph state definitions and Pydantic models for the pipeline."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel


# ── Pydantic models (serialized into AgentState JSON fields) ──


class RepoMetadata(BaseModel):
    name: str = ""
    description: str = ""
    stars: int = 0
    forks: int = 0
    language: str = ""
    topics: list[str] = []
    url: str = ""
    default_branch: str = "main"


class RepoContext(BaseModel):
    url: str = ""
    metadata: RepoMetadata = RepoMetadata()
    readme: str = ""
    file_tree: list[str] = []
    config_files: dict[str, str] = {}
    images_in_readme: list[str] = []


class ProjectAnalysis(BaseModel):
    project_type: str = ""
    summary: str = ""
    tech_stack: list[str] = []
    key_features: list[str] = []
    run_command: str = ""
    install_command: str = ""
    expected_port: int | None = None
    has_dockerfile: bool = False
    visual_type: str = ""
    screenshot_strategy: str = ""


class Screenshot(BaseModel):
    url: str = ""
    alt_text: str = ""
    source: str = ""
    width: int = 0
    height: int = 0


class PostDraft(BaseModel):
    platform: str = "linkedin"
    body: str = ""
    first_comment: str = ""
    screenshot_urls: list[str] = []
    alt_texts: list[str] = []
    status: str = "draft"


class PublishResult(BaseModel):
    platform: str = ""
    success: bool = False
    post_url: str = ""
    error: str = ""
    published_at: str = ""


# ── LangGraph state ──


class AgentState(TypedDict, total=False):
    repo_url: str
    run_id: str
    user_id: str
    repo_context: dict
    analysis: dict
    screenshots: list[dict]
    post_draft: dict
    user_feedback: str
    publish_result: dict
    error: str
    current_stage: str
