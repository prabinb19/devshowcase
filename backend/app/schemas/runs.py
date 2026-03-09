"""Request/response models for the runs API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.models import RunStatus


class CreateRunRequest(BaseModel):
    repo_url: HttpUrl


class RunResponse(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    stream_token: str


class RunDetailResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repo_url: str
    status: RunStatus
    error: str | None = None
    repo_context: dict | None = None
    analysis: dict | None = None
    screenshots: list[dict] | None = None
    post_draft: dict | None = None
    agent_output: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
