"""Shared test fixtures and helpers."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.routes.deps import AuthenticatedUser


def make_fake_auth(
    github_id: str = "12345",
    github_username: str = "testuser",
    user_id: uuid.UUID | None = None,
) -> AuthenticatedUser:
    """Create a fake AuthenticatedUser for test dependency overrides."""
    mock_user = MagicMock()
    mock_user.id = user_id or uuid.uuid4()
    mock_user.github_id = github_id
    mock_user.github_username = github_username
    return AuthenticatedUser(
        github_id=github_id,
        github_username=github_username,
        db_user=mock_user,
    )
