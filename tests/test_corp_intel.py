"""Tests for corp intel analysis."""

import json
import sqlite3

import pytest

from backend.analysis.corp_intel import (
    detect_corp_rivalries,
    get_corp_leaderboard,
    get_corp_profile,
)
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Corp A: 3 members, 2 active
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, kill_count, death_count)"
        " VALUES ('a1', 'character', 'Alpha1', 'corp-A', 10, 2)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, kill_count, death_count)"
        " VALUES ('a2', 'character', 'Alpha2', 'corp-A', 5, 3)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, kill_count, death_count)"
        " VALUES ('a3', 'character', 'Alpha3', 'corp-A', 0, 0)"
    )

    # Corp B: 2 members
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, kill_count, death_count)"
        " VALUES ('b1', 'character', 'Beta1', 'corp-B', 8, 1)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, kill_count, death_count)"
        " VALUES ('b2', 'character', 'Beta2', 'corp-B', 0, 5)"
    )

    # Killmails for rivalry: corp-A kills corp-B members
    for i in range(3):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, victim_corp_id,"
            " attacker_character_ids, attacker_corp_ids, solar_system_id, timestamp)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"km-ab-{i}",
                "b1",
                "corp-B",
                json.dumps([{"address": "a1", "corporationId": "corp-A"}]),
                json.dumps(["corp-A"]),
                "sys-1",
                1000 + i,
            ),
        )

    # corp-B kills corp-A members (rivalry)
    for i in range(2):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, victim_corp_id,"
            " attacker_character_ids, attacker_corp_ids, solar_system_id, timestamp)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"km-ba-{i}",
                "a2",
                "corp-A",
                json.dumps([{"address": "b1", "corporationId": "corp-B"}]),
                json.dumps(["corp-B"]),
                "sys-2",
                2000 + i,
            ),
        )

    conn.commit()
    return conn


def test_corp_profile(db):
    profile = get_corp_profile(db, "corp-A")
    assert profile is not None
    assert profile.member_count == 3
    assert profile.active_members == 2
    assert profile.total_kills == 15  # 10 + 5
    assert profile.total_deaths == 5  # 2 + 3
    assert profile.threat_level == "low"  # 15 < 20


def test_corp_profile_top_killers(db):
    profile = get_corp_profile(db, "corp-A")
    assert len(profile.top_killers) == 2
    assert profile.top_killers[0]["display_name"] == "Alpha1"
    assert profile.top_killers[0]["kills"] == 10


def test_corp_profile_systems(db):
    profile = get_corp_profile(db, "corp-A")
    d = profile.to_dict()
    assert d["system_count"] > 0


def test_corp_profile_not_found(db):
    profile = get_corp_profile(db, "nonexistent")
    assert profile is None


def test_corp_profile_kill_ratio(db):
    profile = get_corp_profile(db, "corp-A")
    assert profile.kill_ratio == 0.75  # 15 / 20


def test_corp_leaderboard(db):
    lb = get_corp_leaderboard(db)
    assert len(lb) == 2
    # corp-A has more kills (15 vs 8)
    assert lb[0]["corp_id"] == "corp-A"
    assert lb[0]["total_kills"] == 15


def test_corp_leaderboard_limit(db):
    lb = get_corp_leaderboard(db, limit=1)
    assert len(lb) == 1


def test_corp_rivalries(db):
    rivalries = detect_corp_rivalries(db)
    assert len(rivalries) > 0
    r = rivalries[0]
    assert r["total"] == 5  # 3 + 2
    pair = {r["corp_1"], r["corp_2"]}
    assert pair == {"corp-A", "corp-B"}


def test_corp_rivalries_no_data(db):
    """Empty killmails should return no rivalries."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    rivalries = detect_corp_rivalries(conn)
    assert rivalries == []


def test_to_dict(db):
    profile = get_corp_profile(db, "corp-A")
    d = profile.to_dict()
    assert "corp_id" in d
    assert "member_count" in d
    assert "kill_ratio" in d
    assert "threat_level" in d
    assert isinstance(d["kill_ratio"], float)
