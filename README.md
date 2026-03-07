# Witness — The Living Memory of EVE Frontier

> **Chain archaeology + AI intelligence + locator agent.**
> Every gate transit, every killmail, every entity on-chain — cataloged, analyzed, named.

**[Live Demo](https://witness-evefrontier.fly.dev)** | [API Docs](#api-endpoints) | [Discord Bot](#discord-bot)

---

## What is Witness?

Witness reads the EVE Frontier blockchain like a history book. It watches the World API, ingests every on-chain event, resolves entities, and generates intelligence — from deterministic earned titles to AI-written dossiers.

The chain never forgets. Neither does Witness.

### Live Data (as of launch)
- **4,795 killmails** ingested and analyzed
- **35,278 smart assemblies** (gates, turrets, storage, manufacturing)
- **36,013 entities** tracked with behavioral fingerprints
- **190 killers** with confirmed kill counts
- **170 earned titles** computed from on-chain stats
- **220 story feed items** auto-generated from event patterns

---

## Features

### Chain Archaeology (Free)
- **Entity Dossiers** — Full profiles with stats, timelines, danger ratings
- **Behavioral Fingerprints** — Temporal patterns, route analysis, social networks, threat assessment, OPSEC scoring
- **Earned Titles** — Deterministic names from chain stats: "The Reaper" (50+ kills), "The Ghost" (30+ transits, zero combat), "The Meatgrinder" (20+ nearby kills on a gate)
- **Story Feed** — Auto-generated news: engagement clusters, new entity appearances, hunter milestones
- **Leaderboards** — Top killers, most deaths, deadliest gates, most traveled
- **Alt Detection** — Fingerprint comparison to identify likely alts and fleet mates
- **AI Narratives** — Entity dossiers and battle reports generated from chain data

### The Oracle (Intelligence Layer)
- **Standing Watches** — Monitor entities, gates, systems with Discord/webhook alerts
- **Movement Detection** — Know when a target transits any gate
- **Traffic Spike Alerts** — Unusual gate activity notifications
- **Killmail Proximity** — Instant notification when ships die in monitored systems

---

## Architecture

```
World API (30s polling) → Poller → SQLite WAL
                                       ↓
                    ┌──────────────────┼──────────────────┐
                    ↓                  ↓                  ↓
             Entity Resolver    Naming Engine      Story Feed
                    ↓                  ↓                  ↓
             Fingerprint       Earned Titles      Auto-News
                Builder              ↓                  ↓
                    ↓           ┌─────┴─────┐           ↓
                    ↓           ↓           ↓           ↓
               FastAPI API ←────────────────────────────┘
                    ↓
          ┌─────────┼─────────┐
          ↓         ↓         ↓
    React SPA   Discord   Webhooks
                  Bot
```

### Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLite WAL
- **Frontend**: React 19, Vite 7, Tailwind CSS 4, TypeScript
- **Intelligence**: Anthropic API (Claude) for narrative generation
- **Bot**: discord.py with slash commands
- **Deployment**: Docker, Fly.io
- **Ingestion**: Never-crash poller with pagination, error isolation

### Design Principles
1. **The poller must never crash** — all errors logged, never raised
2. **Killmails are first-class data** — the only durable positional signal
3. **Deterministic titles** — same data = same names, everyone sees the same thing
4. **Cache AI narratives** — same entity + same events = cached response
5. **Template fallback** — narratives work without API key via rule-based generation

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/AreteDriver/witness.git
cd witness
pip install -e ".[dev]"

# Configure (optional — works without API keys)
cp .env.example .env

# Backfill historical data
python -m scripts.backfill

# Run
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker compose up -d
# → http://localhost:8000
```

---

## API Endpoints

All endpoints under `/api/` prefix.

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Service health + table counts |
| `/api/entities` | GET | List entities (filter, sort, paginate) |
| `/api/entity/{id}` | GET | Full entity dossier |
| `/api/entity/{id}/fingerprint` | GET | Behavioral fingerprint (temporal, route, social, threat, OPSEC) |
| `/api/entity/{id}/timeline` | GET | Unified event timeline with delta analysis |
| `/api/entity/{id}/narrative` | GET | AI-generated or template dossier narrative |
| `/api/feed` | GET | Story feed (auto-generated news) |
| `/api/leaderboard/{category}` | GET | Rankings: `top_killers`, `most_deaths`, `most_traveled`, `deadliest_gates`, `most_active_gates` |
| `/api/titles` | GET | Entities with earned titles |
| `/api/search?q=` | GET | Search entities by name or address |
| `/api/fingerprint/compare` | GET | Compare two entity fingerprints (alt detection) |
| `/api/battle-report` | POST | AI battle analysis from event sequence |
| `/api/watches` | POST | Create standing intelligence watch |
| `/api/watches/{id}` | DELETE | Remove watch |

---

## Discord Bot

5 slash commands for in-game intelligence:

| Command | Description |
|---|---|
| `/witness <name>` | Entity lookup — stats, titles, threat level, OPSEC rating |
| `/killfeed [count]` | Latest killmails with timestamps |
| `/leaderboard <category>` | Top killers, most deaths, most traveled |
| `/feed` | Recent story feed items |
| `/compare <entity1> <entity2>` | Fingerprint comparison — alt detection |

Set `WITNESS_DISCORD_TOKEN` to activate.

---

## Dashboard

React SPA with three views:

- **Intelligence** — Search any entity, view fingerprint card (temporal/route/social/threat profiles), activity heatmap, event timeline, AI narrative
- **Compare** — Side-by-side fingerprint comparison with alt/fleet-mate detection
- **Feed & Rankings** — Live story feed + leaderboard with category switching

---

## Earned Titles

Deterministic titles computed from on-chain stats. Same data = same title for everyone.

### Character Titles
| Title | Criteria |
|---|---|
| The Reaper | 50+ kills |
| The Hunter | 20+ kills |
| The Pathfinder | 50+ gate transits |
| The Wanderer | 20+ gate transits |
| The Marked | 10+ deaths |
| The Survivor | 0 deaths, 50+ events |
| The Ghost | 30+ transits, 0 kills, 0 deaths |

### Gate Titles
| Title | Criteria |
|---|---|
| The Meatgrinder | 20+ nearby killmails |
| The Bloodgate | 10+ nearby killmails |
| The Highway | 1000+ transits |
| The Vault Gate | 50+ transits, 0 nearby kills |
| The Crossroads | 100+ unique pilots |

---

## Development

```bash
# Test (132 passing, 89% coverage)
pytest tests/ -v

# Lint
ruff check backend/ tests/ && ruff format backend/ tests/

# Coverage
pytest --cov=backend --cov-fail-under=80 tests/
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `WITNESS_WORLD_API_BASE` | blockchain-gateway-stillness... | World API endpoint |
| `WITNESS_POLL_INTERVAL_SECONDS` | 30 | Polling interval |
| `WITNESS_DB_PATH` | data/witness.db | SQLite database path |
| `WITNESS_ANTHROPIC_API_KEY` | (empty) | Enables AI narratives (template fallback without) |
| `WITNESS_DISCORD_TOKEN` | (empty) | Enables Discord bot |
| `WITNESS_DISCORD_WEBHOOK_URL` | (empty) | Alert delivery webhook |

---

## Hackathon

Built for the **EVE Frontier Hackathon** (March 2026).

**Category**: Community Tools / Intelligence

**Why Witness?** EVE Frontier generates permanent on-chain data but no tools exist to make sense of it. Witness turns raw blockchain events into actionable intelligence — who's dangerous, which gates are contested, when new players appear, and whether that pilot is an alt.

The chain is the source of truth. Witness is the interpreter.

---

## License

MIT
