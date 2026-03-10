"""Corp intel — organizational analysis from entity data.

Aggregates kills, deaths, members, and territorial footprint
at the corporation level. Surfaces rivalries and org strength.
"""

import json
import sqlite3
from dataclasses import dataclass, field

from backend.core.logger import get_logger

logger = get_logger("corp_intel")


@dataclass
class CorpProfile:
    """Aggregated intel for a corporation."""

    corp_id: str
    member_count: int = 0
    active_members: int = 0  # members with kills or deaths
    total_kills: int = 0
    total_deaths: int = 0
    kill_ratio: float = 0.0
    systems: list[str] = field(default_factory=list)
    top_killers: list[dict] = field(default_factory=list)
    threat_level: str = "unknown"
    tribe_name: str | None = None
    tribe_short: str | None = None

    def to_dict(self) -> dict:
        return {
            "corp_id": self.corp_id,
            "tribe_name": self.tribe_name,
            "tribe_short": self.tribe_short,
            "member_count": self.member_count,
            "active_members": self.active_members,
            "total_kills": self.total_kills,
            "total_deaths": self.total_deaths,
            "kill_ratio": round(self.kill_ratio, 2),
            "systems": self.systems[:10],
            "system_count": len(self.systems),
            "top_killers": self.top_killers[:5],
            "threat_level": self.threat_level,
        }


def get_corp_profile(db: sqlite3.Connection, corp_id: str) -> CorpProfile | None:
    """Build detailed profile for a single corporation."""
    members = db.execute(
        """SELECT entity_id, display_name, kill_count, death_count
           FROM entities WHERE corp_id = ? AND entity_type = 'character'""",
        (corp_id,),
    ).fetchall()

    if not members:
        return None

    profile = CorpProfile(corp_id=corp_id)

    # Enrich with tribe name
    try:
        tribe_row = db.execute(
            "SELECT name, name_short FROM tribes WHERE tribe_id = ?",
            (int(corp_id),),
        ).fetchone()
        if tribe_row:
            profile.tribe_name = tribe_row["name"]
            profile.tribe_short = tribe_row["name_short"]
    except (ValueError, TypeError):
        pass  # corp_id not a valid tribe_id
    profile.member_count = len(members)

    for m in members:
        kills = m["kill_count"] or 0
        deaths = m["death_count"] or 0
        profile.total_kills += kills
        profile.total_deaths += deaths
        if kills > 0 or deaths > 0:
            profile.active_members += 1

    total = profile.total_kills + profile.total_deaths
    if total > 0:
        profile.kill_ratio = profile.total_kills / total

    # Top killers
    killers = sorted(members, key=lambda m: m["kill_count"] or 0, reverse=True)
    profile.top_killers = [
        {
            "entity_id": k["entity_id"],
            "display_name": k["display_name"] or k["entity_id"][:12],
            "kills": k["kill_count"] or 0,
        }
        for k in killers[:5]
        if (k["kill_count"] or 0) > 0
    ]

    # Systems where corp members have been involved in kills
    system_rows = db.execute(
        """SELECT DISTINCT k.solar_system_id FROM killmails k
           WHERE k.solar_system_id != ''
           AND (k.victim_corp_id = ? OR k.attacker_corp_ids LIKE ?)""",
        (corp_id, f'%"{corp_id}"%'),
    ).fetchall()
    profile.systems = [r["solar_system_id"] for r in system_rows]

    # Threat level
    if profile.total_kills >= 100:
        profile.threat_level = "extreme"
    elif profile.total_kills >= 50:
        profile.threat_level = "high"
    elif profile.total_kills >= 20:
        profile.threat_level = "moderate"
    elif profile.total_kills > 0:
        profile.threat_level = "low"
    else:
        profile.threat_level = "none"

    return profile


def get_corp_leaderboard(
    db: sqlite3.Connection,
    limit: int = 20,
) -> list[dict]:
    """Rank corporations by combat activity."""
    corps = db.execute(
        """SELECT corp_id,
                  COUNT(*) as member_count,
                  SUM(kill_count) as total_kills,
                  SUM(death_count) as total_deaths
           FROM entities
           WHERE corp_id != '' AND entity_type = 'character'
           GROUP BY corp_id
           HAVING total_kills > 0 OR total_deaths > 0
           ORDER BY total_kills DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    results = []
    for c in corps:
        kills = c["total_kills"] or 0
        deaths = c["total_deaths"] or 0
        total = kills + deaths
        entry = {
            "corp_id": c["corp_id"],
            "tribe_name": None,
            "tribe_short": None,
            "member_count": c["member_count"],
            "total_kills": kills,
            "total_deaths": deaths,
            "kill_ratio": round(kills / total, 2) if total > 0 else 0.0,
        }
        try:
            tribe_row = db.execute(
                "SELECT name, name_short FROM tribes WHERE tribe_id = ?",
                (int(c["corp_id"]),),
            ).fetchone()
            if tribe_row:
                entry["tribe_name"] = tribe_row["name"]
                entry["tribe_short"] = tribe_row["name_short"]
        except (ValueError, TypeError):
            pass
        results.append(entry)

    return results


def detect_corp_rivalries(
    db: sqlite3.Connection,
    limit: int = 10,
) -> list[dict]:
    """Detect corporations with mutual kill activity."""
    # Get killmails with corp info
    rows = db.execute(
        """SELECT victim_corp_id, attacker_corp_ids
           FROM killmails
           WHERE victim_corp_id != '' AND attacker_corp_ids != '[]'"""
    ).fetchall()

    # Count inter-corp kills
    from collections import defaultdict

    corp_kills: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        victim_corp = row["victim_corp_id"]
        try:
            attacker_corps = json.loads(row["attacker_corp_ids"])
            for ac in attacker_corps:
                if ac and ac != victim_corp:
                    corp_kills[(str(ac), victim_corp)] += 1
        except (json.JSONDecodeError, TypeError):
            continue

    # Find mutual rivalries
    rivalries = []
    seen: set[tuple[str, str]] = set()
    for (corp_a, corp_b), kills_a_to_b in corp_kills.items():
        pair = tuple(sorted([corp_a, corp_b]))
        if pair in seen:
            continue
        reverse = corp_kills.get((corp_b, corp_a), 0)
        if reverse > 0:
            seen.add(pair)
            rivalries.append(
                {
                    "corp_1": corp_a,
                    "corp_2": corp_b,
                    "kills_1_to_2": kills_a_to_b,
                    "kills_2_to_1": reverse,
                    "total": kills_a_to_b + reverse,
                }
            )

    rivalries.sort(key=lambda r: r["total"], reverse=True)
    return rivalries[:limit]
