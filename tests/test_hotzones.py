"""Tests for hotzone analysis."""

import json
import sqlite3
import time

import pytest

from backend.analysis.hotzones import (
    _danger_level,
    get_hotzones,
    get_system_activity,
    get_system_dossier,
)
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    now = int(time.time())

    # System A: 15 kills (recent)
    for i in range(15):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-a-{i}",
                f"victim-{i % 5}",
                json.dumps([{"address": f"attacker-{i % 3}"}]),
                "sys-A",
                now - 3600 + i * 60,  # within last hour
            ),
        )

    # System B: 5 kills (older)
    for i in range(5):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-b-{i}",
                f"victim-b-{i}",
                json.dumps([{"address": "attacker-solo"}]),
                "sys-B",
                now - 86400 * 10 + i * 100,  # 10 days ago
            ),
        )

    # Add a smart assembly for system name lookup
    conn.execute(
        "INSERT INTO smart_assemblies (assembly_id, solar_system_id, solar_system_name)"
        " VALUES ('gate-1', 'sys-A', 'Alpha System')"
    )

    conn.commit()
    return conn


def test_get_hotzones_all(db):
    result = get_hotzones(db, window="all")
    assert len(result) == 2
    # sys-A should be first (more kills)
    assert result[0]["solar_system_id"] == "sys-A"
    assert result[0]["kills"] == 15
    assert result[0]["danger_level"] == "moderate"


def test_get_hotzones_24h(db):
    result = get_hotzones(db, window="24h")
    # Only sys-A kills are within 24h
    assert len(result) == 1
    assert result[0]["solar_system_id"] == "sys-A"


def test_get_hotzones_7d(db):
    result = get_hotzones(db, window="7d")
    # sys-A within 7d, sys-B is 10 days ago
    assert len(result) == 1


def test_get_hotzones_30d(db):
    result = get_hotzones(db, window="30d")
    assert len(result) == 2


def test_system_name_resolved(db):
    result = get_hotzones(db, window="all")
    sys_a = next(h for h in result if h["solar_system_id"] == "sys-A")
    assert sys_a["solar_system_name"] == "Alpha System"


def test_unique_attackers(db):
    result = get_hotzones(db, window="all")
    sys_a = next(h for h in result if h["solar_system_id"] == "sys-A")
    assert sys_a["unique_attackers"] == 3  # attacker-0, 1, 2


def test_unique_victims(db):
    result = get_hotzones(db, window="all")
    sys_a = next(h for h in result if h["solar_system_id"] == "sys-A")
    assert sys_a["unique_victims"] == 5  # victim-0 thru 4


def test_system_activity(db):
    result = get_system_activity(db, "sys-A")
    assert result["total_kills"] == 15
    assert result["danger_level"] == "moderate"
    assert len(result["top_victims"]) > 0
    assert "hour_distribution" in result


def test_system_activity_empty(db):
    result = get_system_activity(db, "nonexistent")
    assert result["total_kills"] == 0


def test_danger_level():
    assert _danger_level(50) == "extreme"
    assert _danger_level(20) == "high"
    assert _danger_level(10) == "moderate"
    assert _danger_level(3) == "low"
    assert _danger_level(1) == "minimal"
    assert _danger_level(0) == "minimal"


def test_limit(db):
    result = get_hotzones(db, window="all", limit=1)
    assert len(result) == 1


def test_system_dossier(db):
    """System dossier returns full intelligence profile."""
    result = get_system_dossier(db, "sys-A")
    assert result["solar_system_id"] == "sys-A"
    assert result["solar_system_name"] == "Alpha System"
    assert result["total_kills"] == 15
    assert result["unique_victims"] == 5
    assert result["unique_attackers"] == 3
    assert result["danger_level"] == "moderate"
    assert len(result["top_attackers"]) > 0
    assert len(result["top_victims"]) > 0
    assert "hour_distribution" in result
    assert result["first_kill"] is not None
    assert result["last_kill"] is not None
    # Infrastructure
    assert len(result["infrastructure"]) == 1
    assert result["infrastructure"][0]["type"] is None  # no type set in fixture


def test_system_dossier_empty(db):
    """System dossier for unknown system returns minimal data."""
    result = get_system_dossier(db, "nonexistent")
    assert result["total_kills"] == 0
    assert result["danger_level"] == "minimal"


def test_system_dossier_attackers_resolved(db):
    """Top attacker names are resolved."""
    # Add entity records for name resolution
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count) VALUES ('attacker-0', 'character', 'Alpha', 5)"
    )
    db.commit()
    result = get_system_dossier(db, "sys-A")
    attacker_names = [a["display_name"] for a in result["top_attackers"]]
    assert "Alpha" in attacker_names
