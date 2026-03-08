"""Tests for EVE SSO authentication routes."""

import sqlite3
import time
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.db.database import SCHEMA


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture
def client(test_db):
    with (
        patch("backend.db.database.get_db", return_value=test_db),
        patch("backend.api.routes.get_db", return_value=test_db),
        patch("backend.api.auth.get_db", return_value=test_db),
        patch("backend.api.app.get_db", return_value=test_db),
        patch("backend.api.routes.check_tier_access"),
        patch("backend.ingestion.poller.run_poller"),
        patch("backend.bot.discord_bot.run_bot"),
    ):
        from backend.api.app import app
        from backend.api.rate_limit import limiter

        limiter.enabled = False
        yield TestClient(app, raise_server_exceptions=False)
        limiter.enabled = True


def test_eve_sso_login_not_configured(client):
    """Returns 503 when SSO client ID not set."""
    r = client.get("/api/auth/eve/login")
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_eve_sso_login_configured(client):
    """Returns auth URL when configured."""
    with (
        patch("backend.api.auth.settings") as mock_settings,
    ):
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_SECRET_KEY = "test-secret"
        mock_settings.EVE_SSO_CALLBACK_URL = "https://example.com/callback"
        r = client.get("/api/auth/eve/login")
    assert r.status_code == 200
    data = r.json()
    assert "auth_url" in data
    assert "state" in data
    assert "test-client-id" in data["auth_url"]


def test_eve_sso_callback_invalid_state(client):
    """Returns 400 for invalid state."""
    r = client.get("/api/auth/eve/callback?code=test&state=invalid")
    assert r.status_code == 400
    assert "expired" in r.json()["detail"].lower() or "invalid" in r.json()["detail"].lower()


def test_eve_sso_me_no_session(client):
    """Returns 401 without session header."""
    r = client.get("/api/auth/eve/me")
    assert r.status_code == 401


def test_eve_sso_me_expired_session(client, test_db):
    """Returns 401 for expired session."""
    import hashlib

    session_hash = hashlib.sha256(b"expired-token").hexdigest()
    test_db.execute(
        "INSERT INTO eve_sessions (session_hash, character_id, character_name, "
        "access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_hash, "123", "TestChar", "", "", 1000),
    )
    test_db.commit()

    r = client.get("/api/auth/eve/me", headers={"X-EVE-Session": "expired-token"})
    assert r.status_code == 401


def test_eve_sso_me_valid_session(client, test_db):
    """Returns character info for valid session."""
    import hashlib

    session_hash = hashlib.sha256(b"valid-token").hexdigest()
    test_db.execute(
        "INSERT INTO eve_sessions (session_hash, character_id, character_name, "
        "access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_hash, "456", "ValidPilot", "", "", int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.get("/api/auth/eve/me", headers={"X-EVE-Session": "valid-token"})
    assert r.status_code == 200
    data = r.json()
    assert data["character_id"] == "456"
    assert data["character_name"] == "ValidPilot"


def test_eve_sso_me_with_on_chain_match(client, test_db):
    """Returns on-chain data when character name matches."""
    import hashlib

    session_hash = hashlib.sha256(b"onchain-token").hexdigest()
    test_db.execute(
        "INSERT INTO eve_sessions (session_hash, character_id, character_name, "
        "access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_hash, "789", "TestPilot", "", "", int(time.time()) + 3600),
    )
    test_db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, "
        "kill_count, death_count, gate_count) "
        "VALUES ('char-001', 'character', 'TestPilot', 10, 3, 25)"
    )
    test_db.commit()

    r = client.get("/api/auth/eve/me", headers={"X-EVE-Session": "onchain-token"})
    assert r.status_code == 200
    data = r.json()
    assert data["on_chain"] is not None
    assert data["on_chain"]["display_name"] == "TestPilot"


def test_eve_sso_logout(client, test_db):
    """Clears session on logout."""
    import hashlib

    session_hash = hashlib.sha256(b"logout-token").hexdigest()
    test_db.execute(
        "INSERT INTO eve_sessions (session_hash, character_id, character_name, "
        "access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_hash, "999", "LogoutPilot", "", "", int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.post("/api/auth/eve/logout", headers={"X-EVE-Session": "logout-token"})
    assert r.status_code == 200
    assert r.json()["status"] == "logged_out"

    # Verify session is gone
    row = test_db.execute(
        "SELECT * FROM eve_sessions WHERE session_hash = ?", (session_hash,)
    ).fetchone()
    assert row is None


def test_eve_sso_logout_no_session(client):
    """Logout without session returns ok."""
    r = client.post("/api/auth/eve/logout")
    assert r.status_code == 200


def test_eve_sso_login_no_callback_url(client):
    """Returns 503 when callback URL not configured."""
    with patch("backend.api.auth.settings") as mock_settings:
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_CALLBACK_URL = ""
        r = client.get("/api/auth/eve/login")
    assert r.status_code == 503
    assert "callback" in r.json()["detail"].lower()


def test_eve_sso_callback_success(client, test_db):
    """Full happy path: token exchange + verify + session creation."""
    import hashlib
    from unittest.mock import AsyncMock, MagicMock

    from backend.api.auth import _pending_states

    # Inject a valid state
    state = "test-valid-state"
    _pending_states[state] = time.time()

    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "expires_in": 1200,
    }
    mock_token_response.raise_for_status = MagicMock()

    mock_verify_response = MagicMock()
    mock_verify_response.json.return_value = {
        "CharacterID": 98765,
        "CharacterName": "TestPilot",
    }
    mock_verify_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_token_response
    mock_client_instance.get.return_value = mock_verify_response
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.api.auth.settings") as mock_settings,
        patch("backend.api.auth.httpx.AsyncClient", return_value=mock_client_instance),
    ):
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_SECRET_KEY = "test-secret"

        r = client.get(f"/api/auth/eve/callback?code=authcode&state={state}")

    assert r.status_code == 200
    data = r.json()
    assert "session_token" in data
    assert data["character_id"] == "98765"
    assert data["character_name"] == "TestPilot"

    # Verify session stored in DB
    session_hash = hashlib.sha256(data["session_token"].encode()).hexdigest()
    row = test_db.execute(
        "SELECT * FROM eve_sessions WHERE session_hash = ?", (session_hash,)
    ).fetchone()
    assert row is not None
    assert row["character_id"] == "98765"
    assert row["character_name"] == "TestPilot"


def test_eve_sso_callback_token_exchange_error(client):
    """Returns 502 when token exchange returns HTTP error."""
    from unittest.mock import AsyncMock, MagicMock

    from backend.api.auth import _pending_states

    state = "test-http-error-state"
    _pending_states[state] = time.time()

    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client_instance = AsyncMock()
    mock_client_instance.post.side_effect = httpx.HTTPStatusError(
        "401 Unauthorized", request=MagicMock(), response=mock_response
    )
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.api.auth.settings") as mock_settings,
        patch("backend.api.auth.httpx.AsyncClient", return_value=mock_client_instance),
    ):
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_SECRET_KEY = "test-secret"

        r = client.get(f"/api/auth/eve/callback?code=authcode&state={state}")

    assert r.status_code == 502
    assert "failed" in r.json()["detail"].lower()


def test_eve_sso_callback_generic_error(client):
    """Returns 502 when token exchange raises generic exception."""
    from unittest.mock import AsyncMock

    from backend.api.auth import _pending_states

    state = "test-generic-error-state"
    _pending_states[state] = time.time()

    mock_client_instance = AsyncMock()
    mock_client_instance.post.side_effect = ConnectionError("Network down")
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.api.auth.settings") as mock_settings,
        patch("backend.api.auth.httpx.AsyncClient", return_value=mock_client_instance),
    ):
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_SECRET_KEY = "test-secret"

        r = client.get(f"/api/auth/eve/callback?code=authcode&state={state}")

    assert r.status_code == 502


def test_eve_sso_callback_missing_character_id(client):
    """Returns 502 when verify response lacks CharacterID."""
    from unittest.mock import AsyncMock, MagicMock

    from backend.api.auth import _pending_states

    state = "test-no-char-id-state"
    _pending_states[state] = time.time()

    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "expires_in": 1200,
    }
    mock_token_response.raise_for_status = MagicMock()

    mock_verify_response = MagicMock()
    mock_verify_response.json.return_value = {
        "CharacterName": "NoIdPilot",
        # No CharacterID
    }
    mock_verify_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_token_response
    mock_client_instance.get.return_value = mock_verify_response
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("backend.api.auth.settings") as mock_settings,
        patch("backend.api.auth.httpx.AsyncClient", return_value=mock_client_instance),
    ):
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_SECRET_KEY = "test-secret"

        r = client.get(f"/api/auth/eve/callback?code=authcode&state={state}")

    assert r.status_code == 502
    assert "verify" in r.json()["detail"].lower()


def test_eve_sso_callback_sso_not_configured(client):
    """Returns 503 when SSO credentials missing during callback."""
    from backend.api.auth import _pending_states

    state = "test-no-config-state"
    _pending_states[state] = time.time()

    with patch("backend.api.auth.settings") as mock_settings:
        mock_settings.EVE_SSO_CLIENT_ID = ""
        mock_settings.EVE_SSO_SECRET_KEY = ""

        r = client.get(f"/api/auth/eve/callback?code=authcode&state={state}")

    assert r.status_code == 503
    assert "configured" in r.json()["detail"].lower()


def test_eve_sso_me_entity_id_match(client, test_db):
    """Returns on-chain data when entity matches by entity_id."""
    import hashlib

    session_hash = hashlib.sha256(b"entity-id-token").hexdigest()
    test_db.execute(
        "INSERT INTO eve_sessions (session_hash, character_id, character_name, "
        "access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
        (session_hash, "ent-42", "UnmatchedName", "", "", int(time.time()) + 3600),
    )
    # Entity matches by entity_id, not display_name
    test_db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, "
        "kill_count, death_count, gate_count) "
        "VALUES ('ent-42', 'character', 'DifferentName', 5, 2, 10)"
    )
    test_db.commit()

    r = client.get("/api/auth/eve/me", headers={"X-EVE-Session": "entity-id-token"})
    assert r.status_code == 200
    data = r.json()
    assert data["on_chain"] is not None
    assert data["on_chain"]["entity_id"] == "ent-42"
    assert data["on_chain"]["display_name"] == "DifferentName"


def test_eve_sso_login_with_redirect_uri(client):
    """Uses custom redirect_uri when provided."""
    with patch("backend.api.auth.settings") as mock_settings:
        mock_settings.EVE_SSO_CLIENT_ID = "test-client-id"
        mock_settings.EVE_SSO_SECRET_KEY = "test-secret"
        mock_settings.EVE_SSO_CALLBACK_URL = "https://default.com/callback"

        r = client.get("/api/auth/eve/login?redirect_uri=https://custom.com/callback")

    assert r.status_code == 200
    data = r.json()
    assert "https://custom.com/callback" in data["auth_url"]
    assert "https://default.com/callback" not in data["auth_url"]
