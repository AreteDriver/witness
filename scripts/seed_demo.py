"""Seed database with realistic demo data.

Generates a believable EVE Frontier universe snapshot:
- Named gates with varying traffic
- Characters with behavioral patterns
- Corps with member activity
- Killmails with spatial clustering
- Story feed entries
- Entity titles

Run: python scripts/seed_demo.py
"""

import json
import random
import sqlite3
import time

from backend.analysis.naming_engine import refresh_all_titles
from backend.analysis.story_feed import (
    detect_gate_milestones,
    detect_killmail_clusters,
    detect_new_entities,
)
from backend.db.database import SCHEMA

GATE_NAMES = [
    "Starfall Passage",
    "The Crimson Gate",
    "Void's Edge",
    "Iron Threshold",
    "Obsidian Arch",
    "The Pale Crossing",
    "Ember Gate",
    "Silent Maw",
    "Dusk Corridor",
    "Warden's Gate",
    "The Fracture",
    "Abyssal Threshold",
    "Titan's Gate",
    "The Bleached Pass",
    "Nomad Gate",
]

SYSTEM_NAMES = [
    "J-7XRQ",
    "K-4LPV",
    "X-9BMN",
    "Q-2TAZ",
    "W-5HEK",
    "R-8YPD",
    "N-3FGC",
    "L-6VMS",
]

PILOT_NAMES = [
    "Kira Voss",
    "Dax Mortis",
    "Sable Wraith",
    "Orion Hale",
    "Vex Nullsec",
    "Lyra Ashborn",
    "Thane Darkwell",
    "Nyx Stormcrow",
    "Jett Ironside",
    "Mira Solari",
    "Cass Blackthorn",
    "Reik Valdyr",
    "Zara Eclipse",
    "Holt Drifter",
    "Pike Vanguard",
    "Nova Trace",
    "Kai Sunder",
    "Rune Ashfield",
    "Talon Graves",
    "Ember Kline",
]

CORP_NAMES = [
    "Shadow Syndicate",
    "Iron Dominion",
    "Void Collective",
    "Frontier Guard",
    "Dead Orbit",
]


def _make_id(prefix: str, name: str) -> str:
    return f"{prefix}-{name.lower().replace(' ', '-')[:20]}"


def seed(db_path: str = "data/demo.db", quiet: bool = False):
    """Generate and populate demo database."""
    import os

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    now = int(time.time())
    day = 86400
    history_start = now - 14 * day  # 2 weeks of history

    # --- Create corps ---
    corps = {}
    for name in CORP_NAMES:
        corp_id = _make_id("corp", name)
        corps[corp_id] = name

    # --- Create pilots with behavioral archetypes ---
    pilots = []
    archetypes = [
        # (archetype, peak_hour, gate_concentration, kill_tendency)
        ("routine", 14, 0.6, 0.1),  # predictable trader
        ("routine", 20, 0.5, 0.05),
        ("hunter", 2, 0.3, 0.8),  # night hunter
        ("hunter", 22, 0.2, 0.9),
        ("ghost", 4, 0.1, 0.0),  # untraceable explorer
        ("nomad", None, 0.15, 0.2),  # no pattern
        ("routine", 16, 0.7, 0.0),  # highly predictable
        ("hunter", 0, 0.25, 0.7),
        ("ghost", 10, 0.1, 0.0),
        ("nomad", None, 0.1, 0.3),
        ("routine", 18, 0.5, 0.15),
        ("hunter", 3, 0.3, 0.6),
        ("ghost", 8, 0.12, 0.0),
        ("nomad", None, 0.2, 0.1),
        ("routine", 12, 0.55, 0.05),
        ("hunter", 1, 0.35, 0.75),
        ("ghost", 6, 0.08, 0.0),
        ("nomad", None, 0.18, 0.25),
        ("routine", 15, 0.45, 0.1),
        ("hunter", 23, 0.28, 0.85),
    ]

    for i, name in enumerate(PILOT_NAMES):
        archetype, peak_hour, gate_conc, kill_tend = archetypes[i % len(archetypes)]
        corp_id = list(corps.keys())[i % len(corps)]
        pilot_id = _make_id("char", name)
        pilots.append(
            {
                "id": pilot_id,
                "name": name,
                "corp_id": corp_id,
                "archetype": archetype,
                "peak_hour": peak_hour,
                "gate_concentration": gate_conc,
                "kill_tendency": kill_tend,
            }
        )

    # --- Create gates with traffic profiles ---
    gates = []
    for i, name in enumerate(GATE_NAMES):
        gate_id = _make_id("gate", name)
        system_id = _make_id("sys", SYSTEM_NAMES[i % len(SYSTEM_NAMES)])
        gates.append(
            {
                "id": gate_id,
                "name": name,
                "system_id": system_id,
                "traffic_weight": random.uniform(0.3, 1.0),
            }
        )

    # --- Generate gate events ---
    if not quiet:
        print("Generating gate events...")

    gate_event_count = 0
    for pilot in pilots:
        # Number of events based on archetype
        if pilot["archetype"] == "ghost":
            n_events = random.randint(30, 60)
        elif pilot["archetype"] == "nomad":
            n_events = random.randint(80, 150)
        else:
            n_events = random.randint(100, 300)

        # Pick preferred gates based on concentration
        n_preferred = max(1, int(len(gates) * pilot["gate_concentration"]))
        preferred_gates = random.sample(gates, n_preferred)

        for _ in range(n_events):
            # Time distribution based on archetype
            if pilot["peak_hour"] is not None:
                # Gaussian around peak hour
                hour = int(random.gauss(pilot["peak_hour"], 3)) % 24
            else:
                hour = random.randint(0, 23)

            # Random day in history
            day_offset = random.randint(0, 13)
            ts = history_start + day_offset * day + hour * 3600
            ts += random.randint(0, 3599)  # jitter within hour

            # Pick gate (weighted toward preferred)
            if random.random() < 0.7:
                gate = random.choice(preferred_gates)
            else:
                gate = random.choice(gates)

            conn.execute(
                "INSERT INTO gate_events "
                "(gate_id, gate_name, character_id, corp_id, "
                "solar_system_id, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    gate["id"],
                    gate["name"],
                    pilot["id"],
                    pilot["corp_id"],
                    gate["system_id"],
                    ts,
                ),
            )
            gate_event_count += 1

    conn.commit()
    if not quiet:
        print(f"  {gate_event_count} gate events")

    # --- Generate killmails ---
    if not quiet:
        print("Generating killmails...")

    killmail_count = 0
    hunters = [p for p in pilots if p["kill_tendency"] > 0.3]

    for _ in range(200):
        attacker = random.choice(hunters)
        victim = random.choice([p for p in pilots if p["id"] != attacker["id"]])
        gate = random.choice(gates)
        ts = history_start + random.randint(0, 13 * day)

        # Cluster some kills in same system/time
        if random.random() < 0.3 and killmail_count > 0:
            ts = ts - random.randint(0, 1800)  # within 30 min

        conn.execute(
            "INSERT INTO killmails "
            "(killmail_id, victim_character_id, victim_corp_id, "
            "attacker_character_ids, attacker_corp_ids, "
            "solar_system_id, x, y, z, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"km-{killmail_count:04d}",
                victim["id"],
                victim["corp_id"],
                json.dumps([attacker["id"]]),
                json.dumps([attacker["corp_id"]]),
                gate["system_id"],
                random.uniform(-1e9, 1e9),
                random.uniform(-1e9, 1e9),
                random.uniform(-1e9, 1e9),
                ts,
            ),
        )
        killmail_count += 1

    conn.commit()
    if not quiet:
        print(f"  {killmail_count} killmails")

    # --- Build entities from events ---
    if not quiet:
        print("Building entities...")

    # Characters
    for pilot in pilots:
        kills = conn.execute(
            "SELECT COUNT(*) as cnt FROM killmails WHERE attacker_character_ids LIKE ?",
            (f'%"{pilot["id"]}"%',),
        ).fetchone()["cnt"]
        deaths = conn.execute(
            "SELECT COUNT(*) as cnt FROM killmails WHERE victim_character_id = ?",
            (pilot["id"],),
        ).fetchone()["cnt"]
        gate_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM gate_events WHERE character_id = ?",
            (pilot["id"],),
        ).fetchone()["cnt"]
        first = conn.execute(
            "SELECT MIN(timestamp) as ts FROM gate_events WHERE character_id = ?",
            (pilot["id"],),
        ).fetchone()["ts"]
        last = conn.execute(
            "SELECT MAX(timestamp) as ts FROM gate_events WHERE character_id = ?",
            (pilot["id"],),
        ).fetchone()["ts"]

        conn.execute(
            "INSERT INTO entities "
            "(entity_id, entity_type, display_name, corp_id, "
            "first_seen, last_seen, event_count, "
            "kill_count, death_count, gate_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pilot["id"],
                "character",
                pilot["name"],
                pilot["corp_id"],
                first or history_start,
                last or now,
                gate_count + kills + deaths,
                kills,
                deaths,
                gate_count,
            ),
        )

    # Gates
    for gate in gates:
        event_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM gate_events WHERE gate_id = ?",
            (gate["id"],),
        ).fetchone()["cnt"]
        first = conn.execute(
            "SELECT MIN(timestamp) as ts FROM gate_events WHERE gate_id = ?",
            (gate["id"],),
        ).fetchone()["ts"]
        last = conn.execute(
            "SELECT MAX(timestamp) as ts FROM gate_events WHERE gate_id = ?",
            (gate["id"],),
        ).fetchone()["ts"]

        conn.execute(
            "INSERT INTO entities "
            "(entity_id, entity_type, display_name, "
            "first_seen, last_seen, event_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                gate["id"],
                "gate",
                gate["name"],
                first or history_start,
                last or now,
                event_count,
            ),
        )

    conn.commit()
    if not quiet:
        print(f"  {len(pilots)} characters, {len(gates)} gates")

    # --- Generate titles ---
    if not quiet:
        print("Computing titles...")
    title_count = refresh_all_titles(conn)
    if not quiet:
        print(f"  {title_count} titles earned")

    # --- Generate story feed ---
    if not quiet:
        print("Generating story feed...")
    clusters = detect_killmail_clusters(conn)
    new_ents = detect_new_entities(conn)
    milestones = detect_gate_milestones(conn)
    conn.commit()
    if not quiet:
        print(f"  {clusters} clusters, {new_ents} new entities, {milestones} milestones")

    # --- Summary ---
    if not quiet:
        print("\n=== Demo Database Ready ===")
        print(f"Path: {db_path}")
        for table in (
            "gate_events",
            "killmails",
            "entities",
            "entity_titles",
            "story_feed",
        ):
            cnt = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()["cnt"]
            print(f"  {table}: {cnt}")

    conn.close()
    return db_path


if __name__ == "__main__":
    seed()
