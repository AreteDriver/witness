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

    # -- Solar system names (so hotzones/dossiers show real names, not raw IDs) --
    if not quiet:
        print("Seeding solar system names...")
    for sys_name in SYSTEMS:
        sys_id = _mid("sys", sys_name)
        conn.execute(
            "INSERT OR IGNORE INTO solar_systems (solar_system_id, name) VALUES (?, ?)",
            (sys_id, sys_name),
        )
    conn.commit()

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

    # -- Clone Blueprints --
    if not quiet:
        print("Seeding clone blueprints...")
    blueprints = [
        ("Standard Clone", 1, 300),
        ("Enhanced Clone", 2, 600),
        ("Augmented Clone", 3, 1200),
        ("Combat Clone", 4, 1800),
    ]
    bp_ids = []
    for bp_name, tier, mtime in blueprints:
        bp_id = _mid("bp", bp_name)
        bp_ids.append(bp_id)
        conn.execute(
            "INSERT INTO clone_blueprints (blueprint_id,name,tier,"
            "materials,manufacture_time_sec) VALUES (?,?,?,?,?)",
            (
                bp_id,
                bp_name,
                tier,
                json.dumps({"biomass": tier * 50, "nanites": tier * 20}),
                mtime,
            ),
        )
    conn.commit()

    # -- Orbital Zones --
    if not quiet:
        print("Seeding orbital zones...")
    zone_names = [
        "Theta Orbital",
        "Kappa Station",
        "Lambda Ring",
        "Sigma Perimeter",
        "Tau Anchorage",
        "Upsilon Dock",
        "Phi Relay",
    ]
    zone_tiers = [0, 1, 2, 0, 1, 3, 2]
    zones = []
    for i, zname in enumerate(zone_names):
        zid = _mid("zone", zname)
        sys_id = _mid("sys", SYSTEMS[i % len(SYSTEMS)])
        tier = zone_tiers[i]
        last_scan = now - random.randint(0, 2 * DAY)
        zones.append({"id": zid, "name": zname, "sys": sys_id, "tier": tier})
        conn.execute(
            "INSERT INTO orbital_zones (zone_id,name,solar_system_id,"
            "x,y,z,feral_ai_tier,last_scanned) VALUES (?,?,?,?,?,?,?,?)",
            (
                zid,
                zname,
                sys_id,
                random.uniform(-1e9, 1e9),
                random.uniform(-1e9, 1e9),
                random.uniform(-1e9, 1e9),
                tier,
                last_scan,
            ),
        )
    conn.commit()

    # -- Feral AI Events --
    if not quiet:
        print("Seeding feral AI events...")
    feral_event_types = ["tier_change", "escalation", "de-escalation", "surge"]
    feral_severities = ["info", "warning", "critical"]
    feral_count = 0
    # Escalation arcs for first two zones with tier > 0
    for z in zones[:3]:
        if z["tier"] == 0:
            continue
        arc_ts = start + random.randint(0, 3 * DAY)
        for step in range(z["tier"]):
            conn.execute(
                "INSERT INTO feral_ai_events (zone_id,event_type,old_tier,"
                "new_tier,severity,timestamp) VALUES (?,?,?,?,?,?)",
                (
                    z["id"],
                    "escalation",
                    step,
                    step + 1,
                    "warning" if step < 2 else "critical",
                    arc_ts + step * random.randint(3600, DAY),
                ),
            )
            feral_count += 1
    # Random events for remaining slots
    while feral_count < 13:
        z = random.choice(zones)
        old_t = random.randint(0, 2)
        new_t = old_t + random.choice([-1, 1])
        new_t = max(0, min(3, new_t))
        conn.execute(
            "INSERT INTO feral_ai_events (zone_id,event_type,old_tier,"
            "new_tier,severity,timestamp) VALUES (?,?,?,?,?,?)",
            (
                z["id"],
                random.choice(feral_event_types),
                old_t,
                new_t,
                random.choice(feral_severities),
                start + random.randint(0, 6 * DAY),
            ),
        )
        feral_count += 1
    conn.commit()

    # -- Scans --
    if not quiet:
        print("Seeding scans...")
    scan_results = ["CLEAR", "ANOMALY", "HOSTILE", "UNKNOWN"]
    scan_weights = [0.4, 0.25, 0.2, 0.15]
    scan_count = random.randint(22, 28)
    for s in range(scan_count):
        z = random.choice(zones)
        p = random.choice(pilots)
        result = random.choices(scan_results, weights=scan_weights, k=1)[0]
        conn.execute(
            "INSERT INTO scans (scan_id,zone_id,scanner_id,scanner_name,"
            "result_type,result_data,scanned_at) VALUES (?,?,?,?,?,?,?)",
            (
                f"scan-{s:04d}",
                z["id"],
                p["id"],
                p["name"],
                result,
                json.dumps({"signal_strength": round(random.uniform(0.1, 1.0), 2)}),
                start + random.randint(0, 6 * DAY),
            ),
        )
    conn.commit()

    # -- Scan Intel --
    if not quiet:
        print("Seeding scan intel...")
    threat_sigs = [
        "feral_swarm",
        "energy_spike",
        "unknown_signature",
        "phase_anomaly",
        "dormant_hive",
    ]
    anomaly_types = ["spatial_rift", "energy_bloom", "signal_ghost", "mass_shadow"]
    intel_count = 0
    for z in zones:
        hostile_scans = _count(
            conn,
            "SELECT COUNT(*) as cnt FROM scans "
            "WHERE zone_id=? AND result_type IN ('HOSTILE','ANOMALY')",
            (z["id"],),
        )
        if hostile_scans > 0:
            conn.execute(
                "INSERT INTO scan_intel (zone_id,threat_signature,"
                "anomaly_type,confidence,reported_at) VALUES (?,?,?,?,?)",
                (
                    z["id"],
                    random.choice(threat_sigs),
                    random.choice(anomaly_types),
                    round(random.uniform(0.4, 0.95), 2),
                    now - random.randint(0, 2 * DAY),
                ),
            )
            intel_count += 1
    # Pad to at least 5 intel entries
    while intel_count < 5:
        z = random.choice(zones)
        conn.execute(
            "INSERT INTO scan_intel (zone_id,threat_signature,"
            "anomaly_type,confidence,reported_at) VALUES (?,?,?,?,?)",
            (
                z["id"],
                random.choice(threat_sigs),
                random.choice(anomaly_types),
                round(random.uniform(0.3, 0.85), 2),
                now - random.randint(0, 3 * DAY),
            ),
        )
        intel_count += 1
    conn.commit()

    # -- Clones --
    if not quiet:
        print("Seeding clones...")
    clone_statuses = ["active", "manufacturing"]
    clone_count = random.randint(8, 12)
    for c in range(clone_count):
        p = pilots[c % len(pilots)]
        z = random.choice(zones)
        status = random.choices(clone_statuses, weights=[0.7, 0.3], k=1)[0]
        conn.execute(
            "INSERT INTO clones (clone_id,owner_id,owner_name,blueprint_id,"
            "status,location_zone_id,manufactured_at) VALUES (?,?,?,?,?,?,?)",
            (
                f"clone-{c:04d}",
                p["id"],
                p["name"],
                random.choice(bp_ids),
                status,
                z["id"],
                start + random.randint(0, 5 * DAY),
            ),
        )
    conn.commit()

    # -- Crowns --
    if not quiet:
        print("Seeding crowns...")
    crown_types = ["warrior", "merchant", "explorer", "diplomat", "engineer"]
    crown_count = random.randint(10, 15)
    for cr in range(crown_count):
        p = pilots[cr % len(pilots)]
        ct = random.choice(crown_types)
        conn.execute(
            "INSERT INTO crowns (crown_id,character_id,character_name,"
            "crown_type,attributes,chain_tx_id,equipped_at) VALUES (?,?,?,?,?,?,?)",
            (
                f"crown-{cr:04d}",
                p["id"],
                p["name"],
                ct,
                json.dumps({"rank": random.randint(1, 5), "bonus": f"{ct}_mastery"}),
                f"0x{random.randbytes(16).hex()}",
                start + random.randint(0, 6 * DAY),
            ),
        )
    conn.commit()

    # -- Summary --
    if not quiet:
        print(f"\n=== Demo DB Ready ({db_path}) ===")
        for t in (
            "entities",
            "killmails",
            "gate_events",
            "entity_titles",
            "story_feed",
            "orbital_zones",
            "feral_ai_events",
            "scans",
            "scan_intel",
            "clones",
            "clone_blueprints",
            "crowns",
        ):
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
