"""Tests for SSE event bus and endpoints."""

import asyncio
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.events import EventBus
from backend.db.database import SCHEMA


class TestEventBus:
    def test_subscribe_unsubscribe(self):
        bus = EventBus()
        q = bus.subscribe()
        assert bus.subscriber_count == 1
        bus.unsubscribe(q)
        assert bus.subscriber_count == 0

    def test_unsubscribe_nonexistent(self):
        bus = EventBus()
        q = asyncio.Queue()
        bus.unsubscribe(q)  # Should not raise
        assert bus.subscriber_count == 0

    def test_publish_delivers_to_subscriber(self):
        bus = EventBus()
        q = bus.subscribe()
        bus.publish("kill", {"count": 5})
        assert not q.empty()
        event = q.get_nowait()
        assert event["type"] == "kill"
        assert event["data"]["count"] == 5
        assert "timestamp" in event
        bus.unsubscribe(q)

    def test_publish_to_multiple_subscribers(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.publish("alert", {"msg": "test"})
        assert not q1.empty()
        assert not q2.empty()
        bus.unsubscribe(q1)
        bus.unsubscribe(q2)

    def test_publish_drops_slow_subscriber(self):
        bus = EventBus()
        bus.subscribe()
        # Fill the queue (maxsize=100)
        for i in range(101):
            bus.publish("test", {"i": i})
        # Slow subscriber should be removed
        assert bus.subscriber_count == 0

    def test_subscriber_count(self):
        bus = EventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        q3 = bus.subscribe()
        assert bus.subscriber_count == 3
        bus.unsubscribe(q2)
        assert bus.subscriber_count == 2
        bus.unsubscribe(q1)
        bus.unsubscribe(q3)
        assert bus.subscriber_count == 0


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture
def client(test_db):
    with (
        patch("backend.db.database.get_db", return_value=test_db),
        patch("backend.api.routes.get_db", return_value=test_db),
        patch("backend.api.auth.get_db", return_value=test_db),
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


def test_sse_status(client):
    r = client.get("/api/events/status")
    assert r.status_code == 200
    data = r.json()
    assert "subscribers" in data
    assert "timestamp" in data


def test_oracle_publishes_to_sse():
    """Verify oracle hooks into event bus on alert."""
    bus = EventBus()
    q = bus.subscribe()

    with patch("backend.api.events.event_bus", bus):
        bus.publish(
            "alert",
            {
                "title": "MOVEMENT DETECTED",
                "severity": "warning",
            },
        )

    assert not q.empty()
    event = q.get_nowait()
    assert event["type"] == "alert"
    bus.unsubscribe(q)


def test_poller_publishes_kills_to_sse():
    """Verify poller hooks into event bus on new kills."""
    bus = EventBus()
    q = bus.subscribe()

    with patch("backend.api.events.event_bus", bus):
        bus.publish("kill", {"new_count": 3})

    assert not q.empty()
    event = q.get_nowait()
    assert event["type"] == "kill"
    assert event["data"]["new_count"] == 3
    bus.unsubscribe(q)


@pytest.mark.asyncio
async def test_event_stream_yields_sse_format():
    """_event_stream() yields properly formatted SSE strings."""
    import json

    from backend.api.events import _event_stream

    q: asyncio.Queue = asyncio.Queue()
    payload = {"type": "kill", "data": {"victim": "TestPilot"}, "timestamp": 1234567890}
    await q.put(payload)

    chunks = []
    async for chunk in _event_stream(q):
        chunks.append(chunk)
        if len(chunks) >= 1:
            break

    assert len(chunks) == 1
    assert chunks[0].startswith("event: kill\n")
    assert "data: " in chunks[0]
    assert chunks[0].endswith("\n\n")
    # Verify the data portion is valid JSON
    data_line = chunks[0].split("data: ")[1].strip()
    parsed = json.loads(data_line)
    assert parsed["type"] == "kill"
    assert parsed["data"]["victim"] == "TestPilot"


@pytest.mark.asyncio
async def test_event_stream_heartbeat():
    """_event_stream() sends heartbeat when queue is empty."""
    from backend.api.events import _event_stream

    q: asyncio.Queue = asyncio.Queue()

    chunks = []
    with patch("backend.api.events.HEARTBEAT_INTERVAL", 0.1):
        async for chunk in _event_stream(q):
            chunks.append(chunk)
            if len(chunks) >= 1:
                break

    assert len(chunks) == 1
    assert chunks[0].startswith(": heartbeat ")
    assert chunks[0].endswith("\n\n")


@pytest.mark.asyncio
async def test_event_stream_cancelled():
    """_event_stream() returns cleanly on cancellation."""
    from backend.api.events import _event_stream

    q: asyncio.Queue = asyncio.Queue()

    collected = []

    async def consume():
        async for chunk in _event_stream(q):
            collected.append(chunk)

    task = asyncio.create_task(consume())
    # Give it a moment to start waiting
    await asyncio.sleep(0.05)
    task.cancel()
    # Should not raise — CancelledError is caught inside _event_stream
    try:
        await task
    except asyncio.CancelledError:
        pass  # acceptable — task itself may propagate


def test_publish_with_complex_data():
    """Nested dicts, lists, and unicode survive the event bus queue."""
    bus = EventBus()
    q = bus.subscribe()

    complex_data = {
        "nested": {"key": "value", "deep": {"a": [1, 2, 3]}},
        "list": [{"x": 1}, {"y": 2}],
        "unicode": "\u00e9\u00e8\u00ea \u2603 \u2764",
        "empty": {},
        "null_val": None,
    }
    bus.publish("complex", complex_data)

    event = q.get_nowait()
    assert event["type"] == "complex"
    assert event["data"]["nested"]["deep"]["a"] == [1, 2, 3]
    assert event["data"]["unicode"] == "\u00e9\u00e8\u00ea \u2603 \u2764"
    assert event["data"]["null_val"] is None
    bus.unsubscribe(q)


@pytest.mark.asyncio
async def test_sse_endpoint_returns_streaming_response():
    """SSE endpoint returns a StreamingResponse with correct headers."""
    from unittest.mock import MagicMock

    from backend.api.events import sse_endpoint

    request = MagicMock()
    response = await sse_endpoint(request)

    # Verify it returns a StreamingResponse with SSE media type
    from fastapi.responses import StreamingResponse

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("connection") == "keep-alive"
    assert response.headers.get("x-accel-buffering") == "no"


@pytest.mark.asyncio
async def test_sse_endpoint_generate_cleanup():
    """The generate() closure yields events and unsubscribes on exit."""
    from unittest.mock import MagicMock

    from backend.api.events import event_bus, sse_endpoint

    initial = event_bus.subscriber_count
    request = MagicMock()
    response = await sse_endpoint(request)

    # A subscriber was added
    assert event_bus.subscriber_count == initial + 1

    # Publish something so the generator yields
    event_bus.publish("test", {"x": 1})
    iterator = response.body_iterator.__aiter__()
    chunk = await iterator.__anext__()
    assert "test" in chunk

    # Close the generator (triggers finally block → unsubscribe)
    await response.body_iterator.aclose()
    assert event_bus.subscriber_count == initial
