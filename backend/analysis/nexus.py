"""NEXUS dispatcher — builder webhook subscriptions with enriched payloads.

Builders register filters (character ID, region, event type, threshold).
When WatchTower indexes a matching event, it POSTs an enriched payload
to their endpoint. This is the enrichment layer the builder ecosystem
plugs into.

Architecture:
  - Subscriptions stored in nexus_subscriptions (API key + HMAC secret)
  - Filters: {"event_types": [...], "entity_ids": [...], "system_ids": [...],
              "min_severity": "warning"}
  - Delivery: POST with HMAC-SHA256 signature, 3 retries, exponential backoff
  - Circuit breaker: disable after 10 consecutive failures
"""

import hashlib
import hmac
import json
import secrets
import time
from datetime import date

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("nexus")

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 5, 15]  # seconds
CIRCUIT_BREAKER_THRESHOLD = 10
DELIVERY_TIMEOUT = 10

# Tier-based quotas
TIER_LIMITS: dict[int, dict[str, int]] = {
    0: {"max_subscriptions": 0, "max_deliveries_day": 0},  # Free
    1: {"max_subscriptions": 0, "max_deliveries_day": 0},  # Scout
    2: {"max_subscriptions": 2, "max_deliveries_day": 100},  # Oracle
    3: {"max_subscriptions": 10, "max_deliveries_day": 1000},  # Spymaster
}


SPYMASTER_TIER = 3


def _is_hackathon_active() -> bool:
    """Check if hackathon mode is active and not expired."""
    if not settings.HACKATHON_MODE:
        return False
    try:
        ends = date.fromisoformat(settings.HACKATHON_ENDS)
        return date.today() <= ends
    except ValueError:
        return False


def _effective_tier(db_tier: int) -> int:
    """Return Spymaster tier during hackathon, else the DB tier."""
    if _is_hackathon_active():
        return SPYMASTER_TIER
    return db_tier


def generate_api_key() -> str:
    """Generate a NEXUS API key."""
    return f"nxs_{secrets.token_urlsafe(32)}"


def generate_secret() -> str:
    """Generate an HMAC signing secret."""
    return secrets.token_hex(32)


def sign_payload(secret: str, payload: str) -> str:
    """HMAC-SHA256 sign a payload."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def check_subscription_quota(db, wallet: str, tier: int) -> dict:
    """Check if a wallet can create more NEXUS subscriptions.

    Returns {"allowed": bool, "current": int, "max": int, "tier": int}.
    """
    tier = _effective_tier(tier)
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[0])
    max_subs = limits["max_subscriptions"]

    # Count subs owned by this wallet
    rows = db.execute(
        "SELECT COUNT(*) as cnt FROM nexus_subscriptions WHERE wallet_address = ?",
        (wallet,),
    ).fetchone()
    if rows:
        count = rows["cnt"]

    return {
        "allowed": count < max_subs,
        "current": count,
        "max": max_subs,
        "tier": tier,
    }


def check_delivery_quota(db, subscription_id: int) -> bool:
    """Check if a subscription has remaining daily delivery quota.

    Returns True if delivery is allowed.
    """
    from backend.api.tier_gate import is_admin_wallet

    sub = db.execute(
        "SELECT wallet_address FROM nexus_subscriptions WHERE id = ?",
        (subscription_id,),
    ).fetchone()
    if not sub or not sub["wallet_address"]:
        return True  # No wallet linked, allow (backward compat)

    # Get wallet's tier
    wallet = sub["wallet_address"]

    # Admin wallets bypass quota checks
    if is_admin_wallet(wallet):
        return True

    tier_row = db.execute(
        "SELECT tier, expires_at FROM watcher_subscriptions WHERE wallet_address = ?",
        (wallet,),
    ).fetchone()

    db_tier = 0
    if tier_row and tier_row["expires_at"] > int(time.time()):
        db_tier = tier_row["tier"]

    tier = _effective_tier(db_tier)
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[0])
    max_daily = limits["max_deliveries_day"]
    if max_daily == 0:
        return False

    # Count today's deliveries across all subs for this wallet
    day_ago = int(time.time()) - 86400
    today_count = db.execute(
        """SELECT COUNT(*) as cnt FROM nexus_deliveries d
           JOIN nexus_subscriptions s ON d.subscription_id = s.id
           WHERE s.wallet_address = ? AND d.delivered_at > ? AND d.success = 1""",
        (wallet, day_ago),
    ).fetchone()

    return (today_count["cnt"] if today_count else 0) < max_daily


def get_quota_usage(db, wallet: str) -> dict:
    """Get current quota usage for a wallet. Used by Account page."""
    tier_row = db.execute(
        "SELECT tier, expires_at FROM watcher_subscriptions WHERE wallet_address = ?",
        (wallet,),
    ).fetchone()

    db_tier = 0
    if tier_row and tier_row["expires_at"] > int(time.time()):
        db_tier = tier_row["tier"]

    tier = _effective_tier(db_tier)
    limits = TIER_LIMITS.get(tier, TIER_LIMITS[0])

    sub_count = db.execute(
        "SELECT COUNT(*) as cnt FROM nexus_subscriptions WHERE wallet_address = ?",
        (wallet,),
    ).fetchone()

    day_ago = int(time.time()) - 86400
    delivery_count = db.execute(
        """SELECT COUNT(*) as cnt FROM nexus_deliveries d
           JOIN nexus_subscriptions s ON d.subscription_id = s.id
           WHERE s.wallet_address = ? AND d.delivered_at > ? AND d.success = 1""",
        (wallet, day_ago),
    ).fetchone()

    return {
        "tier": tier,
        "subscriptions_used": sub_count["cnt"] if sub_count else 0,
        "subscriptions_max": limits["max_subscriptions"],
        "deliveries_today": delivery_count["cnt"] if delivery_count else 0,
        "deliveries_max": limits["max_deliveries_day"],
    }


def match_filters(filters: dict, event: dict) -> bool:
    """Check if an event matches subscription filters.

    Filter fields (all optional, AND logic):
      - event_types: list of event type strings (e.g. ["killmail", "gate_transit"])
      - entity_ids: list of entity IDs to watch
      - system_ids: list of solar system IDs
      - min_severity: minimum severity level ("info", "warning", "critical")
    """
    # Empty filters = match everything
    if not filters:
        return True

    event_types = filters.get("event_types")
    if event_types and event.get("event_type") not in event_types:
        return False

    entity_ids = filters.get("entity_ids")
    if entity_ids:
        event_entities = set()
        for field in (
            "entity_id",
            "victim_character_id",
            "character_id",
            "gate_id",
            "killer_id",
        ):
            val = event.get(field, "")
            if val:
                event_entities.add(str(val))
        # Also check attacker lists
        attackers = event.get("attacker_character_ids", "")
        if isinstance(attackers, str) and attackers.startswith("["):
            try:
                for a in json.loads(attackers):
                    addr = a.get("address", "") if isinstance(a, dict) else str(a)
                    if addr:
                        event_entities.add(addr)
            except (json.JSONDecodeError, TypeError):
                pass
        if not event_entities.intersection(set(entity_ids)):
            return False

    system_ids = filters.get("system_ids")
    if system_ids:
        event_system = str(event.get("solar_system_id", ""))
        if event_system not in system_ids:
            return False

    severity_order = {"info": 0, "warning": 1, "critical": 2}
    min_severity = filters.get("min_severity")
    if min_severity:
        event_severity = event.get("severity", "info")
        if severity_order.get(event_severity, 0) < severity_order.get(min_severity, 0):
            return False

    return True


def _enrich_event(event: dict) -> dict:
    """Enrich a raw event with WatchTower intelligence."""
    db = get_db()
    enriched = dict(event)
    enriched["_nexus"] = {"enriched_at": int(time.time()), "version": 1}

    # Resolve entity names
    for id_field, name_field in [
        ("victim_character_id", "victim_name"),
        ("character_id", "character_name"),
    ]:
        entity_id = event.get(id_field, "")
        if entity_id and not event.get(name_field):
            row = db.execute(
                "SELECT display_name FROM entities WHERE entity_id = ?",
                (entity_id,),
            ).fetchone()
            if row and row["display_name"]:
                enriched[name_field] = row["display_name"]

    # Resolve system name
    system_id = event.get("solar_system_id", "")
    if system_id:
        row = db.execute(
            "SELECT name FROM solar_systems WHERE solar_system_id = ?",
            (system_id,),
        ).fetchone()
        if row:
            enriched["solar_system_name"] = row["name"]

    return enriched


async def dispatch_event(event: dict) -> int:
    """Dispatch an event to all matching NEXUS subscriptions.

    Returns count of successful deliveries.
    """
    db = get_db()
    subs = db.execute("SELECT * FROM nexus_subscriptions WHERE active = 1").fetchall()

    if not subs:
        return 0

    delivered = 0
    enriched = None  # Lazy enrichment

    for sub in subs:
        try:
            filters = json.loads(sub["filters"]) if sub["filters"] else {}
        except json.JSONDecodeError:
            continue

        if not match_filters(filters, event):
            continue

        # Check delivery quota before enriching/delivering
        if not check_delivery_quota(db, sub["id"]):
            logger.debug("NEXUS delivery quota exceeded for subscription %d", sub["id"])
            continue

        # Enrich once, reuse for all matching subs
        if enriched is None:
            enriched = _enrich_event(event)

        success = await _deliver(sub, enriched)
        if success:
            delivered += 1

    return delivered


async def _deliver(sub: dict, enriched_event: dict) -> bool:
    """Deliver an enriched event to a subscription endpoint.

    Retries with exponential backoff. Records delivery in DB.
    Returns True on success.
    """
    db = get_db()
    payload_str = json.dumps(enriched_event, default=str)
    signature = sign_payload(sub["secret"], payload_str)

    headers = {
        "Content-Type": "application/json",
        "X-Nexus-Signature": signature,
        "X-Nexus-Event": enriched_event.get("event_type", "unknown"),
        "User-Agent": "WatchTower-NEXUS/1.0",
    }

    last_status = 0
    last_error = ""

    async with httpx.AsyncClient() as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(
                    sub["endpoint_url"],
                    content=payload_str,
                    headers=headers,
                    timeout=DELIVERY_TIMEOUT,
                )
                last_status = resp.status_code

                if 200 <= resp.status_code < 300:
                    # Success
                    db.execute(
                        """INSERT INTO nexus_deliveries
                           (subscription_id, event_type, payload, status_code, success)
                           VALUES (?, ?, ?, ?, 1)""",
                        (
                            sub["id"],
                            enriched_event.get("event_type", "unknown"),
                            payload_str[:2000],
                            resp.status_code,
                        ),
                    )
                    db.execute(
                        """UPDATE nexus_subscriptions
                           SET delivery_count = delivery_count + 1,
                               last_delivered_at = unixepoch()
                           WHERE id = ?""",
                        (sub["id"],),
                    )
                    db.commit()
                    return True

                # Non-retryable status codes
                if resp.status_code in (400, 401, 403, 404, 410):
                    last_error = f"HTTP {resp.status_code}"
                    break

            except httpx.TimeoutException:
                last_error = "timeout"
            except httpx.ConnectError as e:
                last_error = f"connect_error: {e}"
                break  # Don't retry connection failures
            except Exception as e:
                last_error = str(e)

            # Backoff before retry
            if attempt < MAX_RETRIES - 1:
                import asyncio

                await asyncio.sleep(RETRY_BACKOFF[attempt])

    # Record failed delivery
    db.execute(
        """INSERT INTO nexus_deliveries
           (subscription_id, event_type, payload, status_code, success,
            attempts, error)
           VALUES (?, ?, ?, ?, 0, ?, ?)""",
        (
            sub["id"],
            enriched_event.get("event_type", "unknown"),
            payload_str[:2000],
            last_status,
            MAX_RETRIES,
            last_error[:500],
        ),
    )

    # Circuit breaker: check consecutive failures
    recent_fails = db.execute(
        """SELECT COUNT(*) as cnt FROM nexus_deliveries
           WHERE subscription_id = ? AND success = 0
           ORDER BY delivered_at DESC LIMIT ?""",
        (sub["id"], CIRCUIT_BREAKER_THRESHOLD),
    ).fetchone()

    if recent_fails and recent_fails["cnt"] >= CIRCUIT_BREAKER_THRESHOLD:
        db.execute(
            "UPDATE nexus_subscriptions SET active = 0 WHERE id = ?",
            (sub["id"],),
        )
        logger.warning(
            "NEXUS circuit breaker tripped for subscription %d (%s) — disabled",
            sub["id"],
            sub["name"],
        )

    db.commit()
    return False


async def dispatch_batch(events: list[dict]) -> int:
    """Dispatch a batch of events. Returns total successful deliveries."""
    total = 0
    for event in events:
        total += await dispatch_event(event)
    return total
