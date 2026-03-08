"""SQLite database with WAL mode and FTS5.

Schema confirmed against blockchain-gateway-stillness.live.tech.evefrontier.com
v2 API on 2026-03-07.
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

-- Indexes
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
"""

_connection: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        db_path = Path(settings.DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(db_path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.executescript(SCHEMA)
        logger.info("Database initialized at %s", db_path)
    return _connection


def close_db() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
