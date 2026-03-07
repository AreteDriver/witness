"""World API poller — the sensory system. NEVER LET THIS CRASH."""

import asyncio
import json
import time
from datetime import datetime

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("poller")

# API returns paginated results; fetch all pages up to this limit
MAX_PAGES = 10
PAGE_SIZE = 100


def _parse_iso_time(iso_str: str) -> int:
    """Parse ISO 8601 timestamp to unix epoch. Returns current time on failure."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return int(time.time())


async def poll_endpoint(client: httpx.AsyncClient, endpoint: str) -> list[dict]:
    """Single poll with pagination. Returns empty list on ANY failure."""
    all_items: list[dict] = []
    offset = 0

    for _ in range(MAX_PAGES):
        url = f"{settings.WORLD_API_BASE}/{endpoint}"
        params = {"limit": PAGE_SIZE, "offset": offset}
        try:
            r = await client.get(url, params=params, timeout=settings.POLL_TIMEOUT_SECONDS)
            r.raise_for_status()
            data = r.json()

            if isinstance(data, list):
                all_items.extend(data)
                break  # No pagination info
            if isinstance(data, dict) and "data" in data:
                items = data["data"]
                if isinstance(items, list):
                    all_items.extend(items)
                else:
                    all_items.append(items)
                # Check if more pages
                meta = data.get("metadata", {})
                total = meta.get("total", 0)
                if offset + PAGE_SIZE >= total:
                    break
                offset += PAGE_SIZE
            else:
                if data:
                    all_items.append(data)
                break
        except httpx.TimeoutException:
            logger.warning("Timeout: %s (offset=%d)", endpoint, offset)
            break
        except httpx.HTTPStatusError as e:
            logger.error("HTTP %d: %s", e.response.status_code, endpoint)
            break
        except Exception as e:
            logger.error("Poll error (%s): %s", endpoint, e)
            break

    return all_items


def _ingest_killmails(db, killmails: list[dict]) -> int:
    """Ingest killmails from v2 API. Returns count of new records."""
    count = 0
    for raw in killmails:
        killmail_id = raw.get("id") or raw.get("killmail_id") or raw.get("killMailId")
        if not killmail_id:
            continue

        victim = raw.get("victim", {})
        killer = raw.get("killer", {})

        # v2 API: single killer, not attackers array
        attackers = raw.get("attackers", [])
        if not attackers and killer:
            attackers = [killer]

        timestamp = raw.get("timestamp", 0)
        if isinstance(timestamp, str):
            timestamp = _parse_iso_time(timestamp)
        time_field = raw.get("time", "")
        if time_field and not timestamp:
            timestamp = _parse_iso_time(time_field)
        if not timestamp:
            timestamp = int(time.time())

        try:
            db.execute(
                """INSERT OR IGNORE INTO killmails
                (killmail_id, victim_character_id, victim_name,
                 victim_corp_id,
                 attacker_character_ids, attacker_corp_ids,
                 solar_system_id, x, y, z, timestamp, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(killmail_id),
                    str(victim.get("address") or victim.get("characterId") or victim.get("id", "")),
                    str(victim.get("name", "")),
                    str(victim.get("corporationId", "")),
                    json.dumps(attackers),
                    json.dumps(
                        list({a.get("corporationId") for a in attackers if a.get("corporationId")})
                    ),
                    str(raw.get("solarSystemId", "")),
                    raw.get("position", {}).get("x"),
                    raw.get("position", {}).get("y"),
                    raw.get("position", {}).get("z"),
                    timestamp,
                    json.dumps(raw),
                ),
            )
            count += 1
        except Exception as e:
            logger.error("Killmail ingest error: %s", e)
    return count


def _ingest_smart_assemblies(db, assemblies: list[dict]) -> int:
    """Ingest smart assemblies (gates, turrets, etc). Returns count."""
    count = 0
    for raw in assemblies:
        assembly_id = raw.get("id")
        if not assembly_id:
            continue

        solar = raw.get("solarSystem", {})
        owner = raw.get("owner", {})
        location = solar.get("location", {})

        # EVE coordinates can be huge (>2^63) — store as float
        def _safe_coord(val):
            try:
                return float(val) if val is not None else None
            except (TypeError, ValueError):
                return None

        try:
            db.execute(
                """INSERT OR IGNORE INTO smart_assemblies
                (assembly_id, assembly_type, name, state,
                 solar_system_id, solar_system_name,
                 owner_address, owner_name,
                 x, y, z, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(assembly_id),
                    raw.get("type", ""),
                    raw.get("name", ""),
                    raw.get("state", ""),
                    str(solar.get("id", "")),
                    solar.get("name", ""),
                    str(owner.get("address", "")),
                    owner.get("name", ""),
                    _safe_coord(location.get("x")),
                    _safe_coord(location.get("y")),
                    _safe_coord(location.get("z")),
                    json.dumps(raw),
                ),
            )
            count += 1
        except Exception as e:
            logger.error("Assembly ingest error: %s", e)
    return count


def _ingest_gate_events(db, events: list[dict]) -> int:
    """Ingest gate transit events. Returns count of new records."""
    count = 0
    for raw in events:
        gate_id = raw.get("id") or raw.get("gateId") or raw.get("smartGateId")
        if not gate_id:
            continue

        timestamp = raw.get("timestamp", 0)
        if isinstance(timestamp, str):
            timestamp = _parse_iso_time(timestamp)
        if not timestamp:
            timestamp = int(time.time())

        try:
            db.execute(
                """INSERT INTO gate_events
                (gate_id, gate_name, character_id, corp_id,
                 solar_system_id, direction, timestamp, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(gate_id),
                    raw.get("name", ""),
                    str(raw.get("characterId", "")),
                    str(raw.get("corporationId", "")),
                    str(raw.get("solarSystemId", "")),
                    raw.get("direction", ""),
                    timestamp,
                    json.dumps(raw),
                ),
            )
            count += 1
        except Exception as e:
            logger.error("Gate event ingest error: %s", e)
    return count


def _update_entities(db) -> None:
    """Rebuild entity stats from event tables. Lightweight — runs each cycle."""
    try:
        # Characters from killmails (victims)
        db.execute("""
            INSERT INTO entities (entity_id, entity_type, display_name,
                first_seen, last_seen, death_count, event_count)
            SELECT victim_character_id, 'character',
                   MAX(victim_name),
                   MIN(timestamp), MAX(timestamp), COUNT(*), COUNT(*)
            FROM killmails WHERE victim_character_id != ''
            GROUP BY victim_character_id
            ON CONFLICT(entity_id) DO UPDATE SET
                last_seen = MAX(entities.last_seen, excluded.last_seen),
                display_name = COALESCE(
                    NULLIF(excluded.display_name, ''),
                    entities.display_name
                ),
                death_count = excluded.death_count,
                event_count = entities.event_count + excluded.event_count,
                updated_at = unixepoch()
        """)

        # Characters from gate events
        db.execute("""
            INSERT INTO entities (entity_id, entity_type,
                first_seen, last_seen, gate_count, event_count)
            SELECT character_id, 'character',
                   MIN(timestamp), MAX(timestamp), COUNT(*), COUNT(*)
            FROM gate_events WHERE character_id != ''
            GROUP BY character_id
            ON CONFLICT(entity_id) DO UPDATE SET
                last_seen = MAX(entities.last_seen, excluded.last_seen),
                gate_count = excluded.gate_count,
                event_count = entities.event_count + excluded.event_count,
                updated_at = unixepoch()
        """)

        # Gates/assemblies as entities
        db.execute("""
            INSERT INTO entities (entity_id, entity_type, display_name,
                first_seen, last_seen, event_count)
            SELECT assembly_id, assembly_type,
                   COALESCE(NULLIF(name, ''), owner_name),
                   unixepoch(), unixepoch(), 1
            FROM smart_assemblies WHERE assembly_id != ''
            GROUP BY assembly_id
            ON CONFLICT(entity_id) DO UPDATE SET
                last_seen = unixepoch(),
                display_name = COALESCE(
                    NULLIF(excluded.display_name, ''),
                    entities.display_name
                ),
                updated_at = unixepoch()
        """)
    except Exception as e:
        logger.error("Entity update error: %s", e)


async def run_poller() -> None:
    """Main ingestion loop. Runs forever. Never raises."""
    logger.info("Poller starting — base: %s", settings.WORLD_API_BASE)
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Poll all endpoints in parallel
                kill_task = poll_endpoint(client, "v2/killmails")
                assembly_task = poll_endpoint(client, "v2/smartassemblies")
                raw_kills, raw_assemblies = await asyncio.gather(kill_task, assembly_task)

                db = get_db()
                new_kills = _ingest_killmails(db, raw_kills)
                new_assemblies = _ingest_smart_assemblies(db, raw_assemblies)

                if new_kills or new_assemblies:
                    _update_entities(db)
                    db.commit()
                    logger.info(
                        "Ingested: %d killmails, %d assemblies",
                        new_kills,
                        new_assemblies,
                    )
                else:
                    db.commit()

            except Exception as e:
                logger.critical("Poller loop error (continuing): %s", e)

            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
