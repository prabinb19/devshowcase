"""Request/response models for the drafts API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models import DraftStatus


class CreateDraftRequest(BaseModel):
    run_id: uuid.UUID
    user_id: uuid.UUID
    body: str
    first_comment: str | None = None
    screenshot_urls: list[str] | None = None
    alt_texts: list[str] | None = None


class UpdateDraftRequest(BaseModel):
    body: str | None = None
    first_comment: str | None = None
    screenshot_urls: list[str] | None = None
    alt_texts: list[str] | None = None
    status: DraftStatus | None = None


class DraftResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    user_id: uuid.UUID
    platform: str
    body: str
    first_comment: str | None = None
    screenshot_urls: list[str] | None = None
    alt_texts: list[str] | None = None
    status: DraftStatus
    published_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
