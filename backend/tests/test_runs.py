"""Tests for the runs API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.models import Run, RunStatus


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_run(user_id: uuid.UUID) -> Run:
    run = Run(
        id=uuid.uuid4(),
        user_id=user_id,
        repo_url="https://github.com/test/repo",
        status=RunStatus.pending,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return run


def _make_mock_session(
    *, execute_return=None, scalar_one_or_none=None
) -> AsyncMock:
    """Build a mock AsyncSession with configurable query results."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    if execute_return is not None:
        session.execute = AsyncMock(return_value=execute_return)
    return session


@pytest.fixture
def mock_graph():
    """Patch the compiled_graph and lifespan so tests don't need Postgres."""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value={"current_stage": "completed"})

    with (
        patch("app.graph.init_graph", new_callable=AsyncMock),
        patch("app.graph.shutdown_graph", new_callable=AsyncMock),
        patch("app.graph.compiled_graph", mock),
        patch("app.routes.runs.compiled_graph", mock),
        patch("app.services.run_executor.compiled_graph", mock),
    ):
        yield mock


@pytest_asyncio.fixture
async def client(mock_graph):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_run_returns_202(
    client: AsyncClient, user_id: uuid.UUID
):
    """POST /api/runs returns 202 with a run_id."""
    from app.main import app

    run_id = uuid.uuid4()
    session = _make_mock_session()
    session.refresh = AsyncMock(
        side_effect=lambda run: setattr(run, "id", run_id)
    )

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.post(
            "/api/runs",
            json={"repo_url": "https://github.com/test/repo"},
            headers={"X-User-Id": str(user_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "pending"


async def test_get_run_not_found(client: AsyncClient):
    """GET /api/runs/{id} returns 404 for unknown run."""
    from app.main import app

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.get(f"/api/runs/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


async def test_get_run_found(client: AsyncClient, sample_run: Run):
    """GET /api/runs/{id} returns run data for a known run."""
    from app.main import app

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_run
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.get(f"/api/runs/{sample_run.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["repo_url"] == "https://github.com/test/repo"
    assert data["status"] == "pending"


async def test_rate_limit_returns_429(
    client: AsyncClient, user_id: uuid.UUID
):
    """POST /api/runs returns 429 after rate limit is exceeded."""
    with patch(
        "app.middleware.rate_limit.async_session"
    ) as mock_session_factory:
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one.return_value = 10
        session.execute = AsyncMock(return_value=result)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = session

        response = await client.post(
            "/api/runs",
            json={"repo_url": "https://github.com/test/repo"},
            headers={"X-User-Id": str(user_id)},
        )

    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]
