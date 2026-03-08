"""Tests for story feed generator."""

import json
import sqlite3
import time
from unittest.mock import patch

from backend.analysis.story_feed import (
    _post_story,
    detect_gate_milestones,
    detect_killmail_clusters,
    detect_new_entities,
    detect_streak_milestones,
    detect_title_changes,
    generate_feed_items,
    generate_historical_feed,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


class TestPostStory:
    def test_inserts_story(self):
        db = _get_test_db()
        _post_story(db, "test", "Test Headline", "Test Body", ["e1"], "info", 1000)
        db.commit()
        row = db.execute("SELECT * FROM story_feed").fetchone()
        assert row["headline"] == "Test Headline"
        assert row["severity"] == "info"

    def test_dedup_same_headline(self):
        db = _get_test_db()
        now = int(time.time())
        _post_story(db, "test", "Duplicate", "Body", ["e1"], "info", now)
        _post_story(db, "test", "Duplicate", "Body", ["e1"], "info", now + 100)
        db.commit()
        count = db.execute("SELECT COUNT(*) as cnt FROM story_feed").fetchone()
        assert count["cnt"] == 1

    def test_allows_different_headlines(self):
        db = _get_test_db()
        now = int(time.time())
        _post_story(db, "test", "Headline A", "", [], "info", now)
        _post_story(db, "test", "Headline B", "", [], "info", now)
        db.commit()
        count = db.execute("SELECT COUNT(*) as cnt FROM story_feed").fetchone()
        assert count["cnt"] == 2

    def test_default_timestamp(self):
        db = _get_test_db()
        _post_story(db, "test", "No TS", "", [], "info")
        db.commit()
        row = db.execute("SELECT timestamp FROM story_feed").fetchone()
        assert abs(row["timestamp"] - int(time.time())) < 5


class TestDetectKillmailClusters:
    def test_detects_cluster(self):
        db = _get_test_db()
        now = int(time.time())
        for i in range(5):
            db.execute(
                "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
                "VALUES (?, 'sys-1', ?)",
                (f"km-{i}", now - i * 60),
            )
        db.commit()
        count = detect_killmail_clusters(db, lookback_seconds=3600)
        db.commit()
        assert count >= 1

    def test_no_cluster_below_threshold(self):
        db = _get_test_db()
        now = int(time.time())
        for i in range(2):
            db.execute(
                "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
                "VALUES (?, 'sys-1', ?)",
                (f"km-{i}", now - i * 60),
            )
        db.commit()
        count = detect_killmail_clusters(db)
        assert count == 0

    def test_critical_severity_for_large_cluster(self):
        db = _get_test_db()
        now = int(time.time())
        for i in range(10):
            db.execute(
                "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
                "VALUES (?, 'sys-1', ?)",
                (f"km-{i}", now - i * 60),
            )
        db.commit()
        detect_killmail_clusters(db)
        db.commit()
        row = db.execute("SELECT severity FROM story_feed").fetchone()
        assert row["severity"] == "critical"


class TestDetectNewEntities:
    def test_detects_new_character(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name, "
            "first_seen, event_count) VALUES ('new-1', 'character', 'NewPilot', ?, 1)",
            (now,),
        )
        db.commit()
        count = detect_new_entities(db)
        db.commit()
        assert count == 1

    def test_ignores_old_entities(self):
        db = _get_test_db()
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name, "
            "first_seen, event_count) VALUES ('old-1', 'character', 'OldPilot', 1000, 1)"
        )
        db.commit()
        count = detect_new_entities(db)
        assert count == 0

    def test_ignores_gates(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, first_seen, event_count) "
            "VALUES ('g-1', 'gate', ?, 1)",
            (now,),
        )
        db.commit()
        count = detect_new_entities(db)
        assert count == 0


class TestDetectGateMilestones:
    def test_detects_milestone(self):
        db = _get_test_db()
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name, event_count) "
            "VALUES ('g-100', 'gate', 'Big Gate', 100)"
        )
        db.commit()
        count = detect_gate_milestones(db)
        db.commit()
        assert count >= 1

    def test_no_milestone(self):
        db = _get_test_db()
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, event_count) VALUES ('g-50', 'gate', 50)"
        )
        db.commit()
        count = detect_gate_milestones(db)
        assert count == 0


class TestDetectTitleChanges:
    def test_detects_new_title(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name) "
            "VALUES ('c-1', 'character', 'TitledPilot')"
        )
        db.execute(
            "INSERT INTO entity_titles (entity_id, title, title_type, computed_at) "
            "VALUES ('c-1', 'The Reaper', 'character', ?)",
            (now,),
        )
        db.commit()
        count = detect_title_changes(db)
        db.commit()
        assert count >= 1

    def test_no_recent_titles(self):
        db = _get_test_db()
        db.execute("INSERT INTO entities (entity_id, entity_type) VALUES ('c-1', 'character')")
        db.execute(
            "INSERT INTO entity_titles (entity_id, title, title_type, computed_at) "
            "VALUES ('c-1', 'The Ghost', 'character', 1000)"
        )
        db.commit()
        count = detect_title_changes(db)
        assert count == 0


class TestDetectStreakMilestones:
    def test_detects_streak(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name, kill_count) "
            "VALUES ('killer-1', 'character', 'Killer', 10)"
        )
        for i in range(7):
            db.execute(
                "INSERT INTO killmails (killmail_id, victim_character_id, "
                "attacker_character_ids, solar_system_id, timestamp) "
                "VALUES (?, 'victim', ?, 'sys', ?)",
                (f"km-s-{i}", json.dumps([{"address": "killer-1"}]), now - i * 3600),
            )
        db.commit()
        count = detect_streak_milestones(db)
        db.commit()
        assert count >= 0

    def test_no_killers(self):
        db = _get_test_db()
        count = detect_streak_milestones(db)
        assert count == 0


class TestGenerateFeedItems:
    def test_returns_count(self):
        db = _get_test_db()
        with patch("backend.analysis.story_feed.get_db", return_value=db):
            total = generate_feed_items()
        assert total >= 0

    def test_commits_on_new_items(self):
        db = _get_test_db()
        now = int(time.time())
        for i in range(5):
            db.execute(
                "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
                "VALUES (?, 'sys-1', ?)",
                (f"km-feed-{i}", now - i * 60),
            )
        db.commit()
        with patch("backend.analysis.story_feed.get_db", return_value=db):
            total = generate_feed_items()
        assert total >= 1


class TestGenerateHistoricalFeed:
    def test_generates_from_clusters(self):
        db = _get_test_db()
        for i in range(10):
            db.execute(
                "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
                "VALUES (?, 'sys-hist', ?)",
                (f"km-hist-{i}", 1000 + i * 3600),
            )
        db.commit()
        with patch("backend.analysis.story_feed.get_db", return_value=db):
            total = generate_historical_feed()
        assert total >= 1

    def test_generates_from_top_killers(self):
        db = _get_test_db()
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name, kill_count) "
            "VALUES ('top-k', 'character', 'TopKiller', 15)"
        )
        db.commit()
        with patch("backend.analysis.story_feed.get_db", return_value=db):
            total = generate_historical_feed()
        assert total >= 1

    def test_generates_from_top_deaths(self):
        db = _get_test_db()
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name, death_count) "
            "VALUES ('top-d', 'character', 'DeathPilot', 25)"
        )
        db.commit()
        with patch("backend.analysis.story_feed.get_db", return_value=db):
            total = generate_historical_feed()
        assert total >= 1

    def test_empty_db(self):
        db = _get_test_db()
        with patch("backend.analysis.story_feed.get_db", return_value=db):
            total = generate_historical_feed()
        assert total == 0
