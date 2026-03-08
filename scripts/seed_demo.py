"""Seed database with realistic EVE Frontier demo data for hackathon judges.

Run: python scripts/seed_demo.py [--db PATH]
  or: python -m scripts.seed_demo [--db PATH]
"""

import json
import random
import sqlite3
import sys
import time
from pathlib import Path

from backend.analysis.naming_engine import refresh_all_titles
from backend.analysis.story_feed import (
    detect_gate_milestones,
    detect_killmail_clusters,
    detect_new_entities,
)
from backend.core.config import settings
from backend.db.database import SCHEMA

PILOTS = [
    "Asterix",
    "Kali Nox",
    "Void Runner",
    "Ghost Protocol",
    "Omega Prime",
    "Sable Wraith",
    "Nyx Stormcrow",
    "Jett Ironside",
    "Lyra Ashborn",
    "Dax Mortis",
    "Zara Eclipse",
    "Pike Vanguard",
    "Nova Trace",
    "Talon Graves",
    "Ember Kline",
    "Reik Valdyr",
    "Mira Solari",
    "Orion Hale",
    "Cass Blackthorn",
    "Kai Sunder",
    "Rune Ashfield",
]
GATES = [
    "Alpha Gate",
    "Bravo Conduit",
    "Nexus Relay",
    "Void's Edge",
    "Iron Threshold",
    "Obsidian Arch",
    "Ember Gate",
    "Silent Maw",
    "Dusk Corridor",
    "Warden's Gate",
    "The Fracture",
    "Titan's Gate",
]
SYSTEMS = ["J-001", "K-117", "Z-42", "X-9BMN", "Q-2TAZ", "W-5HEK", "R-8YPD", "N-3FGC"]
CORPS = [
    "Shadow Syndicate",
    "Iron Dominion",
    "Void Collective",
    "Frontier Guard",
    "Dead Orbit",
    "Crimson Fleet",
]
# (peak_hour|None, gate_concentration, kill_tendency)
ARCHETYPES = [
    (14, 0.6, 0.1),
    (20, 0.5, 0.05),
    (2, 0.3, 0.8),
    (22, 0.2, 0.9),
    (4, 0.1, 0.0),
    (None, 0.15, 0.2),
    (16, 0.7, 0.0),
    (0, 0.25, 0.7),
    (10, 0.1, 0.0),
    (None, 0.1, 0.3),
    (18, 0.5, 0.15),
    (3, 0.3, 0.6),
    (8, 0.12, 0.0),
    (None, 0.2, 0.1),
    (12, 0.55, 0.05),
    (1, 0.35, 0.75),
    (6, 0.08, 0.0),
    (None, 0.18, 0.25),
    (15, 0.45, 0.1),
    (23, 0.28, 0.85),
    (19, 0.4, 0.12),
]
DAY = 86400


def _mid(prefix: str, name: str) -> str:
    return f"{prefix}-{name.lower().replace(' ', '-')[:20]}"


def _count(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()["cnt"]


def _ts_range(conn, col, table, where_col, where_val):
    r = conn.execute(
        f"SELECT MIN({col}) as lo, MAX({col}) as hi FROM {table} WHERE {where_col}=?",
        (where_val,),
    ).fetchone()
    return r["lo"], r["hi"]


def seed(db_path: str, quiet: bool = False) -> str:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    if _count(conn, "SELECT COUNT(*) as cnt FROM entities") > 0:
        if not quiet:
            print(f"Already populated: {db_path} -- skipping.")
        conn.close()
        return db_path

    now = int(time.time())
    start = now - 7 * DAY
    corp_ids = [_mid("corp", c) for c in CORPS]

    pilots = []
    for i, name in enumerate(PILOTS):
        peak, gc, kt = ARCHETYPES[i % len(ARCHETYPES)]
        pilots.append(
            {
                "id": _mid("char", name),
                "name": name,
                "corp": corp_ids[i % len(corp_ids)],
                "peak": peak,
                "gc": gc,
                "kt": kt,
            }
        )

    gates = [
        {"id": _mid("gate", n), "name": n, "sys": _mid("sys", SYSTEMS[i % len(SYSTEMS)])}
        for i, n in enumerate(GATES)
    ]

    # -- Gate events --
    if not quiet:
        print("Seeding gate events...")
    ge = 0
    for p in pilots:
        n = random.randint(5, 12) if p["gc"] < 0.15 else random.randint(12, 35)
        pref = random.sample(gates, max(1, int(len(gates) * p["gc"])))
        for _ in range(n):
            if p["peak"] is not None:
                h = int(random.gauss(p["peak"], 3)) % 24
            else:
                h = random.randint(0, 23)
            ts = start + random.randint(0, 6) * DAY + h * 3600 + random.randint(0, 3599)
            g = random.choice(pref if random.random() < 0.7 else gates)
            conn.execute(
                "INSERT INTO gate_events (gate_id,gate_name,character_id,corp_id,"
                "solar_system_id,direction,timestamp) VALUES (?,?,?,?,?,?,?)",
                (
                    g["id"],
                    g["name"],
                    p["id"],
                    p["corp"],
                    g["sys"],
                    random.choice(["inbound", "outbound"]),
                    ts,
                ),
            )
            ge += 1
    conn.commit()

    # -- Killmails (60) --
    if not quiet:
        print("Seeding killmails...")
    hunters = [p for p in pilots if p["kt"] > 0.3]
    for km in range(60):
        a = random.choice(hunters)
        v = random.choice([p for p in pilots if p["id"] != a["id"]])
        g = random.choice(gates)
        ts = start + random.randint(0, 6 * DAY)
        if random.random() < 0.3 and km > 0:
            ts -= random.randint(0, 1800)
        conn.execute(
            "INSERT INTO killmails (killmail_id,victim_character_id,victim_name,"
            "victim_corp_id,attacker_character_ids,attacker_corp_ids,"
            "solar_system_id,x,y,z,timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"km-{km:04d}",
                v["id"],
                v["name"],
                v["corp"],
                json.dumps([a["id"]]),
                json.dumps([a["corp"]]),
                g["sys"],
                random.uniform(-1e9, 1e9),
                random.uniform(-1e9, 1e9),
                random.uniform(-1e9, 1e9),
                ts,
            ),
        )
    conn.commit()

    # -- Entities from events --
    if not quiet:
        print("Building entities...")
    for p in pilots:
        kills = _count(
            conn,
            "SELECT COUNT(*) as cnt FROM killmails WHERE attacker_character_ids LIKE ?",
            (f'%"{p["id"]}"%',),
        )
        deaths = _count(
            conn,
            "SELECT COUNT(*) as cnt FROM killmails WHERE victim_character_id=?",
            (p["id"],),
        )
        gc = _count(
            conn,
            "SELECT COUNT(*) as cnt FROM gate_events WHERE character_id=?",
            (p["id"],),
        )
        lo, hi = _ts_range(conn, "timestamp", "gate_events", "character_id", p["id"])
        conn.execute(
            "INSERT INTO entities (entity_id,entity_type,display_name,corp_id,"
            "first_seen,last_seen,event_count,kill_count,death_count,gate_count) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                p["id"],
                "character",
                p["name"],
                p["corp"],
                lo or start,
                hi or now,
                gc + kills + deaths,
                kills,
                deaths,
                gc,
            ),
        )

    for g in gates:
        ec = _count(conn, "SELECT COUNT(*) as cnt FROM gate_events WHERE gate_id=?", (g["id"],))
        lo, hi = _ts_range(conn, "timestamp", "gate_events", "gate_id", g["id"])
        conn.execute(
            "INSERT INTO entities (entity_id,entity_type,display_name,"
            "first_seen,last_seen,event_count) VALUES (?,?,?,?,?,?)",
            (g["id"], "gate", g["name"], lo or start, hi or now, ec),
        )
    conn.commit()

    # -- Titles + story feed --
    if not quiet:
        print("Computing titles...")
    tc = refresh_all_titles(conn)
    if not quiet:
        print(f"  {tc} titles earned")
        print("Generating story feed...")
    cl = detect_killmail_clusters(conn)
    ne = detect_new_entities(conn)
    ms = detect_gate_milestones(conn)
    conn.commit()

    # -- Summary --
    if not quiet:
        print(f"\n=== Demo DB Ready ({db_path}) ===")
        for t in ("entities", "killmails", "gate_events", "entity_titles", "story_feed"):
            print(f"  {t}: {_count(conn, f'SELECT COUNT(*) as cnt FROM {t}')}")
        print(f"  story_feed breakdown: {cl} clusters, {ne} new, {ms} milestones")
        print(f"  gate_events total: {ge}")
    conn.close()
    return db_path


def main() -> None:
    db_path = settings.DB_PATH
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--db" and i + 1 < len(args):
            db_path = args[i + 1]
            break
    seed(db_path)


if __name__ == "__main__":
    main()
