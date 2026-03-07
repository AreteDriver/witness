"""Tests for database initialization and schema."""

import sqlite3

from backend.db import database


def _get_test_db():
    """Create an in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(database.SCHEMA)
    return conn


def test_schema_creates_all_tables():
    db = _get_test_db()
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {t["name"] for t in tables}

    expected = {
        "killmails",
        "gate_events",
        "smart_assemblies",
        "entities",
        "entity_titles",
        "watches",
        "narrative_cache",
        "story_feed",
    }
    assert expected.issubset(table_names)


def test_killmail_unique_constraint():
    db = _get_test_db()
    db.execute("INSERT INTO killmails (killmail_id, timestamp) VALUES ('km1', 1000)")
    db.execute("INSERT OR IGNORE INTO killmails (killmail_id, timestamp) VALUES ('km1', 2000)")
    row = db.execute("SELECT COUNT(*) as cnt FROM killmails").fetchone()
    assert row["cnt"] == 1


def test_entity_upsert():
    db = _get_test_db()
    db.execute(
        """INSERT INTO entities (entity_id, entity_type, event_count)
           VALUES ('e1', 'character', 5)"""
    )
    db.execute(
        """INSERT INTO entities (entity_id, entity_type, event_count)
           VALUES ('e1', 'character', 10)
           ON CONFLICT(entity_id) DO UPDATE SET event_count = excluded.event_count"""
    )
    row = db.execute("SELECT event_count FROM entities WHERE entity_id = 'e1'").fetchone()
    assert row["event_count"] == 10


def test_entity_title_unique_constraint():
    db = _get_test_db()
    db.execute("INSERT INTO entities (entity_id, entity_type) VALUES ('g1', 'gate')")
    db.execute(
        """INSERT INTO entity_titles (entity_id, title, title_type)
           VALUES ('g1', 'The Meatgrinder', 'earned')"""
    )
    db.execute(
        """INSERT OR IGNORE INTO entity_titles (entity_id, title, title_type)
           VALUES ('g1', 'The Meatgrinder', 'earned')"""
    )
    row = db.execute("SELECT COUNT(*) as cnt FROM entity_titles").fetchone()
    assert row["cnt"] == 1


def test_indexes_exist():
    db = _get_test_db()
    indexes = db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()
    index_names = {i["name"] for i in indexes}
    assert "idx_killmails_timestamp" in index_names
    assert "idx_gate_events_timestamp" in index_names
    assert "idx_entities_type" in index_names


def test_get_db_creates_and_caches(tmp_path):
    """get_db creates DB file and returns same connection on second call."""
    from unittest.mock import patch

    db_path = str(tmp_path / "test.db")
    with patch.object(database, "_connection", None):
        with patch.object(database.settings, "DB_PATH", db_path):
            database._connection = None
            conn = database.get_db()
            assert conn is not None
            # Second call returns same connection
            assert database.get_db() is conn
            database.close_db()
            assert database._connection is None


def test_close_db_noop_when_not_connected():
    """close_db does nothing when no connection exists."""
    from unittest.mock import patch

    with patch.object(database, "_connection", None):
        database.close_db()  # Should not raise
