"""Tests for FastAPI routes."""

import json
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
    # Seed killmails for kill graph / hotzone / streak tests
    for i in range(5):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-{i}",
                "char-001",
                json.dumps([{"address": f"attacker-{i}"}]),
                f"sys-{i % 2}",
                1000 + i * 3600,
            ),
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
        patch("backend.api.routes.check_tier_access"),
        patch("backend.ingestion.poller.run_poller"),
        patch("backend.bot.discord_bot.run_bot"),
    ):
        from backend.api.app import app
        from backend.api.rate_limit import limiter

        limiter.enabled = False
        yield TestClient(app, raise_server_exceptions=False)
        limiter.enabled = True


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-XSS-Protection"] == "1; mode=block"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


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


def test_create_watch_with_valid_webhook(client):
    r = client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "entity_movement",
            "target_id": "char-001",
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
        },
    )
    assert r.status_code == 200


def test_create_watch_http_webhook_rejected(client):
    r = client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "entity_movement",
            "target_id": "char-001",
            "webhook_url": "http://discord.com/api/webhooks/123/abc",
        },
    )
    assert r.status_code == 400
    assert "HTTPS" in r.json()["detail"]


def test_create_watch_private_ip_rejected(client):
    r = client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "entity_movement",
            "target_id": "char-001",
            "webhook_url": "https://127.0.0.1/callback",
        },
    )
    assert r.status_code == 400
    assert "private" in r.json()["detail"].lower()


def test_create_watch_disallowed_domain_rejected(client):
    r = client.post(
        "/api/watches",
        json={
            "user_id": "u1",
            "watch_type": "entity_movement",
            "target_id": "char-001",
            "webhook_url": "https://evil.com/steal",
        },
    )
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"].lower()


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


def test_kill_graph_global(client):
    r = client.get("/api/kill-graph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data
    assert "vendettas" in data


def test_kill_graph_entity(client):
    r = client.get("/api/kill-graph?entity_id=char-001")
    assert r.status_code == 200


def test_hotzones(client):
    r = client.get("/api/hotzones")
    assert r.status_code == 200
    data = r.json()
    assert "hotzones" in data
    assert data["window"] == "all"


def test_hotzones_window(client):
    r = client.get("/api/hotzones?window=7d")
    assert r.status_code == 200
    assert r.json()["window"] == "7d"


def test_hotzones_invalid_window(client):
    r = client.get("/api/hotzones?window=invalid")
    assert r.status_code == 422


def test_system_detail(client):
    r = client.get("/api/hotzones/sys-0")
    assert r.status_code == 200


def test_entity_streak(client):
    r = client.get("/api/entity/char-001/streak")
    assert r.status_code == 200
    data = r.json()
    assert "current_streak" in data
    assert "status" in data


def test_hot_streaks(client):
    r = client.get("/api/streaks")
    assert r.status_code == 200
    assert "streaks" in r.json()


def test_corps_leaderboard(client):
    r = client.get("/api/corps")
    assert r.status_code == 200
    assert "corps" in r.json()


def test_corp_rivalries(client):
    r = client.get("/api/corps/rivalries")
    assert r.status_code == 200
    assert "rivalries" in r.json()


def test_corp_not_found(client):
    r = client.get("/api/corp/nonexistent")
    assert r.status_code == 404


def test_entity_reputation(client):
    r = client.get("/api/entity/char-001/reputation")
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "char-001"
    assert "trust_score" in data
    assert "rating" in data
    assert "breakdown" in data
    assert "factors" in data
    assert 0 <= data["trust_score"] <= 100


def test_assemblies(client):
    r = client.get("/api/assemblies")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "online" in data
    assert "systems_covered" in data


def test_assemblies_list(client):
    r = client.get("/api/assemblies/list")
    assert r.status_code == 200
    assert "assemblies" in r.json()


def test_subscription_not_found(client):
    r = client.get("/api/subscription/0xNobody")
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == 0
    assert data["active"] is False


def test_subscribe(client):
    r = client.post(
        "/api/subscribe",
        json={"wallet_address": "0x" + "a1b2c3d4" * 8, "tier": 2},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == 2
    assert data["active"] is True


def test_subscribe_invalid_wallet(client):
    r = client.post(
        "/api/subscribe",
        json={"wallet_address": "not-a-wallet", "tier": 1},
    )
    assert r.status_code == 422


def test_subscribe_invalid_tier(client):
    r = client.post(
        "/api/subscribe",
        json={"wallet_address": "0x" + "a1b2c3d4" * 8, "tier": 5},
    )
    assert r.status_code == 400


def test_entity_reputation_not_found(client):
    r = client.get("/api/entity/nonexistent/reputation")
    assert r.status_code == 200  # Returns default neutral score
    data = r.json()
    assert data["trust_score"] == 50
    assert data["rating"] == "neutral"


def test_battle_report_no_events(client):
    r = client.post(
        "/api/battle-report",
        json={"entity_id": "nonexistent", "start": 0, "end": 1},
    )
    assert r.status_code == 200
    assert "error" in r.json()


def test_list_watches_empty(client):
    r = client.get("/api/watches?user_id=nobody")
    assert r.status_code == 200
    assert r.json()["watches"] == []


def test_list_watches_after_create(client):
    client.post(
        "/api/watches",
        json={
            "user_id": "0x1234567890abcdef1234567890abcdef12345678",
            "watch_type": "entity_movement",
            "target_id": "char-001",
        },
    )
    r = client.get("/api/watches?user_id=0x1234567890abcdef1234567890abcdef12345678")
    assert r.status_code == 200
    watches = r.json()["watches"]
    assert len(watches) == 1
    assert watches[0]["target_id"] == "char-001"
    assert watches[0]["watch_type"] == "entity_movement"


def test_list_watches_missing_user_id(client):
    r = client.get("/api/watches")
    assert r.status_code == 422


def test_list_alerts_empty(client):
    r = client.get("/api/alerts?user_id=nobody")
    assert r.status_code == 200
    assert r.json()["alerts"] == []


def test_mark_alert_read(client):
    r = client.post("/api/alerts/999/read")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_admin_analytics_ai_usage(test_db, client):
    """Admin analytics returns AI usage stats."""
    import time

    now = int(time.time())
    test_db.execute(
        "INSERT INTO ai_usage (model, operation, input_tokens, output_tokens,"
        " cached_tokens, entity_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("claude-sonnet-4-5", "dossier", 500, 200, 50, "char-001", now),
    )
    test_db.execute(
        "INSERT INTO ai_usage (model, operation, input_tokens, output_tokens,"
        " cached_tokens, entity_id, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("claude-sonnet-4-5", "battle_report", 1000, 400, 0, "battle", now),
    )
    test_db.commit()

    with patch("backend.api.routes.is_admin_wallet", return_value=True):
        r = client.get("/api/admin/analytics", headers={"X-Wallet-Address": "admin"})
    assert r.status_code == 200
    data = r.json()
    ai = data["ai_usage"]
    assert ai["total_calls"] == 2
    assert ai["total_input_tokens"] == 1500
    assert ai["total_output_tokens"] == 600
    assert ai["total_cached_tokens"] == 50
    assert ai["calls_24h"] == 2
    assert len(ai["by_operation"]) == 2
    assert len(ai["recent"]) == 2
