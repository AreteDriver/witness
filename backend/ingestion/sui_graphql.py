"""Sui GraphQL data source — replaces dead World API with live on-chain events.

CCP migrated all dynamic data to Sui GraphQL (March 11, 2026).
This module queries events from the Stillness world contract and transforms
them into the same dict shapes the existing _ingest_* functions expect.
"""

import time
from datetime import datetime

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("sui_graphql")

# Sui GraphQL endpoint (testnet — where Stillness lives)
SUI_GRAPHQL_URL = "https://graphql.testnet.sui.io/graphql"

# Stillness world-contract package ID
STILLNESS_PKG = (
    "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c"
)

# Event type templates
EVENT_TYPES = {
    "killmail": f"{STILLNESS_PKG}::killmail::KillmailCreatedEvent",
    "character": f"{STILLNESS_PKG}::character::CharacterCreatedEvent",
    "assembly": f"{STILLNESS_PKG}::assembly::AssemblyCreatedEvent",
    "jump": f"{STILLNESS_PKG}::gate::JumpEvent",
    "location": f"{STILLNESS_PKG}::location::LocationRevealedEvent",
}

# GraphQL query template for paginated event fetching
EVENTS_QUERY = """
query FetchEvents($eventType: String!, $first: Int!, $after: String) {
  events(
    filter: { type: $eventType }
    first: $first
    after: $after
  ) {
    nodes {
      contents { json }
      sender { address }
      timestamp
      sequenceNumber
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def _parse_sui_timestamp(ts_str: str) -> int:
    """Parse Sui ISO timestamp (e.g. '2026-03-12T18:56:26.699Z') to unix epoch."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return int(time.time())


def _item_id(obj: dict) -> str:
    """Extract item_id from a Sui InGameId struct like {item_id: '123', tenant: 'stillness'}."""
    if isinstance(obj, dict):
        return str(obj.get("item_id", ""))
    return str(obj)


async def fetch_events(
    client: httpx.AsyncClient,
    event_type: str,
    max_pages: int = 10,
    page_size: int = 50,
    after_cursor: str | None = None,
) -> tuple[list[dict], str | None]:
    """Fetch paginated events from Sui GraphQL.

    Returns (events_list, last_cursor) where last_cursor can be stored
    for incremental polling on next cycle.
    """
    all_events: list[dict] = []
    cursor = after_cursor

    for _ in range(max_pages):
        variables = {
            "eventType": event_type,
            "first": page_size,
        }
        if cursor:
            variables["after"] = cursor

        try:
            r = await client.post(
                SUI_GRAPHQL_URL,
                json={"query": EVENTS_QUERY, "variables": variables},
                timeout=settings.POLL_TIMEOUT_SECONDS,
            )
            r.raise_for_status()
            data = r.json()

            if "errors" in data:
                logger.error("Sui GraphQL errors: %s", data["errors"])
                break

            events_data = data.get("data", {}).get("events", {})
            nodes = events_data.get("nodes", [])
            all_events.extend(nodes)

            page_info = events_data.get("pageInfo", {})
            cursor = page_info.get("endCursor")
            if not page_info.get("hasNextPage"):
                break

        except httpx.TimeoutException:
            logger.warning("Sui GraphQL timeout fetching %s", event_type)
            break
        except httpx.HTTPStatusError as e:
            logger.error("Sui GraphQL HTTP %d", e.response.status_code)
            break
        except Exception as e:
            logger.error("Sui GraphQL error: %s", e)
            break

    return all_events, cursor


def transform_killmails(events: list[dict]) -> list[dict]:
    """Transform Sui KillmailCreatedEvent → World API killmail dict shape.

    World API shape expected by _ingest_killmails:
    {
        "id": str,
        "victim": {"address": str, "name": ""},
        "killer": {"address": str, "name": ""},
        "attackers": [{"address": str}],
        "solarSystemId": str,
        "timestamp": int,
    }
    """
    results = []
    for event in events:
        json_data = event.get("contents", {}).get("json", {})
        if not json_data:
            continue

        killmail_id = _item_id(json_data.get("key", {}))
        victim_id = _item_id(json_data.get("victim_id", {}))
        killer_id = _item_id(json_data.get("killer_id", {}))
        solar_system_id = _item_id(json_data.get("solar_system_id", {}))

        # kill_timestamp is unix epoch as string
        timestamp = json_data.get("kill_timestamp", "0")
        try:
            timestamp = int(timestamp)
        except (ValueError, TypeError):
            timestamp = _parse_sui_timestamp(event.get("timestamp", ""))

        killer = {"address": killer_id, "name": "", "characterId": killer_id}
        victim = {"address": victim_id, "name": "", "characterId": victim_id}

        results.append({
            "id": killmail_id,
            "killmail_id": killmail_id,
            "victim": victim,
            "killer": killer,
            "attackers": [killer],
            "solarSystemId": solar_system_id,
            "timestamp": timestamp,
            "loss_type": json_data.get("loss_type", {}).get("@variant", ""),
            "reported_by": _item_id(
                json_data.get("reported_by_character_id", {})
            ),
            "_sui_sender": event.get("sender", {}).get("address", ""),
            "_sui_timestamp": event.get("timestamp", ""),
        })

    return results


def transform_characters(events: list[dict]) -> list[dict]:
    """Transform Sui CharacterCreatedEvent → World API smartcharacters dict shape.

    World API shape expected by _ingest_smart_characters:
    {
        "address": str,  # character_address (wallet)
        "name": str,     # empty from events, enriched later
        "id": str,       # in-game character ID (item_id)
    }
    """
    results = []
    for event in events:
        json_data = event.get("contents", {}).get("json", {})
        if not json_data:
            continue

        character_address = json_data.get("character_address", "")
        character_item_id = _item_id(json_data.get("key", {}))
        tribe_id = json_data.get("tribe_id", 0)

        results.append({
            "address": character_address,
            "name": "",  # Not available in creation event
            "id": character_item_id,
            "_sui_character_id": json_data.get("character_id", ""),
            "_tribe_id": tribe_id,
        })

    return results


def transform_assemblies(events: list[dict]) -> list[dict]:
    """Transform Sui AssemblyCreatedEvent → World API smartassemblies dict shape.

    World API shape expected by _ingest_smart_assemblies:
    {
        "id": str,
        "type": str,
        "name": str,
        "state": str,
        "solarSystem": {"id": str, "name": str, "location": {"x": None, "y": None, "z": None}},
        "owner": {"address": str, "name": str},
    }
    """
    results = []
    for event in events:
        json_data = event.get("contents", {}).get("json", {})
        if not json_data:
            continue

        assembly_id = json_data.get("assembly_id", "")
        assembly_item_id = _item_id(json_data.get("assembly_key", {}))
        type_id = json_data.get("type_id", "")

        results.append({
            "id": assembly_id or assembly_item_id,
            "type": type_id,
            "name": "",
            "state": "online",
            "solarSystem": {
                "id": "",
                "name": "",
                "location": {"x": None, "y": None, "z": None},
            },
            "owner": {
                "address": event.get("sender", {}).get("address", ""),
                "name": "",
            },
        })

    return results


def transform_gate_jumps(events: list[dict]) -> list[dict]:
    """Transform Sui JumpEvent → World API gate_events dict shape.

    World API shape expected by _ingest_gate_events:
    {
        "id": str,  # gate ID
        "name": str,
        "characterId": str,
        "corporationId": str,
        "solarSystemId": str,
        "direction": str,
        "timestamp": int,
    }
    """
    results = []
    for event in events:
        json_data = event.get("contents", {}).get("json", {})
        if not json_data:
            continue

        gate_id = _item_id(json_data.get("gate_id", json_data.get("key", {})))
        character_id = _item_id(
            json_data.get("character_id", json_data.get("jumper_id", {}))
        )
        solar_system_id = _item_id(json_data.get("solar_system_id", {}))
        timestamp = _parse_sui_timestamp(event.get("timestamp", ""))

        results.append({
            "id": gate_id,
            "name": "",
            "characterId": character_id,
            "corporationId": "",
            "solarSystemId": solar_system_id,
            "direction": json_data.get("direction", ""),
            "timestamp": timestamp,
        })

    return results


def transform_location_reveals(events: list[dict]) -> list[dict]:
    """Transform Sui LocationRevealedEvent → assembly location updates.

    Returns list of dicts with assembly_id, solar_system_id, x, y, z.
    Used to backfill location data on assemblies (not available in creation events).
    """
    results = []
    for event in events:
        json_data = event.get("contents", {}).get("json", {})
        if not json_data:
            continue

        assembly_id = json_data.get("assembly_id", "")
        solarsystem = str(json_data.get("solarsystem", ""))
        x = json_data.get("x", "")
        y = json_data.get("y", "")
        z = json_data.get("z", "")

        if assembly_id and solarsystem:
            results.append({
                "assembly_id": assembly_id,
                "solar_system_id": solarsystem,
                "x": x,
                "y": y,
                "z": z,
            })

    return results


# GraphQL query for bulk Character objects (name resolution)
CHARACTERS_QUERY = """
query FetchCharacters($type: String!, $first: Int!, $after: String) {
  objects(
    filter: { type: $type }
    first: $first
    after: $after
  ) {
    nodes {
      asMoveObject {
        contents { json }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

CHARACTER_TYPE = f"{STILLNESS_PKG}::character::Character"


async def fetch_all_character_names(
    client: httpx.AsyncClient,
    max_pages: int = 30,
    page_size: int = 50,
) -> list[dict]:
    """Bulk fetch all Character objects from Sui to resolve names.

    Returns list of World API-compatible smartcharacter dicts with names populated
    from on-chain metadata.name field. ~1,300 characters, ~27 pages.
    """
    all_chars: list[dict] = []
    cursor: str | None = None

    for page in range(max_pages):
        variables: dict = {
            "type": CHARACTER_TYPE,
            "first": page_size,
        }
        if cursor:
            variables["after"] = cursor

        try:
            r = await client.post(
                SUI_GRAPHQL_URL,
                json={"query": CHARACTERS_QUERY, "variables": variables},
                timeout=15.0,  # Longer timeout for bulk queries
            )
            r.raise_for_status()
            data = r.json()

            if "errors" in data:
                logger.error(
                    "Sui character fetch errors (page %d): %s",
                    page,
                    data["errors"],
                )
                break

            objects_data = data.get("data", {}).get("objects", {})
            nodes = objects_data.get("nodes", [])

            for node in nodes:
                contents = (
                    node.get("asMoveObject", {})
                    .get("contents", {})
                    .get("json", {})
                )
                if not contents:
                    continue

                character_address = contents.get("character_address", "")
                metadata = contents.get("metadata", {})
                name = ""
                if isinstance(metadata, dict):
                    name = metadata.get("name", "")
                character_item_id = _item_id(contents.get("key", {}))
                tribe_id = contents.get("tribe_id", 0)

                all_chars.append({
                    "address": character_address,
                    "name": name,
                    "id": character_item_id,
                    "_tribe_id": tribe_id,
                })

            page_info = objects_data.get("pageInfo", {})
            cursor = page_info.get("endCursor")
            if not page_info.get("hasNextPage"):
                break

        except httpx.TimeoutException:
            logger.warning(
                "Sui character bulk fetch timeout (page %d)", page
            )
            break
        except Exception as e:
            logger.error("Sui character bulk fetch error: %s", e)
            break

    logger.info("Fetched %d character names from Sui objects", len(all_chars))
    return all_chars


class SuiGraphQLPoller:
    """Stateful poller that tracks cursors for incremental fetching."""

    def __init__(self) -> None:
        self.cursors: dict[str, str | None] = {
            "killmail": None,
            "character": None,
            "assembly": None,
            "jump": None,
            "location": None,
        }
        self.names_bootstrapped = False

    async def poll_killmails(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """Fetch new killmails since last cursor."""
        events, cursor = await fetch_events(
            client,
            EVENT_TYPES["killmail"],
            after_cursor=self.cursors["killmail"],
        )
        if cursor:
            self.cursors["killmail"] = cursor
        return transform_killmails(events)

    async def poll_characters(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """Fetch new character creation events since last cursor."""
        events, cursor = await fetch_events(
            client,
            EVENT_TYPES["character"],
            after_cursor=self.cursors["character"],
        )
        if cursor:
            self.cursors["character"] = cursor
        return transform_characters(events)

    async def poll_assemblies(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """Fetch new assembly creation events since last cursor."""
        events, cursor = await fetch_events(
            client,
            EVENT_TYPES["assembly"],
            after_cursor=self.cursors["assembly"],
        )
        if cursor:
            self.cursors["assembly"] = cursor
        return transform_assemblies(events)

    async def poll_gate_jumps(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """Fetch new gate jump events since last cursor."""
        events, cursor = await fetch_events(
            client,
            EVENT_TYPES["jump"],
            after_cursor=self.cursors["jump"],
        )
        if cursor:
            self.cursors["jump"] = cursor
        return transform_gate_jumps(events)

    async def poll_locations(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """Fetch new location reveal events since last cursor."""
        events, cursor = await fetch_events(
            client,
            EVENT_TYPES["location"],
            after_cursor=self.cursors["location"],
        )
        if cursor:
            self.cursors["location"] = cursor
        return transform_location_reveals(events)

    async def bootstrap_character_names(
        self, client: httpx.AsyncClient
    ) -> list[dict]:
        """One-time bulk fetch of all character names from on-chain objects.

        Returns smartcharacter-shaped dicts with names populated.
        Should be called once on startup, then incremental via poll_characters.
        """
        if self.names_bootstrapped:
            return []
        chars = await fetch_all_character_names(client)
        self.names_bootstrapped = True
        return chars
