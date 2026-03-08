"""Subscription verification — check on-chain Watcher tier access.

Queries the blockchain gateway to verify if a wallet address has
an active subscription at a given tier. Caches results to avoid
hammering the chain on every request.
"""

import sqlite3
import time

from backend.core.logger import get_logger

logger = get_logger("subscriptions")

# Tier constants (mirror WatcherSystem.sol)
TIER_FREE = 0
TIER_SCOUT = 1
TIER_ORACLE = 2
TIER_SPYMASTER = 3

TIER_NAMES = {
    TIER_FREE: "free",
    TIER_SCOUT: "scout",
    TIER_ORACLE: "oracle",
    TIER_SPYMASTER: "spymaster",
}

# Cache TTL: 5 minutes (avoid querying chain every request)
CACHE_TTL = 300

# In-memory cache: {address: (tier, expires_at, cached_at)}
_cache: dict[str, tuple[int, int, float]] = {}


def check_subscription(
    db: sqlite3.Connection,
    wallet_address: str,
) -> dict:
    """Check subscription status for a wallet address.

    Returns dict with tier, tier_name, expires_at, active.
    For hackathon: uses local DB cache. Production would query chain.
    """
    now = int(time.time())

    # Check in-memory cache first
    if wallet_address in _cache:
        tier, expires_at, cached_at = _cache[wallet_address]
        if time.time() - cached_at < CACHE_TTL:
            return {
                "wallet": wallet_address,
                "tier": tier,
                "tier_name": TIER_NAMES.get(tier, "unknown"),
                "expires_at": expires_at,
                "active": tier > TIER_FREE and expires_at > now,
            }

    # Check local subscription table
    row = db.execute(
        "SELECT tier, expires_at FROM watcher_subscriptions WHERE wallet_address = ?",
        (wallet_address,),
    ).fetchone()

    if row:
        tier = row["tier"]
        expires_at = row["expires_at"]
    else:
        tier = TIER_FREE
        expires_at = 0

    # Update cache
    _cache[wallet_address] = (tier, expires_at, time.time())

    return {
        "wallet": wallet_address,
        "tier": tier,
        "tier_name": TIER_NAMES.get(tier, "unknown"),
        "expires_at": expires_at,
        "active": tier > TIER_FREE and expires_at > now,
    }


def record_subscription(
    db: sqlite3.Connection,
    wallet_address: str,
    tier: int,
    duration: int = 7 * 86400,
) -> dict:
    """Record a subscription (called when chain event detected or manual).

    For hackathon demo: direct DB write. Production: chain event listener.
    """
    now = int(time.time())

    existing = db.execute(
        "SELECT expires_at FROM watcher_subscriptions WHERE wallet_address = ?",
        (wallet_address,),
    ).fetchone()

    if existing and existing["expires_at"] > now:
        # Extend existing
        expires_at = existing["expires_at"] + duration
    else:
        expires_at = now + duration

    db.execute(
        """INSERT INTO watcher_subscriptions (wallet_address, tier, expires_at, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(wallet_address)
           DO UPDATE SET tier = ?, expires_at = ?""",
        (wallet_address, tier, expires_at, now, tier, expires_at),
    )
    db.commit()

    # Invalidate cache
    _cache.pop(wallet_address, None)

    logger.info(
        "Subscription recorded: %s tier=%d expires=%d",
        wallet_address[:16],
        tier,
        expires_at,
    )

    return check_subscription(db, wallet_address)


def get_tier_for_endpoint(endpoint: str) -> int:
    """Map API endpoints to required subscription tiers."""
    gated = {
        # Scout tier
        "/entity/{entity_id}/fingerprint": TIER_SCOUT,
        "/entity/{entity_id}/reputation": TIER_SCOUT,
        "/fingerprint/compare": TIER_SCOUT,
        # Oracle tier
        "/entity/{entity_id}/narrative": TIER_ORACLE,
        "/watches": TIER_ORACLE,
        "/battle-report": TIER_ORACLE,
        # Spymaster tier
        "/kill-graph": TIER_SPYMASTER,
    }
    return gated.get(endpoint, TIER_FREE)
