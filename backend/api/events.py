"""Server-Sent Events (SSE) for real-time updates.

Provides a streaming endpoint that pushes live events to connected
clients: kill feed, watch alerts, feed items, and system status.

Architecture:
  - EventBus singleton manages subscriber queues
  - Producers (poller, oracle, story_feed) call publish()
  - Each SSE client gets its own asyncio.Queue
  - Heartbeat every 30s keeps connections alive
"""

import asyncio
import json
import time
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.core.logger import get_logger

logger = get_logger("events")

router = APIRouter()


class EventBus:
    """Pub/sub event bus for SSE broadcasting."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Add a new subscriber. Returns their personal queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber."""
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def publish(self, event_type: str, data: dict) -> None:
        """Broadcast an event to all subscribers. Non-blocking."""
        payload = {"type": event_type, "data": data, "timestamp": int(time.time())}
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.append(q)
        # Remove dead subscribers (queue full = client too slow)
        for q in dead:
            self.unsubscribe(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Singleton event bus
event_bus = EventBus()

HEARTBEAT_INTERVAL = 30  # seconds


async def _event_stream(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Generate SSE events from a subscriber queue."""
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            except TimeoutError:
                # Send heartbeat to keep connection alive
                yield f": heartbeat {int(time.time())}\n\n"
    except asyncio.CancelledError:
        return


@router.get("/events")
async def sse_endpoint(request: Request):
    """SSE endpoint for real-time event streaming.

    Events:
      - kill: New killmail ingested
      - alert: Watch alert triggered
      - feed: New story feed item
      - status: System status update
    """
    queue = event_bus.subscribe()

    async def generate():
        try:
            async for chunk in _event_stream(queue):
                yield chunk
        finally:
            event_bus.unsubscribe(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/events/status")
async def sse_status():
    """Current SSE connection status."""
    return {
        "subscribers": event_bus.subscriber_count,
        "timestamp": int(time.time()),
    }
