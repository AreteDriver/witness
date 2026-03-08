"""Tests for reputation scoring module."""

import json
import sqlite3

import pytest

from backend.analysis.reputation import (
    _combat_honor_score,
    _community_score,
    _consistency_score,
    _restraint_score,
    _target_diversity_score,
    _trust_rating,
    compute_reputation,
)
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture
def seeded_db(db):
    """DB with entities and killmails for reputation testing."""
    now = 1700000000
    # Insert entities
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, "
        "kill_count, death_count, gate_count, event_count, "
        "first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("balanced", "character", "Balanced Bob", 10, 8, 20, 38, now - 86400 * 30, now),
    )
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, "
        "kill_count, death_count, gate_count, event_count, "
        "first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("ganker", "character", "Serial Ganker", 50, 1, 5, 56, now - 86400 * 7, now),
    )
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, "
        "kill_count, death_count, gate_count, event_count, corp_id, "
        "first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("peaceful", "character", "Peaceful Pete", 0, 2, 30, 32, "corp1", now - 86400 * 60, now),
    )
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, "
        "kill_count, death_count, gate_count, event_count, "
        "first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("newbie", "character", "Fresh Newbie", 0, 0, 1, 1, now, now),
    )

    # Killmails: balanced fights different people
    for i, victim in enumerate(["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10"]):
        db.execute(
            "INSERT INTO killmails (killmail_id, timestamp, solar_system_id, "
            "victim_character_id, attacker_character_ids) VALUES (?, ?, ?, ?, ?)",
            (f"km-b-{i}", now - i * 3600, "sys1", victim, json.dumps(["balanced"])),
        )

    # Balanced also dies to some of the same people (vendettas)
    for i, attacker in enumerate(["v1", "v2", "v3"]):
        db.execute(
            "INSERT INTO killmails (killmail_id, timestamp, solar_system_id, "
            "victim_character_id, attacker_character_ids) VALUES (?, ?, ?, ?, ?)",
            (f"km-bv-{i}", now - i * 7200, "sys1", "balanced", json.dumps([attacker])),
        )

    # Ganker kills the same person repeatedly
    for i in range(50):
        db.execute(
            "INSERT INTO killmails (killmail_id, timestamp, solar_system_id, "
            "victim_character_id, attacker_character_ids) VALUES (?, ?, ?, ?, ?)",
            (f"km-g-{i}", now - i * 600, "sys2", "target_dummy", json.dumps(["ganker"])),
        )

    db.commit()
    return db


class TestTrustRating:
    def test_trusted(self):
        assert _trust_rating(80) == "trusted"
        assert _trust_rating(100) == "trusted"

    def test_reputable(self):
        assert _trust_rating(60) == "reputable"
        assert _trust_rating(79) == "reputable"

    def test_neutral(self):
        assert _trust_rating(40) == "neutral"
        assert _trust_rating(59) == "neutral"

    def test_suspicious(self):
        assert _trust_rating(20) == "suspicious"
        assert _trust_rating(39) == "suspicious"

    def test_dangerous(self):
        assert _trust_rating(0) == "dangerous"
        assert _trust_rating(19) == "dangerous"


class TestCombatHonor:
    def test_no_combat(self):
        assert _combat_honor_score(0, 0) == 50.0

    def test_balanced_fighter(self):
        score = _combat_honor_score(10, 10)
        assert score > 70  # Balanced = high honor

    def test_pure_ganker(self):
        score = _combat_honor_score(50, 0)
        assert score < 40  # All kills no deaths = low honor

    def test_pure_victim(self):
        score = _combat_honor_score(0, 10)
        assert score < 50  # All deaths = moderate-low


class TestTargetDiversity:
    def test_no_kills(self):
        assert _target_diversity_score([]) == 50.0

    def test_all_different_targets(self):
        score = _target_diversity_score(["a", "b", "c", "d", "e"])
        assert score > 70  # All unique = high diversity

    def test_farming_one_target(self):
        score = _target_diversity_score(["a"] * 20)
        assert score < 20  # Same target = low diversity


class TestComputeReputation:
    def test_entity_not_found(self, db):
        rep = compute_reputation(db, "nonexistent")
        assert rep.trust_score == 50
        assert rep.rating == "neutral"
        assert "Entity not found" in rep.factors[0]

    def test_balanced_fighter_reputation(self, seeded_db):
        rep = compute_reputation(seeded_db, "balanced")
        assert rep.trust_score > 40
        assert rep.kills == 10
        assert rep.deaths == 8
        assert rep.unique_victims == 10
        assert rep.vendettas == 3  # v1, v2, v3 are mutual
        assert rep.rating in ("neutral", "reputable", "trusted")

    def test_ganker_reputation(self, seeded_db):
        rep = compute_reputation(seeded_db, "ganker")
        # Ganker should score lower than balanced fighter
        balanced_rep = compute_reputation(seeded_db, "balanced")
        assert rep.trust_score < balanced_rep.trust_score
        assert rep.unique_victims == 1  # Only kills target_dummy
        assert rep.vendettas == 0

    def test_peaceful_entity(self, seeded_db):
        rep = compute_reputation(seeded_db, "peaceful")
        assert rep.kills == 0
        assert rep.trust_score >= 40  # Peaceful should be neutral or better

    def test_newbie_entity(self, seeded_db):
        rep = compute_reputation(seeded_db, "newbie")
        assert rep.trust_score >= 40  # New entity = neutral
        assert rep.kills == 0
        assert rep.deaths == 0

    def test_to_dict_structure(self, seeded_db):
        rep = compute_reputation(seeded_db, "balanced")
        d = rep.to_dict()
        assert "trust_score" in d
        assert "rating" in d
        assert "breakdown" in d
        assert "stats" in d
        assert "factors" in d
        assert "combat_honor" in d["breakdown"]
        assert "kills" in d["stats"]

    def test_factors_generated(self, seeded_db):
        rep = compute_reputation(seeded_db, "balanced")
        assert len(rep.factors) > 0

    def test_ganker_factors(self, seeded_db):
        rep = compute_reputation(seeded_db, "ganker")
        factor_text = " ".join(rep.factors)
        assert "farming" in factor_text.lower() or "one-directional" in factor_text.lower()


class TestConsistencyScore:
    def test_no_entity(self, db):
        assert _consistency_score(db, "missing") == 50.0

    def test_consistent_entity(self, seeded_db):
        score = _consistency_score(seeded_db, "balanced")
        assert score > 30  # 30 days of activity


class TestCommunityScore:
    def test_no_entity(self, db):
        assert _community_score(db, "missing") == 50.0

    def test_corp_member(self, seeded_db):
        score = _community_score(seeded_db, "peaceful")
        assert score > 60  # Has corp + gates


class TestRestraintScore:
    def test_no_kills(self, db):
        assert _restraint_score(db, 0) == 80.0

    def test_average_kills(self, seeded_db):
        score = _restraint_score(seeded_db, 5)
        assert score >= 50

    def test_excessive_kills(self, seeded_db):
        score = _restraint_score(seeded_db, 500)
        assert score <= 30
