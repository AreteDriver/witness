"""Tests for World API poller."""

import asyncio
import json
import sqlite3
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from httpx import Response

from backend.db.database import SCHEMA
from backend.ingestion.poller import (
    _archive_pre_cycle_data,
    _detect_universe_reset,
    _ingest_gate_events,
    _ingest_killmails,
    _ingest_smart_assemblies,
    _ingest_subscriptions,
    _parse_iso_time,
    _update_entities,
    poll_endpoint,
    run_poller,
)


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _mock_settings(**overrides):
    defaults = {
        "WORLD_API_BASE": "http://test",
        "POLL_TIMEOUT_SECONDS": 5,
        "POLL_INTERVAL_SECONDS": 30,
    }
    defaults.update(overrides)
    return type("S", (), defaults)()


def test_parse_iso_time():
    ts = _parse_iso_time("2025-12-10T16:20:58Z")
    assert ts == 1765383658


def test_parse_iso_time_invalid():
    ts = _parse_iso_time("not-a-date")
    assert abs(ts - int(time.time())) < 2


def test_parse_iso_time_attribute_error():
    """None input triggers AttributeError branch."""
    ts = _parse_iso_time(None)
    assert abs(ts - int(time.time())) < 2


# --- poll_endpoint ---


@respx.mock
async def test_poll_endpoint_returns_list():
    respx.get("http://test/killmails").mock(return_value=Response(200, json=[{"id": "km1"}]))
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "killmails")
    assert result == [{"id": "km1"}]


@respx.mock
async def test_poll_endpoint_returns_empty_on_error():
    respx.get("http://test/bad").mock(return_value=Response(500))
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "bad")
    assert result == []


@respx.mock
async def test_poll_endpoint_unwraps_data_key():
    respx.get("http://test/wrapped").mock(
        return_value=Response(
            200,
            json={
                "data": [{"id": "a"}, {"id": "b"}],
                "metadata": {"total": 2, "limit": 100, "offset": 0},
            },
        )
    )
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "wrapped")
    assert len(result) == 2


@respx.mock
async def test_poll_endpoint_data_single_item():
    """Line 51: data value is a dict, not a list — appended."""
    respx.get("http://test/single-data").mock(
        return_value=Response(
            200,
            json={
                "data": {"id": "solo"},
                "metadata": {"total": 1, "limit": 100, "offset": 0},
            },
        )
    )
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "single-data")
    assert len(result) == 1
    assert result[0]["id"] == "solo"


@respx.mock
async def test_poll_endpoint_pagination():
    """Lines 55-57: pagination with offset increment."""
    # Page 1: 100 items, total 150
    page1 = {
        "data": [{"id": f"item-{i}"} for i in range(100)],
        "metadata": {"total": 150, "limit": 100, "offset": 0},
    }
    # Page 2: 50 items
    page2 = {
        "data": [{"id": f"item-{i}"} for i in range(100, 150)],
        "metadata": {"total": 150, "limit": 100, "offset": 100},
    }
    route = respx.get("http://test/paged")
    route.side_effect = [
        Response(200, json=page1),
        Response(200, json=page2),
    ]
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "paged")
    assert len(result) == 150


@respx.mock
async def test_poll_endpoint_timeout():
    """Timeout returns empty list, never crashes."""
    respx.get("http://test/slow").mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "slow")
    assert result == []


@respx.mock
async def test_poll_endpoint_generic_exception():
    """Lines 68-70: generic Exception branch."""
    respx.get("http://test/explode").mock(side_effect=RuntimeError("something broke"))
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "explode")
    assert result == []


@respx.mock
async def test_poll_endpoint_returns_single_dict():
    """Non-list, non-data-key response is wrapped in list."""
    respx.get("http://test/single").mock(
        return_value=Response(200, json={"id": "item1", "value": 42})
    )
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                _mock_settings(),
            )
            result = await poll_endpoint(client, "single")
    assert len(result) == 1
    assert result[0]["id"] == "item1"


# --- _ingest_killmails ---


def test_ingest_killmails_v2_format():
    """Ingest killmail with v2 API structure (killer not attackers)."""
    db = _get_test_db()
    raw = [
        {
            "id": 9,
            "victim": {
                "address": "0x81fe62db",
                "name": "Phaseone",
                "id": "937214402",
            },
            "killer": {
                "address": "0xb4b9ebca",
                "name": "Konradt Curze",
                "id": "396447741",
            },
            "solarSystemId": 30023604,
            "time": "2025-12-10T16:20:58Z",
        }
    ]
    count = _ingest_killmails(db, raw)
    assert count == 1

    row = db.execute("SELECT * FROM killmails WHERE killmail_id = '9'").fetchone()
    assert row is not None
    assert row["victim_character_id"] == "0x81fe62db"
    assert row["timestamp"] == 1765383658


def test_ingest_killmails_legacy_format():
    db = _get_test_db()
    now = int(time.time())
    raw = [
        {
            "id": "km-001",
            "victim": {"characterId": "char-v1", "corporationId": "corp-v1"},
            "attackers": [{"corporationId": "corp-a1"}],
            "solarSystemId": "sys-1",
            "position": {"x": 1.0, "y": 2.0, "z": 3.0},
            "timestamp": now,
        }
    ]
    count = _ingest_killmails(db, raw)
    assert count == 1

    row = db.execute("SELECT * FROM killmails WHERE killmail_id = 'km-001'").fetchone()
    assert row["victim_character_id"] == "char-v1"
    assert row["x"] == 1.0


def test_ingest_killmails_skips_no_id():
    db = _get_test_db()
    count = _ingest_killmails(db, [{"noId": True}])
    assert count == 0


def test_ingest_killmails_dedup():
    db = _get_test_db()
    raw = [{"id": "km-dup", "timestamp": 1000}]
    _ingest_killmails(db, raw)
    count = _ingest_killmails(db, raw)
    assert count == 0  # duplicate correctly rejected

    total = db.execute("SELECT COUNT(*) as cnt FROM killmails").fetchone()
    assert total["cnt"] == 1


def test_ingest_killmails_iso_timestamp():
    """Line 93: timestamp is a string, parsed via _parse_iso_time."""
    db = _get_test_db()
    raw = [{"id": "km-str-ts", "timestamp": "2025-12-10T16:20:58Z"}]
    count = _ingest_killmails(db, raw)
    assert count == 1
    row = db.execute("SELECT timestamp FROM killmails WHERE killmail_id = 'km-str-ts'").fetchone()
    assert row["timestamp"] == 1765383658


def test_ingest_killmails_no_timestamp_fallback():
    """Line 98: no timestamp, no time field — falls back to now."""
    db = _get_test_db()
    raw = [{"id": "km-no-ts"}]
    count = _ingest_killmails(db, raw)
    assert count == 1
    row = db.execute("SELECT timestamp FROM killmails WHERE killmail_id = 'km-no-ts'").fetchone()
    assert abs(row["timestamp"] - int(time.time())) < 5


def test_ingest_killmails_db_error():
    """Lines 126-127: DB error is caught and logged."""
    db = MagicMock()
    db.execute.side_effect = sqlite3.OperationalError("table locked")
    count = _ingest_killmails(db, [{"id": "km-err", "timestamp": 1000}])
    assert count == 0


def test_ingest_killmails_alternative_field_names():
    db = _get_test_db()
    now = int(time.time())
    raw = [
        {"killMailId": "km-camel", "timestamp": now},
        {"killmail_id": "km-snake", "timestamp": now},
    ]
    count = _ingest_killmails(db, raw)
    assert count == 2


def test_ingest_killmails_iso_time_field():
    """Killmail with ISO time string in 'time' field."""
    db = _get_test_db()
    raw = [{"id": "km-iso", "time": "2025-12-10T16:20:58Z"}]
    count = _ingest_killmails(db, raw)
    assert count == 1
    row = db.execute("SELECT timestamp FROM killmails WHERE killmail_id = 'km-iso'").fetchone()
    assert row["timestamp"] == 1765383658


def test_ingest_killmails_missing_position():
    db = _get_test_db()
    raw = [{"id": "km-nopos", "timestamp": 1000}]
    count = _ingest_killmails(db, raw)
    assert count == 1
    row = db.execute("SELECT * FROM killmails WHERE killmail_id = 'km-nopos'").fetchone()
    assert row["x"] is None


def test_ingest_killmails_missing_victim():
    db = _get_test_db()
    raw = [{"id": "km-novictim", "timestamp": 1000, "attackers": []}]
    count = _ingest_killmails(db, raw)
    assert count == 1
    row = db.execute("SELECT * FROM killmails WHERE killmail_id = 'km-novictim'").fetchone()
    assert row["victim_character_id"] == ""


# --- _ingest_smart_assemblies ---


def test_ingest_smart_assemblies():
    db = _get_test_db()
    raw = [
        {
            "id": "935035856535",
            "type": "SmartGate",
            "name": "",
            "state": "online",
            "solarSystem": {
                "id": 30016141,
                "name": "I8D-J6B",
                "constellationId": 20001122,
                "regionId": 10000141,
                "location": {
                    "x": -2.16e19,
                    "y": -8.17e17,
                    "z": -1.38e18,
                },
            },
            "owner": {
                "address": "0xe99bec67f5a04f26",
                "name": "Captain Killian",
                "id": "403596359",
            },
        }
    ]
    count = _ingest_smart_assemblies(db, raw)
    assert count == 1
    row = db.execute("SELECT * FROM smart_assemblies").fetchone()
    assert row["assembly_type"] == "SmartGate"
    assert row["owner_name"] == "Captain Killian"


def test_ingest_smart_assemblies_skips_no_id():
    db = _get_test_db()
    count = _ingest_smart_assemblies(db, [{"noId": True}])
    assert count == 0


def test_ingest_smart_assemblies_safe_coord_bad_value():
    """Lines 147-148: _safe_coord returns None for bad values."""
    db = _get_test_db()
    raw = [
        {
            "id": "asm-bad-coord",
            "solarSystem": {
                "location": {"x": "not-a-number", "y": None, "z": [1]},
            },
        }
    ]
    count = _ingest_smart_assemblies(db, raw)
    assert count == 1
    row = db.execute(
        "SELECT * FROM smart_assemblies WHERE assembly_id = 'asm-bad-coord'"
    ).fetchone()
    assert row["x"] is None
    assert row["y"] is None
    assert row["z"] is None


def test_ingest_smart_assemblies_db_error():
    """Lines 174-175: DB error is caught and logged."""
    db = MagicMock()
    db.execute.side_effect = sqlite3.OperationalError("table locked")
    count = _ingest_smart_assemblies(db, [{"id": "asm-err", "solarSystem": {}}])
    assert count == 0


# --- _ingest_gate_events ---


def test_ingest_gate_events():
    db = _get_test_db()
    now = int(time.time())
    raw = [
        {
            "id": "gate-001",
            "name": "Alpha Gate",
            "characterId": "char-1",
            "corporationId": "corp-1",
            "solarSystemId": "sys-1",
            "direction": "enter",
            "timestamp": now,
        }
    ]
    count = _ingest_gate_events(db, raw)
    assert count == 1
    row = db.execute("SELECT * FROM gate_events WHERE gate_id = 'gate-001'").fetchone()
    assert row["gate_name"] == "Alpha Gate"


def test_ingest_gate_events_skips_no_id():
    db = _get_test_db()
    count = _ingest_gate_events(db, [{"noId": True}])
    assert count == 0


def test_ingest_gate_events_iso_timestamp():
    """Line 189: timestamp is a string, parsed."""
    db = _get_test_db()
    raw = [{"id": "g-iso", "timestamp": "2025-12-10T16:20:58Z"}]
    count = _ingest_gate_events(db, raw)
    assert count == 1
    row = db.execute("SELECT timestamp FROM gate_events WHERE gate_id = 'g-iso'").fetchone()
    assert row["timestamp"] == 1765383658


def test_ingest_gate_events_no_timestamp():
    """Line 191: no timestamp — falls back to now."""
    db = _get_test_db()
    raw = [{"id": "g-nots"}]
    count = _ingest_gate_events(db, raw)
    assert count == 1
    row = db.execute("SELECT timestamp FROM gate_events WHERE gate_id = 'g-nots'").fetchone()
    assert abs(row["timestamp"] - int(time.time())) < 5


def test_ingest_gate_events_db_error():
    """Lines 211-212: DB error is caught."""
    db = MagicMock()
    db.execute.side_effect = sqlite3.OperationalError("locked")
    count = _ingest_gate_events(db, [{"id": "g-err", "timestamp": 1000}])
    assert count == 0


def test_ingest_gate_events_alternative_fields():
    db = _get_test_db()
    now = int(time.time())
    raw = [
        {"gateId": "gate-camel", "timestamp": now},
        {"smartGateId": "gate-smart", "timestamp": now},
    ]
    count = _ingest_gate_events(db, raw)
    assert count == 2


# --- _update_entities ---


def test_update_entities_from_killmails():
    db = _get_test_db()
    now = int(time.time())
    for i in range(3):
        db.execute(
            "INSERT INTO killmails "
            "(killmail_id, victim_character_id, victim_name, "
            "solar_system_id, timestamp) "
            f"VALUES ('km{i}', 'victim-1', 'TestVictim', 'sys-1', {now + i})"
        )
    db.commit()
    _update_entities(db)
    db.commit()

    entity = db.execute("SELECT * FROM entities WHERE entity_id = 'victim-1'").fetchone()
    assert entity is not None
    assert entity["death_count"] == 3


def test_update_entities_kill_counts():
    """Lines 246-256: attacker kill count extraction from JSON."""
    db = _get_test_db()
    now = int(time.time())
    attackers = [
        {"address": "killer-A", "corporationId": "corp-1"},
        {"address": "killer-B"},
    ]
    for i in range(3):
        db.execute(
            "INSERT INTO killmails "
            "(killmail_id, victim_character_id, victim_name, "
            "attacker_character_ids, solar_system_id, timestamp) "
            "VALUES (?, 'victim-x', 'Victim', ?, 'sys-1', ?)",
            (f"km-kc-{i}", json.dumps(attackers), now + i),
        )
    db.commit()

    _update_entities(db)
    db.commit()

    # killer-A won't be in entities unless also a victim/gate user.
    # Verify the victim entity exists (created by the first SQL).
    victim = db.execute("SELECT * FROM entities WHERE entity_id = 'victim-x'").fetchone()
    assert victim is not None
    assert victim["death_count"] == 3


def test_update_entities_kill_counts_with_existing_entity():
    """Lines 246-256: kill count updates existing entity."""
    db = _get_test_db()
    now = int(time.time())
    # Create an attacker who is also a victim (so entity exists)
    attackers = [{"address": "dual-role"}]
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, victim_character_id, victim_name, "
        "attacker_character_ids, solar_system_id, timestamp) "
        "VALUES ('km-dual-v', 'dual-role', 'DualRole', '[]', 'sys', ?)",
        (now,),
    )
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, victim_character_id, victim_name, "
        "attacker_character_ids, solar_system_id, timestamp) "
        "VALUES ('km-dual-k', 'other-victim', 'Other', ?, 'sys', ?)",
        (json.dumps(attackers), now),
    )
    db.commit()

    _update_entities(db)
    db.commit()

    entity = db.execute("SELECT * FROM entities WHERE entity_id = 'dual-role'").fetchone()
    assert entity is not None
    assert entity["kill_count"] == 1


def test_update_entities_malformed_attacker_json():
    """Lines 253-254: malformed JSON in attacker_character_ids."""
    db = _get_test_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, victim_character_id, victim_name, "
        "attacker_character_ids, solar_system_id, timestamp) "
        "VALUES ('km-bad-json', 'v1', 'V', 'not-json', 'sys', ?)",
        (now,),
    )
    db.commit()
    # Should not raise
    _update_entities(db)
    db.commit()


def test_update_entities_from_gate_events():
    db = _get_test_db()
    now = int(time.time())
    for i in range(5):
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, gate_name, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'Gate One', 'pilot-1', 'sys-1', {now + i})"
        )
    db.commit()
    _update_entities(db)
    db.commit()

    pilot = db.execute("SELECT * FROM entities WHERE entity_id = 'pilot-1'").fetchone()
    assert pilot is not None
    assert pilot["gate_count"] == 5


def test_update_entities_from_smart_assemblies():
    db = _get_test_db()
    db.execute(
        "INSERT INTO smart_assemblies "
        "(assembly_id, assembly_type, name, state, "
        "solar_system_id, solar_system_name, owner_address, owner_name) "
        "VALUES ('gate-1', 'SmartGate', '', 'online', "
        "'30016141', 'I8D-J6B', '0xabc', 'Captain Killian')"
    )
    db.commit()
    _update_entities(db)
    db.commit()

    gate = db.execute("SELECT * FROM entities WHERE entity_id = 'gate-1'").fetchone()
    assert gate is not None
    assert gate["entity_type"] == "SmartGate"
    assert gate["display_name"] == "Captain Killian"


def test_update_entities_empty_tables():
    db = _get_test_db()
    _update_entities(db)
    db.commit()
    count = db.execute("SELECT COUNT(*) as cnt FROM entities").fetchone()
    assert count["cnt"] == 0


def test_update_entities_db_error():
    """Lines 294-295: generic error in _update_entities."""
    db = MagicMock()
    db.execute.side_effect = sqlite3.OperationalError("boom")
    # Should not raise
    _update_entities(db)


# --- run_poller ---


@respx.mock
async def test_run_poller_one_iteration():
    """Lines 300-327: run_poller main loop, one iteration."""
    respx.get(url__regex=r".*/v2/killmails.*").mock(
        return_value=Response(200, json=[{"id": "km-poll", "timestamp": 1000}])
    )
    respx.get(url__regex=r".*/v2/smartassemblies.*").mock(
        return_value=Response(200, json=[{"id": "asm-poll"}])
    )

    test_db = _get_test_db()
    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            raise asyncio.CancelledError()

    with (
        patch(
            "backend.ingestion.poller.settings",
            _mock_settings(),
        ),
        patch(
            "backend.ingestion.poller.get_db",
            return_value=test_db,
        ),
        patch(
            "backend.ingestion.poller.asyncio.sleep",
            side_effect=mock_sleep,
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_poller()

    # Verify data was ingested
    km = test_db.execute("SELECT COUNT(*) as c FROM killmails").fetchone()
    assert km["c"] >= 1
    asm = test_db.execute("SELECT COUNT(*) as c FROM smart_assemblies").fetchone()
    assert asm["c"] >= 1


@respx.mock
async def test_run_poller_handles_loop_error():
    """Lines 324-325: exception in loop body is caught."""
    respx.get(url__regex=r".*/v2/killmails.*").mock(return_value=Response(200, json=[]))
    respx.get(url__regex=r".*/v2/smartassemblies.*").mock(return_value=Response(200, json=[]))

    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError()

    def exploding_db():
        raise RuntimeError("DB exploded")

    with (
        patch(
            "backend.ingestion.poller.settings",
            _mock_settings(),
        ),
        patch(
            "backend.ingestion.poller.get_db",
            side_effect=exploding_db,
        ),
        patch(
            "backend.ingestion.poller.asyncio.sleep",
            side_effect=mock_sleep,
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_poller()

    # Should have survived at least one error iteration
    assert call_count >= 1


@respx.mock
async def test_run_poller_no_new_data():
    """Lines 321-322: commit without entity update when no new data."""
    respx.get(url__regex=r".*/v2/killmails.*").mock(return_value=Response(200, json=[]))
    respx.get(url__regex=r".*/v2/smartassemblies.*").mock(return_value=Response(200, json=[]))

    test_db = _get_test_db()
    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            raise asyncio.CancelledError()

    with (
        patch(
            "backend.ingestion.poller.settings",
            _mock_settings(),
        ),
        patch(
            "backend.ingestion.poller.get_db",
            return_value=test_db,
        ),
        patch(
            "backend.ingestion.poller.asyncio.sleep",
            side_effect=mock_sleep,
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_poller()

    # No data ingested
    km = test_db.execute("SELECT COUNT(*) as c FROM killmails").fetchone()
    assert km["c"] == 0


# --- Subscription ingest tests ---


def test_ingest_subscriptions_basic():
    db = _get_test_db()
    assemblies = [
        {
            "id": "asm-1",
            "type": "SmartStorageUnit",
            "subscriptions": [
                {"subscriber": "0xABCD", "tier": 2, "expiresAt": 9999999999},
            ],
        }
    ]
    count = _ingest_subscriptions(db, assemblies)
    db.commit()
    assert count == 1
    row = db.execute(
        "SELECT tier, expires_at FROM watcher_subscriptions WHERE wallet_address = ?",
        ("0xabcd",),
    ).fetchone()
    assert row["tier"] == 2
    assert row["expires_at"] == 9999999999


def test_ingest_subscriptions_upgrade():
    db = _get_test_db()
    # Insert initial sub
    db.execute(
        "INSERT INTO watcher_subscriptions (wallet_address, tier, expires_at) VALUES (?, ?, ?)",
        ("0xabcd", 1, 1000),
    )
    db.commit()
    assemblies = [
        {
            "id": "asm-1",
            "type": "SmartStorageUnit",
            "subscriptions": [
                {"subscriber": "0xABCD", "tier": 3, "expiresAt": 2000},
            ],
        }
    ]
    _ingest_subscriptions(db, assemblies)
    db.commit()
    row = db.execute(
        "SELECT tier, expires_at FROM watcher_subscriptions WHERE wallet_address = ?",
        ("0xabcd",),
    ).fetchone()
    assert row["tier"] == 3  # Upgraded
    assert row["expires_at"] == 2000


def test_ingest_subscriptions_empty():
    db = _get_test_db()
    count = _ingest_subscriptions(db, [{"id": "asm-1", "type": "gate"}])
    assert count == 0


def test_ingest_subscriptions_no_wallet():
    db = _get_test_db()
    assemblies = [
        {
            "id": "asm-1",
            "type": "SmartStorageUnit",
            "subscriptions": [{"tier": 1, "expiresAt": 9999}],
        }
    ]
    count = _ingest_subscriptions(db, assemblies)
    assert count == 0


# =========================================================================
# Universe Reset Detection
# =========================================================================


def test_detect_reset_no_data():
    """No data = no reset detected."""
    db = _get_test_db()
    assert _detect_universe_reset(db) is False


def test_detect_reset_with_pre_cycle_data():
    """Pre-cycle killmails trigger reset detection."""
    db = _get_test_db()
    # Insert a killmail from before the reset epoch
    db.execute(
        """INSERT INTO killmails (killmail_id, timestamp, cycle)
           VALUES ('old-kill-1', 1741000000, 5)"""
    )
    db.commit()
    assert _detect_universe_reset(db) is True


def test_detect_reset_all_post_cycle():
    """Post-cycle data only = no reset detected."""
    db = _get_test_db()
    db.execute(
        """INSERT INTO killmails (killmail_id, timestamp, cycle)
           VALUES ('new-kill-1', 1741700000, 5)"""
    )
    db.commit()
    assert _detect_universe_reset(db) is False


def test_archive_pre_cycle_data():
    """Pre-cycle killmails get moved to cycle 4."""
    db = _get_test_db()
    # Insert one old and one new killmail
    db.execute(
        """INSERT INTO killmails (killmail_id, timestamp, cycle)
           VALUES ('old-1', 1741000000, 5)"""
    )
    db.execute(
        """INSERT INTO killmails (killmail_id, timestamp, cycle)
           VALUES ('new-1', 1741700000, 5)"""
    )
    db.commit()

    _archive_pre_cycle_data(db)

    # Old one should be cycle 4
    old = db.execute("SELECT cycle FROM killmails WHERE killmail_id = 'old-1'").fetchone()
    assert old["cycle"] == 4

    # New one should still be cycle 5
    new = db.execute("SELECT cycle FROM killmails WHERE killmail_id = 'new-1'").fetchone()
    assert new["cycle"] == 5


def test_archive_clears_c5_stale_tables():
    """C5-specific tables get stale rows cleared."""
    db = _get_test_db()
    # Insert a stale orbital zone from cycle 4
    db.execute(
        """INSERT INTO orbital_zones (zone_id, name, cycle)
           VALUES ('zone-1', 'Test Zone', 4)"""
    )
    db.commit()

    _archive_pre_cycle_data(db)

    row = db.execute("SELECT COUNT(*) as cnt FROM orbital_zones").fetchone()
    assert row["cnt"] == 0


def test_archive_preserves_c5_data():
    """Current cycle C5 data is untouched."""
    db = _get_test_db()
    db.execute(
        """INSERT INTO orbital_zones (zone_id, name, cycle)
           VALUES ('zone-1', 'Test Zone', 5)"""
    )
    db.commit()

    _archive_pre_cycle_data(db)

    row = db.execute("SELECT COUNT(*) as cnt FROM orbital_zones").fetchone()
    assert row["cnt"] == 1
