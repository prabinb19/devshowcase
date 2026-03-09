"""Tests for the LinkedIn OAuth & publishing endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

from app.database import get_session
from app.models import Draft, DraftStatus, Token, User
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
def github_id() -> str:
    return "12345"


@pytest.fixture
def github_username() -> str:
    return "testuser"


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def sample_user(user_id: uuid.UUID) -> User:
    return User(
        id=user_id,
        github_id="12345",
        github_username="testuser",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_draft(user_id: uuid.UUID) -> Draft:
    return Draft(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=user_id,
        platform="linkedin",
        body="Check out my project!",
        first_comment="GitHub link: https://github.com/test/repo",
        screenshot_urls=["https://img.example.com/1.png"],
        alt_texts=["Screenshot of the app"],
        status=DraftStatus.draft,
        published_url=None,
        published_at=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_token(user_id: uuid.UUID, fernet_key: str) -> Token:
    from cryptography.fernet import Fernet

    f = Fernet(fernet_key.encode())
    return Token(
        id=uuid.uuid4(),
        user_id=user_id,
        platform="linkedin",
        encrypted_access_token=f.encrypt(b"test_access_token").decode(),
        encrypted_refresh_token=f.encrypt(b"test_refresh_token").decode(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Token encryption round-trip ---


async def test_token_encryption_roundtrip(fernet_key: str):
    """encrypt_token and decrypt_token are inverse operations."""
    with patch("app.services.token_encryption.settings") as mock_settings:
        mock_settings.token_encryption_key = fernet_key
        # Reset the singleton so it picks up our test key
        import app.services.token_encryption as te

        te._fernet = None

        plaintext = "my_secret_access_token_12345"
        encrypted = te.encrypt_token(plaintext)
        assert encrypted != plaintext
        decrypted = te.decrypt_token(encrypted)
        assert decrypted == plaintext

        te._fernet = None  # Clean up singleton


# --- GET /api/linkedin/auth-url ---


async def test_get_auth_url(client: AsyncClient):
    """GET /api/linkedin/auth-url returns a valid LinkedIn OAuth URL."""
    from app.main import app

    fake_auth = make_fake_auth()

    with patch("app.services.linkedin_client.settings") as mock_settings:
        mock_settings.linkedin_client_id = "test_client_id"
        mock_settings.linkedin_redirect_uri = (
            "http://localhost:3000/api/linkedin/callback"
        )

        app.dependency_overrides[verify_auth] = lambda: fake_auth
        try:
            response = await client.get("/api/linkedin/auth-url")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert "auth_url" in data
    assert "linkedin.com/oauth" in data["auth_url"]
    assert "test_client_id" in data["auth_url"]


# --- POST /api/linkedin/callback ---


async def test_callback_stores_token(
    client: AsyncClient,
    github_id: str,
    github_username: str,
    user_id: uuid.UUID,
    sample_user: User,
    fernet_key: str,
):
    """POST /api/linkedin/callback stores encrypted tokens."""
    from app.main import app

    fake_auth = make_fake_auth(
        github_id=github_id, github_username=github_username, user_id=user_id
    )

    session = _make_mock_session()

    # Mock _get_user_token returning None (no existing token)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    # Pre-store a valid state to pass validation
    from app.routes.linkedin import _store_state

    _store_state("test_state", github_id)

    # Mock token exchange
    with patch(
        "app.routes.linkedin.exchange_code_for_tokens", new_callable=AsyncMock
    ) as mock_exchange:
        mock_exchange.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        with patch("app.routes.linkedin.encrypt_token") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_value"

            async def override_session():
                yield session

            app.dependency_overrides[get_session] = override_session
            app.dependency_overrides[verify_auth] = lambda: fake_auth
            try:
                response = await client.post(
                    "/api/linkedin/callback",
                    json={"code": "test_auth_code", "state": "test_state"},
                )
            finally:
                app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    session.add.assert_called_once()


# --- GET /api/linkedin/status ---


async def test_status_connected(
    client: AsyncClient,
    user_id: uuid.UUID,
    sample_user: User,
    sample_token: Token,
    fernet_key: str,
):
    """GET /api/linkedin/status returns connected=True when token exists."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    session = _make_mock_session()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_token
    session.execute = AsyncMock(return_value=result_mock)

    with patch("app.routes.linkedin.decrypt_token", return_value="test_access_token"):

        async def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[verify_auth] = lambda: fake_auth
        try:
            response = await client.get("/api/linkedin/status")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True


async def test_status_not_connected(
    client: AsyncClient,
    user_id: uuid.UUID,
    sample_user: User,
):
    """GET /api/linkedin/status returns connected=False when no token."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    session = _make_mock_session()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.get("/api/linkedin/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False


# --- POST /api/linkedin/publish ---


async def test_publish_success(
    client: AsyncClient,
    user_id: uuid.UUID,
    sample_user: User,
    sample_token: Token,
    sample_draft: Draft,
):
    """POST /api/linkedin/publish succeeds with mocked LinkedIn API."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    session = _make_mock_session()

    # First execute returns token, second returns draft
    result_token = MagicMock()
    result_token.scalar_one_or_none.return_value = sample_token

    result_draft = MagicMock()
    result_draft.scalar_one_or_none.return_value = sample_draft

    session.execute = AsyncMock(side_effect=[result_token, result_draft])

    with (
        patch("app.routes.linkedin.decrypt_token", return_value="test_access_token"),
        patch(
            "app.routes.linkedin.get_linkedin_profile",
            new_callable=AsyncMock,
            return_value="urn:li:person:abc123",
        ),
        patch(
            "app.routes.linkedin.upload_image",
            new_callable=AsyncMock,
            return_value="urn:li:image:img1",
        ),
        patch(
            "app.routes.linkedin.create_post",
            new_callable=AsyncMock,
            return_value={"post_urn": "urn:li:share:12345", "status_code": 201},
        ),
        patch("app.routes.linkedin.create_comment", new_callable=AsyncMock),
    ):

        async def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[verify_auth] = lambda: fake_auth
        try:
            response = await client.post(
                "/api/linkedin/publish",
                json={"draft_id": str(sample_draft.id)},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "linkedin.com" in data["post_url"]


async def test_publish_no_token(
    client: AsyncClient,
    user_id: uuid.UUID,
    sample_user: User,
):
    """POST /api/linkedin/publish returns 401 when not connected."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    session = _make_mock_session()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.post(
            "/api/linkedin/publish",
            json={"draft_id": str(uuid.uuid4())},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


async def test_publish_draft_not_found(
    client: AsyncClient,
    user_id: uuid.UUID,
    sample_user: User,
    sample_token: Token,
):
    """POST /api/linkedin/publish returns 404 when draft doesn't exist."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    session = _make_mock_session()

    result_token = MagicMock()
    result_token.scalar_one_or_none.return_value = sample_token

    result_draft = MagicMock()
    result_draft.scalar_one_or_none.return_value = None

    session.execute = AsyncMock(side_effect=[result_token, result_draft])

    with patch("app.routes.linkedin.decrypt_token", return_value="test_access_token"):

        async def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[verify_auth] = lambda: fake_auth
        try:
            response = await client.post(
                "/api/linkedin/publish",
                json={"draft_id": str(uuid.uuid4())},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 404


# --- Retry logic ---


async def test_retry_on_server_error():
    """_request_with_retry retries on 500 then succeeds on 200."""
    import httpx

    from app.services.linkedin_client import _request_with_retry

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    response_500 = MagicMock(spec=httpx.Response)
    response_500.status_code = 500
    response_200 = MagicMock(spec=httpx.Response)
    response_200.status_code = 200

    mock_client.request = AsyncMock(side_effect=[response_500, response_200])

    with patch("app.services.linkedin_client.asyncio.sleep", new_callable=AsyncMock):
        result = await _request_with_retry(
            mock_client, "GET", "https://api.linkedin.com/test"
        )

    assert result.status_code == 200
    assert mock_client.request.call_count == 2


# --- DELETE /api/linkedin/disconnect ---


async def test_disconnect(
    client: AsyncClient,
    user_id: uuid.UUID,
    sample_user: User,
    sample_token: Token,
):
    """DELETE /api/linkedin/disconnect removes the token and returns 204."""
    from app.main import app

    fake_auth = make_fake_auth(user_id=user_id)

    session = _make_mock_session()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_token
    session.execute = AsyncMock(return_value=result_mock)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_auth] = lambda: fake_auth
    try:
        response = await client.delete("/api/linkedin/disconnect")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    session.delete.assert_called_once_with(sample_token)
