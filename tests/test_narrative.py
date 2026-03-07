"""Tests for narrative generation — template fallback, AI paths, and caching."""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from backend.analysis.narrative import (
    _event_hash,
    _template_narrative,
    generate_battle_report,
    generate_dossier_narrative,
)
from backend.db.database import SCHEMA


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-hunter', 'character', 'TestHunter',"
        " 100, 25, 3, 50, 1000, 90000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-ghost', 'character', 'GhostPilot',"
        " 40, 0, 0, 30, 1000, 90000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('gate-alpha', 'gate', 'Alpha Gate',"
        " 500, 15, 0, 0, 1000, 90000)"
    )
    conn.execute(
        "INSERT INTO entity_titles (entity_id, title, title_type) "
        "VALUES ('char-hunter', 'The Reaper', 'earned')"
    )
    conn.commit()
    return conn


def test_template_hunter_character():
    profile = {
        "entity_type": "character",
        "display_name": "TestHunter",
        "event_count": 100,
        "kill_count": 25,
        "death_count": 3,
        "gate_count": 50,
        "titles": ["The Reaper"],
        "danger_rating": "high",
    }
    text = _template_narrative(profile)
    assert "TestHunter" in text
    assert "The Reaper" in text
    assert "combat threat" in text
    assert "25" in text  # kills mentioned


def test_template_ghost_character():
    profile = {
        "entity_type": "character",
        "display_name": "GhostPilot",
        "event_count": 40,
        "kill_count": 0,
        "death_count": 0,
        "gate_count": 30,
        "titles": [],
        "danger_rating": "none",
    }
    text = _template_narrative(profile)
    assert "GhostPilot" in text
    assert "ghost" in text


def test_template_gate():
    profile = {
        "entity_type": "gate",
        "display_name": "Alpha Gate",
        "event_count": 500,
        "kill_count": 15,
        "titles": ["The Bloodgate"],
    }
    text = _template_narrative(profile)
    assert "Alpha Gate" in text
    assert "500 transits" in text
    assert "caution" in text


def test_template_gate_peaceful():
    profile = {
        "entity_type": "gate",
        "display_name": "Safe Gate",
        "event_count": 100,
        "kill_count": 0,
        "titles": [],
    }
    text = _template_narrative(profile)
    assert "Safe Gate" in text
    assert "peacefully" in text


def test_generate_uses_template_without_api_key(test_db):
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
    ):
        mock_settings.ANTHROPIC_API_KEY = ""
        text = generate_dossier_narrative("char-hunter")
        assert "TestHunter" in text
        assert len(text) > 50


def test_generate_caches_template_result(test_db):
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
    ):
        mock_settings.ANTHROPIC_API_KEY = ""
        text1 = generate_dossier_narrative("char-hunter")
        # Second call should return cached
        text2 = generate_dossier_narrative("char-hunter")
        assert text1 == text2
        # Verify it's in the cache table
        row = test_db.execute(
            "SELECT COUNT(*) as cnt FROM narrative_cache WHERE entity_id = 'char-hunter'"
        ).fetchone()
        assert row["cnt"] == 1


def test_generate_entity_not_found(test_db):
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
    ):
        mock_settings.ANTHROPIC_API_KEY = ""
        text = generate_dossier_narrative("nonexistent")
        assert text == "Entity not found."


def test_template_victim_character():
    profile = {
        "entity_type": "character",
        "display_name": "Victim",
        "event_count": 30,
        "kill_count": 1,
        "death_count": 8,
        "gate_count": 15,
        "titles": [],
        "danger_rating": "low",
    }
    text = _template_narrative(profile)
    assert "Victim" in text
    assert "losses" in text


def test_template_balanced_character():
    """Character with roughly equal kills/deaths gets balanced description."""
    profile = {
        "entity_type": "character",
        "display_name": "BalancedPilot",
        "event_count": 20,
        "kill_count": 3,
        "death_count": 3,
        "gate_count": 10,
        "titles": [],
        "danger_rating": "medium",
    }
    text = _template_narrative(profile)
    assert "BalancedPilot" in text
    assert "balanced" in text


def test_template_unknown_entity_type():
    """Unknown entity type gets minimal description."""
    profile = {
        "entity_type": "corp",
        "display_name": "TestCorp",
        "event_count": 42,
    }
    text = _template_narrative(profile)
    assert "TestCorp" in text
    assert "42" in text


def test_template_missing_display_name():
    """Falls back to truncated entity_id when no display_name."""
    profile = {
        "entity_type": "character",
        "entity_id": "0x1234567890abcdef1234567890abcdef12345678",
        "event_count": 5,
        "kill_count": 0,
        "death_count": 0,
        "gate_count": 2,
        "titles": [],
    }
    text = _template_narrative(profile)
    assert "0x12345678" in text  # Truncated to 16 chars


def test_event_hash_deterministic():
    data = {"key": "value", "num": 42}
    h1 = _event_hash(data)
    h2 = _event_hash(data)
    assert h1 == h2
    assert len(h1) == 16


def test_event_hash_different_for_different_data():
    h1 = _event_hash({"a": 1})
    h2 = _event_hash({"a": 2})
    assert h1 != h2


def test_generate_dossier_ai_success(test_db):
    """Test AI narrative generation path."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="AI-generated dossier about TestHunter.")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
        patch("backend.analysis.narrative._get_client", return_value=mock_client),
    ):
        mock_settings.ANTHROPIC_API_KEY = "sk-test-key"
        text = generate_dossier_narrative("char-hunter")

    assert "AI-generated dossier" in text
    mock_client.messages.create.assert_called_once()

    # Verify it was cached
    row = test_db.execute(
        "SELECT content FROM narrative_cache WHERE entity_id = 'char-hunter'"
    ).fetchone()
    assert row is not None
    assert "AI-generated" in row["content"]


def test_generate_dossier_ai_error_falls_back_to_template(test_db):
    """AI failure falls back to template narrative."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("API unreachable")

    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
        patch("backend.analysis.narrative._get_client", return_value=mock_client),
    ):
        mock_settings.ANTHROPIC_API_KEY = "sk-test-key"
        text = generate_dossier_narrative("char-hunter")

    assert "TestHunter" in text  # Template fallback used
    assert len(text) > 20


def test_generate_dossier_value_error(test_db):
    """ValueError (no API key) returns error message."""
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
        patch(
            "backend.analysis.narrative._get_client",
            side_effect=ValueError("ANTHROPIC_API_KEY not set"),
        ),
    ):
        mock_settings.ANTHROPIC_API_KEY = "sk-test-key"
        text = generate_dossier_narrative("char-hunter")

    assert "unavailable" in text.lower()


def test_generate_battle_report_empty_events():
    result = generate_battle_report([])
    assert "error" in result


def test_generate_battle_report_ai_success():
    """Test AI battle report generation."""
    report_json = {
        "title": "The Battle of X-7",
        "summary": "A fierce engagement.",
        "narrative": [],
        "key_moments": [],
        "anomalies": [],
        "outcome": "Attackers won",
        "lessons": ["Don't fly alone"],
    }

    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(report_json))]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    events = [
        {"killmail_id": "km1", "solar_system_id": "sys-1", "timestamp": 1000},
        {"killmail_id": "km2", "solar_system_id": "sys-1", "timestamp": 1060},
    ]

    with (
        patch("backend.analysis.narrative.get_db", return_value=db),
        patch("backend.analysis.narrative._get_client", return_value=mock_client),
    ):
        result = generate_battle_report(events)

    assert result["title"] == "The Battle of X-7"
    assert result["outcome"] == "Attackers won"
    mock_client.messages.create.assert_called_once()

    # Verify cache
    row = db.execute("SELECT COUNT(*) as cnt FROM narrative_cache").fetchone()
    assert row["cnt"] == 1


def test_generate_battle_report_cached():
    """Second call returns cached result."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    events = [{"solar_system_id": "sys-1", "timestamp": 1000}]

    # Pre-populate cache
    from backend.analysis.narrative import _event_hash, _store_cache

    eh = _event_hash(events)
    cached_report = json.dumps({"title": "Cached Battle", "cached": True})
    _store_cache(db, "sys-1", "battle", eh, cached_report)

    with patch("backend.analysis.narrative.get_db", return_value=db):
        result = generate_battle_report(events)

    assert result["title"] == "Cached Battle"
    assert result["cached"] is True


def test_generate_battle_report_ai_error():
    """AI error returns error dict."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("API down")

    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    events = [{"solar_system_id": "sys-1", "timestamp": 1000}]

    with (
        patch("backend.analysis.narrative.get_db", return_value=db),
        patch("backend.analysis.narrative._get_client", return_value=mock_client),
    ):
        result = generate_battle_report(events)

    assert "error" in result
    assert "unavailable" in result["error"].lower()


def test_generate_battle_report_bad_json_response():
    """AI returns non-JSON — falls back to regex extraction."""
    mock_msg = MagicMock()
    mock_msg.content = [
        MagicMock(text='Here is the report:\n{"title": "Extracted", "summary": "ok"}')
    ]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    events = [{"solar_system_id": "sys-1", "timestamp": 1000}]

    with (
        patch("backend.analysis.narrative.get_db", return_value=db),
        patch("backend.analysis.narrative._get_client", return_value=mock_client),
    ):
        result = generate_battle_report(events)

    assert result["title"] == "Extracted"


def test_generate_battle_report_no_json_at_all():
    """AI returns completely non-JSON text."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="I cannot generate a report.")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg

    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    events = [{"solar_system_id": "sys-1", "timestamp": 1000}]

    with (
        patch("backend.analysis.narrative.get_db", return_value=db),
        patch("backend.analysis.narrative._get_client", return_value=mock_client),
    ):
        result = generate_battle_report(events)

    assert "error" in result
    assert "raw" in result
