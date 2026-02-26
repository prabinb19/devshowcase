"""Tests for the settings API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_session


def _make_mock_session(*, execute_return=None) -> AsyncMock:
    """Build a mock AsyncSession with configurable query results."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    if execute_return is not None:
        session.execute = AsyncMock(return_value=execute_return)
    return session


def _make_user(*, preferences: dict | None = None) -> MagicMock:
    """Create a mock User with optional preferences."""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.github_id = "12345"
    user.github_username = "testuser"
    user.preferences = preferences
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


@pytest.fixture
def mock_graph():
    """Patch the compiled_graph and lifespan so tests don't need Postgres."""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value={"current_stage": "completed"})

    with (
        patch("app.graph.init_graph", new_callable=AsyncMock),
        patch("app.graph.shutdown_graph", new_callable=AsyncMock),
        patch("app.graph.compiled_graph", mock),
    ):
        yield mock


@pytest_asyncio.fixture
async def client(mock_graph):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


HEADERS = {"X-GitHub-Id": "12345", "X-GitHub-Username": "testuser"}


async def test_get_settings_defaults(client: AsyncClient):
    """GET /api/settings returns defaults when user has no preferences."""
    from app.main import app

    user = _make_user(preferences=None)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.get("/api/settings", headers=HEADERS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["default_tone"] == "professional"
    assert data["hashtags"] == []


async def test_get_settings_stored(client: AsyncClient):
    """GET /api/settings returns stored preferences."""
    from app.main import app

    user = _make_user(preferences={
        "default_tone": "casual",
        "hashtags": ["python", "devops"],
    })
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.get("/api/settings", headers=HEADERS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["default_tone"] == "casual"
    assert data["hashtags"] == ["python", "devops"]


async def test_put_settings_updates(client: AsyncClient):
    """PUT /api/settings updates and returns new preferences."""
    from app.main import app

    user = _make_user(preferences=None)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session = _make_mock_session(execute_return=result_mock)

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
    try:
        response = await client.put(
            "/api/settings",
            headers=HEADERS,
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

    user = _make_user()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.put(
            "/api/settings",
            headers=HEADERS,
            json={"default_tone": "sarcastic", "hashtags": []},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_get_settings_missing_auth(client: AsyncClient):
    """GET /api/settings without required header returns 422."""
    response = await client.get("/api/settings")
    assert response.status_code == 422
