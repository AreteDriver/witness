"""Tests for FastAPI routes."""

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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
        "VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 0, 0, 0, 1000, 5000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 3, 1, 10, 1000, 5000)"
    )
    conn.execute(
        "INSERT INTO story_feed (event_type, headline, body, entity_ids, severity, timestamp) "
        "VALUES ('engagement', 'Test Battle', 'Details', '[\"gate-001\"]', 'warning', 1000)"
    )
    # Seed gate events for fingerprint tests
    for i in range(30):
        conn.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('gate-{i % 3}', 'char-001', "
            f"'sys-{i % 2}', {1000 + i * 3600})"
        )
    conn.commit()
    return conn


@pytest.fixture
def client(test_db):
    # Patch at the source module so all importers see the mock
    with (
        patch("backend.db.database.get_db", return_value=test_db),
        patch("backend.api.routes.get_db", return_value=test_db),
        patch("backend.api.app.get_db", return_value=test_db),
        patch("backend.ingestion.poller.run_poller"),
        patch("backend.bot.discord_bot.run_bot"),
    ):
        from backend.api.app import app

        yield TestClient(app, raise_server_exceptions=False)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "tables" in data


def test_get_entity(client):
    r = client.get("/api/entity/gate-001")
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "gate-001"
    assert data["display_name"] == "Alpha Gate"


def test_get_entity_not_found(client):
    r = client.get("/api/entity/nonexistent")
    assert r.status_code == 404


def test_list_entities(client):
    r = client.get("/api/entities")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["entities"]) == 2


def test_list_entities_by_type(client):
    r = client.get("/api/entities?entity_type=gate")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1


def test_story_feed(client):
    r = client.get("/api/feed")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["headline"] == "Test Battle"


def test_search(client):
    r = client.get("/api/search?q=Alpha")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["display_name"] == "Alpha Gate"


def test_search_min_length(client):
    r = client.get("/api/search?q=A")
    assert r.status_code == 422


def test_titles_empty(client):
    r = client.get("/api/titles")
    assert r.status_code == 200
    data = r.json()
    assert data["titles"] == []


def test_fingerprint(client):
    r = client.get("/api/entity/char-001/fingerprint")
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "char-001"
    assert "temporal" in data
    assert "route" in data
    assert "social" in data
    assert "threat" in data
    assert "opsec_score" in data
    assert data["route"]["unique_gates"] == 3


def test_fingerprint_not_found(client):
    r = client.get("/api/entity/nonexistent/fingerprint")
    assert r.status_code == 404


def test_fingerprint_compare(client):
    r = client.get("/api/fingerprint/compare?entity_1=char-001&entity_2=gate-001")
    assert r.status_code == 200
    data = r.json()
    assert "temporal_similarity" in data
    assert "route_similarity" in data
    assert "overall_similarity" in data


def test_fingerprint_compare_not_found(client):
    r = client.get("/api/fingerprint/compare?entity_1=char-001&entity_2=nope")
    assert r.status_code == 404


def test_entity_timeline(client):
    r = client.get("/api/entity/char-001/timeline?start=0&end=999999999")
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "char-001"
    assert len(data["events"]) > 0


def test_entity_timeline_gate(client):
    r = client.get("/api/entity/gate-0/timeline?start=0&end=999999999")
    assert r.status_code == 200
    data = r.json()
    assert len(data["events"]) > 0


def test_feed_with_before(client):
    r = client.get("/api/feed?before=9999999")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) >= 1


def test_leaderboard_most_active_gates(client):
    r = client.get("/api/leaderboard/most_active_gates")
    assert r.status_code == 200
    data = r.json()
    assert data["category"] == "most_active_gates"


def test_leaderboard_top_killers(client):
    r = client.get("/api/leaderboard/top_killers")
    assert r.status_code == 200


def test_leaderboard_most_deaths(client):
    r = client.get("/api/leaderboard/most_deaths")
    assert r.status_code == 200


def test_leaderboard_most_traveled(client):
    r = client.get("/api/leaderboard/most_traveled")
    assert r.status_code == 200


def test_leaderboard_deadliest_gates(client):
    r = client.get("/api/leaderboard/deadliest_gates")
    assert r.status_code == 200


def test_leaderboard_invalid_category(client):
    r = client.get("/api/leaderboard/nonsense")
    assert r.status_code == 400


def test_entity_narrative(client):
    r = client.get("/api/entity/gate-001/narrative")
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "gate-001"
    assert len(data["narrative"]) > 0


def test_entity_narrative_not_found(client):
    r = client.get("/api/entity/nonexistent/narrative")
    assert r.status_code == 200
    data = r.json()
    assert data["narrative"] == "Entity not found."


def test_create_watch(client):
    r = client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "entity_movement",
            "target_id": "char-001",
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "created"


def test_create_watch_invalid_type(client):
    r = client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "invalid",
            "target_id": "char-001",
        },
    )
    assert r.status_code == 400


def test_delete_watch(client):
    # Create then delete
    client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "entity_movement",
            "target_id": "char-001",
        },
    )
    r = client.delete("/api/watches/char-001?user_id=u1")
    assert r.status_code == 200
    assert r.json()["status"] == "removed"


def test_list_entities_invalid_sort(client):
    r = client.get("/api/entities?sort=invalid_column")
    assert r.status_code == 200
    # Falls back to event_count sort
    data = r.json()
    assert data["total"] == 2


def test_battle_report_no_events(client):
    r = client.post(
        "/api/battle-report",
        json={"entity_id": "nonexistent", "start": 0, "end": 1},
    )
    assert r.status_code == 200
    assert "error" in r.json()
