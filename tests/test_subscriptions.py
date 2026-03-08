"""Tests for subscription verification module."""

import sqlite3
import time

import pytest

from backend.analysis.subscriptions import (
    TIER_FREE,
    TIER_ORACLE,
    TIER_SCOUT,
    TIER_SPYMASTER,
    _cache,
    check_subscription,
    get_tier_for_endpoint,
    record_subscription,
)
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear subscription cache between tests."""
    _cache.clear()
    yield
    _cache.clear()


class TestCheckSubscription:
    def test_no_subscription(self, db):
        result = check_subscription(db, "0xNewPlayer")
        assert result["tier"] == TIER_FREE
        assert result["tier_name"] == "free"
        assert result["active"] is False

    def test_active_subscription(self, db):
        future = int(time.time()) + 86400
        db.execute(
            "INSERT INTO watcher_subscriptions (wallet_address, tier, expires_at) VALUES (?, ?, ?)",
            ("0xPaid", TIER_ORACLE, future),
        )
        db.commit()

        result = check_subscription(db, "0xPaid")
        assert result["tier"] == TIER_ORACLE
        assert result["tier_name"] == "oracle"
        assert result["active"] is True

    def test_expired_subscription(self, db):
        past = int(time.time()) - 86400
        db.execute(
            "INSERT INTO watcher_subscriptions (wallet_address, tier, expires_at) VALUES (?, ?, ?)",
            ("0xExpired", TIER_SCOUT, past),
        )
        db.commit()

        result = check_subscription(db, "0xExpired")
        assert result["tier"] == TIER_SCOUT
        assert result["active"] is False

    def test_cache_hit(self, db):
        future = int(time.time()) + 86400
        db.execute(
            "INSERT INTO watcher_subscriptions (wallet_address, tier, expires_at) VALUES (?, ?, ?)",
            ("0xCached", TIER_SPYMASTER, future),
        )
        db.commit()

        # First call populates cache
        check_subscription(db, "0xCached")
        # Delete from DB — cache should still work
        db.execute("DELETE FROM watcher_subscriptions WHERE wallet_address = '0xCached'")
        db.commit()

        result = check_subscription(db, "0xCached")
        assert result["tier"] == TIER_SPYMASTER
        assert result["active"] is True


class TestRecordSubscription:
    def test_new_subscription(self, db):
        result = record_subscription(db, "0xNew", TIER_SCOUT)
        assert result["tier"] == TIER_SCOUT
        assert result["active"] is True
        assert result["expires_at"] > int(time.time())

    def test_extend_subscription(self, db):
        r1 = record_subscription(db, "0xExtend", TIER_ORACLE)
        r2 = record_subscription(db, "0xExtend", TIER_ORACLE)
        assert r2["expires_at"] > r1["expires_at"]

    def test_upgrade_tier(self, db):
        record_subscription(db, "0xUpgrade", TIER_SCOUT)
        result = record_subscription(db, "0xUpgrade", TIER_SPYMASTER)
        assert result["tier"] == TIER_SPYMASTER

    def test_invalidates_cache(self, db):
        # Populate cache
        check_subscription(db, "0xInvalidate")
        assert "0xInvalidate" not in _cache or _cache["0xInvalidate"][0] == 0

        # Record subscription should clear cache
        record_subscription(db, "0xInvalidate", TIER_ORACLE)
        # Next check should hit DB with new data
        result = check_subscription(db, "0xInvalidate")
        assert result["tier"] == TIER_ORACLE


class TestTierMapping:
    def test_free_endpoints(self):
        assert get_tier_for_endpoint("/health") == TIER_FREE
        assert get_tier_for_endpoint("/feed") == TIER_FREE
        assert get_tier_for_endpoint("/hotzones") == TIER_FREE

    def test_scout_endpoints(self):
        assert get_tier_for_endpoint("/entity/{entity_id}/fingerprint") == TIER_SCOUT
        assert get_tier_for_endpoint("/entity/{entity_id}/reputation") == TIER_SCOUT

    def test_oracle_endpoints(self):
        assert get_tier_for_endpoint("/entity/{entity_id}/narrative") == TIER_ORACLE
        assert get_tier_for_endpoint("/watches") == TIER_ORACLE

    def test_spymaster_endpoints(self):
        assert get_tier_for_endpoint("/kill-graph") == TIER_SPYMASTER
