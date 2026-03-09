"""Tests for the drafts API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.models import Draft, DraftStatus
from app.routes.deps import verify_auth
from tests.conftest import make_fake_auth


def _make_mock_session(*, execute_return=None) -> AsyncMock:
    """Build a mock AsyncSession with configurable query results."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    if execute_return is not None:
        session.execute = AsyncMock(return_value=execute_return)
    return session


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def run_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_draft(user_id: uuid.UUID, run_id: uuid.UUID) -> Draft:
    return Draft(
        id=uuid.uuid4(),
        run_id=run_id,
        user_id=user_id,
        platform="linkedin",
        body="Check out my project!",
        first_comment="Link in bio",
        screenshot_urls=["https://img.example.com/1.png"],
        alt_texts=["Screenshot of the app"],
        status=DraftStatus.draft,
        published_url=None,
        published_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_draft(client: AsyncClient, user_id: uuid.UUID, run_id: uuid.UUID):
    """POST /api/drafts creates a draft and returns 201."""
    from app.main import app

    draft_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_auth = make_fake_auth(user_id=user_id)
    session = _make_mock_session()
    session.refresh = AsyncMock(
        side_effect=lambda draft: (
            setattr(draft, "id", draft_id),
            setattr(draft, "platform", "linkedin"),
            setattr(draft, "status", DraftStatus.draft),
            setattr(draft, "created_at", now),
            setattr(draft, "updated_at", now),
        )
    )

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.post(
            "/api/drafts",
            json={
                "run_id": str(run_id),
                "user_id": str(user_id),
                "body": "My awesome project!",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["body"] == "My awesome project!"
    assert data["status"] == "draft"


async def test_list_drafts(
    client: AsyncClient, user_id: uuid.UUID, sample_draft: Draft
):
    """GET /api/drafts returns drafts for the authenticated user."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [sample_draft]
    result_mock.scalars.return_value = scalars_mock
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.get("/api/drafts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["body"] == "Check out my project!"


async def test_get_draft_found(
    client: AsyncClient, user_id: uuid.UUID, sample_draft: Draft
):
    """GET /api/drafts/{id} returns draft data for a known draft."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_draft
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.get(f"/api/drafts/{sample_draft.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["body"] == "Check out my project!"


async def test_get_draft_not_found(client: AsyncClient):
    """GET /api/drafts/{id} returns 404 for unknown draft."""
    from app.main import app

    fake_auth = make_fake_auth()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.get(f"/api/drafts/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


async def test_update_draft(
    client: AsyncClient, user_id: uuid.UUID, sample_draft: Draft
):
    """PATCH /api/drafts/{id} updates fields."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_draft
    session = _make_mock_session(execute_return=result_mock)
    session.refresh = AsyncMock(
        side_effect=lambda draft: setattr(draft, "body", "Updated body")
    )

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.patch(
            f"/api/drafts/{sample_draft.id}",
            json={"body": "Updated body"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["body"] == "Updated body"


async def test_update_draft_not_found(client: AsyncClient):
    """PATCH /api/drafts/{id} returns 404 for unknown draft."""
    from app.main import app

    fake_auth = make_fake_auth()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.patch(
            f"/api/drafts/{uuid.uuid4()}",
            json={"body": "Updated body"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


async def test_delete_draft(
    client: AsyncClient, user_id: uuid.UUID, sample_draft: Draft
):
    """DELETE /api/drafts/{id} deletes and returns 204."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_draft
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.delete(f"/api/drafts/{sample_draft.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204


async def test_delete_draft_not_found(client: AsyncClient):
    """DELETE /api/drafts/{id} returns 404 for unknown draft."""
    from app.main import app

    fake_auth = make_fake_auth()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session = _make_mock_session(execute_return=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.delete(f"/api/drafts/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
