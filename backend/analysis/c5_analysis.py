"""Cycle 5 analysis — intelligence from orbital zones, scans, clones, crowns.

Transforms raw C5 data into actionable intelligence summaries.
"""

import sqlite3
import time
from dataclasses import dataclass, field

from backend.core.logger import get_logger

logger = get_logger("c5_analysis")

# Feral AI tier → threat level
THREAT_LEVELS = {0: "DORMANT", 1: "ACTIVE", 2: "EVOLVED", 3: "CRITICAL"}


@dataclass
class ZoneThreatSummary:
    """Intelligence summary for a single orbital zone."""

    zone_id: str
    name: str
    current_tier: int
    threat_level: str
    escalation_count: int = 0
    last_escalation: int | None = None
    hours_at_current_tier: float = 0.0
    scan_count_24h: int = 0
    hostile_scan_count_24h: int = 0
    is_blind_spot: bool = False

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "current_tier": self.current_tier,
            "threat_level": self.threat_level,
            "escalation_count": self.escalation_count,
            "last_escalation": self.last_escalation,
            "hours_at_current_tier": round(self.hours_at_current_tier, 1),
            "scan_count_24h": self.scan_count_24h,
            "hostile_scan_count_24h": self.hostile_scan_count_24h,
            "is_blind_spot": self.is_blind_spot,
        }


@dataclass
class C5Briefing:
    """Cycle 5 situation briefing."""

    total_zones: int = 0
    zones_by_threat: dict[str, int] = field(default_factory=dict)
    most_volatile_zones: list[dict] = field(default_factory=list)
    blind_spots: list[dict] = field(default_factory=list)
    scan_coverage_pct: float = 0.0
    hostile_zones: list[str] = field(default_factory=list)
    total_clones: int = 0
    low_reserve_owners: list[dict] = field(default_factory=list)
    crown_distribution: list[dict] = field(default_factory=list)
    uncrowned_count: int = 0

    def to_dict(self) -> dict:
        return {
            "total_zones": self.total_zones,
            "zones_by_threat": self.zones_by_threat,
            "most_volatile_zones": self.most_volatile_zones,
            "blind_spots": self.blind_spots,
            "scan_coverage_pct": round(self.scan_coverage_pct, 1),
            "hostile_zones": self.hostile_zones,
            "total_clones": self.total_clones,
            "low_reserve_owners": self.low_reserve_owners,
            "crown_distribution": self.crown_distribution,
            "uncrowned_count": self.uncrowned_count,
        }


def analyze_zone_threat(db: sqlite3.Connection, zone_id: str) -> ZoneThreatSummary | None:
    """Build threat intelligence for a single orbital zone."""
    row = db.execute(
        "SELECT zone_id, name, feral_ai_tier, last_scanned FROM orbital_zones WHERE zone_id = ?",
        (zone_id,),
    ).fetchone()
    if not row:
        return None

    now = int(time.time())
    tier = row["feral_ai_tier"] or 0
    summary = ZoneThreatSummary(
        zone_id=row["zone_id"],
        name=row["name"] or row["zone_id"][:16],
        current_tier=tier,
        threat_level=THREAT_LEVELS.get(tier, "UNKNOWN"),
    )

    # Escalation history
    evolutions = db.execute(
        "SELECT new_tier, timestamp FROM feral_ai_events "
        "WHERE zone_id = ? AND event_type = 'evolution' "
        "ORDER BY timestamp DESC",
        (zone_id,),
    ).fetchall()
    summary.escalation_count = len(evolutions)
    if evolutions:
        summary.last_escalation = evolutions[0]["timestamp"]
        hours = (now - evolutions[0]["timestamp"]) / 3600
        summary.hours_at_current_tier = max(0, hours)

    # Scan activity (24h window)
    day_ago = now - 86400
    scan_row = db.execute(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN result_type = 'HOSTILE' THEN 1 ELSE 0 END) as hostile "
        "FROM scans WHERE zone_id = ? AND scanned_at > ?",
        (zone_id, day_ago),
    ).fetchone()
    summary.scan_count_24h = scan_row["total"] or 0
    summary.hostile_scan_count_24h = scan_row["hostile"] or 0

    # Blind spot check (>20 min since last scan)
    last_scanned = row["last_scanned"] or 0
    summary.is_blind_spot = (now - last_scanned) > 1200 if last_scanned else True

    return summary


def get_c5_briefing(db: sqlite3.Connection, clone_threshold: int = 5) -> C5Briefing:
    """Generate a full Cycle 5 situation briefing."""
    briefing = C5Briefing()
    now = int(time.time())

    # --- Zone analysis ---
    zones = db.execute(
        "SELECT zone_id, name, feral_ai_tier, last_scanned FROM orbital_zones"
    ).fetchall()
    briefing.total_zones = len(zones)

    threat_counts: dict[str, int] = {}
    for z in zones:
        tier = z["feral_ai_tier"] or 0
        level = THREAT_LEVELS.get(tier, "UNKNOWN")
        threat_counts[level] = threat_counts.get(level, 0) + 1

        # Blind spots
        last = z["last_scanned"] or 0
        if not last or (now - last) > 1200:
            briefing.blind_spots.append(
                {
                    "zone_id": z["zone_id"],
                    "name": z["name"] or z["zone_id"][:16],
                    "minutes_unseen": (now - last) // 60 if last else None,
                }
            )
    briefing.zones_by_threat = threat_counts

    # Most volatile zones (most escalations)
    volatile = db.execute(
        "SELECT zone_id, COUNT(*) as escalations "
        "FROM feral_ai_events WHERE event_type = 'evolution' "
        "GROUP BY zone_id ORDER BY escalations DESC LIMIT 5"
    ).fetchall()
    for v in volatile:
        zone = db.execute(
            "SELECT name, feral_ai_tier FROM orbital_zones WHERE zone_id = ?",
            (v["zone_id"],),
        ).fetchone()
        briefing.most_volatile_zones.append(
            {
                "zone_id": v["zone_id"],
                "name": zone["name"] if zone else v["zone_id"][:16],
                "escalation_count": v["escalations"],
                "current_tier": zone["feral_ai_tier"] if zone else 0,
            }
        )

    # --- Scan coverage ---
    if briefing.total_zones > 0:
        scanned_zones = db.execute(
            "SELECT COUNT(DISTINCT zone_id) as cnt FROM scans WHERE scanned_at > ?",
            (now - 86400,),
        ).fetchone()
        briefing.scan_coverage_pct = (scanned_zones["cnt"] / briefing.total_zones) * 100

    # Hostile zones (hostile scans in last 30 min)
    hostile = db.execute(
        "SELECT DISTINCT zone_id FROM scans WHERE result_type = 'HOSTILE' AND scanned_at > ?",
        (now - 1800,),
    ).fetchall()
    briefing.hostile_zones = [h["zone_id"] for h in hostile]

    # --- Clone readiness ---
    clone_row = db.execute("SELECT COUNT(*) as cnt FROM clones WHERE status = 'active'").fetchone()
    briefing.total_clones = clone_row["cnt"] or 0

    low = db.execute(
        "SELECT owner_id, owner_name, COUNT(*) as active "
        "FROM clones WHERE status = 'active' "
        "GROUP BY owner_id HAVING active < ?",
        (clone_threshold,),
    ).fetchall()
    briefing.low_reserve_owners = [
        {
            "owner_id": r["owner_id"],
            "owner_name": r["owner_name"] or r["owner_id"][:16],
            "active_clones": r["active"],
        }
        for r in low
    ]

    # --- Crown distribution ---
    crowns = db.execute(
        "SELECT crown_type, COUNT(*) as count FROM crowns GROUP BY crown_type ORDER BY count DESC"
    ).fetchall()
    briefing.crown_distribution = [dict(r) for r in crowns]

    crowned = db.execute("SELECT COUNT(DISTINCT character_id) as cnt FROM crowns").fetchone()
    total_chars = db.execute(
        "SELECT COUNT(*) as cnt FROM entities WHERE entity_type = 'character'"
    ).fetchone()
    crowned_count = crowned["cnt"] or 0
    total_count = total_chars["cnt"] or 0
    briefing.uncrowned_count = max(0, total_count - crowned_count)

    return briefing
