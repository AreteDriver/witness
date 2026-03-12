"""Tests for subscription tier gating."""

import sqlite3
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.analysis.subscriptions import _cache as sub_cache
from backend.api.tier_gate import check_tier_access, is_admin_wallet
from backend.db.database import SCHEMA

_INSERT_SUB = (
    "INSERT INTO watcher_subscriptions"
    " (wallet_address, tier, expires_at, created_at)"
    " VALUES (?, ?, ?, ?)"
)

# Sui-format addresses (0x + 64 hex)
WALLET_A = "0x" + "aa" * 32
WALLET_B = "0x" + "bb" * 32
WALLET_C = "0x" + "cc" * 32
WALLET_D = "0x" + "dd" * 32
WALLET_E = "0x" + "ee" * 32
WALLET_F = "0x" + "ff" * 32
ADMIN_WALLET = "0x" + "01" * 32


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture(autouse=True)
def clear_sub_cache():
    """Clear subscription cache between tests."""
    sub_cache.clear()
    yield
    sub_cache.clear()


def _make_request(wallet: str = "") -> MagicMock:
    req = MagicMock()
    req.headers = {"X-Wallet-Address": wallet} if wallet else {}
    return req


def test_ungated_route_passes(test_db):
    """Non-gated routes should pass without any checks."""
    req = _make_request()
    check_tier_access(req, "health")


def test_gated_route_no_wallet(test_db):
    """Gated route with no wallet header should raise 403."""
    req = _make_request()
    with pytest.raises(Exception) as exc:
        check_tier_access(req, "get_entity_fingerprint")
    assert exc.value.status_code == 403
    assert "Wallet address required" in str(exc.value.detail)


def test_gated_route_no_subscription(test_db):
    """Gated route with wallet but no subscription should raise 403."""
    req = _make_request(WALLET_A)
    with patch("backend.db.database.get_db", return_value=test_db):
        with pytest.raises(Exception) as exc:
            check_tier_access(req, "get_entity_fingerprint")
    assert exc.value.status_code == 403
    assert "Insufficient tier" in str(exc.value.detail)


def test_gated_route_sufficient_tier(test_db):
    """Gated route with sufficient tier should pass."""
    now = int(time.time())
    test_db.execute(_INSERT_SUB, (WALLET_B, 1, now + 86400, now))
    test_db.commit()

    req = _make_request(WALLET_B)
    with patch("backend.db.database.get_db", return_value=test_db):
        check_tier_access(req, "get_entity_fingerprint")


def test_gated_route_insufficient_tier(test_db):
    """Scout trying to access Spymaster endpoint should raise 403."""
    now = int(time.time())
    test_db.execute(_INSERT_SUB, (WALLET_C, 1, now + 86400, now))
    test_db.commit()

    req = _make_request(WALLET_C)
    with patch("backend.db.database.get_db", return_value=test_db):
        with pytest.raises(Exception) as exc:
            check_tier_access(req, "get_kill_graph")
    assert exc.value.status_code == 403
    assert "spymaster" in str(exc.value.detail).lower()


def test_gated_route_expired_subscription(test_db):
    """Expired subscription should raise 403."""
    test_db.execute(_INSERT_SUB, (WALLET_D, 3, 1000, 500))
    test_db.commit()

    req = _make_request(WALLET_D)
    with patch("backend.db.database.get_db", return_value=test_db):
        with pytest.raises(Exception) as exc:
            check_tier_access(req, "get_entity_fingerprint")
    assert exc.value.status_code == 403


def test_oracle_can_access_scout(test_db):
    """Higher tier should access lower tier endpoints."""
    now = int(time.time())
    test_db.execute(_INSERT_SUB, (WALLET_E, 2, now + 86400, now))
    test_db.commit()

    req = _make_request(WALLET_E)
    with patch("backend.db.database.get_db", return_value=test_db):
        check_tier_access(req, "get_entity_fingerprint")


def test_spymaster_can_access_all(test_db):
    """Spymaster should access all gated endpoints."""
    now = int(time.time())
    test_db.execute(_INSERT_SUB, (WALLET_F, 3, now + 86400, now))
    test_db.commit()

    req = _make_request(WALLET_F)
    with patch("backend.db.database.get_db", return_value=test_db):
        for route in [
            "get_entity_fingerprint",
            "get_entity_narrative",
            "get_kill_graph",
        ]:
            check_tier_access(req, route)


def test_admin_bypasses_tier_gate(test_db):
    """Admin wallet skips tier check entirely, even with no subscription."""
    req = _make_request(ADMIN_WALLET)
    with (
        patch("backend.api.tier_gate.settings") as mock_settings,
        patch("backend.db.database.get_db", return_value=test_db),
    ):
        mock_settings.admin_address_set = {ADMIN_WALLET.lower()}
        mock_settings.HACKATHON_MODE = False
        # Should pass Spymaster-gated route without any subscription
        check_tier_access(req, "get_kill_graph")


def test_is_admin_wallet():
    """is_admin_wallet correctly checks admin set."""
    with patch("backend.api.tier_gate.settings") as mock_settings:
        mock_settings.admin_address_set = {ADMIN_WALLET.lower()}
        assert is_admin_wallet(ADMIN_WALLET) is True
        assert is_admin_wallet(WALLET_A) is False
        assert is_admin_wallet("") is False
