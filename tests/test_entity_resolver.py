"""Tests for entity resolver."""

import sqlite3

from backend.analysis.entity_resolver import EntityDossier, resolve_entity
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_gate(db):
    """Seed a gate with some events."""
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 0, 0, 0, 1000, 5000)"
    )
    for i in range(20):
        db.execute(
            "INSERT INTO gate_events (gate_id, gate_name,"
            " character_id, corp_id, solar_system_id, timestamp)"
            f" VALUES ('gate-001', 'Alpha Gate',"
            f" 'char-{i % 5}', 'corp-{i % 3}',"
            f" 'sys-001', {1000 + i * 100})"
        )
    db.commit()


def _seed_character(db):
    """Seed a character with events."""
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 3, 1, 10, 1000, 5000)"
    )
    for i in range(10):
        db.execute(
            "INSERT INTO gate_events (gate_id, gate_name,"
            " character_id, corp_id, solar_system_id, timestamp)"
            f" VALUES ('gate-{i % 3}', 'Gate {i % 3}',"
            f" 'char-001', 'corp-001',"
            f" 'sys-001', {1000 + i * 100})"
        )
    db.commit()


def test_resolve_gate():
    db = _get_test_db()
    _seed_gate(db)
    dossier = resolve_entity(db, "gate-001")
    assert dossier is not None
    assert dossier.entity_type == "gate"
    assert dossier.display_name == "Alpha Gate"
    assert dossier.unique_pilots == 5
    assert len(dossier.associated_corps) > 0


def test_resolve_character():
    db = _get_test_db()
    _seed_character(db)
    dossier = resolve_entity(db, "char-001")
    assert dossier is not None
    assert dossier.entity_type == "character"
    assert dossier.gate_count == 3  # 3 unique gates


def test_resolve_nonexistent():
    db = _get_test_db()
    dossier = resolve_entity(db, "nonexistent")
    assert dossier is None


def test_dossier_to_dict():
    db = _get_test_db()
    _seed_gate(db)
    dossier = resolve_entity(db, "gate-001")
    d = dossier.to_dict()
    assert isinstance(d, dict)
    assert d["entity_id"] == "gate-001"
    assert "danger_rating" in d
    assert "titles" in d
    assert "tribe_name" in d
    assert "tribe_short" in d
    assert "character_id" in d


def test_enriches_from_smart_characters():
    """Character name and character_id from smart_characters."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('0xabc', 'character', '',"
        " 10, 5, 3, 2, 1000, 5000)"
    )
    db.execute(
        "INSERT INTO smart_characters (address, name, character_id)"
        " VALUES ('0xabc', 'Captain Cool', '12345')"
    )
    db.commit()
    dossier = resolve_entity(db, "0xabc")
    assert dossier.display_name == "Captain Cool"
    assert dossier.character_id == "12345"


def test_enriches_tribe_from_smart_characters():
    """Tribe name resolved via smart_characters → tribes."""
    db = _get_test_db()
    _seed_character(db)
    # Change entity_id to match what _seed_character uses
    db.execute(
        "INSERT INTO smart_characters (address, name, character_id, tribe_id)"
        " VALUES ('char-001', 'TestPilot', '123', '98000361')"
    )
    db.execute(
        "INSERT INTO tribes (tribe_id, name, name_short) VALUES (98000361, 'The Saints', 'SAINT')"
    )
    db.commit()
    dossier = resolve_entity(db, "char-001")
    assert dossier.tribe_name == "The Saints"
    assert dossier.tribe_short == "SAINT"
    assert dossier.corp_id == "98000361"


def test_tribe_from_corp_id_fallback():
    """Tribe resolved from entity corp_id when no smart_characters."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('0xdef', 'character', 'Pilot', '98000361',"
        " 5, 2, 1, 2, 1000, 2000)"
    )
    db.execute(
        "INSERT INTO tribes (tribe_id, name, name_short) VALUES (98000361, 'The Saints', 'SAINT')"
    )
    db.commit()
    dossier = resolve_entity(db, "0xdef")
    assert dossier.tribe_name == "The Saints"


def test_no_crash_invalid_corp_id():
    """Non-numeric corp_id doesn't crash tribe lookup."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " corp_id, event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('0xghi', 'character', 'Pilot', 'not-a-number',"
        " 5, 2, 1, 2, 1000, 2000)"
    )
    db.commit()
    dossier = resolve_entity(db, "0xghi")
    assert dossier is not None
    assert dossier.tribe_name is None


def test_dossier_dataclass_tribe_fields():
    """Tribe fields present in to_dict output."""
    dossier = EntityDossier(
        entity_id="0xabc",
        entity_type="character",
        display_name="Test",
        first_seen=1000,
        last_seen=2000,
        event_count=10,
        kill_count=5,
        death_count=3,
        gate_count=2,
        corp_id="98000361",
        tribe_name="The Saints",
        tribe_short="SAINT",
        character_id="12345",
    )
    d = dossier.to_dict()
    assert d["tribe_name"] == "The Saints"
    assert d["tribe_short"] == "SAINT"
    assert d["character_id"] == "12345"
