"""Tests for Sui wallet authentication with signature verification."""

import base64
import hashlib
import sqlite3
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from backend.api.auth import (
    PERSONAL_MESSAGE_INTENT,
    SCHEME_ED25519,
    _derive_sui_address,
    _encode_uleb128,
    _pending_challenges,
    _verify_sui_signature,
)
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
        _pending_challenges.clear()
        yield TestClient(app, raise_server_exceptions=False)
        limiter.enabled = True
        _pending_challenges.clear()


# Valid Sui address (0x + 64 hex chars)
VALID_SUI_ADDR = "0x" + "ab" * 32
ADMIN_SUI_ADDR = "0x" + "ff" * 32


def _sign_personal_message(private_key: Ed25519PrivateKey, message: str) -> tuple[str, str]:
    """Sign a message using Sui's signPersonalMessage convention.

    Returns (signature_b64, derived_address).
    """
    msg_bytes = message.encode("utf-8")
    bcs_msg = _encode_uleb128(len(msg_bytes)) + msg_bytes
    intent_msg = PERSONAL_MESSAGE_INTENT + bcs_msg
    msg_hash = hashlib.blake2b(intent_msg, digest_size=32).digest()

    raw_sig = private_key.sign(msg_hash)
    public_key = private_key.public_key().public_bytes_raw()

    # Sui signature format: scheme_byte || raw_sig || public_key
    sig_bytes = bytes([SCHEME_ED25519]) + raw_sig + public_key
    sig_b64 = base64.b64encode(sig_bytes).decode()

    address = _derive_sui_address(SCHEME_ED25519, public_key)
    return sig_b64, address


@pytest.fixture
def ed25519_keypair():
    """Generate a fresh Ed25519 keypair for testing."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes_raw()
    address = _derive_sui_address(SCHEME_ED25519, public_key)
    return private_key, address


# ---------- Unit tests: crypto helpers ----------


class TestULEB128:
    def test_zero(self):
        assert _encode_uleb128(0) == b"\x00"

    def test_small(self):
        assert _encode_uleb128(42) == bytes([42])

    def test_multibyte(self):
        # 300 = 0b100101100 → [0xAC, 0x02]
        assert _encode_uleb128(300) == bytes([0xAC, 0x02])


class TestDeriveAddress:
    def test_deterministic(self):
        pubkey = bytes(range(32))
        addr1 = _derive_sui_address(SCHEME_ED25519, pubkey)
        addr2 = _derive_sui_address(SCHEME_ED25519, pubkey)
        assert addr1 == addr2
        assert addr1.startswith("0x")
        assert len(addr1) == 66  # 0x + 64 hex

    def test_different_keys_different_addresses(self):
        addr1 = _derive_sui_address(SCHEME_ED25519, bytes(32))
        addr2 = _derive_sui_address(SCHEME_ED25519, bytes([1]) + bytes(31))
        assert addr1 != addr2


class TestVerifySuiSignature:
    def test_valid_signature(self, ed25519_keypair):
        private_key, expected_addr = ed25519_keypair
        message = "WatchTower authentication: test-nonce-123"
        sig_b64, derived_addr = _sign_personal_message(private_key, message)
        assert derived_addr == expected_addr

        result = _verify_sui_signature(message.encode("utf-8"), sig_b64)
        assert result == expected_addr

    def test_wrong_message_fails(self, ed25519_keypair):
        private_key, _ = ed25519_keypair
        sig_b64, _ = _sign_personal_message(private_key, "original message")

        with pytest.raises(ValueError, match="verification failed"):
            _verify_sui_signature(b"different message", sig_b64)

    def test_invalid_base64(self):
        with pytest.raises(ValueError, match="Invalid base64"):
            _verify_sui_signature(b"test", "not-valid-base64!!!")

    def test_truncated_signature(self):
        with pytest.raises(ValueError, match="too short"):
            _verify_sui_signature(b"test", base64.b64encode(b"\x00").decode())

    def test_wrong_length_ed25519(self):
        with pytest.raises(ValueError, match="wrong length"):
            sig = bytes([SCHEME_ED25519]) + bytes(50)
            _verify_sui_signature(b"test", base64.b64encode(sig).decode())

    def test_unsupported_scheme(self):
        with pytest.raises(ValueError, match="Unsupported"):
            sig = bytes([0x99]) + bytes(96)
            _verify_sui_signature(b"test", base64.b64encode(sig).decode())


# ---------- Integration tests: challenge-response flow ----------


class TestChallengeEndpoint:
    def test_returns_nonce_and_message(self, client):
        r = client.post("/api/auth/wallet/challenge")
        assert r.status_code == 200
        data = r.json()
        assert "nonce" in data
        assert "message" in data
        assert data["message"].startswith("WatchTower authentication: ")
        assert data["nonce"] in data["message"]

    def test_nonce_stored_in_pending(self, client):
        r = client.post("/api/auth/wallet/challenge")
        nonce = r.json()["nonce"]
        assert nonce in _pending_challenges


class TestWalletConnectWithSignature:
    def test_full_challenge_response_flow(self, client, test_db, ed25519_keypair):
        private_key, wallet_addr = ed25519_keypair

        # Step 1: Get challenge
        r = client.post("/api/auth/wallet/challenge")
        assert r.status_code == 200
        challenge = r.json()

        # Step 2: Sign the challenge message
        sig_b64, _ = _sign_personal_message(private_key, challenge["message"])

        # Step 3: Connect with signature
        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": wallet_addr,
                "signature": sig_b64,
                "message": challenge["message"],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "session_token" in data
        assert data["wallet_address"] == wallet_addr.lower()
        assert data["tier"] == 0
        assert data["tier_name"] == "free"

        # Nonce consumed
        assert challenge["nonce"] not in _pending_challenges

    def test_missing_signature_rejected(self, client):
        r = client.post(
            "/api/auth/wallet/connect",
            json={"wallet_address": VALID_SUI_ADDR},
        )
        assert r.status_code == 422  # Pydantic validation error

    def test_invalid_address_format(self, client):
        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": "0x1234",
                "signature": "fake",
                "message": "fake",
            },
        )
        assert r.status_code == 422

    def test_bad_challenge_format(self, client):
        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": VALID_SUI_ADDR,
                "signature": "fake",
                "message": "not a valid challenge",
            },
        )
        assert r.status_code == 400
        assert "Invalid challenge" in r.json()["detail"]

    def test_unknown_nonce_rejected(self, client):
        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": VALID_SUI_ADDR,
                "signature": "fake",
                "message": "WatchTower authentication: unknown-nonce",
            },
        )
        assert r.status_code == 400
        assert "expired or not found" in r.json()["detail"]

    def test_expired_nonce_rejected(self, client, ed25519_keypair):
        private_key, wallet_addr = ed25519_keypair

        # Get challenge
        r = client.post("/api/auth/wallet/challenge")
        challenge = r.json()

        # Expire it
        _pending_challenges[challenge["nonce"]] = time.time() - 600

        sig_b64, _ = _sign_personal_message(private_key, challenge["message"])

        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": wallet_addr,
                "signature": sig_b64,
                "message": challenge["message"],
            },
        )
        assert r.status_code == 400
        assert "expired" in r.json()["detail"]

    def test_wrong_wallet_address_rejected(self, client, ed25519_keypair):
        private_key, _ = ed25519_keypair
        wrong_addr = "0x" + "cc" * 32

        r = client.post("/api/auth/wallet/challenge")
        challenge = r.json()

        sig_b64, _ = _sign_personal_message(private_key, challenge["message"])

        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": wrong_addr,
                "signature": sig_b64,
                "message": challenge["message"],
            },
        )
        assert r.status_code == 401
        assert "does not match" in r.json()["detail"]

    def test_nonce_single_use(self, client, ed25519_keypair):
        private_key, wallet_addr = ed25519_keypair

        r = client.post("/api/auth/wallet/challenge")
        challenge = r.json()
        sig_b64, _ = _sign_personal_message(private_key, challenge["message"])

        # First connect succeeds
        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": wallet_addr,
                "signature": sig_b64,
                "message": challenge["message"],
            },
        )
        assert r.status_code == 200

        # Replay fails
        r = client.post(
            "/api/auth/wallet/connect",
            json={
                "wallet_address": wallet_addr,
                "signature": sig_b64,
                "message": challenge["message"],
            },
        )
        assert r.status_code == 400

    def test_admin_wallet_detected(self, client, ed25519_keypair):
        private_key, wallet_addr = ed25519_keypair

        r = client.post("/api/auth/wallet/challenge")
        challenge = r.json()
        sig_b64, _ = _sign_personal_message(private_key, challenge["message"])

        with patch("backend.api.auth.settings") as mock_settings:
            mock_settings.admin_address_set = {wallet_addr.lower()}
            r = client.post(
                "/api/auth/wallet/connect",
                json={
                    "wallet_address": wallet_addr,
                    "signature": sig_b64,
                    "message": challenge["message"],
                },
            )
        assert r.status_code == 200
        assert r.json()["is_admin"] is True


# ---------- Session management (unchanged) ----------


def test_wallet_me_no_session(client):
    """Returns 401 without session header."""
    r = client.get("/api/auth/wallet/me")
    assert r.status_code == 401


def test_wallet_me_valid_session(client, test_db):
    """Returns wallet info for valid session."""
    session_token = "test-valid-session"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["wallet_address"] == VALID_SUI_ADDR.lower()
    assert data["tier"] == 0


def test_wallet_me_expired_session(client, test_db):
    """Returns 401 for expired session."""
    session_token = "test-expired-session"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), 1000),
    )
    test_db.commit()

    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 401


def test_wallet_me_backwards_compat_header(client, test_db):
    """X-EVE-Session header works as fallback."""
    session_token = "test-eve-compat"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-EVE-Session": session_token},
    )
    assert r.status_code == 200
    assert r.json()["wallet_address"] == VALID_SUI_ADDR.lower()


def test_wallet_disconnect(client, test_db):
    """Clears session on disconnect."""
    session_token = "test-disconnect-session"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.post(
        "/api/auth/wallet/disconnect",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "disconnected"

    row = test_db.execute(
        "SELECT * FROM wallet_sessions WHERE session_hash = ?",
        (session_hash,),
    ).fetchone()
    assert row is None


def test_wallet_disconnect_no_session(client):
    """Disconnect without session returns ok."""
    r = client.post("/api/auth/wallet/disconnect")
    assert r.status_code == 200


def test_admin_bypass_tier_gate(client, test_db):
    """Admin wallets bypass tier checks."""
    from backend.api.tier_gate import is_admin_wallet

    with patch("backend.api.tier_gate.settings") as mock_settings:
        mock_settings.admin_address_set = {ADMIN_SUI_ADDR.lower()}
        assert is_admin_wallet(ADMIN_SUI_ADDR) is True
        assert is_admin_wallet(VALID_SUI_ADDR) is False
        assert is_admin_wallet("") is False


def test_full_flow_challenge_connect_me_disconnect(client, test_db, ed25519_keypair):
    """Full flow: challenge -> connect -> me -> disconnect."""
    private_key, wallet_addr = ed25519_keypair

    # Challenge
    r = client.post("/api/auth/wallet/challenge")
    assert r.status_code == 200
    challenge = r.json()

    # Sign and connect
    sig_b64, _ = _sign_personal_message(private_key, challenge["message"])
    r = client.post(
        "/api/auth/wallet/connect",
        json={
            "wallet_address": wallet_addr,
            "signature": sig_b64,
            "message": challenge["message"],
        },
    )
    assert r.status_code == 200
    session_token = r.json()["session_token"]

    # Me
    r = client.get("/api/auth/wallet/me", headers={"X-Session": session_token})
    assert r.status_code == 200
    assert r.json()["wallet_address"] == wallet_addr.lower()

    # Disconnect
    r = client.post("/api/auth/wallet/disconnect", headers={"X-Session": session_token})
    assert r.status_code == 200

    # Me should fail
    r = client.get("/api/auth/wallet/me", headers={"X-Session": session_token})
    assert r.status_code == 401
