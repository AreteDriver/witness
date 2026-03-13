"""Tests for NEXUS webhook subscription system."""

import json
import sqlite3

import pytest

from backend.analysis.nexus import (
    generate_api_key,
    generate_secret,
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
