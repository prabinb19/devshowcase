"""Tests for the settings API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.routes.deps import verify_auth
from tests.conftest import make_fake_auth


def _make_mock_session(*, execute_return=None) -> AsyncMock:
    """Build a mock AsyncSession with configurable query results."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    if execute_return is not None:
        session.execute = AsyncMock(return_value=execute_return)
    return session


def _make_user(*, preferences: dict | None = None, user_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock User with optional preferences."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.github_id = "12345"
    user.github_username = "testuser"
    user.preferences = preferences
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_get_settings_defaults(client: AsyncClient):
    """GET /api/settings returns defaults when user has no preferences."""
    from app.main import app

    uid = uuid.uuid4()
    user = _make_user(preferences=None, user_id=uid)
    fake_auth = make_fake_auth(user_id=uid)
    fake_auth.db_user = user

    session = _make_mock_session()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.get("/api/settings")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["default_tone"] == "professional"
    assert data["hashtags"] == []


async def test_get_settings_stored(client: AsyncClient):
    """GET /api/settings returns stored preferences."""
    from app.main import app

    uid = uuid.uuid4()
    user = _make_user(
        preferences={"default_tone": "casual", "hashtags": ["python", "devops"]},
        user_id=uid,
    )
    fake_auth = make_fake_auth(user_id=uid)
    fake_auth.db_user = user

    session = _make_mock_session()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.get("/api/settings")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["default_tone"] == "casual"
    assert data["hashtags"] == ["python", "devops"]


async def test_put_settings_updates(client: AsyncClient):
    """PUT /api/settings updates and returns new preferences."""
    from app.main import app

    uid = uuid.uuid4()
    user = _make_user(preferences=None, user_id=uid)
    fake_auth = make_fake_auth(user_id=uid)
    fake_auth.db_user = user

    session = _make_mock_session()

    # After refresh, user.preferences should reflect the update
    def fake_refresh(obj):
        obj.preferences = {
            "default_tone": "technical",
            "hashtags": ["ai"],
        }

    session.refresh = AsyncMock(side_effect=fake_refresh)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.put(
            "/api/settings",
            json={"default_tone": "technical", "hashtags": ["ai"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["default_tone"] == "technical"
    assert data["hashtags"] == ["ai"]
    session.commit.assert_awaited_once()


async def test_put_settings_invalid_tone(client: AsyncClient):
    """PUT /api/settings with invalid tone returns 422."""
    from app.main import app

    fake_auth = make_fake_auth()

    session = _make_mock_session()

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.put(
            "/api/settings",
            json={"default_tone": "sarcastic", "hashtags": []},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_get_settings_missing_auth(client: AsyncClient):
    """GET /api/settings without authorization returns 401."""
    response = await client.get("/api/settings")
    assert response.status_code == 401
