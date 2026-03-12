"""Entity resolver — builds dossiers from chain events.

Queries all event types for a given entity and produces a structured profile.
"""

import sqlite3
from dataclasses import dataclass, field

from backend.core.logger import get_logger

logger = get_logger("entity_resolver")


@dataclass
class EntityDossier:
    entity_id: str
    entity_type: str
    display_name: str
    first_seen: int
    last_seen: int
    event_count: int
    kill_count: int
    death_count: int
    gate_count: int
    corp_id: str | None

    # Computed stats
    killmails_nearby: int = 0
    unique_pilots: int = 0
    peak_hour: int | None = None
    danger_rating: str = "unknown"
    notable_events: list[dict] = field(default_factory=list)
    associated_corps: list[str] = field(default_factory=list)
    associated_characters: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)

    # Enriched from reference data
    tribe_name: str | None = None
    tribe_short: str | None = None
    character_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "display_name": self.display_name,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "event_count": self.event_count,
            "kill_count": self.kill_count,
            "death_count": self.death_count,
            "gate_count": self.gate_count,
            "corp_id": self.corp_id,
            "killmails_nearby": self.killmails_nearby,
            "unique_pilots": self.unique_pilots,
            "peak_hour": self.peak_hour,
            "danger_rating": self.danger_rating,
            "notable_events": self.notable_events,
            "associated_corps": self.associated_corps,
            "associated_characters": self.associated_characters,
            "titles": self.titles,
            "tribe_name": self.tribe_name,
            "tribe_short": self.tribe_short,
            "character_id": self.character_id,
        }


def resolve_entity(db: sqlite3.Connection, entity_id: str) -> EntityDossier | None:
    """Build a complete dossier for any entity ID."""
    row = db.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
    if not row:
        return None

    dossier = EntityDossier(
        entity_id=row["entity_id"],
        entity_type=row["entity_type"],
        display_name=row["display_name"] or row["entity_id"][:12],
        first_seen=row["first_seen"] or 0,
        last_seen=row["last_seen"] or 0,
        event_count=row["event_count"] or 0,
        kill_count=row["kill_count"] or 0,
        death_count=row["death_count"] or 0,
        gate_count=row["gate_count"] or 0,
        corp_id=row["corp_id"],
    )

    # Enrich based on entity type
    if dossier.entity_type == "gate":
        _enrich_gate(db, dossier)
    elif dossier.entity_type == "character":
        _enrich_character(db, dossier)

    # Load titles
    titles = db.execute(
        "SELECT title FROM entity_titles WHERE entity_id = ? ORDER BY inscription_count DESC",
        (entity_id,),
    ).fetchall()
    dossier.titles = [t["title"] for t in titles]

    return dossier


def _enrich_gate(db: sqlite3.Connection, dossier: EntityDossier) -> None:
    """Add gate-specific stats."""
    gate_id = dossier.entity_id

    # Unique pilots
    row = db.execute(
        "SELECT COUNT(DISTINCT character_id) as cnt FROM gate_events WHERE gate_id = ?",
        (gate_id,),
    ).fetchone()
    dossier.unique_pilots = row["cnt"] if row else 0

    # Peak hour (UTC)
    rows = db.execute(
        """SELECT (timestamp % 86400) / 3600 as hour, COUNT(*) as cnt
           FROM gate_events WHERE gate_id = ?
           GROUP BY hour ORDER BY cnt DESC LIMIT 1""",
        (gate_id,),
    ).fetchone()
    if rows:
        dossier.peak_hour = rows["hour"]

    # Nearby killmails (same solar system)
    system_row = db.execute(
        "SELECT solar_system_id FROM gate_events WHERE gate_id = ? LIMIT 1",
        (gate_id,),
    ).fetchone()
    if system_row and system_row["solar_system_id"]:
        km_row = db.execute(
            "SELECT COUNT(*) as cnt FROM killmails WHERE solar_system_id = ?",
            (system_row["solar_system_id"],),
        ).fetchone()
        dossier.killmails_nearby = km_row["cnt"] if km_row else 0

    # Danger rating based on killmail density
    if dossier.killmails_nearby > 20:
        dossier.danger_rating = "critical"
    elif dossier.killmails_nearby > 10:
        dossier.danger_rating = "high"
    elif dossier.killmails_nearby > 3:
        dossier.danger_rating = "medium"
    else:
        dossier.danger_rating = "low"

    # Associated corps (most frequent transitors)
    corps = db.execute(
        """SELECT corp_id, COUNT(*) as cnt FROM gate_events
           WHERE gate_id = ? AND corp_id != ''
           GROUP BY corp_id ORDER BY cnt DESC LIMIT 10""",
        (gate_id,),
    ).fetchall()
    dossier.associated_corps = [r["corp_id"] for r in corps]


def _enrich_character(db: sqlite3.Connection, dossier: EntityDossier) -> None:
    """Add character-specific stats."""
    char_id = dossier.entity_id

    # Enrich from smart_characters (name, tribe, character_id)
    sc_row = db.execute(
        "SELECT name, character_id, tribe_id FROM smart_characters WHERE address = ?",
        (char_id,),
    ).fetchone()
    if sc_row:
        # Overwrite if display_name is empty or just a truncated address
        if sc_row["name"] and (
            not dossier.display_name or dossier.display_name == dossier.entity_id[:12]
        ):
            dossier.display_name = sc_row["name"]
        dossier.character_id = sc_row["character_id"]
        tribe_id = sc_row["tribe_id"]
        if tribe_id:
            dossier.corp_id = str(tribe_id)
            tribe_row = db.execute(
                "SELECT name, name_short FROM tribes WHERE tribe_id = ?",
                (int(tribe_id),),
            ).fetchone()
            if tribe_row:
                dossier.tribe_name = tribe_row["name"]
                dossier.tribe_short = tribe_row["name_short"]

    # Tribe lookup from corp_id if not already resolved
    if dossier.corp_id and not dossier.tribe_name:
        try:
            tribe_row = db.execute(
                "SELECT name, name_short FROM tribes WHERE tribe_id = ?",
                (int(dossier.corp_id),),
            ).fetchone()
            if tribe_row:
                dossier.tribe_name = tribe_row["name"]
                dossier.tribe_short = tribe_row["name_short"]
        except (ValueError, TypeError):
            pass  # corp_id not a valid tribe_id

    # Gates used
    gates = db.execute(
        """SELECT DISTINCT gate_id FROM gate_events WHERE character_id = ?""",
        (char_id,),
    ).fetchall()
    dossier.gate_count = len(gates)

    # Associated characters (co-transitors within 5 min window)
    assoc = db.execute(
        """SELECT DISTINCT g2.character_id FROM gate_events g1
           JOIN gate_events g2 ON g1.gate_id = g2.gate_id
           AND ABS(g1.timestamp - g2.timestamp) < 300
           AND g1.character_id != g2.character_id
           WHERE g1.character_id = ?
           LIMIT 20""",
        (char_id,),
    ).fetchall()
    dossier.associated_characters = [r["character_id"] for r in assoc]
