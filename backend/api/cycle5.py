"""Cycle 5: Shroud of Fear — orbital zones, void scans, clones, crowns."""

import time

from fastapi import APIRouter, Query

from backend.analysis.c5_analysis import analyze_zone_threat, get_c5_briefing
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("cycle5")

router = APIRouter(tags=["cycle5"])

# Cycle constants — update on universe reset
CYCLE_NUMBER = 5
CYCLE_NAME = "Shroud of Fear"
CYCLE_RESET_EPOCH = 1741651200  # 2026-03-11T00:00:00Z

# Feral AI tier → threat level mapping (derived, not stored)
THREAT_LEVELS = {0: "DORMANT", 1: "ACTIVE", 2: "EVOLVED", 3: "CRITICAL"}


def _threat_level(tier: int) -> str:
    return THREAT_LEVELS.get(tier, "UNKNOWN")


def _cycle_envelope(data: dict | list) -> dict:
    """Wrap response in cycle envelope per C5 spec."""
    return {
        "cycle": CYCLE_NUMBER,
        "reset_at": CYCLE_RESET_EPOCH,
        "data": data,
    }


@router.get("/cycle")
async def get_cycle():
    """Current cycle info with days elapsed."""
    now = int(time.time())
    days_elapsed = max(0, (now - CYCLE_RESET_EPOCH) // 86400)
    return _cycle_envelope(
        {
            "number": CYCLE_NUMBER,
            "name": CYCLE_NAME,
            "reset_at": CYCLE_RESET_EPOCH,
            "days_elapsed": days_elapsed,
        }
    )


@router.get("/orbital-zones")
async def list_orbital_zones(
    threat_level: str | None = None,
    limit: int = Query(default=50, le=200),
):
    """Orbital zones with derived threat level."""
    db = get_db()
    if threat_level:
        # Reverse-map threat level to tier
        tier = None
        for t, name in THREAT_LEVELS.items():
            if name == threat_level.upper():
                tier = t
                break
        if tier is None:
            return _cycle_envelope([])
        rows = db.execute(
            """SELECT zone_id, name, solar_system_id, x, y, z,
                      feral_ai_tier, last_scanned
               FROM orbital_zones WHERE feral_ai_tier = ?
               ORDER BY feral_ai_tier DESC, last_scanned ASC
               LIMIT ?""",
            (tier, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT zone_id, name, solar_system_id, x, y, z,
                      feral_ai_tier, last_scanned
               FROM orbital_zones
               ORDER BY feral_ai_tier DESC, last_scanned ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    now = int(time.time())
    zones = []
    for r in rows:
        d = dict(r)
        d["threat_level"] = _threat_level(d["feral_ai_tier"])
        last = d.get("last_scanned") or 0
        d["stale"] = (now - last) > 900 if last else True  # >15 min
        zones.append(d)
    return _cycle_envelope(zones)


@router.get("/orbital-zones/{zone_id}/history")
async def zone_history(
    zone_id: str,
    limit: int = Query(default=50, le=200),
):
    """Feral AI event history for a zone."""
    db = get_db()
    rows = db.execute(
        """SELECT event_type, old_tier, new_tier, severity, timestamp
           FROM feral_ai_events WHERE zone_id = ?
           ORDER BY timestamp DESC LIMIT ?""",
        (zone_id, limit),
    ).fetchall()
    events = []
    for r in rows:
        d = dict(r)
        d["old_threat"] = _threat_level(d.get("old_tier") or 0)
        d["new_threat"] = _threat_level(d.get("new_tier") or 0)
        events.append(d)
    return _cycle_envelope(events)


@router.get("/scans")
async def list_scans(
    zone_id: str | None = None,
    result_type: str | None = None,
    since: int | None = None,
    limit: int = Query(default=50, le=200),
):
    """Recent void scans, filterable by zone and result type."""
    db = get_db()
    conditions = []
    params: list = []
    if zone_id:
        conditions.append("zone_id = ?")
        params.append(zone_id)
    if result_type:
        conditions.append("result_type = ?")
        params.append(result_type.upper())
    if since:
        conditions.append("scanned_at >= ?")
        params.append(since)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        f"""SELECT scan_id, zone_id, scanner_id, scanner_name,
                   result_type, result_data, scanned_at
            FROM scans {where}
            ORDER BY scanned_at DESC LIMIT ?""",
        params + [limit],
    ).fetchall()
    return _cycle_envelope([dict(r) for r in rows])


@router.get("/scans/feed")
async def scan_feed(limit: int = Query(default=20, le=100)):
    """Live scan feed — newest first, for real-time dashboard."""
    db = get_db()
    rows = db.execute(
        """SELECT scan_id, zone_id, scanner_name, result_type, scanned_at
           FROM scans ORDER BY scanned_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()

    now = int(time.time())
    items = []
    for r in rows:
        d = dict(r)
        # Flag zones with recent hostile results
        hostile = db.execute(
            """SELECT COUNT(*) as cnt FROM scans
               WHERE zone_id = ? AND result_type = 'HOSTILE'
               AND scanned_at > ?""",
            (d["zone_id"], now - 1800),  # last 30 min
        ).fetchone()
        d["zone_hostile_recent"] = hostile["cnt"] > 0
        items.append(d)
    return _cycle_envelope(items)


@router.get("/clones")
async def list_clones(
    corp_id: str | None = None,
    limit: int = Query(default=50, le=200),
):
    """Active clones, optionally filtered by corp (via owner entity lookup)."""
    db = get_db()
    if corp_id:
        rows = db.execute(
            """SELECT c.clone_id, c.owner_id, c.owner_name, c.blueprint_id,
                      c.status, c.location_zone_id, c.manufactured_at
               FROM clones c
               JOIN entities e ON c.owner_id = e.entity_id
               WHERE e.corp_id = ? AND c.status = 'active'
               ORDER BY c.manufactured_at DESC LIMIT ?""",
            (corp_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT clone_id, owner_id, owner_name, blueprint_id,
                      status, location_zone_id, manufactured_at
               FROM clones WHERE status = 'active'
               ORDER BY manufactured_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return _cycle_envelope([dict(r) for r in rows])


@router.get("/clones/queue")
async def clone_queue(limit: int = Query(default=50, le=200)):
    """Manufacturing queue — clones being built."""
    db = get_db()
    rows = db.execute(
        """SELECT c.clone_id, c.owner_id, c.owner_name,
                  cb.name as blueprint_name, cb.tier, cb.manufacture_time_sec,
                  c.manufactured_at
           FROM clones c
           LEFT JOIN clone_blueprints cb ON c.blueprint_id = cb.blueprint_id
           WHERE c.status = 'manufacturing'
           ORDER BY c.manufactured_at ASC LIMIT ?""",
        (limit,),
    ).fetchall()
    return _cycle_envelope([dict(r) for r in rows])


@router.get("/crowns")
async def list_crowns(
    corp_id: str | None = None,
    limit: int = Query(default=50, le=200),
):
    """Crown roster, optionally filtered by corp."""
    db = get_db()
    if corp_id:
        rows = db.execute(
            """SELECT cr.crown_id, cr.character_id, cr.character_name,
                      cr.crown_type, cr.attributes, cr.equipped_at
               FROM crowns cr
               JOIN entities e ON cr.character_id = e.entity_id
               WHERE e.corp_id = ?
               ORDER BY cr.equipped_at DESC LIMIT ?""",
            (corp_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT crown_id, character_id, character_name,
                      crown_type, attributes, equipped_at
               FROM crowns ORDER BY equipped_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return _cycle_envelope([dict(r) for r in rows])


@router.get("/crowns/roster")
async def crown_roster(corp_id: str | None = None):
    """Crown type distribution — breakdown for chart."""
    db = get_db()
    if corp_id:
        rows = db.execute(
            """SELECT cr.crown_type, COUNT(*) as count
               FROM crowns cr
               JOIN entities e ON cr.character_id = e.entity_id
               WHERE e.corp_id = ?
               GROUP BY cr.crown_type
               ORDER BY count DESC""",
            (corp_id,),
        ).fetchall()
        total = db.execute(
            """SELECT COUNT(DISTINCT e.entity_id) as total
               FROM entities e WHERE e.corp_id = ? AND e.entity_type = 'character'""",
            (corp_id,),
        ).fetchone()
    else:
        rows = db.execute(
            """SELECT crown_type, COUNT(*) as count
               FROM crowns GROUP BY crown_type
               ORDER BY count DESC""",
        ).fetchall()
        total = db.execute(
            "SELECT COUNT(DISTINCT character_id) as total FROM crowns",
        ).fetchone()

    distribution = [dict(r) for r in rows]
    crowned_count = sum(d["count"] for d in distribution)
    total_characters = total["total"] if total else 0

    return _cycle_envelope(
        {
            "distribution": distribution,
            "crowned": crowned_count,
            "total_characters": total_characters,
            "uncrowned": max(0, total_characters - crowned_count),
        }
    )


@router.get("/orbital-zones/{zone_id}/threat")
async def zone_threat_analysis(zone_id: str):
    """Threat intelligence summary for a single zone."""
    db = get_db()
    summary = analyze_zone_threat(db, zone_id)
    if not summary:
        return _cycle_envelope(None)
    return _cycle_envelope(summary.to_dict())


@router.get("/briefing")
async def c5_briefing():
    """Full Cycle 5 situation briefing — threat, scan, clone, crown analysis."""
    db = get_db()
    briefing = get_c5_briefing(db)
    return _cycle_envelope(briefing.to_dict())
