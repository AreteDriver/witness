"""FastAPI routes — entity dossiers, story feed, watches, health."""

import json
import re
import time
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.analysis.assembly_tracker import get_assembly_stats, get_watcher_assemblies
from backend.analysis.corp_intel import (
    detect_corp_rivalries,
    get_corp_leaderboard,
    get_corp_profile,
)
from backend.analysis.entity_resolver import resolve_entity
from backend.analysis.fingerprint import build_fingerprint, compare_fingerprints
from backend.analysis.hotzones import get_hotzones, get_system_activity
from backend.analysis.kill_graph import build_kill_graph
from backend.analysis.narrative import generate_battle_report, generate_dossier_narrative
from backend.analysis.reputation import compute_reputation
from backend.analysis.streaks import compute_streaks, get_hot_streaks
from backend.analysis.subscriptions import check_subscription, record_subscription
from backend.api.rate_limit import limiter
from backend.api.tier_gate import check_tier_access, is_admin_wallet
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("routes")

router = APIRouter()

# Private/reserved IP ranges for SSRF prevention
_PRIVATE_IP_PATTERN = re.compile(
    r"^(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.0\.0\.0|169\.254\.|localhost)"
)
_ALLOWED_WEBHOOK_DOMAINS = {"discord.com", "discordapp.com"}


def _validate_webhook_url(url: str) -> None:
    """Validate webhook URL to prevent SSRF attacks."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(400, "Webhook URL must use HTTPS.")
    hostname = parsed.hostname or ""
    if _PRIVATE_IP_PATTERN.match(hostname):
        raise HTTPException(400, "Webhook URL cannot point to private addresses.")
    if not any(hostname.endswith(d) for d in _ALLOWED_WEBHOOK_DOMAINS):
        raise HTTPException(
            400,
            f"Webhook domain not allowed. Allowed: {', '.join(_ALLOWED_WEBHOOK_DOMAINS)}",
        )


_HEALTH_TABLES = ("killmails", "gate_events", "entities", "story_feed", "watches")
_HEALTH_QUERIES = {t: f"SELECT COUNT(*) as cnt FROM {t}" for t in _HEALTH_TABLES}


@router.get("/health")
async def health():
    db = get_db()
    counts = {}
    for table, query in _HEALTH_QUERIES.items():
        row = db.execute(query).fetchone()
        counts[table] = row["cnt"]
    return {"status": "ok", "tables": counts, "timestamp": int(time.time())}


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str):
    db = get_db()
    dossier = resolve_entity(db, entity_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Entity not found")
    return dossier.to_dict()


_ALLOWED_SORTS = frozenset({"event_count", "last_seen", "kill_count", "death_count", "gate_count"})

_ENTITY_LIST_SQL = {
    sort_col: (
        f"""SELECT entity_id, entity_type, display_name, corp_id,
                   first_seen, last_seen, event_count, kill_count, death_count, gate_count
            FROM entities {{where}}
            ORDER BY {sort_col} DESC
            LIMIT ? OFFSET ?""",
        "SELECT COUNT(*) as cnt FROM entities {where}",
    )
    for sort_col in _ALLOWED_SORTS
}


@router.get("/entities")
async def list_entities(
    entity_type: str | None = None,
    sort: str = "event_count",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    db = get_db()
    if sort not in _ALLOWED_SORTS:
        sort = "event_count"

    where = "WHERE entity_type = ?" if entity_type else ""
    params = [entity_type] if entity_type else []

    list_sql, count_sql = _ENTITY_LIST_SQL[sort]
    rows = db.execute(list_sql.format(where=where), params + [limit, offset]).fetchall()
    total = db.execute(count_sql.format(where=where), params).fetchone()

    return {
        "entities": [dict(r) for r in rows],
        "total": total["cnt"],
        "limit": limit,
        "offset": offset,
    }


@router.get("/entity/{entity_id}/timeline")
async def get_entity_timeline(
    entity_id: str,
    start: int | None = None,
    end: int | None = None,
    limit: int = Query(default=100, le=500),
):
    """Unified timeline of all events for an entity."""
    db = get_db()
    now = int(time.time())
    start = start if start is not None else (now - 7 * 86400)
    end = end if end is not None else now

    events = []

    # Gate events
    gate_rows = db.execute(
        """SELECT 'gate_transit' as event_type, timestamp, gate_id, gate_name,
                  character_id, corp_id, solar_system_id, direction
           FROM gate_events
           WHERE timestamp BETWEEN ? AND ?
           AND (gate_id = ? OR character_id = ? OR corp_id = ?)
           ORDER BY timestamp ASC LIMIT ?""",
        (start, end, entity_id, entity_id, entity_id, limit),
    ).fetchall()
    events.extend([dict(r) for r in gate_rows])

    # Killmails
    kill_rows = db.execute(
        """SELECT 'killmail' as event_type, timestamp, killmail_id,
                  victim_character_id, victim_corp_id, solar_system_id, x, y, z
           FROM killmails
           WHERE timestamp BETWEEN ? AND ?
           AND (victim_character_id = ? OR victim_corp_id = ?
                OR attacker_character_ids LIKE ? OR attacker_corp_ids LIKE ?)
           ORDER BY timestamp ASC LIMIT ?""",
        (start, end, entity_id, entity_id, f'%"{entity_id}"%', f'%"{entity_id}"%', limit),
    ).fetchall()
    events.extend([dict(r) for r in kill_rows])

    events.sort(key=lambda e: e["timestamp"])

    # Add delta_seconds
    for i, event in enumerate(events):
        event["delta_seconds"] = 0 if i == 0 else event["timestamp"] - events[i - 1]["timestamp"]

    return {"entity_id": entity_id, "start": start, "end": end, "events": events}


@router.get("/feed")
async def get_story_feed(
    limit: int = Query(default=20, le=100),
    before: int | None = None,
):
    db = get_db()
    if before:
        rows = db.execute(
            """SELECT * FROM story_feed WHERE timestamp < ?
               ORDER BY timestamp DESC LIMIT ?""",
            (before, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM story_feed ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        try:
            item["entity_ids"] = json.loads(item.get("entity_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            item["entity_ids"] = []
        items.append(item)
    return {"items": items}


@router.get("/leaderboard/{category}")
async def get_leaderboard(
    category: str,
    limit: int = Query(default=20, le=50),
):
    db = get_db()

    queries = {
        "deadliest_gates": """
            SELECT e.entity_id, e.display_name,
                   (SELECT COUNT(*) FROM killmails k WHERE k.solar_system_id =
                    (SELECT solar_system_id FROM gate_events WHERE gate_id = e.entity_id LIMIT 1)
                   ) as score
            FROM entities e WHERE e.entity_type = 'gate'
            ORDER BY score DESC LIMIT ?
        """,
        "most_active_gates": """
            SELECT entity_id, display_name, event_count as score
            FROM entities WHERE entity_type = 'gate'
            ORDER BY event_count DESC LIMIT ?
        """,
        "top_killers": """
            SELECT entity_id, display_name, kill_count as score
            FROM entities WHERE entity_type = 'character' AND kill_count > 0
            ORDER BY kill_count DESC LIMIT ?
        """,
        "most_deaths": """
            SELECT entity_id, display_name, death_count as score
            FROM entities WHERE entity_type = 'character' AND death_count > 0
            ORDER BY death_count DESC LIMIT ?
        """,
        "most_traveled": """
            SELECT entity_id, display_name, gate_count as score
            FROM entities WHERE entity_type = 'character'
            ORDER BY gate_count DESC LIMIT ?
        """,
    }

    if category not in queries:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category. Available: {list(queries.keys())}",
        )

    rows = db.execute(queries[category], (limit,)).fetchall()
    return {"category": category, "entries": [dict(r) for r in rows]}


@router.get("/titles")
async def get_titled_entities(limit: int = Query(default=50, le=200)):
    db = get_db()
    rows = db.execute(
        """SELECT t.entity_id, t.title, t.title_type, t.inscription_count,
                  e.entity_type, e.display_name
           FROM entity_titles t
           JOIN entities e ON t.entity_id = e.entity_id
           ORDER BY t.inscription_count DESC, t.computed_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return {"titles": [dict(r) for r in rows]}


@router.get("/search")
async def search_entities(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, le=50),
):
    db = get_db()
    pattern = f"%{q}%"
    rows = db.execute(
        """SELECT entity_id, entity_type, display_name, corp_id, event_count
           FROM entities
           WHERE entity_id LIKE ? OR display_name LIKE ? OR corp_id LIKE ?
           ORDER BY event_count DESC LIMIT ?""",
        (pattern, pattern, pattern, limit),
    ).fetchall()
    return {"query": q, "results": [dict(r) for r in rows]}


@router.get("/entity/{entity_id}/fingerprint")
@limiter.limit("60/minute")
async def get_entity_fingerprint(request: Request, entity_id: str):
    check_tier_access(request, "get_entity_fingerprint")
    db = get_db()
    try:
        fp = build_fingerprint(db, entity_id)
    except Exception:
        logger.exception("Error building fingerprint")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    if not fp:
        raise HTTPException(status_code=404, detail="Entity not found")
    return fp.to_dict()


@router.get("/fingerprint/compare")
@limiter.limit("30/minute")
async def compare_entity_fingerprints(
    request: Request,
    entity_1: str = Query(...),
    entity_2: str = Query(...),
):
    check_tier_access(request, "compare_entity_fingerprints")
    db = get_db()
    fp1 = build_fingerprint(db, entity_1)
    fp2 = build_fingerprint(db, entity_2)
    if not fp1:
        raise HTTPException(404, f"Entity not found: {entity_1}")
    if not fp2:
        raise HTTPException(404, f"Entity not found: {entity_2}")
    return compare_fingerprints(fp1, fp2)


@router.get("/entity/{entity_id}/narrative")
@limiter.limit("20/minute")
async def get_entity_narrative(request: Request, entity_id: str):
    check_tier_access(request, "get_entity_narrative")
    narrative = generate_dossier_narrative(entity_id)
    return {"entity_id": entity_id, "narrative": narrative}


@router.get("/kill-graph")
@limiter.limit("30/minute")
async def get_kill_graph(
    request: Request,
    entity_id: str | None = None,
    min_kills: int = Query(default=1, ge=1),
    limit: int = Query(default=50, le=200),
):
    """Kill graph: who kills whom, vendetta detection."""
    check_tier_access(request, "get_kill_graph")
    db = get_db()
    return build_kill_graph(db, entity_id=entity_id, min_kills=min_kills, limit=limit)


@router.get("/hotzones")
async def get_hotzones_endpoint(
    window: str = Query(default="all", pattern="^(24h|7d|30d|all)$"),
    limit: int = Query(default=20, le=50),
):
    """Dangerous systems ranked by kill density."""
    db = get_db()
    return {"window": window, "hotzones": get_hotzones(db, window=window, limit=limit)}


@router.get("/hotzones/{solar_system_id}")
async def get_system_detail(solar_system_id: str):
    """Detailed kill activity for a specific system."""
    db = get_db()
    return get_system_activity(db, solar_system_id)


@router.get("/entity/{entity_id}/streak")
async def get_entity_streak(entity_id: str):
    """Kill streak and momentum data for an entity."""
    db = get_db()
    info = compute_streaks(db, entity_id)
    return info.to_dict()


@router.get("/streaks")
async def get_streaks(limit: int = Query(default=10, le=50)):
    """Entities currently on kill streaks."""
    db = get_db()
    return {"streaks": get_hot_streaks(db, limit=limit)}


@router.get("/corps")
async def get_corps(limit: int = Query(default=20, le=50)):
    """Corporation leaderboard by combat activity."""
    db = get_db()
    return {"corps": get_corp_leaderboard(db, limit=limit)}


@router.get("/corps/rivalries")
async def get_rivalries(limit: int = Query(default=10, le=50)):
    """Inter-corporation rivalries (mutual kills)."""
    db = get_db()
    return {"rivalries": detect_corp_rivalries(db, limit=limit)}


@router.get("/corp/{corp_id}")
async def get_corp(corp_id: str):
    """Detailed corporation profile."""
    db = get_db()
    profile = get_corp_profile(db, corp_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Corporation not found")
    return profile.to_dict()


@router.get("/entity/{entity_id}/reputation")
@limiter.limit("60/minute")
async def get_entity_reputation(request: Request, entity_id: str):
    """Trust/reputation score for an entity. Designed for Smart Assembly gating."""
    check_tier_access(request, "get_entity_reputation")
    db = get_db()
    rep = compute_reputation(db, entity_id)
    return rep.to_dict()


@router.get("/assemblies")
async def get_assemblies():
    """Live Watcher Smart Assembly locations — auto-updated from chain."""
    db = get_db()
    return get_assembly_stats(db)


@router.get("/assemblies/list")
async def list_assemblies():
    """All Watcher assembly locations."""
    db = get_db()
    return {"assemblies": get_watcher_assemblies(db)}


@router.get("/subscription/{wallet_address}")
async def get_subscription(wallet_address: str):
    """Check subscription status for a wallet address."""
    if settings.HACKATHON_MODE:
        from datetime import UTC, date, datetime

        try:
            ends = date.fromisoformat(settings.HACKATHON_ENDS)
            if date.today() <= ends:
                expires_ts = int(
                    datetime.combine(ends, datetime.min.time(), UTC).timestamp()
                )
                return {
                    "wallet": wallet_address,
                    "tier": 3,
                    "tier_name": "Spymaster",
                    "expires_at": expires_ts,
                    "active": True,
                }
        except ValueError:
            pass
    db = get_db()
    return check_subscription(db, wallet_address)


class SubscribeRequest(BaseModel):
    wallet_address: str = Field(pattern=r"^0x[a-fA-F0-9]{64}$")
    tier: int
    duration: int = 604800  # 7 days default


@router.post("/subscribe")
@limiter.limit("5/minute")
async def subscribe(request: Request, req: SubscribeRequest):
    """Record a subscription (chain event handler / demo endpoint)."""
    db = get_db()
    if req.tier < 1 or req.tier > 3:
        raise HTTPException(400, "Tier must be 1 (Scout), 2 (Oracle), or 3 (Spymaster)")
    return record_subscription(db, req.wallet_address, req.tier, req.duration)


@router.get("/admin/analytics")
@limiter.limit("30/minute")
async def get_admin_analytics(request: Request):
    """Private analytics dashboard — admin only."""
    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet or not is_admin_wallet(wallet):
        raise HTTPException(403, "Admin access required.")

    db = get_db()
    now = int(time.time())
    day_ago = now - 86400
    week_ago = now - 7 * 86400

    # Core counts
    entity_count = db.execute("SELECT COUNT(*) as cnt FROM entities").fetchone()["cnt"]
    char_count = db.execute(
        "SELECT COUNT(*) as cnt FROM entities WHERE entity_type = 'character'"
    ).fetchone()["cnt"]
    gate_count = db.execute(
        "SELECT COUNT(*) as cnt FROM entities WHERE entity_type = 'gate'"
    ).fetchone()["cnt"]
    killmail_count = db.execute("SELECT COUNT(*) as cnt FROM killmails").fetchone()["cnt"]
    gate_event_count = db.execute("SELECT COUNT(*) as cnt FROM gate_events").fetchone()["cnt"]
    title_count = db.execute("SELECT COUNT(*) as cnt FROM entity_titles").fetchone()["cnt"]
    story_count = db.execute("SELECT COUNT(*) as cnt FROM story_feed").fetchone()["cnt"]
    watch_count = db.execute(
        "SELECT COUNT(*) as cnt FROM watches WHERE active = 1"
    ).fetchone()["cnt"]

    # Activity (24h / 7d)
    kills_24h = db.execute(
        "SELECT COUNT(*) as cnt FROM killmails WHERE timestamp > ?", (day_ago,)
    ).fetchone()["cnt"]
    kills_7d = db.execute(
        "SELECT COUNT(*) as cnt FROM killmails WHERE timestamp > ?", (week_ago,)
    ).fetchone()["cnt"]
    gates_24h = db.execute(
        "SELECT COUNT(*) as cnt FROM gate_events WHERE timestamp > ?", (day_ago,)
    ).fetchone()["cnt"]
    gates_7d = db.execute(
        "SELECT COUNT(*) as cnt FROM gate_events WHERE timestamp > ?", (week_ago,)
    ).fetchone()["cnt"]

    # Subscription distribution
    tier_rows = db.execute(
        """SELECT tier, COUNT(*) as cnt FROM watcher_subscriptions
           WHERE expires_at > ? GROUP BY tier""",
        (now,),
    ).fetchall()
    tier_dist = {r["tier"]: r["cnt"] for r in tier_rows}

    # Top entities by activity (last 7d)
    top_active = db.execute(
        """SELECT entity_id, display_name, kill_count, death_count, event_count
           FROM entities WHERE last_seen > ?
           ORDER BY event_count DESC LIMIT 10""",
        (week_ago,),
    ).fetchall()

    # New entities (last 24h)
    new_entities_24h = db.execute(
        "SELECT COUNT(*) as cnt FROM entities WHERE first_seen > ?", (day_ago,)
    ).fetchone()["cnt"]

    return {
        "timestamp": now,
        "totals": {
            "entities": entity_count,
            "characters": char_count,
            "gates": gate_count,
            "killmails": killmail_count,
            "gate_events": gate_event_count,
            "titles": title_count,
            "stories": story_count,
            "active_watches": watch_count,
        },
        "activity": {
            "kills_24h": kills_24h,
            "kills_7d": kills_7d,
            "gate_transits_24h": gates_24h,
            "gate_transits_7d": gates_7d,
            "new_entities_24h": new_entities_24h,
        },
        "subscriptions": {
            "scout": tier_dist.get(1, 0),
            "oracle": tier_dist.get(2, 0),
            "spymaster": tier_dist.get(3, 0),
        },
        "top_active_7d": [dict(r) for r in top_active],
    }


@router.post("/admin/backfill-stories")
@limiter.limit("2/minute")
async def backfill_stories(request: Request):
    """Clear and regenerate all story feed items with current templates."""
    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet or not is_admin_wallet(wallet):
        raise HTTPException(403, "Admin access required.")

    db = get_db()
    old_count = db.execute("SELECT COUNT(*) as cnt FROM story_feed").fetchone()["cnt"]
    db.execute("DELETE FROM story_feed")
    db.commit()

    from backend.analysis.story_feed import generate_feed_items, generate_historical_feed

    hist = generate_historical_feed()
    live = generate_feed_items()

    new_count = db.execute("SELECT COUNT(*) as cnt FROM story_feed").fetchone()["cnt"]
    return {
        "cleared": old_count,
        "historical_generated": hist,
        "live_generated": live,
        "total": new_count,
    }


class BattleReportRequest(BaseModel):
    entity_id: str
    start: int
    end: int


@router.post("/battle-report")
@limiter.limit("10/minute")
async def create_battle_report(request: Request, req: BattleReportRequest):
    check_tier_access(request, "create_battle_report")
    db = get_db()
    try:
        events = []

        for table, id_cols in [
            ("gate_events", ["gate_id", "character_id", "corp_id"]),
            ("killmails", ["victim_character_id", "victim_corp_id", "solar_system_id"]),
        ]:
            for col in id_cols:
                rows = db.execute(
                    f"""SELECT * FROM {table}
                        WHERE {col} = ? AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp ASC""",
                    (req.entity_id, req.start, req.end),
                ).fetchall()
                events.extend([dict(r) for r in rows])

        # Deduplicate by (event_type implied by table, timestamp, entity)
        seen = set()
        unique_events = []
        for e in events:
            key = (e.get("killmail_id") or e.get("id"), e.get("timestamp"))
            if key not in seen:
                seen.add(key)
                unique_events.append(e)

        unique_events.sort(key=lambda e: e.get("timestamp", 0))

        if not unique_events:
            return {"error": "No events found for this query"}

        if len(unique_events) > 500:
            unique_events = unique_events[:500]

        report = generate_battle_report(unique_events)
        report["event_count"] = len(unique_events)
        return report
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error generating battle report")
        raise HTTPException(status_code=500, detail="Internal server error") from None


class WatchRequest(BaseModel):
    user_id: str
    watch_type: str
    target_id: str
    webhook_url: str = ""
    conditions: dict = {}


@router.get("/watches")
async def list_watches(user_id: str = Query(..., min_length=1)):
    """List active watches for a user/wallet."""
    db = get_db()
    rows = db.execute(
        "SELECT id, user_id, watch_type, target_id, active, webhook_url, "
        "CAST(strftime('%s', created_at) AS INTEGER) as created_at "
        "FROM watches WHERE user_id = ? AND active = 1 ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    return {"watches": [dict(r) for r in rows]}


@router.post("/watches")
@limiter.limit("20/minute")
async def create_watch(request: Request, req: WatchRequest):
    check_tier_access(request, "create_watch")
    valid_types = {
        "entity_movement",
        "gate_traffic_spike",
        "killmail_proximity",
        "hostile_sighting",
    }
    if req.watch_type not in valid_types:
        raise HTTPException(400, f"Invalid type. Choose: {', '.join(valid_types)}")

    # SSRF prevention: validate webhook URL
    if req.webhook_url:
        _validate_webhook_url(req.webhook_url)

    db = get_db()
    db.execute(
        """INSERT INTO watches (user_id, watch_type, target_id, conditions, webhook_url)
           VALUES (?, ?, ?, ?, ?)""",
        (req.user_id, req.watch_type, req.target_id, json.dumps(req.conditions), req.webhook_url),
    )
    db.commit()
    return {"status": "created", "watch_type": req.watch_type, "target_id": req.target_id}


@router.delete("/watches/{target_id}")
async def delete_watch(target_id: str, user_id: str):
    db = get_db()
    db.execute(
        "UPDATE watches SET active = 0 WHERE user_id = ? AND target_id = ? AND active = 1",
        (user_id, target_id),
    )
    db.commit()
    return {"status": "removed"}


@router.get("/alerts")
async def list_alerts(user_id: str = Query(..., min_length=1), limit: int = 50):
    """List recent watch alerts for a user."""
    db = get_db()
    rows = db.execute(
        """SELECT id, watch_id, title, body, severity, read, created_at
           FROM watch_alerts WHERE user_id = ?
           ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    return {"alerts": [dict(r) for r in rows]}


@router.post("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: int):
    """Mark an alert as read."""
    db = get_db()
    db.execute("UPDATE watch_alerts SET read = 1 WHERE id = ?", (alert_id,))
    db.commit()
    return {"status": "ok"}
