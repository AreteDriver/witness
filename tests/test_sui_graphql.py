"""Tests for Sui GraphQL data source adapter."""

import pytest

from backend.ingestion.sui_graphql import (
    EVENT_TYPES,
    STILLNESS_PKG,
    SuiGraphQLPoller,
    _item_id,
    _parse_sui_timestamp,
    fetch_all_character_names,
    transform_assemblies,
    transform_characters,
    transform_gate_jumps,
    transform_killmails,
)

# --- Helpers ---


def test_parse_sui_timestamp():
    assert _parse_sui_timestamp("2026-03-12T18:56:26.699Z") == 1773341786
    # Bad input returns current time (non-zero)
    assert _parse_sui_timestamp("garbage") > 0


def test_item_id_dict():
    assert _item_id({"item_id": "252", "tenant": "stillness"}) == "252"


def test_item_id_string():
    assert _item_id("12345") == "12345"


def test_item_id_empty():
    assert _item_id({}) == ""


# --- Event type constants ---


def test_event_types_contain_package():
    for key, val in EVENT_TYPES.items():
        assert STILLNESS_PKG in val, f"{key} missing package ID"


# --- Transform killmails ---


SAMPLE_KILLMAIL_EVENT = {
    "contents": {
        "json": {
            "key": {"item_id": "252", "tenant": "stillness"},
            "killer_id": {"item_id": "2112077749", "tenant": "stillness"},
            "victim_id": {"item_id": "2112077944", "tenant": "stillness"},
            "reported_by_character_id": {
                "item_id": "2112077749",
                "tenant": "stillness",
            },
            "loss_type": {"@variant": "STRUCTURE"},
            "kill_timestamp": "1773340896",
            "solar_system_id": {"item_id": "30013496", "tenant": "stillness"},
        }
    },
    "sender": {"address": "0x59714bcd14f03bd20794bd3b5a2a52a0045e75e1bc9cc78aada8c56847e5731c"},
    "timestamp": "2026-03-12T18:56:26.699Z",
    "sequenceNumber": 0,
}


def test_transform_killmails_basic():
    results = transform_killmails([SAMPLE_KILLMAIL_EVENT])
    assert len(results) == 1

    km = results[0]
    assert km["id"] == "252"
    assert km["killmail_id"] == "252"
    assert km["victim"]["address"] == "2112077944"
    assert km["killer"]["address"] == "2112077749"
    assert km["attackers"] == [km["killer"]]
    assert km["solarSystemId"] == "30013496"
    assert km["timestamp"] == 1773340896
    assert km["loss_type"] == "STRUCTURE"


def test_transform_killmails_empty():
    assert transform_killmails([]) == []


def test_transform_killmails_missing_contents():
    assert transform_killmails([{"contents": {"json": {}}}]) == []
    assert transform_killmails([{"contents": {}}]) == []


# --- Transform characters ---


SAMPLE_CHARACTER_EVENT = {
    "contents": {
        "json": {
            "character_id": "0x978a73b03801b2a0a79b20012f6f9f69a239fcc14074e5909a9a4ad66c95eecf",
            "key": {"item_id": "2112077429", "tenant": "stillness"},
            "tribe_id": 1000167,
            "character_address": "0xc4b7d17877d2d6c64423e90a6df24a1a5445d0bf0415a263eb97e069c3120946",
        }
    },
    "timestamp": "2026-03-11T15:33:06.104Z",
}


def test_transform_characters_basic():
    results = transform_characters([SAMPLE_CHARACTER_EVENT])
    assert len(results) == 1

    ch = results[0]
    assert ch["address"] == "0xc4b7d17877d2d6c64423e90a6df24a1a5445d0bf0415a263eb97e069c3120946"
    assert ch["id"] == "2112077429"
    assert ch["name"] == ""
    assert ch["_tribe_id"] == 1000167


def test_transform_characters_empty():
    assert transform_characters([]) == []


# --- Transform assemblies ---


SAMPLE_ASSEMBLY_EVENT = {
    "contents": {
        "json": {
            "assembly_id": "0x62f5797becab1d2448c0e7eb4654760a026f1796cfa7e0c75047e9dc71346140",
            "assembly_key": {"item_id": "1000000011455", "tenant": "stillness"},
            "owner_cap_id": "0xd858efdea8bdfa3a3914d7bbf8efb3ab238835fe14fc4470e837301a62c29017",
            "type_id": "91978",
        }
    },
    "sender": {"address": "0xabc123"},
    "timestamp": "2026-03-11T18:44:11.313Z",
}


def test_transform_assemblies_basic():
    results = transform_assemblies([SAMPLE_ASSEMBLY_EVENT])
    assert len(results) == 1

    a = results[0]
    assert a["id"] == "0x62f5797becab1d2448c0e7eb4654760a026f1796cfa7e0c75047e9dc71346140"
    assert a["type"] == "91978"
    assert a["owner"]["address"] == "0xabc123"
    assert a["solarSystem"]["id"] == ""
    assert a["state"] == "online"


def test_transform_assemblies_empty():
    assert transform_assemblies([]) == []


# --- Transform gate jumps ---


SAMPLE_JUMP_EVENT = {
    "contents": {
        "json": {
            "key": {"item_id": "gate-001", "tenant": "stillness"},
            "character_id": {"item_id": "char-42", "tenant": "stillness"},
            "solar_system_id": {"item_id": "30013496", "tenant": "stillness"},
            "direction": "outbound",
        }
    },
    "sender": {"address": "0xsender"},
    "timestamp": "2026-03-12T20:00:00.000Z",
    "sequenceNumber": 5,
}


def test_transform_gate_jumps_basic():
    results = transform_gate_jumps([SAMPLE_JUMP_EVENT])
    assert len(results) == 1

    j = results[0]
    assert j["id"] == "gate-001"
    assert j["characterId"] == "char-42"
    assert j["solarSystemId"] == "30013496"
    assert j["direction"] == "outbound"
    assert j["timestamp"] > 0


def test_transform_gate_jumps_empty():
    assert transform_gate_jumps([]) == []


# --- SuiGraphQLPoller ---


def test_poller_initial_cursors():
    poller = SuiGraphQLPoller()
    assert poller.cursors["killmail"] is None
    assert poller.cursors["character"] is None
    assert poller.cursors["assembly"] is None
    assert poller.cursors["jump"] is None


@pytest.mark.asyncio
async def test_poller_poll_killmails(monkeypatch):
    """Test that poller calls fetch_events and transforms results."""
    poller = SuiGraphQLPoller()

    async def mock_fetch(client, event_type, max_pages=10, page_size=50, after_cursor=None):
        return [SAMPLE_KILLMAIL_EVENT], "cursor123"

    monkeypatch.setattr("backend.ingestion.sui_graphql.fetch_events", mock_fetch)

    import httpx

    async with httpx.AsyncClient() as client:
        results = await poller.poll_killmails(client)

    assert len(results) == 1
    assert results[0]["id"] == "252"
    assert poller.cursors["killmail"] == "cursor123"


@pytest.mark.asyncio
async def test_poller_poll_characters(monkeypatch):
    poller = SuiGraphQLPoller()

    async def mock_fetch(client, event_type, max_pages=10, page_size=50, after_cursor=None):
        return [SAMPLE_CHARACTER_EVENT], "char_cursor"

    monkeypatch.setattr("backend.ingestion.sui_graphql.fetch_events", mock_fetch)

    import httpx

    async with httpx.AsyncClient() as client:
        results = await poller.poll_characters(client)

    assert len(results) == 1
    assert results[0]["id"] == "2112077429"
    assert poller.cursors["character"] == "char_cursor"


@pytest.mark.asyncio
async def test_poller_cursor_persists(monkeypatch):
    """Test that cursor is passed on subsequent calls."""
    poller = SuiGraphQLPoller()
    poller.cursors["killmail"] = "prev_cursor"

    captured_cursors = []

    async def mock_fetch(client, event_type, max_pages=10, page_size=50, after_cursor=None):
        captured_cursors.append(after_cursor)
        return [], "new_cursor"

    monkeypatch.setattr("backend.ingestion.sui_graphql.fetch_events", mock_fetch)

    import httpx

    async with httpx.AsyncClient() as client:
        await poller.poll_killmails(client)

    assert captured_cursors == ["prev_cursor"]
    assert poller.cursors["killmail"] == "new_cursor"


# --- Bulk character name resolution ---


SAMPLE_CHARACTER_OBJECT = {
    "asMoveObject": {
        "contents": {
            "json": {
                "character_address": "0xc4b7d17877d2d6c64423e90a6df24a1a5445d0bf0415a263eb97e069c3120946",
                "key": {"item_id": "2112077429", "tenant": "stillness"},
                "tribe_id": 1000167,
                "metadata": {
                    "assembly_id": "0x978a73b0",
                    "name": "Bhal Jhor",
                    "description": "",
                    "url": "",
                },
            }
        }
    }
}


@pytest.mark.asyncio
async def test_fetch_all_character_names(monkeypatch):
    """Test bulk character name resolution from Sui objects."""
    from unittest.mock import AsyncMock, MagicMock

    import httpx

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "objects": {
                "nodes": [SAMPLE_CHARACTER_OBJECT],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    results = await fetch_all_character_names(mock_client, max_pages=1)

    assert len(results) == 1
    assert results[0]["name"] == "Bhal Jhor"
    assert (
        results[0]["address"]
        == "0xc4b7d17877d2d6c64423e90a6df24a1a5445d0bf0415a263eb97e069c3120946"
    )
    assert results[0]["id"] == "2112077429"
    assert results[0]["_tribe_id"] == 1000167


@pytest.mark.asyncio
async def test_bootstrap_only_runs_once(monkeypatch):
    """Test that bootstrap_character_names only runs once."""
    poller = SuiGraphQLPoller()

    async def mock_fetch_names(client, max_pages=30, page_size=50):
        return [{"address": "0xabc", "name": "Test", "id": "1", "_tribe_id": 0}]

    monkeypatch.setattr(
        "backend.ingestion.sui_graphql.fetch_all_character_names",
        mock_fetch_names,
    )

    import httpx

    async with httpx.AsyncClient() as client:
        first = await poller.bootstrap_character_names(client)
        second = await poller.bootstrap_character_names(client)

    assert len(first) == 1
    assert len(second) == 0  # Already bootstrapped
    assert poller.names_bootstrapped is True
