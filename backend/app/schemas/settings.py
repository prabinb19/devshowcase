"""Request/response models for user settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ToneOption = Literal["professional", "casual", "technical", "enthusiastic"]


class UserSettings(BaseModel):
    default_tone: ToneOption = "professional"
    hashtags: list[str] = Field(default=[], max_length=30)


class UserSettingsResponse(BaseModel):
    default_tone: ToneOption
    hashtags: list[str]
