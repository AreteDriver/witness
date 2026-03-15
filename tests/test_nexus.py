"""Tests for NEXUS webhook subscription system."""

import json
import sqlite3
from unittest.mock import patch

import pytest

from backend.analysis.nexus import (
    TIER_LIMITS,
    _is_hackathon_active,
    check_delivery_quota,
    check_subscription_quota,
    generate_api_key,
    generate_secret,
    get_quota_usage,
    match_filters,
    sign_payload,
)


@pytest.fixture
def nexus_db(tmp_path):
    """In-memory DB with NEXUS tables."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE nexus_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            endpoint_url TEXT NOT NULL,
            filters TEXT NOT NULL DEFAULT '{}',
            active INTEGER DEFAULT 1,
            secret TEXT NOT NULL,
            wallet_address TEXT NOT NULL DEFAULT '',
            delivery_count INTEGER DEFAULT 0,
            last_delivered_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE nexus_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status_code INTEGER,
            success INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 1,
            error TEXT,
            delivered_at INTEGER DEFAULT (strftime('%s', 'now'))
        );
        CREATE TABLE entities (
            entity_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            display_name TEXT,
            corp_id TEXT,
            first_seen INTEGER,
            last_seen INTEGER,
            event_count INTEGER DEFAULT 0,
            kill_count INTEGER DEFAULT 0,
            death_count INTEGER DEFAULT 0,
            gate_count INTEGER DEFAULT 0,
            updated_at INTEGER
        );
        CREATE TABLE solar_systems (
            solar_system_id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE watcher_subscriptions (
            wallet_address TEXT PRIMARY KEY,
            tier INTEGER NOT NULL DEFAULT 0,
            expires_at INTEGER NOT NULL DEFAULT 0
        );
    """)
    return db


# -- Key generation --


def test_generate_api_key():
    key = generate_api_key()
    assert key.startswith("nxs_")
    assert len(key) > 10


def test_generate_secret():
    secret = generate_secret()
    assert len(secret) == 64  # 32 bytes hex


def test_api_keys_unique():
    keys = {generate_api_key() for _ in range(100)}
    assert len(keys) == 100


# -- HMAC signing --


def test_sign_payload():
    secret = "test_secret"
    payload = '{"event": "killmail"}'
    sig = sign_payload(secret, payload)
    assert len(sig) == 64  # SHA-256 hex digest
    # Same input = same output
    assert sign_payload(secret, payload) == sig


def test_sign_different_secrets():
    payload = '{"event": "test"}'
    sig1 = sign_payload("secret1", payload)
    sig2 = sign_payload("secret2", payload)
    assert sig1 != sig2


# -- Filter matching --


def test_match_empty_filters():
    assert match_filters({}, {"event_type": "killmail"})


def test_match_event_type():
    filters = {"event_types": ["killmail"]}
    assert match_filters(filters, {"event_type": "killmail"})
    assert not match_filters(filters, {"event_type": "gate_transit"})


def test_match_entity_ids():
    filters = {"entity_ids": ["0xabc123"]}
    assert match_filters(filters, {"victim_character_id": "0xabc123"})
    assert match_filters(filters, {"character_id": "0xabc123"})
    assert not match_filters(filters, {"character_id": "0xother"})


def test_match_entity_in_attackers():
    filters = {"entity_ids": ["0xkiller"]}
    event = {
        "event_type": "killmail",
        "attacker_character_ids": json.dumps([{"address": "0xkiller"}]),
    }
    assert match_filters(filters, event)


def test_match_system_ids():
    filters = {"system_ids": ["30000142"]}
    assert match_filters(filters, {"solar_system_id": "30000142"})
    assert not match_filters(filters, {"solar_system_id": "30000999"})


def test_match_min_severity():
    filters = {"min_severity": "warning"}
    assert match_filters(filters, {"severity": "critical"})
    assert match_filters(filters, {"severity": "warning"})
    assert not match_filters(filters, {"severity": "info"})


def test_match_combined_filters():
    filters = {
        "event_types": ["killmail"],
        "system_ids": ["30000142"],
        "min_severity": "warning",
    }
    event = {
        "event_type": "killmail",
        "solar_system_id": "30000142",
        "severity": "critical",
    }
    assert match_filters(filters, event)

    # Wrong event type
    event_wrong = dict(event)
    event_wrong["event_type"] = "gate_transit"
    assert not match_filters(filters, event_wrong)


def test_match_no_filters_matches_all():
    assert match_filters(None, {"event_type": "anything"})
    assert match_filters({}, {"event_type": "anything"})


# -- Tier limits --


def test_tier_limits_free_blocked():
    assert TIER_LIMITS[0]["max_subscriptions"] == 0
    assert TIER_LIMITS[0]["max_deliveries_day"] == 0


def test_tier_limits_scout_blocked():
    assert TIER_LIMITS[1]["max_subscriptions"] == 0


def test_tier_limits_oracle_has_quota():
    assert TIER_LIMITS[2]["max_subscriptions"] == 2
    assert TIER_LIMITS[2]["max_deliveries_day"] == 100


def test_tier_limits_spymaster_highest():
    assert TIER_LIMITS[3]["max_subscriptions"] == 10
    assert TIER_LIMITS[3]["max_deliveries_day"] == 1000
    assert TIER_LIMITS[3]["max_subscriptions"] > TIER_LIMITS[2]["max_subscriptions"]


# -- Hackathon mode --


@patch("backend.analysis.nexus.settings")
def test_hackathon_mode_active(mock_settings):
    mock_settings.HACKATHON_MODE = True
    mock_settings.HACKATHON_ENDS = "2099-12-31"
    assert _is_hackathon_active() is True


@patch("backend.analysis.nexus.settings")
def test_hackathon_mode_expired(mock_settings):
    mock_settings.HACKATHON_MODE = True
    mock_settings.HACKATHON_ENDS = "2020-01-01"
    assert _is_hackathon_active() is False


@patch("backend.analysis.nexus.settings")
def test_hackathon_mode_disabled(mock_settings):
    mock_settings.HACKATHON_MODE = False
    mock_settings.HACKATHON_ENDS = "2099-12-31"
    assert _is_hackathon_active() is False


@patch("backend.analysis.nexus.settings")
def test_hackathon_grants_spymaster_quota(mock_settings, nexus_db):
    """Free-tier wallet gets Spymaster limits during hackathon."""
    mock_settings.HACKATHON_MODE = True
    mock_settings.HACKATHON_ENDS = "2099-12-31"

    # Wallet has no subscription row at all (tier 0 normally)
    result = check_subscription_quota(nexus_db, "0xhacker", tier=0)
    assert result["allowed"] is True
    assert result["max"] == 10  # Spymaster limit
    assert result["tier"] == 3  # Elevated to Spymaster


@patch("backend.analysis.nexus.settings")
def test_no_hackathon_free_tier_blocked(mock_settings, nexus_db):
    """Free-tier wallet is blocked when hackathon is off."""
    mock_settings.HACKATHON_MODE = False
    mock_settings.HACKATHON_ENDS = "2099-12-31"

    result = check_subscription_quota(nexus_db, "0xhacker", tier=0)
    assert result["allowed"] is False
    assert result["max"] == 0


@patch("backend.analysis.nexus.settings")
def test_hackathon_quota_usage_shows_spymaster(mock_settings, nexus_db):
    """Quota usage endpoint returns Spymaster limits during hackathon."""
    mock_settings.HACKATHON_MODE = True
    mock_settings.HACKATHON_ENDS = "2099-12-31"

    usage = get_quota_usage(nexus_db, "0xhacker")
    assert usage["tier"] == 3
    assert usage["subscriptions_max"] == 10
    assert usage["deliveries_max"] == 1000


@patch("backend.analysis.nexus.settings")
def test_hackathon_expired_reverts_to_real_tier(mock_settings, nexus_db):
    """After hackathon ends, wallet reverts to actual tier."""
    mock_settings.HACKATHON_MODE = True
    mock_settings.HACKATHON_ENDS = "2020-01-01"  # Expired

    usage = get_quota_usage(nexus_db, "0xhacker")
    assert usage["tier"] == 0
    assert usage["subscriptions_max"] == 0


# -- Admin bypass --


@patch("backend.api.tier_gate.is_admin_wallet", return_value=True)
@patch("backend.analysis.nexus.settings")
def test_admin_wallet_bypasses_delivery_quota(mock_settings, mock_admin, nexus_db):
    """Admin wallet bypasses delivery quota even without hackathon mode."""
    mock_settings.HACKATHON_MODE = False
    mock_settings.HACKATHON_ENDS = "2020-01-01"

    # Create sub owned by admin wallet
    nexus_db.execute(
        "INSERT INTO nexus_subscriptions (api_key, name, endpoint_url, secret, wallet_address) "
        "VALUES (?, ?, ?, ?, ?)",
        ("nxs_test", "admin-sub", "https://example.com/hook", "secret123", "admin"),
    )
    nexus_db.commit()
    row = nexus_db.execute(
        "SELECT id FROM nexus_subscriptions WHERE api_key = 'nxs_test'"
    ).fetchone()
    sub_id = row["id"]

    # No watcher_subscriptions row, no hackathon — would normally be blocked
    assert check_delivery_quota(nexus_db, sub_id) is True


@patch("backend.analysis.nexus.settings")
def test_non_admin_blocked_without_tier(mock_settings, nexus_db):
    """Non-admin wallet with no tier is blocked when hackathon is off."""
    mock_settings.HACKATHON_MODE = False
    mock_settings.HACKATHON_ENDS = "2020-01-01"
    mock_settings.ADMIN_ADDRESSES = ""
    mock_settings.admin_address_set = set()

    nexus_db.execute(
        "INSERT INTO nexus_subscriptions (api_key, name, endpoint_url, secret, wallet_address) "
        "VALUES (?, ?, ?, ?, ?)",
        ("nxs_blocked", "blocked-sub", "https://example.com/hook", "secret456", "0xrandom"),
    )
    nexus_db.commit()
    row = nexus_db.execute(
        "SELECT id FROM nexus_subscriptions WHERE api_key = 'nxs_blocked'"
    ).fetchone()
    sub_id = row["id"]

    assert check_delivery_quota(nexus_db, sub_id) is False
