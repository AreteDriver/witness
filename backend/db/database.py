"""SQLite database with WAL mode and FTS5.

Schema confirmed against blockchain-gateway-stillness.live.tech.evefrontier.com
v2 API on 2026-03-10. Live endpoints: killmails, smartassemblies,
smartcharacters, tribes, fuels, solarsystems, types.
C5 endpoints (orbitalzones, scans, clones, crowns) not yet live pre-reset.
"""

import sqlite3
from pathlib import Path

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS killmails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    killmail_id TEXT UNIQUE NOT NULL,
    victim_character_id TEXT,
    victim_name TEXT,
    victim_corp_id TEXT,
    attacker_character_ids TEXT,
    attacker_corp_ids TEXT,
    solar_system_id TEXT,
    x REAL,
    y REAL,
    z REAL,
    timestamp INTEGER NOT NULL,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS gate_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_id TEXT NOT NULL,
    gate_name TEXT,
    character_id TEXT,
    corp_id TEXT,
    solar_system_id TEXT,
    direction TEXT,
    timestamp INTEGER NOT NULL,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS smart_assemblies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assembly_id TEXT UNIQUE NOT NULL,
    assembly_type TEXT,
    name TEXT,
    state TEXT,
    solar_system_id TEXT,
    solar_system_name TEXT,
    owner_address TEXT,
    owner_name TEXT,
    x REAL,
    y REAL,
    z REAL,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    display_name TEXT,
    corp_id TEXT,
    first_seen INTEGER,
    last_seen INTEGER,
    event_count INTEGER DEFAULT 0,
    kill_count INTEGER DEFAULT 0,
    death_count INTEGER DEFAULT 0,
    gate_count INTEGER DEFAULT 0,
    updated_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS entity_titles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_type TEXT NOT NULL,
    evidence_hash TEXT,
    computed_at INTEGER DEFAULT (unixepoch()),
    inscription_count INTEGER DEFAULT 0,
    UNIQUE(entity_id, title)
);

CREATE TABLE IF NOT EXISTS watches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    watch_type TEXT NOT NULL,
    target_id TEXT,
    conditions TEXT,
    webhook_url TEXT,
    channel_id TEXT,
    active INTEGER DEFAULT 1,
    last_triggered INTEGER,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS narrative_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    narrative_type TEXT NOT NULL,
    content TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    generated_at INTEGER DEFAULT (unixepoch()),
    UNIQUE(entity_id, narrative_type, event_hash)
);

CREATE TABLE IF NOT EXISTS story_feed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    headline TEXT NOT NULL,
    body TEXT,
    entity_ids TEXT,
    severity TEXT DEFAULT 'info',
    timestamp INTEGER NOT NULL,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS watcher_subscriptions (
    wallet_address TEXT PRIMARY KEY,
    tier INTEGER NOT NULL DEFAULT 0,
    expires_at INTEGER NOT NULL DEFAULT 0,
    stripe_customer_id TEXT DEFAULT '',
    stripe_subscription_id TEXT DEFAULT '',
    payment_channel TEXT DEFAULT '',
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS eve_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_hash TEXT UNIQUE NOT NULL,
    character_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    expires_at INTEGER NOT NULL,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_eve_sessions_hash ON eve_sessions(session_hash);

CREATE TABLE IF NOT EXISTS wallet_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_hash TEXT UNIQUE NOT NULL,
    wallet_address TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_wallet_sessions_hash ON wallet_sessions(session_hash);

CREATE TABLE IF NOT EXISTS watch_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watch_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    severity TEXT DEFAULT 'info',
    read INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_watch_alerts_user ON watch_alerts(user_id, read, created_at DESC);

-- Reference data from live API

CREATE TABLE IF NOT EXISTS smart_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE NOT NULL,
    name TEXT,
    character_id TEXT,
    tribe_id TEXT,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS tribes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tribe_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_short TEXT,
    description TEXT,
    member_count INTEGER DEFAULT 0,
    tax_rate REAL DEFAULT 0,
    tribe_url TEXT,
    founded_at TEXT,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_smart_characters_name ON smart_characters(name);
CREATE INDEX IF NOT EXISTS idx_smart_characters_tribe ON smart_characters(tribe_id);
CREATE INDEX IF NOT EXISTS idx_tribes_name ON tribes(name);

-- Cycle 5: Shroud of Fear — new tables

CREATE TABLE IF NOT EXISTS orbital_zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT UNIQUE NOT NULL,
    name TEXT,
    solar_system_id TEXT,
    x REAL,  -- HIDDEN POST-CYCLE
    y REAL,  -- HIDDEN POST-CYCLE
    z REAL,  -- HIDDEN POST-CYCLE
    feral_ai_tier INTEGER DEFAULT 0,
    last_scanned INTEGER,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS feral_ai_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_tier INTEGER,
    new_tier INTEGER,
    severity TEXT DEFAULT 'info',
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    timestamp INTEGER NOT NULL,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT UNIQUE NOT NULL,
    zone_id TEXT NOT NULL,
    scanner_id TEXT,
    scanner_name TEXT,
    result_type TEXT NOT NULL,
    result_data TEXT,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    scanned_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_intel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT NOT NULL,
    threat_signature TEXT,
    anomaly_type TEXT,
    confidence REAL,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    reported_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS clones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clone_id TEXT UNIQUE NOT NULL,
    owner_id TEXT NOT NULL,
    owner_name TEXT,
    blueprint_id TEXT,
    status TEXT DEFAULT 'active',
    location_zone_id TEXT,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    manufactured_at INTEGER,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS clone_blueprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blueprint_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    tier INTEGER DEFAULT 1,
    materials TEXT,
    manufacture_time_sec INTEGER,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS crowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crown_id TEXT UNIQUE NOT NULL,
    character_id TEXT NOT NULL,
    character_name TEXT,
    crown_type TEXT,
    attributes TEXT,
    chain_tx_id TEXT,
    raw_json TEXT,
    cycle INTEGER DEFAULT 5,
    equipped_at INTEGER,
    ingested_at INTEGER DEFAULT (unixepoch())
);

-- 2-step gate permits (issued → consumed)
CREATE TABLE IF NOT EXISTS gate_permits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    permit_id TEXT NOT NULL,
    gate_id TEXT NOT NULL,
    character_id TEXT,
    solar_system_id TEXT,
    status TEXT NOT NULL DEFAULT 'issued',
    issued_at INTEGER,
    consumed_at INTEGER,
    cycle INTEGER DEFAULT 5,
    ingested_at INTEGER DEFAULT (unixepoch())
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gate_permits_id ON gate_permits(permit_id, status);
CREATE INDEX IF NOT EXISTS idx_gate_permits_gate ON gate_permits(gate_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_gate_permits_character ON gate_permits(character_id);

-- Solar system name lookup (from World API static data)
CREATE TABLE IF NOT EXISTS solar_systems (
    solar_system_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    constellation_id TEXT,
    region_id TEXT
);

-- Ship reference data (from World API /v2/ships)
CREATE TABLE IF NOT EXISTS ships (
    ship_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    class_id TEXT,
    class_name TEXT,
    armor INTEGER DEFAULT 0,
    shield INTEGER DEFAULT 0,
    structure INTEGER DEFAULT 0,
    high_slots INTEGER DEFAULT 0,
    medium_slots INTEGER DEFAULT 0,
    low_slots INTEGER DEFAULT 0,
    cpu_output INTEGER DEFAULT 0,
    powergrid_output INTEGER DEFAULT 0,
    max_velocity REAL DEFAULT 0,
    fuel_capacity INTEGER DEFAULT 0,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch())
);

-- Item type reference data (from World API /v2/types)
CREATE TABLE IF NOT EXISTS item_types (
    type_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    group_name TEXT,
    volume REAL DEFAULT 0,
    mass REAL DEFAULT 0,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch())
);

-- Constellation reference data (from World API /v2/constellations)
CREATE TABLE IF NOT EXISTS constellations (
    constellation_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_id TEXT,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch())
);

-- Gate link topology (from World API /v2/solarsystems/{id} gateLinks)
CREATE TABLE IF NOT EXISTS gate_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_id TEXT NOT NULL,
    gate_name TEXT,
    source_system_id TEXT NOT NULL,
    destination_system_id TEXT NOT NULL,
    x REAL,
    y REAL,
    z REAL,
    raw_json TEXT,
    ingested_at INTEGER DEFAULT (unixepoch()),
    UNIQUE(gate_id)
);

CREATE INDEX IF NOT EXISTS idx_gate_links_source ON gate_links(source_system_id);
CREATE INDEX IF NOT EXISTS idx_gate_links_dest ON gate_links(destination_system_id);
CREATE INDEX IF NOT EXISTS idx_item_types_category ON item_types(category);
CREATE INDEX IF NOT EXISTS idx_ships_class ON ships(class_name);
CREATE INDEX IF NOT EXISTS idx_constellations_region ON constellations(region_id);

-- AI token usage tracking
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    operation TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_tokens INTEGER DEFAULT 0,
    entity_id TEXT,
    created_at INTEGER DEFAULT (unixepoch())
);

-- NEXUS: builder webhook subscriptions
CREATE TABLE IF NOT EXISTS nexus_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    endpoint_url TEXT NOT NULL,
    filters TEXT NOT NULL DEFAULT '{}',
    active INTEGER DEFAULT 1,
    secret TEXT NOT NULL,
    wallet_address TEXT NOT NULL DEFAULT '',
    delivery_count INTEGER DEFAULT 0,
    last_delivered_at INTEGER,
    created_at INTEGER DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS nexus_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status_code INTEGER,
    success INTEGER DEFAULT 0,
    attempts INTEGER DEFAULT 1,
    error TEXT,
    delivered_at INTEGER DEFAULT (unixepoch()),
    FOREIGN KEY (subscription_id) REFERENCES nexus_subscriptions(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_nexus_subscriptions_active ON nexus_subscriptions(active);
CREATE INDEX IF NOT EXISTS idx_nexus_subscriptions_key ON nexus_subscriptions(api_key);
CREATE INDEX IF NOT EXISTS idx_nexus_deliveries_sub
    ON nexus_deliveries(subscription_id, delivered_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_killmails_timestamp ON killmails(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_killmails_system ON killmails(solar_system_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_killmails_victim ON killmails(victim_character_id);
CREATE INDEX IF NOT EXISTS idx_gate_events_timestamp ON gate_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gate_events_gate ON gate_events(gate_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gate_events_character ON gate_events(character_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_gate_events_corp ON gate_events(corp_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_corp ON entities(corp_id);
CREATE INDEX IF NOT EXISTS idx_watches_active ON watches(active, watch_type);
CREATE INDEX IF NOT EXISTS idx_story_feed_timestamp ON story_feed(timestamp DESC);

-- Cycle 5 indexes
CREATE INDEX IF NOT EXISTS idx_orbital_zones_tier ON orbital_zones(feral_ai_tier);
CREATE INDEX IF NOT EXISTS idx_feral_ai_events_zone ON feral_ai_events(zone_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scans_zone ON scans(zone_id, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_result ON scans(result_type, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_intel_zone ON scan_intel(zone_id, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_clones_owner ON clones(owner_id);
CREATE INDEX IF NOT EXISTS idx_clones_status ON clones(status);
CREATE INDEX IF NOT EXISTS idx_crowns_character ON crowns(character_id);
CREATE INDEX IF NOT EXISTS idx_crowns_type ON crowns(crown_type);
"""

MIGRATIONS = [
    "ALTER TABLE killmails ADD COLUMN cycle INTEGER DEFAULT 5",
    "ALTER TABLE gate_events ADD COLUMN cycle INTEGER DEFAULT 5",
    "ALTER TABLE nexus_subscriptions ADD COLUMN wallet_address TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE watcher_subscriptions ADD COLUMN stripe_customer_id TEXT DEFAULT ''",
    "ALTER TABLE watcher_subscriptions ADD COLUMN stripe_subscription_id TEXT DEFAULT ''",
    "ALTER TABLE watcher_subscriptions ADD COLUMN payment_channel TEXT DEFAULT ''",
    "ALTER TABLE solar_systems ADD COLUMN constellation_id TEXT",
    "ALTER TABLE solar_systems ADD COLUMN region_id TEXT",
]

_connection: sqlite3.Connection | None = None


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply ALTER TABLE migrations for existing databases."""
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
            logger.info("Migration applied: %s", sql[:60])
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                pass  # Already applied
            else:
                logger.warning("Migration skipped: %s", e)


def get_db() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        db_path = Path(settings.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(db_path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.executescript(SCHEMA)
        _run_migrations(_connection)
        logger.info("Database initialized at %s", db_path)
    return _connection


def close_db() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
