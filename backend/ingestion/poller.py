"""World API poller — the sensory system. NEVER LET THIS CRASH.

Data source: Sui GraphQL (primary) with World API fallback for static data.
CCP migrated all dynamic data to Sui on March 11, 2026.
"""

import asyncio
import json
import time
from datetime import datetime

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db
from backend.ingestion.sui_graphql import SuiGraphQLPoller

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


async def bootstrap_system_names(client: httpx.AsyncClient) -> int:
    """Fetch all solar system names from World API static endpoint.

    Populates the solar_systems lookup table. Only fetches if table is empty.
    Returns count of systems loaded.
    """
    db = get_db()
    existing = db.execute("SELECT COUNT(*) FROM solar_systems").fetchone()[0]
    if existing > 0:
        logger.info("Solar systems already loaded (%d), skipping bootstrap", existing)
        return 0

    base = settings.WORLD_API_STATIC
    all_systems: list[dict] = []
    offset = 0
    page_size = 100
    max_pages = 300  # 24,502 systems / 100 per page

    for _ in range(max_pages):
        try:
            r = await client.get(
                f"{base}/v2/solarsystems",
                params={"limit": page_size, "offset": offset, "format": "json"},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()

            items = data.get("data", []) if isinstance(data, dict) else data
            if not items:
                break
            all_systems.extend(items)
            offset += len(items)

            if len(items) < page_size:
                break
        except Exception as e:
            logger.error("System names fetch error at offset %d: %s", offset, e)
            break

    if all_systems:
        for sys in all_systems:
            sys_id = str(sys.get("id", ""))
            name = sys.get("name", "")
            if sys_id and name:
                db.execute(
                    "INSERT OR IGNORE INTO solar_systems (solar_system_id, name) VALUES (?, ?)",
                    (sys_id, name),
                )
        db.commit()
        logger.info("Bootstrapped %d solar system names from World API", len(all_systems))

    return len(all_systems)


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
            cursor = db.execute(
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
            if cursor.rowcount > 0:
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
            cursor = db.execute(
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
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            logger.error("Assembly ingest error: %s", e)
    return count


def _update_assembly_locations(db, locations: list[dict]) -> int:
    """Update assembly records with location data from LocationRevealedEvent."""
    count = 0
    for loc in locations:
        assembly_id = loc.get("assembly_id", "")
        solar_system_id = loc.get("solar_system_id", "")
        if not assembly_id or not solar_system_id:
            continue

        # Resolve system name from solar_systems table
        name_row = db.execute(
            "SELECT name FROM solar_systems WHERE solar_system_id = ?",
            (solar_system_id,),
        ).fetchone()
        system_name = name_row["name"] if name_row else ""

        def _safe_coord(val):
            try:
                return float(val) if val else None
            except (TypeError, ValueError):
                return None

        try:
            cursor = db.execute(
                """UPDATE smart_assemblies
                   SET solar_system_id = ?, solar_system_name = ?,
                       x = ?, y = ?, z = ?
                   WHERE assembly_id = ? AND (solar_system_id IS NULL OR solar_system_id = '')""",
                (
                    solar_system_id,
                    system_name,
                    _safe_coord(loc.get("x")),
                    _safe_coord(loc.get("y")),
                    _safe_coord(loc.get("z")),
                    assembly_id,
                ),
            )
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            logger.error("Assembly location update error: %s", e)
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


def _ingest_subscriptions(db, assemblies: list[dict]) -> int:
    """Extract subscription events from assembly interactions.

    The World API exposes inventory transfers to Watcher assemblies.
    When a player transfers items to a Watcher assembly, the WatcherSystem
    contract records a subscription on-chain. We mirror that to local DB.
    """
    count = 0
    for raw in assemblies:
        # Look for subscription data embedded in assembly state
        subs = raw.get("subscriptions", [])
        if not subs and raw.get("type") != "SmartStorageUnit":
            continue
        for sub in subs:
            wallet = sub.get("subscriber") or sub.get("address", "")
            tier = sub.get("tier", 0)
            expires_at = sub.get("expiresAt") or sub.get("expires_at", 0)
            if isinstance(expires_at, str):
                expires_at = _parse_iso_time(expires_at)
            if not wallet or not tier:
                continue
            try:
                db.execute(
                    """INSERT INTO watcher_subscriptions
                       (wallet_address, tier, expires_at, created_at)
                       VALUES (?, ?, ?, unixepoch())
                       ON CONFLICT(wallet_address) DO UPDATE SET
                           tier = MAX(watcher_subscriptions.tier, excluded.tier),
                           expires_at = MAX(watcher_subscriptions.expires_at, excluded.expires_at)
                    """,
                    (wallet.lower(), tier, expires_at),
                )
                count += 1
            except Exception as e:
                logger.error("Subscription ingest error: %s", e)
    return count


def _update_entities(db) -> None:
    """Rebuild entity stats from event tables.

    Uses direct assignment (not accumulation) for counts to prevent
    double-counting on repeated polls. Recomputes event_count as sum
    of all activity types at the end.
    """
    try:
        # Characters from killmails (victims) — set death_count directly
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
                updated_at = unixepoch()
        """)

        # Kill counts from attacker data (JSON arrays)
        rows = db.execute(
            "SELECT attacker_character_ids FROM killmails WHERE attacker_character_ids != '[]'"
        ).fetchall()
        kill_counts: dict[str, int] = {}
        for row in rows:
            try:
                attackers = json.loads(row["attacker_character_ids"])
                for a in attackers:
                    addr = a.get("address") or a.get("characterId") or a.get("id", "")
                    if addr:
                        addr = str(addr)
                        kill_counts[addr] = kill_counts.get(addr, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue
        for entity_id, kc in kill_counts.items():
            db.execute(
                """UPDATE entities SET kill_count = ?, updated_at = unixepoch()
                   WHERE entity_id = ?""",
                (kc, entity_id),
            )

        # Characters from gate events — set gate_count directly
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

        # Recompute event_count as sum of all activity types
        db.execute("""
            UPDATE entities SET
                event_count = COALESCE(kill_count, 0)
                            + COALESCE(death_count, 0)
                            + COALESCE(gate_count, 0),
                updated_at = unixepoch()
            WHERE entity_type = 'character'
        """)
    except Exception as e:
        logger.error("Entity update error: %s", e)


def _ingest_orbital_zones(db, zones: list[dict]) -> int:
    """Ingest orbital zone data. Detects feral AI tier changes."""
    count = 0
    for raw in zones:
        zone_id = raw.get("id") or raw.get("zoneId")
        if not zone_id:
            continue

        new_tier = raw.get("feralAiTier") or raw.get("feral_ai_tier") or 0
        location = raw.get("location", raw.get("position", {}))

        try:
            # Check existing tier for evolution detection
            existing = db.execute(
                "SELECT feral_ai_tier FROM orbital_zones WHERE zone_id = ?",
                (str(zone_id),),
            ).fetchone()
            old_tier = existing["feral_ai_tier"] if existing else 0

            db.execute(
                """INSERT INTO orbital_zones
                   (zone_id, name, solar_system_id, x, y, z,
                    feral_ai_tier, last_scanned, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(zone_id) DO UPDATE SET
                       name = COALESCE(excluded.name, orbital_zones.name),
                       feral_ai_tier = excluded.feral_ai_tier,
                       last_scanned = excluded.last_scanned,
                       raw_json = excluded.raw_json""",
                (
                    str(zone_id),
                    raw.get("name", ""),
                    str(raw.get("solarSystemId", "")),
                    location.get("x"),
                    location.get("y"),
                    location.get("z"),
                    new_tier,
                    int(time.time()),
                    json.dumps(raw),
                ),
            )

            # Record evolution event if tier changed
            if existing and new_tier > old_tier:
                severity = "critical" if new_tier >= 3 else "warning"
                db.execute(
                    """INSERT INTO feral_ai_events
                       (zone_id, event_type, old_tier, new_tier, severity, timestamp)
                       VALUES (?, 'evolution', ?, ?, ?, ?)""",
                    (str(zone_id), old_tier, new_tier, severity, int(time.time())),
                )

            count += 1
        except Exception as e:
            logger.error("Zone ingest error: %s", e)
    return count


def _ingest_scans(db, scans: list[dict]) -> int:
    """Ingest void scan results."""
    count = 0
    for raw in scans:
        scan_id = raw.get("id") or raw.get("scanId")
        if not scan_id:
            continue

        timestamp = raw.get("scannedAt") or raw.get("timestamp", 0)
        if isinstance(timestamp, str):
            timestamp = _parse_iso_time(timestamp)

        try:
            db.execute(
                """INSERT OR IGNORE INTO scans
                   (scan_id, zone_id, scanner_id, scanner_name,
                    result_type, result_data, raw_json, scanned_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(scan_id),
                    str(raw.get("zoneId", "")),
                    str(raw.get("scannerId", "")),
                    raw.get("scannerName", ""),
                    raw.get("resultType", "UNKNOWN").upper(),
                    json.dumps(raw.get("resultData", {})),
                    json.dumps(raw),
                    timestamp or int(time.time()),
                ),
            )

            # Update zone last_scanned
            zone_id = raw.get("zoneId")
            if zone_id:
                db.execute(
                    "UPDATE orbital_zones SET last_scanned = ? WHERE zone_id = ?",
                    (int(time.time()), str(zone_id)),
                )

            count += 1
        except Exception as e:
            logger.error("Scan ingest error: %s", e)
    return count


def _ingest_clones(db, clones: list[dict]) -> int:
    """Ingest clone manufacturing data."""
    count = 0
    for raw in clones:
        clone_id = raw.get("id") or raw.get("cloneId")
        if not clone_id:
            continue

        manufactured_at = raw.get("manufacturedAt") or raw.get("timestamp", 0)
        if isinstance(manufactured_at, str):
            manufactured_at = _parse_iso_time(manufactured_at)

        try:
            db.execute(
                """INSERT INTO clones
                   (clone_id, owner_id, owner_name, blueprint_id,
                    status, location_zone_id, raw_json, manufactured_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(clone_id) DO UPDATE SET
                       status = excluded.status,
                       location_zone_id = excluded.location_zone_id,
                       raw_json = excluded.raw_json""",
                (
                    str(clone_id),
                    str(raw.get("ownerId", "")),
                    raw.get("ownerName", ""),
                    str(raw.get("blueprintId", "")),
                    raw.get("status", "active"),
                    str(raw.get("locationZoneId", "")),
                    json.dumps(raw),
                    manufactured_at or int(time.time()),
                ),
            )
            count += 1
        except Exception as e:
            logger.error("Clone ingest error: %s", e)
    return count


def _ingest_crowns(db, crowns: list[dict]) -> int:
    """Ingest crown/identity data."""
    count = 0
    for raw in crowns:
        crown_id = raw.get("id") or raw.get("crownId")
        if not crown_id:
            continue

        equipped_at = raw.get("equippedAt") or raw.get("timestamp", 0)
        if isinstance(equipped_at, str):
            equipped_at = _parse_iso_time(equipped_at)

        try:
            db.execute(
                """INSERT INTO crowns
                   (crown_id, character_id, character_name, crown_type,
                    attributes, chain_tx_id, raw_json, equipped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(crown_id) DO UPDATE SET
                       crown_type = excluded.crown_type,
                       attributes = excluded.attributes,
                       raw_json = excluded.raw_json""",
                (
                    str(crown_id),
                    str(raw.get("characterId", "")),
                    raw.get("characterName", ""),
                    raw.get("crownType", ""),
                    json.dumps(raw.get("attributes", {})),
                    raw.get("chainTxId", ""),
                    json.dumps(raw),
                    equipped_at or int(time.time()),
                ),
            )
            count += 1
        except Exception as e:
            logger.error("Crown ingest error: %s", e)
    return count


def _ingest_smart_characters(db, characters: list[dict]) -> int:
    """Ingest smart character data for entity resolution."""
    count = 0
    for raw in characters:
        address = raw.get("address")
        if not address:
            continue

        # Sui data passes tribe_id as _tribe_id
        tribe_id = raw.get("_tribe_id") or raw.get("tribe_id")

        try:
            cursor = db.execute(
                """INSERT INTO smart_characters
                   (address, name, character_id, tribe_id, raw_json)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(address) DO UPDATE SET
                       name = COALESCE(NULLIF(excluded.name, ''), smart_characters.name),
                       character_id = COALESCE(
                           NULLIF(excluded.character_id, ''),
                           smart_characters.character_id
                       ),
                       tribe_id = COALESCE(
                           NULLIF(excluded.tribe_id, ''),
                           smart_characters.tribe_id
                       ),
                       raw_json = excluded.raw_json,
                       ingested_at = unixepoch()""",
                (
                    str(address),
                    raw.get("name", ""),
                    str(raw.get("id", "")),
                    str(tribe_id) if tribe_id else None,
                    json.dumps(raw),
                ),
            )
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            logger.error("Character ingest error: %s", e)
    return count


def _ingest_tribes(db, tribes: list[dict]) -> int:
    """Ingest tribe (corp) data and member→tribe associations."""
    count = 0
    for raw in tribes:
        tribe_id = raw.get("id")
        if not tribe_id:
            continue
        try:
            cursor = db.execute(
                """INSERT INTO tribes
                   (tribe_id, name, name_short, description,
                    member_count, tax_rate, tribe_url, founded_at, raw_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(tribe_id) DO UPDATE SET
                       name = excluded.name,
                       name_short = excluded.name_short,
                       member_count = excluded.member_count,
                       tax_rate = excluded.tax_rate,
                       tribe_url = excluded.tribe_url,
                       raw_json = excluded.raw_json,
                       ingested_at = unixepoch()""",
                (
                    int(tribe_id),
                    raw.get("name", ""),
                    raw.get("nameShort", ""),
                    raw.get("description", ""),
                    raw.get("memberCount", 0),
                    raw.get("taxRate", 0),
                    raw.get("tribeUrl", ""),
                    raw.get("foundedAt", ""),
                    json.dumps(raw),
                ),
            )
            if cursor.rowcount > 0:
                count += 1

            # Link members to tribe in smart_characters
            members = raw.get("members", [])
            for member in members:
                addr = member.get("address")
                if not addr:
                    continue
                db.execute(
                    """UPDATE smart_characters
                       SET tribe_id = ?
                       WHERE address = ?""",
                    (str(tribe_id), str(addr)),
                )
        except Exception as e:
            logger.error("Tribe ingest error: %s", e)
    return count


async def _fetch_tribe_details(
    client: httpx.AsyncClient,
    tribes: list[dict],
) -> list[dict]:
    """Fetch individual tribe details to get member lists."""
    details = []
    for tribe in tribes:
        tribe_id = tribe.get("id")
        if not tribe_id:
            continue
        try:
            url = f"{settings.WORLD_API_BASE}/v2/tribes/{tribe_id}"
            r = await client.get(url, timeout=settings.POLL_TIMEOUT_SECONDS)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                details.append(data)
        except Exception as e:
            logger.warning("Tribe detail %s: %s", tribe_id, e)
    return details


def _enrich_entities_from_characters(db) -> None:
    """Update entity display names and corp_id from smart_characters.

    Joins on BOTH address and character_id because:
    - World API entities used wallet address as entity_id
    - Sui GraphQL entities use item_id (from key.item_id) as entity_id
    """
    try:
        # Update display names (match on address OR character_id)
        db.execute("""
            UPDATE entities SET
                display_name = (
                    SELECT sc.name FROM smart_characters sc
                    WHERE (sc.address = entities.entity_id
                           OR sc.character_id = entities.entity_id)
                    AND sc.name != ''
                    LIMIT 1
                ),
                updated_at = unixepoch()
            WHERE entity_type = 'character'
            AND EXISTS (
                SELECT 1 FROM smart_characters sc
                WHERE (sc.address = entities.entity_id
                       OR sc.character_id = entities.entity_id)
                AND sc.name != ''
                AND sc.name != COALESCE(entities.display_name, '')
            )
        """)

        # Update corp_id from tribe_id (match on address OR character_id)
        db.execute("""
            UPDATE entities SET
                corp_id = (
                    SELECT sc.tribe_id FROM smart_characters sc
                    WHERE (sc.address = entities.entity_id
                           OR sc.character_id = entities.entity_id)
                    AND sc.tribe_id IS NOT NULL
                    AND sc.tribe_id != ''
                    LIMIT 1
                ),
                updated_at = unixepoch()
            WHERE entity_type = 'character'
            AND EXISTS (
                SELECT 1 FROM smart_characters sc
                WHERE (sc.address = entities.entity_id
                       OR sc.character_id = entities.entity_id)
                AND sc.tribe_id IS NOT NULL
                AND sc.tribe_id != ''
                AND (entities.corp_id IS NULL
                     OR entities.corp_id != sc.tribe_id)
            )
        """)
    except Exception as e:
        logger.error("Entity enrichment error: %s", e)


async def _poll_c5_endpoints(client: httpx.AsyncClient) -> None:
    """Poll Cycle 5 endpoints. Gracefully handles 404 (API not yet live)."""
    # Endpoint names are guesses — will confirm from sandbox after March 11
    c5_endpoints = {
        "zones": "v2/orbitalzones",
        "scans": "v2/scans",
        "clones": "v2/clones",
        "crowns": "v2/crowns",
    }

    tasks = {name: poll_endpoint(client, ep) for name, ep in c5_endpoints.items()}
    results = {}
    for name, task in tasks.items():
        results[name] = await task

    # Skip if all empty (API not live yet)
    if not any(results.values()):
        return

    db = get_db()
    new_zones = _ingest_orbital_zones(db, results.get("zones", []))
    new_scans = _ingest_scans(db, results.get("scans", []))
    new_clones = _ingest_clones(db, results.get("clones", []))
    new_crowns = _ingest_crowns(db, results.get("crowns", []))

    total = new_zones + new_scans + new_clones + new_crowns
    if total:
        db.commit()
        logger.info(
            "C5 ingested: %d zones, %d scans, %d clones, %d crowns",
            new_zones,
            new_scans,
            new_clones,
            new_crowns,
        )

        # SSE notification
        try:
            from backend.api.events import event_bus

            event_bus.publish(
                "c5_update",
                {
                    "zones": new_zones,
                    "scans": new_scans,
                    "clones": new_clones,
                    "crowns": new_crowns,
                },
            )
        except Exception:
            pass


def _detect_universe_reset(db) -> bool:
    """Detect if universe has reset by checking for killmails newer than reset epoch.

    If the API returns killmails with timestamps *before* our latest ingested
    killmail, the universe likely reset (all old data is stale).
    Returns True if reset detected (pre-cycle data should be archived).
    """
    try:
        from backend.api.cycle5 import CYCLE_RESET_EPOCH

        row = db.execute(
            "SELECT MAX(timestamp) as latest FROM killmails WHERE cycle = 5"
        ).fetchone()
        if not row or not row["latest"]:
            return False  # No data yet — nothing to reset

        # If we have data from before the reset epoch, mark it
        pre_reset = db.execute(
            "SELECT COUNT(*) as cnt FROM killmails WHERE cycle = 5 AND timestamp < ?",
            (CYCLE_RESET_EPOCH,),
        ).fetchone()
        if pre_reset and pre_reset["cnt"] > 0:
            logger.warning(
                "Universe reset detected — %d pre-cycle killmails found",
                pre_reset["cnt"],
            )
            return True
        return False
    except Exception as e:
        logger.error("Reset detection failed: %s", e)
        return False


def _archive_pre_cycle_data(db) -> None:
    """Mark pre-cycle data as cycle 4 to isolate from Cycle 5 queries.

    Does NOT delete — archives by reassigning the cycle field.
    """
    from backend.api.cycle5 import CYCLE_RESET_EPOCH

    tables_with_timestamps = [
        ("killmails", "timestamp"),
        ("gate_events", "timestamp"),
    ]
    for table, ts_col in tables_with_timestamps:
        try:
            result = db.execute(
                f"UPDATE {table} SET cycle = 4 WHERE cycle = 5 AND {ts_col} < ?",  # noqa: S608
                (CYCLE_RESET_EPOCH,),
            )
            if result.rowcount > 0:
                logger.info(
                    "Archived %d pre-cycle rows from %s",
                    result.rowcount,
                    table,
                )
        except Exception as e:
            logger.error("Archive %s failed: %s", table, e)

    # C5 tables: clear all (they're cycle-specific, no pre-cycle data expected)
    c5_tables = [
        "orbital_zones",
        "feral_ai_events",
        "scans",
        "scan_intel",
        "clones",
        "clone_blueprints",
        "crowns",
    ]
    for table in c5_tables:
        try:
            result = db.execute(f"DELETE FROM {table} WHERE cycle < 5")  # noqa: S608
            if result.rowcount > 0:
                logger.info("Cleared %d stale rows from %s", result.rowcount, table)
        except Exception as e:
            logger.error("Clear %s failed: %s", table, e)

    db.commit()
    logger.info("Pre-cycle data archived to cycle 4")


async def run_poller() -> None:
    """Main ingestion loop. Runs forever. Never raises.

    Primary data source: Sui GraphQL (killmails, characters, assemblies, gate jumps).
    Fallback: World API for static/reference data (tribes, C5 endpoints).
    """
    logger.info("Poller starting — Sui GraphQL primary, World API fallback for static data")
    sui = SuiGraphQLPoller()
    cycle_counter = 0
    reset_checked = False
    async with httpx.AsyncClient() as client:
        while True:
            # One-time reset detection on first poll
            if not reset_checked:
                try:
                    db = get_db()
                    if _detect_universe_reset(db):
                        _archive_pre_cycle_data(db)
                except Exception as e:
                    logger.error("Reset check failed (continuing): %s", e)
                reset_checked = True

            # === Primary: Sui GraphQL for dynamic data ===
            try:
                kill_task = sui.poll_killmails(client)
                assembly_task = sui.poll_assemblies(client)
                jump_task = sui.poll_gate_jumps(client)
                location_task = sui.poll_locations(client)
                raw_kills, raw_assemblies, raw_jumps, raw_locations = await asyncio.gather(
                    kill_task, assembly_task, jump_task, location_task
                )

                db = get_db()
                new_kills = _ingest_killmails(db, raw_kills)
                new_assemblies = _ingest_smart_assemblies(db, raw_assemblies)
                new_jumps = _ingest_gate_events(db, raw_jumps)
                new_locs = _update_assembly_locations(db, raw_locations)

                if new_kills or new_assemblies or new_jumps or new_locs:
                    _update_entities(db)
                    db.commit()
                    logger.info(
                        "Sui ingested: %d kills, %d assemblies, %d jumps, %d locs",
                        new_kills,
                        new_assemblies,
                        new_jumps,
                        new_locs,
                    )
                    # Publish to SSE event bus
                    try:
                        from backend.api.events import event_bus

                        if new_kills:
                            event_bus.publish(
                                "kill",
                                {"new_count": new_kills},
                            )
                        if new_assemblies:
                            event_bus.publish(
                                "status",
                                {"new_assemblies": new_assemblies},
                            )
                    except Exception:
                        pass  # SSE is best-effort

                    # NEXUS: dispatch enriched events to builder webhooks
                    try:
                        from backend.analysis.nexus import dispatch_batch

                        nexus_events = []
                        for km in raw_kills:
                            nexus_events.append(
                                {
                                    "event_type": "killmail",
                                    "killmail_id": km.get("id", ""),
                                    "victim_character_id": (
                                        km.get("victim", {}).get("address", "")
                                    ),
                                    "attacker_character_ids": json.dumps(
                                        km.get("attackers", [km.get("killer", {})])
                                    ),
                                    "solar_system_id": str(km.get("solarSystemId", "")),
                                    "timestamp": km.get("timestamp", 0),
                                    "severity": "critical",
                                }
                            )
                        for jump in raw_jumps:
                            nexus_events.append(
                                {
                                    "event_type": "gate_transit",
                                    "gate_id": jump.get("id", ""),
                                    "character_id": str(jump.get("characterId", "")),
                                    "solar_system_id": str(jump.get("solarSystemId", "")),
                                    "timestamp": jump.get("timestamp", 0),
                                    "severity": "info",
                                }
                            )
                        if nexus_events:
                            nexus_delivered = await dispatch_batch(nexus_events)
                            if nexus_delivered:
                                logger.info("NEXUS dispatched %d deliveries", nexus_delivered)
                    except Exception as e:
                        logger.error("NEXUS dispatch error (continuing): %s", e)
                else:
                    db.commit()

            except Exception as e:
                logger.critical("Sui poller loop error (continuing): %s", e)

            # === Bootstrap: one-time bulk character name resolution ===
            try:
                if not sui.names_bootstrapped:
                    raw_names = await sui.bootstrap_character_names(client)
                    if raw_names:
                        boot_db = get_db()
                        new_names = _ingest_smart_characters(boot_db, raw_names)
                        if new_names:
                            _enrich_entities_from_characters(boot_db)
                            boot_db.commit()
                            logger.info(
                                "Bootstrap: %d character names resolved from Sui",
                                new_names,
                            )
            except Exception as e:
                logger.error("Character name bootstrap error (continuing): %s", e)

            # === Bootstrap: solar system names from World API static data ===
            try:
                await bootstrap_system_names(client)
            except Exception as e:
                logger.error("System names bootstrap error (continuing): %s", e)

            # === Reference data from Sui GraphQL (characters) ===
            # NOTE: World API is dead (NXDOMAIN since March 11, 2026).
            # Tribes and C5 endpoints removed — no data returns.
            try:
                if cycle_counter % 10 == 0:
                    raw_chars = await sui.poll_characters(client)
                    if raw_chars:
                        ref_db = get_db()
                        new_chars = _ingest_smart_characters(ref_db, raw_chars)
                        if new_chars:
                            _enrich_entities_from_characters(ref_db)
                            ref_db.commit()
                            logger.info(
                                "Reference data: %d chars from Sui events",
                                new_chars,
                            )
            except Exception as e:
                logger.error("Reference data poll error (continuing): %s", e)

            # === Periodic name re-bootstrap (every 100 cycles ~50 min) ===
            # Catches new players who joined after initial bootstrap
            try:
                if cycle_counter > 0 and cycle_counter % 100 == 0:
                    sui.names_bootstrapped = False  # Reset to allow re-fetch
            except Exception:
                pass

            cycle_counter += 1
            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
