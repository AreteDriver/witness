"""Tests for Oracle watch evaluation engine."""

import sqlite3
import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.analysis.oracle import (
    _C5_ALERT_COOLDOWNS,
    BLIND_SPOT_THRESHOLD,
    CLONE_RESERVE_THRESHOLD,
    COOLDOWN_SECONDS,
    EVE_ORANGE,
    EVE_PURPLE,
    EVE_RED,
    EVE_YELLOW,
    check_c5_alerts,
    check_watches,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _insert_watch(db, watch_type, target_id, conditions="{}"):
    db.execute(
        "INSERT INTO watches "
        "(user_id, watch_type, target_id, conditions, "
        "webhook_url, active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (
            "user1",
            watch_type,
            target_id,
            conditions,
            "https://discord.com/api/webhooks/test",
        ),
    )
    db.commit()


@pytest.mark.asyncio
async def test_entity_movement_triggers():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "entity_movement",
        "pilot-1",
        '{"lookback_seconds": 600}',
    )
    db.execute(
        "INSERT INTO gate_events "
        "(gate_id, gate_name, character_id, "
        "solar_system_id, timestamp) "
        f"VALUES ('g1', 'Test Gate', 'pilot-1', 's1', {now - 10})"
    )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    mock_webhook.assert_called_once()
    title = mock_webhook.call_args[0][1]
    assert "MOVEMENT" in title


@pytest.mark.asyncio
async def test_gate_traffic_spike_triggers():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "gate_traffic_spike",
        "g1",
        '{"threshold": 3, "lookback_seconds": 3600}',
    )
    for i in range(5):
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'c{i}', 's1', {now - 10 + i})"
        )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    title = mock_webhook.call_args[0][1]
    assert "TRAFFIC SPIKE" in title


@pytest.mark.asyncio
async def test_killmail_proximity_triggers():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "killmail_proximity",
        "sys-1",
        '{"lookback_seconds": 1800}',
    )
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, solar_system_id, timestamp) "
        f"VALUES ('km1', 'sys-1', {now - 60})"
    )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    title = mock_webhook.call_args[0][1]
    assert "KILLMAIL" in title


@pytest.mark.asyncio
async def test_cooldown_prevents_refire():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "killmail_proximity",
        "sys-1",
        '{"lookback_seconds": 1800}',
    )
    # Mark as recently triggered
    db.execute(
        "UPDATE watches SET last_triggered = ?",
        (now - 60,),
    )
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, solar_system_id, timestamp) "
        f"VALUES ('km1', 'sys-1', {now - 10})"
    )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_no_watches_returns_zero():
    db = _get_test_db()

    with patch(
        "backend.analysis.oracle.get_db",
        return_value=db,
    ):
        fired = await check_watches()

    assert fired == 0


@pytest.mark.asyncio
async def test_hostile_sighting_triggers():
    db = _get_test_db()
    now = int(time.time())
    import json

    conditions = json.dumps(
        {
            "corps": ["evil-corp"],
            "gates": ["g1"],
            "lookback_seconds": 300,
        }
    )
    _insert_watch(db, "hostile_sighting", "watch-hostiles", conditions)
    db.execute(
        "INSERT INTO gate_events "
        "(gate_id, gate_name, character_id, corp_id, "
        "solar_system_id, timestamp) "
        f"VALUES ('g1', 'War Gate', 'bad-pilot', 'evil-corp', 's1', {now - 10})"
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    title = mock_webhook.call_args[0][1]
    assert "HOSTILE" in title


@pytest.mark.asyncio
async def test_watch_no_webhook_uses_default():
    """Watch with empty webhook_url falls back to settings default."""
    db = _get_test_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO watches "
        "(user_id, watch_type, target_id, conditions, webhook_url, active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("user1", "killmail_proximity", "sys-1", '{"lookback_seconds": 1800}', ""),
    )
    db.execute(
        "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
        f"VALUES ('km1', 'sys-1', {now - 60})"
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/default"
        fired = await check_watches()

    assert fired == 1
    # Should use the default webhook URL
    mock_webhook.assert_called_once()
    assert mock_webhook.call_args[0][0] == "https://discord.com/api/webhooks/default"


@pytest.mark.asyncio
async def test_invalid_conditions_json_skipped():
    """Watch with invalid JSON conditions is silently skipped."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO watches "
        "(user_id, watch_type, target_id, conditions, webhook_url, active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("user1", "entity_movement", "pilot-1", "not-valid-json", "https://example.com"),
    )
    db.commit()

    with patch("backend.analysis.oracle.get_db", return_value=db):
        fired = await check_watches()

    assert fired == 0


# ---------- C5 Alert Tests ----------


@pytest.fixture(autouse=True)
def _clear_c5_cooldowns():
    """Clear C5 cooldown dict before and after each test."""
    _C5_ALERT_COOLDOWNS.clear()
    yield
    _C5_ALERT_COOLDOWNS.clear()


def _seed_zone(db, zone_id="zone-1", name="Alpha Orbital", last_scanned=None):
    """Insert an orbital zone for C5 tests."""
    db.execute(
        "INSERT INTO orbital_zones (zone_id, name, last_scanned) VALUES (?, ?, ?)",
        (zone_id, name, last_scanned),
    )
    db.commit()


# --- No webhook URL configured ---


@pytest.mark.asyncio
async def test_c5_returns_zero_when_no_webhook():
    """check_c5_alerts returns 0 immediately when no webhook URL is set."""
    db = _get_test_db()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = ""
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_c5_returns_zero_when_webhook_none():
    """check_c5_alerts returns 0 when webhook URL is None."""
    db = _get_test_db()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = None
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


# --- Feral AI Evolution ---


@pytest.mark.asyncio
async def test_c5_feral_ai_evolution_regular():
    """Feral AI evolution with tier < 3 fires a regular (purple) alert."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 1, 2, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    mock_webhook.assert_called_once()
    call_args = mock_webhook.call_args[0]
    assert call_args[1] == "FERAL AI EVOLVED"
    assert "Alpha Orbital" in call_args[2]
    assert "Tier 2" in call_args[2]
    assert call_args[3] == EVE_PURPLE


@pytest.mark.asyncio
async def test_c5_feral_ai_evolution_critical():
    """Feral AI evolution with tier >= 3 fires a critical (red) alert."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 2, 3, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    call_args = mock_webhook.call_args[0]
    assert call_args[1] == "CRITICAL FERAL AI"
    assert "immediate response" in call_args[2]
    assert call_args[3] == EVE_RED


@pytest.mark.asyncio
async def test_c5_feral_ai_evolution_tier_5_critical():
    """Tier 5 evolution also fires critical alert."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 4, 5, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    assert mock_webhook.call_args[0][1] == "CRITICAL FERAL AI"


@pytest.mark.asyncio
async def test_c5_feral_ai_unknown_zone_uses_id():
    """When zone not in orbital_zones, falls back to zone_id[:16]."""
    db = _get_test_db()
    now = int(time.time())
    # No zone seeded — zone lookup returns None
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("abcdef1234567890extra", "evolution", 0, 1, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    body = mock_webhook.call_args[0][2]
    assert "abcdef1234567890" in body


@pytest.mark.asyncio
async def test_c5_feral_ai_old_event_ignored():
    """Evolution events older than COOLDOWN_SECONDS are not returned by query."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 1, 2, now - COOLDOWN_SECONDS - 100),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_c5_feral_ai_non_evolution_event_ignored():
    """Events with event_type != 'evolution' are not picked up."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "spawn", 0, 1, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


# --- Hostile Scan ---


@pytest.mark.asyncio
async def test_c5_hostile_scan_fires():
    """HOSTILE scan result fires a red alert with zone name and scanner."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO scans (scan_id, zone_id, scanner_name, result_type, scanned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("scan-1", "zone-1", "Pilot Alpha", "HOSTILE", now - 30),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    call_args = mock_webhook.call_args[0]
    assert call_args[1] == "HOSTILE DETECTED"
    assert "Alpha Orbital" in call_args[2]
    assert "Pilot Alpha" in call_args[2]
    assert call_args[3] == EVE_RED


@pytest.mark.asyncio
async def test_c5_hostile_scan_unknown_zone():
    """HOSTILE scan with unknown zone falls back to zone_id[:16]."""
    db = _get_test_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO scans (scan_id, zone_id, scanner_name, result_type, scanned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("scan-1", "unknown-zone-id-long", None, "HOSTILE", now - 30),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    body = mock_webhook.call_args[0][2]
    assert "unknown-zone-id-" in body
    assert "unknown" in body  # scanner fallback


@pytest.mark.asyncio
async def test_c5_hostile_scan_non_hostile_ignored():
    """Non-HOSTILE scan results are not picked up."""
    db = _get_test_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO scans (scan_id, zone_id, scanner_name, result_type, scanned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("scan-1", "zone-1", "Pilot Alpha", "CLEAR", now - 30),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


# --- Blind Spot ---


@pytest.mark.asyncio
async def test_c5_blind_spot_fires():
    """Zone not scanned for >BLIND_SPOT_THRESHOLD fires a yellow alert."""
    db = _get_test_db()
    now = int(time.time())
    old_scan = now - BLIND_SPOT_THRESHOLD - 600  # 30 min old
    _seed_zone(db, "zone-1", "Alpha Orbital", last_scanned=old_scan)

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    call_args = mock_webhook.call_args[0]
    assert call_args[1] == "BLIND SPOT"
    assert "Alpha Orbital" in call_args[2]
    assert "30m" in call_args[2]
    assert call_args[3] == EVE_YELLOW


@pytest.mark.asyncio
async def test_c5_blind_spot_recently_scanned_no_alert():
    """Zone scanned recently does not trigger blind spot."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital", last_scanned=now - 60)

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_c5_blind_spot_null_last_scanned_no_alert():
    """Zone with NULL last_scanned does not trigger blind spot."""
    db = _get_test_db()
    _seed_zone(db, "zone-1", "Alpha Orbital", last_scanned=None)

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_c5_blind_spot_no_name_uses_zone_id():
    """Blind spot zone with NULL name falls back to zone_id[:16]."""
    db = _get_test_db()
    now = int(time.time())
    old_scan = now - BLIND_SPOT_THRESHOLD - 60
    _seed_zone(db, "zone-longid-1234567890", None, last_scanned=old_scan)

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    body = mock_webhook.call_args[0][2]
    assert "zone-longid-1234" in body


# --- Clone Reserve Low ---


@pytest.mark.asyncio
async def test_c5_clone_reserve_low_fires():
    """Owner with fewer than CLONE_RESERVE_THRESHOLD active clones fires alert."""
    db = _get_test_db()
    # Insert 3 active clones (below threshold of 5)
    for i in range(3):
        db.execute(
            "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
            (f"clone-{i}", "owner-1", "Captain Rex", "active"),
        )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    call_args = mock_webhook.call_args[0]
    assert call_args[1] == "CLONE RESERVE LOW"
    assert "Captain Rex" in call_args[2]
    assert "3 active clones" in call_args[2]
    assert call_args[3] == EVE_ORANGE


@pytest.mark.asyncio
async def test_c5_clone_reserve_at_threshold_no_alert():
    """Owner with exactly CLONE_RESERVE_THRESHOLD clones does not fire."""
    db = _get_test_db()
    for i in range(CLONE_RESERVE_THRESHOLD):
        db.execute(
            "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
            (f"clone-{i}", "owner-1", "Captain Rex", "active"),
        )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_c5_clone_reserve_inactive_not_counted():
    """Inactive clones are not counted toward active reserve."""
    db = _get_test_db()
    # 2 active + 5 inactive = still low
    for i in range(2):
        db.execute(
            "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
            (f"clone-active-{i}", "owner-1", "Captain Rex", "active"),
        )
    for i in range(5):
        db.execute(
            "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
            (f"clone-dead-{i}", "owner-1", "Captain Rex", "destroyed"),
        )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    assert "2 active clones" in mock_webhook.call_args[0][2]


@pytest.mark.asyncio
async def test_c5_clone_reserve_null_name_uses_id():
    """Owner with NULL name falls back to owner_id[:16]."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
        ("clone-1", "owner-abcdef1234567890extra", None, "active"),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 1
    body = mock_webhook.call_args[0][2]
    assert "owner-abcdef1234" in body


# --- Cooldown Tests ---


@pytest.mark.asyncio
async def test_c5_cooldown_prevents_duplicate_feral_alert():
    """Same zone evolution does not re-fire within cooldown window."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 1, 2, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        # First call fires
        fired1 = await check_c5_alerts()
        # Second call within cooldown does not fire
        fired2 = await check_c5_alerts()

    assert fired1 == 1
    assert fired2 == 0
    assert mock_webhook.call_count == 1


@pytest.mark.asyncio
async def test_c5_cooldown_prevents_duplicate_hostile_scan():
    """Same zone hostile scan does not re-fire within cooldown."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    db.execute(
        "INSERT INTO scans (scan_id, zone_id, scanner_name, result_type, scanned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("scan-1", "zone-1", "Pilot Alpha", "HOSTILE", now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired1 = await check_c5_alerts()
        fired2 = await check_c5_alerts()

    assert fired1 == 1
    assert fired2 == 0
    assert mock_webhook.call_count == 1


@pytest.mark.asyncio
async def test_c5_cooldown_prevents_duplicate_blind_spot():
    """Same zone blind spot does not re-fire within cooldown."""
    db = _get_test_db()
    now = int(time.time())
    old_scan = now - BLIND_SPOT_THRESHOLD - 60
    _seed_zone(db, "zone-1", "Alpha Orbital", last_scanned=old_scan)

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired1 = await check_c5_alerts()
        fired2 = await check_c5_alerts()

    assert fired1 == 1
    assert fired2 == 0
    assert mock_webhook.call_count == 1


@pytest.mark.asyncio
async def test_c5_cooldown_prevents_duplicate_clone_low():
    """Same owner clone low does not re-fire within cooldown."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
        ("clone-1", "owner-1", "Captain Rex", "active"),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired1 = await check_c5_alerts()
        fired2 = await check_c5_alerts()

    assert fired1 == 1
    assert fired2 == 0
    assert mock_webhook.call_count == 1


@pytest.mark.asyncio
async def test_c5_cooldown_different_zones_fire_independently():
    """Cooldown is per-zone — different zones fire independently."""
    db = _get_test_db()
    now = int(time.time())
    _seed_zone(db, "zone-1", "Alpha Orbital")
    _seed_zone(db, "zone-2", "Beta Orbital")
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 1, 2, now - 10),
    )
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-2", "evolution", 0, 1, now - 10),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 2
    assert mock_webhook.call_count == 2


# --- Multiple alert types in one call ---


@pytest.mark.asyncio
async def test_c5_multiple_alert_types_fire_together():
    """All four alert types can fire in a single check_c5_alerts call."""
    db = _get_test_db()
    now = int(time.time())

    # 1. Feral AI evolution
    _seed_zone(db, "zone-1", "Alpha Orbital", last_scanned=now - 60)
    db.execute(
        "INSERT INTO feral_ai_events (zone_id, event_type, old_tier, new_tier, timestamp) "
        "VALUES (?, ?, ?, ?, ?)",
        ("zone-1", "evolution", 1, 2, now - 10),
    )

    # 2. Hostile scan (different zone)
    _seed_zone(db, "zone-2", "Beta Orbital", last_scanned=now - 60)
    db.execute(
        "INSERT INTO scans (scan_id, zone_id, scanner_name, result_type, scanned_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("scan-1", "zone-2", "Scout", "HOSTILE", now - 20),
    )

    # 3. Blind spot (third zone, old scan)
    _seed_zone(db, "zone-3", "Gamma Orbital", last_scanned=now - BLIND_SPOT_THRESHOLD - 300)

    # 4. Clone reserve low
    db.execute(
        "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
        ("clone-1", "owner-1", "Captain Rex", "active"),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 4
    assert mock_webhook.call_count == 4
    titles = [call[0][1] for call in mock_webhook.call_args_list]
    assert "FERAL AI EVOLVED" in titles
    assert "HOSTILE DETECTED" in titles
    assert "BLIND SPOT" in titles
    assert "CLONE RESERVE LOW" in titles


@pytest.mark.asyncio
async def test_c5_no_data_returns_zero():
    """Empty database with webhook configured returns 0."""
    db = _get_test_db()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/test"
        fired = await check_c5_alerts()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_c5_webhook_url_passed_correctly():
    """Webhook URL from settings is passed to fire_webhook."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO clones (clone_id, owner_id, owner_name, status) VALUES (?, ?, ?, ?)",
        ("clone-1", "owner-1", "Test", "active"),
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/specific-url"
        fired = await check_c5_alerts()

    assert fired == 1
    assert mock_webhook.call_args[0][0] == "https://discord.com/api/webhooks/specific-url"
