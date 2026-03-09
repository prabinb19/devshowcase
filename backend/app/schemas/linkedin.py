"""Request/response models for the LinkedIn OAuth & publishing API."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class LinkedInAuthURLResponse(BaseModel):
    auth_url: str


class LinkedInCallbackRequest(BaseModel):
    code: str
    state: str


class LinkedInTokenStatus(BaseModel):
    connected: bool
    expires_at: str | None = None


class PublishRequest(BaseModel):
    draft_id: uuid.UUID


class PublishResponse(BaseModel):
    success: bool
    post_url: str | None = None
    error: str | None = None
