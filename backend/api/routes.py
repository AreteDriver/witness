"""FastAPI routes — entity dossiers, story feed, watches, health."""

import json
import re
import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.analysis.assembly_tracker import get_assembly_stats, get_watcher_assemblies
from backend.analysis.chain_verify import verify_subscription_on_chain
from backend.analysis.corp_intel import (
    detect_corp_rivalries,
    get_corp_leaderboard,
    get_corp_profile,
)
from backend.analysis.entity_resolver import resolve_entity
from backend.analysis.fingerprint import build_fingerprint, compare_fingerprints
from backend.analysis.hotzones import get_hotzones, get_system_activity, get_system_dossier
from backend.analysis.kill_graph import build_kill_graph
from backend.analysis.narrative import (
    generate_battle_report,
    generate_dossier_narrative,
    generate_system_narrative,
)
from backend.analysis.nexus import get_quota_usage
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


_SUI_GRAPHQL_URL = "https://graphql.testnet.sui.io/graphql"
_SUI_GRAPHQL_PROBE = '{"query":"{ checkpoint { sequenceNumber } }"}'


async def _check_sui_graphql() -> str:
    """Non-blocking connectivity check to Sui GraphQL endpoint (2s timeout)."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                _SUI_GRAPHQL_URL,
                content=_SUI_GRAPHQL_PROBE,
                headers={"Content-Type": "application/json"},
                timeout=2.0,
            )
            if r.status_code == 200:
                return "ok"
            return f"http_{r.status_code}"
    except Exception:
        return "unreachable"


@router.get("/health")
async def health():
    db = get_db()
    counts = {}
    for table, query in _HEALTH_QUERIES.items():
        row = db.execute(query).fetchone()
        counts[table] = row["cnt"]
    sui_graphql = await _check_sui_graphql()
    return {
        "status": "ok",
        "tables": counts,
        "sui_graphql": sui_graphql,
        "timestamp": int(time.time()),
    }


@router.get("/entity/{entity_id}")
@limiter.limit("120/minute")
async def get_entity(request: Request, entity_id: str):
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
@limiter.limit("100/minute")
async def list_entities(
    request: Request,
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
@limiter.limit("120/minute")
async def get_entity_timeline(
    request: Request,
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
@limiter.limit("100/minute")
async def get_story_feed(
    request: Request,
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
@limiter.limit("100/minute")
async def get_leaderboard(
    request: Request,
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
@limiter.limit("100/minute")
async def get_titled_entities(request: Request, limit: int = Query(default=50, le=200)):
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
@limiter.limit("60/minute")
async def search_entities(
    request: Request,
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
    results = [dict(r) for r in rows]

    # Search solar systems (dedicated lookup table, fallback to assemblies)
    sys_rows = db.execute(
        """SELECT ss.solar_system_id, ss.name as solar_system_name
           FROM solar_systems ss
           WHERE ss.name LIKE ?
           ORDER BY ss.name LIMIT 5""",
        (pattern,),
    ).fetchall()
    if not sys_rows:
        # Fallback: legacy smart_assemblies data
        sys_rows = db.execute(
            """SELECT solar_system_id, solar_system_name
               FROM smart_assemblies
               WHERE solar_system_name LIKE ? AND solar_system_name != ''
               GROUP BY solar_system_id
               ORDER BY solar_system_name LIMIT 5""",
            (pattern,),
        ).fetchall()
    for sr in sys_rows:
        results.append(
            {
                "entity_id": sr["solar_system_id"],
                "entity_type": "system",
                "display_name": sr["solar_system_name"],
                "event_count": 0,
            }
        )

    return {"query": q, "results": results}


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


@router.get("/system/{system_id}/narrative")
@limiter.limit("20/minute")
async def get_system_narrative(request: Request, system_id: str):
    check_tier_access(request, "get_system_narrative")
    narrative = generate_system_narrative(system_id)
    return {"system_id": system_id, "narrative": narrative}


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
@limiter.limit("100/minute")
async def get_hotzones_endpoint(
    request: Request,
    window: str = Query(default="all", pattern="^(24h|7d|30d|all)$"),
    limit: int = Query(default=20, le=50),
):
    """Dangerous systems ranked by kill density."""
    db = get_db()
    return {"window": window, "hotzones": get_hotzones(db, window=window, limit=limit)}


@router.get("/hotzones/{solar_system_id}")
@limiter.limit("100/minute")
async def get_system_detail(request: Request, solar_system_id: str):
    """Detailed kill activity for a specific system."""
    db = get_db()
    return get_system_activity(db, solar_system_id)


@router.get("/system/{solar_system_id}")
@limiter.limit("120/minute")
async def get_system_dossier_endpoint(request: Request, solar_system_id: str):
    """Full intelligence dossier for a solar system."""
    db = get_db()
    return get_system_dossier(db, solar_system_id)


@router.get("/entity/{entity_id}/streak")
@limiter.limit("120/minute")
async def get_entity_streak(request: Request, entity_id: str):
    """Kill streak and momentum data for an entity."""
    db = get_db()
    info = compute_streaks(db, entity_id)
    return info.to_dict()


@router.get("/streaks")
@limiter.limit("100/minute")
async def get_streaks(request: Request, limit: int = Query(default=10, le=50)):
    """Entities currently on kill streaks."""
    db = get_db()
    return {"streaks": get_hot_streaks(db, limit=limit)}


@router.get("/corps")
@limiter.limit("100/minute")
async def get_corps(request: Request, limit: int = Query(default=20, le=50)):
    """Corporation leaderboard by combat activity."""
    db = get_db()
    return {"corps": get_corp_leaderboard(db, limit=limit)}


@router.get("/corps/rivalries")
@limiter.limit("100/minute")
async def get_rivalries(request: Request, limit: int = Query(default=10, le=50)):
    """Inter-corporation rivalries (mutual kills)."""
    db = get_db()
    return {"rivalries": detect_corp_rivalries(db, limit=limit)}


@router.get("/corp/{corp_id}")
@limiter.limit("120/minute")
async def get_corp(request: Request, corp_id: str):
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
@limiter.limit("100/minute")
async def get_assemblies(request: Request):
    """Live Watcher Smart Assembly locations — auto-updated from chain."""
    db = get_db()
    return get_assembly_stats(db)


@router.get("/assemblies/list")
@limiter.limit("100/minute")
async def list_assemblies(request: Request):
    """All Watcher assembly locations."""
    db = get_db()
    return {"assemblies": get_watcher_assemblies(db)}


@router.get("/subscription/{wallet_address}")
@limiter.limit("120/minute")
async def get_subscription(request: Request, wallet_address: str):
    """Check subscription status for a wallet address."""
    if settings.HACKATHON_MODE:
        from datetime import UTC, date, datetime

        try:
            ends = date.fromisoformat(settings.HACKATHON_ENDS)
            if date.today() <= ends:
                expires_ts = int(datetime.combine(ends, datetime.min.time(), UTC).timestamp())
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


@router.get("/wallet/{address}/subscription/verify")
async def verify_subscription_chain(address: str):
    """Verify subscription status directly from on-chain SubscriptionCap objects.

    Supplementary check — queries Sui GraphQL for SubscriptionCap owned by the wallet.
    No auth required (public chain data). DB remains primary source of truth.
    """
    result = await verify_subscription_on_chain(address)
    if result:
        return {
            "has_subscription": True,
            "tier": result["tier"],
            "expires_at": result["expires_at"],
            "source": "chain",
        }
    return {
        "has_subscription": False,
        "tier": None,
        "expires_at": None,
        "source": "chain",
    }


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


def _get_ai_usage_stats(db, day_ago: int, week_ago: int) -> dict:
    """Query AI token usage stats for admin dashboard."""
    totals = db.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(input_tokens), 0) as input_total,
                  COALESCE(SUM(output_tokens), 0) as output_total,
                  COALESCE(SUM(cached_tokens), 0) as cached_total
           FROM ai_usage"""
    ).fetchone()

    usage_24h = db.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(input_tokens), 0) as input_total,
                  COALESCE(SUM(output_tokens), 0) as output_total
           FROM ai_usage WHERE created_at > ?""",
        (day_ago,),
    ).fetchone()

    usage_7d = db.execute(
        """SELECT COUNT(*) as calls,
                  COALESCE(SUM(input_tokens), 0) as input_total,
                  COALESCE(SUM(output_tokens), 0) as output_total
           FROM ai_usage WHERE created_at > ?""",
        (week_ago,),
    ).fetchone()

    by_operation = db.execute(
        """SELECT operation, COUNT(*) as calls,
                  SUM(input_tokens) as input_total,
                  SUM(output_tokens) as output_total
           FROM ai_usage GROUP BY operation ORDER BY calls DESC"""
    ).fetchall()

    recent = db.execute(
        """SELECT model, operation, input_tokens, output_tokens,
                  cached_tokens, entity_id, created_at
           FROM ai_usage ORDER BY created_at DESC LIMIT 10"""
    ).fetchall()

    return {
        "total_calls": totals["calls"],
        "total_input_tokens": totals["input_total"],
        "total_output_tokens": totals["output_total"],
        "total_cached_tokens": totals["cached_total"],
        "calls_24h": usage_24h["calls"],
        "tokens_24h": usage_24h["input_total"] + usage_24h["output_total"],
        "calls_7d": usage_7d["calls"],
        "tokens_7d": usage_7d["input_total"] + usage_7d["output_total"],
        "by_operation": [dict(r) for r in by_operation],
        "recent": [dict(r) for r in recent],
    }


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
    watch_count = db.execute("SELECT COUNT(*) as cnt FROM watches WHERE active = 1").fetchone()[
        "cnt"
    ]

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
        "ai_usage": _get_ai_usage_stats(db, day_ago, week_ago),
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
@limiter.limit("60/minute")
async def list_watches(request: Request, user_id: str = Query(..., min_length=1)):
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
@limiter.limit("60/minute")
async def delete_watch(request: Request, target_id: str, user_id: str):
    db = get_db()
    db.execute(
        "UPDATE watches SET active = 0 WHERE user_id = ? AND target_id = ? AND active = 1",
        (user_id, target_id),
    )
    db.commit()
    return {"status": "removed"}


@router.get("/alerts")
@limiter.limit("60/minute")
async def list_alerts(request: Request, user_id: str = Query(..., min_length=1), limit: int = 50):
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
@limiter.limit("60/minute")
async def mark_alert_read(request: Request, alert_id: int):
    """Mark an alert as read."""
    db = get_db()
    db.execute("UPDATE watch_alerts SET read = 1 WHERE id = ?", (alert_id,))
    db.commit()
    return {"status": "ok"}


# ---------- NEXUS: Builder webhook subscriptions ----------


class NexusSubscribeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    endpoint_url: str = Field(min_length=10, max_length=500)
    filters: dict = Field(default_factory=dict)


def _validate_nexus_endpoint(url: str) -> None:
    """Validate NEXUS endpoint URL — HTTPS only, no private IPs."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(400, "Endpoint URL must use HTTPS.")
    hostname = parsed.hostname or ""
    if _PRIVATE_IP_PATTERN.match(hostname):
        raise HTTPException(400, "Endpoint URL cannot point to private addresses.")


@router.post("/nexus/subscribe")
@limiter.limit("10/minute")
async def nexus_subscribe(request: Request, req: NexusSubscribeRequest):
    """Register a NEXUS webhook subscription.

    Requires Oracle tier (2) or higher. Returns API key and HMAC secret.
    Store the secret — it cannot be retrieved again.
    """
    check_tier_access(request, "nexus_subscribe")
    _validate_nexus_endpoint(req.endpoint_url)

    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet:
        raise HTTPException(403, "Wallet address required for NEXUS subscriptions.")

    from backend.analysis.nexus import (
        check_subscription_quota,
        generate_api_key,
        generate_secret,
    )

    db = get_db()

    # Get wallet tier
    sub_info = check_subscription(db, wallet)
    tier = sub_info["tier"] if sub_info["active"] else 0

    # Check quota
    quota = check_subscription_quota(db, wallet, tier)
    if not quota["allowed"]:
        raise HTTPException(
            403,
            f"Subscription limit reached ({quota['current']}/{quota['max']}). "
            f"Upgrade tier for more subscriptions.",
        )

    api_key = generate_api_key()
    secret = generate_secret()

    db.execute(
        """INSERT INTO nexus_subscriptions
           (api_key, name, endpoint_url, filters, secret, wallet_address)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (api_key, req.name, req.endpoint_url, json.dumps(req.filters), secret, wallet),
    )
    db.commit()
    logger.info(
        "NEXUS subscription created: %s → %s (wallet=%s)",
        req.name,
        req.endpoint_url,
        wallet[:16],
    )

    return {
        "status": "subscribed",
        "api_key": api_key,
        "secret": secret,
        "name": req.name,
        "endpoint_url": req.endpoint_url,
        "filters": req.filters,
    }


@router.get("/nexus/quota")
@limiter.limit("60/minute")
async def nexus_quota(request: Request):
    """Get NEXUS quota usage for the connected wallet."""
    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet:
        raise HTTPException(403, "Wallet address required.")
    db = get_db()
    return get_quota_usage(db, wallet)


@router.get("/nexus/subscriptions")
@limiter.limit("60/minute")
async def nexus_list_subscriptions(
    request: Request,
    api_key: str = Query(..., min_length=1),
):
    """List subscriptions for an API key."""
    db = get_db()
    rows = db.execute(
        """SELECT id, name, endpoint_url, filters, active,
                  delivery_count, last_delivered_at, created_at
           FROM nexus_subscriptions WHERE api_key = ?
           ORDER BY created_at DESC""",
        (api_key,),
    ).fetchall()
    subs = []
    for r in rows:
        sub = dict(r)
        try:
            sub["filters"] = json.loads(sub["filters"]) if sub["filters"] else {}
        except json.JSONDecodeError:
            sub["filters"] = {}
        subs.append(sub)
    return {"subscriptions": subs}


@router.put("/nexus/subscriptions/{sub_id}")
@limiter.limit("20/minute")
async def nexus_update_subscription(
    request: Request,
    sub_id: int,
    api_key: str = Query(..., min_length=1),
    filters: dict | None = None,
    active: bool | None = None,
):
    """Update subscription filters or active status."""
    db = get_db()
    sub = db.execute(
        "SELECT id FROM nexus_subscriptions WHERE id = ? AND api_key = ?",
        (sub_id, api_key),
    ).fetchone()
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if filters is not None:
        db.execute(
            "UPDATE nexus_subscriptions SET filters = ? WHERE id = ?",
            (json.dumps(filters), sub_id),
        )
    if active is not None:
        db.execute(
            "UPDATE nexus_subscriptions SET active = ? WHERE id = ?",
            (1 if active else 0, sub_id),
        )
    db.commit()
    return {"status": "updated", "id": sub_id}


@router.delete("/nexus/subscriptions/{sub_id}")
@limiter.limit("60/minute")
async def nexus_delete_subscription(
    request: Request,
    sub_id: int,
    api_key: str = Query(..., min_length=1),
):
    """Delete a NEXUS subscription."""
    db = get_db()
    result = db.execute(
        "DELETE FROM nexus_subscriptions WHERE id = ? AND api_key = ?",
        (sub_id, api_key),
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Subscription not found")
    return {"status": "deleted", "id": sub_id}


@router.get("/nexus/deliveries")
@limiter.limit("60/minute")
async def nexus_list_deliveries(
    request: Request,
    api_key: str = Query(..., min_length=1),
    limit: int = Query(default=50, le=200),
):
    """List recent delivery attempts for a subscription."""
    db = get_db()
    rows = db.execute(
        """SELECT d.id, d.event_type, d.status_code, d.success,
                  d.attempts, d.error, d.delivered_at, s.name
           FROM nexus_deliveries d
           JOIN nexus_subscriptions s ON d.subscription_id = s.id
           WHERE s.api_key = ?
           ORDER BY d.delivered_at DESC LIMIT ?""",
        (api_key, limit),
    ).fetchall()
    return {"deliveries": [dict(r) for r in rows]}
