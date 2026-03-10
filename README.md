# Witness — The Living Memory of EVE Frontier

> **Chain archaeology + AI intelligence + on-chain economy.**
> Every gate transit, every killmail, every entity on-chain — cataloged, analyzed, scored, enforced.
>
> *Witness doesn't just watch — it remembers, and the chain listens.*

**[Live Demo](https://witness-evefrontier.fly.dev)** | [API Docs](#api-endpoints) | [Discord Bot](#discord-bot) | [Assembly Guide](docs/ASSEMBLY_GUIDE.md)

---

## What is Witness?

Witness reads the EVE Frontier blockchain like a history book. It watches the World API, ingests every on-chain event, resolves entities, and generates intelligence — from deterministic earned titles to AI-written dossiers to on-chain reputation scores that gate Smart Assembly access.

The chain never forgets. Neither does Witness.

### Live Data (as of launch)
- **4,795 killmails** ingested and analyzed
- **35,278 smart assemblies** (gates, turrets, storage, manufacturing)
- **36,085 entities** tracked with behavioral fingerprints
- **190 killers** with confirmed kill counts (Asterix #1: 484 kills)
- **170 earned titles** computed from on-chain stats
- **224 story feed items** auto-generated from event patterns
- **457 tests** passing (80%+ coverage), all lint clean

---

## Features

### Chain Archaeology (Free)
- **Entity Dossiers** — Full profiles with stats, timelines, danger ratings
- **Behavioral Fingerprints** — Temporal patterns, route analysis, social networks, threat assessment, OPSEC scoring
- **Earned Titles** — Deterministic names from chain stats: "The Reaper" (50+ kills), "The Ghost" (30+ transits, zero combat), "The Meatgrinder" (20+ nearby kills on a gate)
- **Story Feed** — Auto-generated news: engagement clusters, streak milestones, new entity appearances, hunter milestones
- **Leaderboards** — Top killers, most deaths, deadliest gates, most traveled
- **Alt Detection** — Fingerprint comparison to identify likely alts and fleet mates
- **AI Narratives** — Entity dossiers and battle reports generated from chain data

### Tactical Intelligence
- **Kill Network** — Attacker→victim graph with vendetta detection (mutual kills between entities)
- **Danger Zones** — Solar systems ranked by kill density with time window filtering (24h/7d/30d/all)
- **Streak Tracker** — Kill streak tracking, momentum status (hot/active/cooling/dormant), active hunter board
- **Corp Intel** — Corporation combat rankings, member aggregation, inter-corp rivalry detection

### Reputation System (NEW)
- **On-Chain Trust Scoring** — Every entity scored 0-100 across 6 dimensions:
  - **Combat Honor** — Clean kills vs ganking behavior
  - **Target Diversity** — Range of opponents (not farming the same pilot)
  - **Reciprocity** — Fair fights vs one-sided engagements
  - **Consistency** — Stable behavior over time (not erratic)
  - **Community** — Gate construction, assembly deployment, positive-sum actions
  - **Restraint** — Avoidance of excessive force, new player protection
- **Smart Assembly Gating** — Reputation scores flow back on-chain. Deployers can set thresholds: "deny docking if trust < 40"
- **Designed for Smart Contracts** — Scores structured for direct consumption by WatcherSystem.sol

### Real-Time Intelligence
- **Server-Sent Events** — Live push feed for kills, alerts, and system status
- **Live Ticker** — Dashboard shows real-time events as they happen (kills, alerts, status)
- **EVE SSO Login** — Verify character identity via CCP's OAuth2, cross-reference with on-chain data

### The Oracle (Intelligence Layer)
- **Standing Watches** — Monitor entities, gates, systems with Discord/webhook alerts
- **Movement Detection** — Know when a target transits any gate
- **Traffic Spike Alerts** — Unusual gate activity notifications
- **Killmail Proximity** — Instant notification when ships die in monitored systems

### On-Chain Economy
- **Smart Contract Subscriptions** — [WatcherSystem.sol](#smart-contract) (MUD v2 Solidity) manages three paid tiers via on-chain item transfer
- **Watcher Assembly Network** — Live tracker of deployed "The Watcher" Smart Assemblies across the frontier. Auto-updates from chain data. Shows online/offline status, system coverage, fleet health
- **Tier-Gated Access** — Backend verifies on-chain subscription status (5-min cache) and gates endpoints by tier

---

## Architecture

```
World API (30s polling) → Poller → SQLite WAL
                                       ↓
            ┌──────────┬───────────────┼───────────┬──────────┐
            ↓          ↓               ↓           ↓          ↓
      Entity      Naming         Story Feed   Kill Graph  Hotzones
      Resolver    Engine         + Streaks    + Vendettas  + Corps
            ↓          ↓               ↓           ↓          ↓
      Fingerprint  Earned            Auto-      Network    Danger
       Builder     Titles            News      Analysis    Zones
            ↓          ↓               ↓           ↓          ↓
            └──────────┴───────────┬───┼───────────┴──────────┘
                                   ↓   ↓
                             Reputation Engine
                            (6-dimension scoring)
                                   ↓
                              FastAPI API (28 endpoints)
                                   ↓
                         ┌─────────┼──────────┬──────────────┐
                         ↓         ↓          ↓              ↓
                    React SPA   Discord    Webhooks    WatcherSystem.sol
                    (4 tabs,      Bot                  (MUD v2 contract)
                   12 components)                            ↓
                                                   Smart Assembly gating
                                                  ("deny dock if trust < 40")
                                                             ↓
                                                    ← back on-chain →
```

**The loop**: Data flows in from the chain → Witness analyzes and scores → reputation scores flow back on-chain via WatcherSystem.sol → Smart Assemblies enforce access based on trust → player behavior changes → new chain data flows in.

### Smart Contract

**WatcherSystem.sol** — MUD v2 Solidity contract deployed on-chain.

Three subscription tiers, paid via Smart Assembly inventory transfer (in-game items):

| Tier | Duration | Includes |
|---|---|---|
| **Scout** | 7 days | Behavioral fingerprints, reputation scores |
| **Oracle** | 7 days | + AI narratives, standing watches, locator agent |
| **Spymaster** | 7 days | + Alt detection, kill networks, battle reports |

Subscription status is verified on-chain. The backend checks wallet subscription state with a 5-minute cache and gates endpoint access by tier.

### Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLite WAL
- **Frontend**: React 19, Vite 7, Tailwind CSS 4, TypeScript (5 tabs, 20 components)
- **Intelligence**: Anthropic API (Claude) for narrative generation
- **On-Chain**: MUD v2, Solidity (WatcherSystem.sol)
- **Bot**: discord.py with slash commands
- **Deployment**: Docker, Fly.io
- **Ingestion**: Never-crash poller with pagination, error isolation

### Design Principles
1. **The poller must never crash** — all errors logged, never raised
2. **Killmails are first-class data** — the only durable positional signal
3. **Deterministic titles** — same data = same names, everyone sees the same thing
4. **Cache AI narratives** — same entity + same events = cached response
5. **Template fallback** — narratives work without API key via rule-based generation
6. **The chain loop** — data in → analysis → reputation → on-chain enforcement → behavioral change → new data

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

All endpoints under `/api/` prefix. 33 endpoints total.

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Service health + table counts |
| `/api/entities` | GET | List entities (filter, sort, paginate) |
| `/api/entity/{id}` | GET | Full entity dossier |
| `/api/entity/{id}/fingerprint` | GET | Behavioral fingerprint (temporal, route, social, threat, OPSEC) |
| `/api/entity/{id}/timeline` | GET | Unified event timeline with delta analysis |
| `/api/entity/{id}/narrative` | GET | AI-generated or template dossier narrative |
| `/api/entity/{id}/reputation` | GET | Trust score (0-100) with 6-dimension breakdown |
| `/api/feed` | GET | Story feed (auto-generated news) |
| `/api/leaderboard/{category}` | GET | Rankings: `top_killers`, `most_deaths`, `most_traveled`, `deadliest_gates`, `most_active_gates` |
| `/api/titles` | GET | Entities with earned titles |
| `/api/search?q=` | GET | Search entities by name or address |
| `/api/fingerprint/compare` | GET | Compare two entity fingerprints (alt detection) |
| `/api/kill-graph` | GET | Kill network (who kills whom, vendettas) |
| `/api/hotzones` | GET | Dangerous systems ranked by kill density |
| `/api/hotzones/{system_id}` | GET | System detail (hourly distribution, top victims) |
| `/api/entity/{id}/streak` | GET | Kill streak and momentum data |
| `/api/streaks` | GET | Active hunters on kill streaks |
| `/api/corps` | GET | Corporation combat leaderboard |
| `/api/corps/rivalries` | GET | Inter-corporation rivalries |
| `/api/corp/{id}` | GET | Corporation profile (members, kills, systems) |
| `/api/battle-report` | POST | AI battle analysis from event sequence |
| `/api/watches` | POST | Create standing intelligence watch |
| `/api/watches/{id}` | DELETE | Remove watch |
| `/api/subscription/{wallet}` | GET | Check on-chain subscription status and tier |
| `/api/subscribe` | POST | Initiate subscription (triggers on-chain verification) |
| `/api/assemblies` | GET | Watcher Assembly Network summary (coverage, fleet health) |
| `/api/assemblies/list` | GET | List deployed Watcher assemblies with online/offline status |
| `/api/auth/eve/login` | GET | EVE SSO authorization URL |
| `/api/auth/eve/callback` | GET | OAuth2 callback — exchange code for session |
| `/api/auth/eve/me` | GET | Current EVE character info (with on-chain cross-ref) |
| `/api/auth/eve/logout` | POST | Clear EVE SSO session |
| `/api/events` | GET | SSE stream (kills, alerts, status) |
| `/api/events/status` | GET | SSE connection status |

---

## Discord Bot

10 slash commands for in-game intelligence:

| Command | Description |
|---|---|
| `/witness <name>` | Entity lookup — stats, titles, threat level, OPSEC rating |
| `/killfeed [count]` | Latest killmails with timestamps |
| `/leaderboard <category>` | Top killers, most deaths, most traveled |
| `/feed` | Recent story feed items |
| `/compare <entity1> <entity2>` | Fingerprint comparison — alt detection |
| `/locate <id>` | Full entity lookup with danger rating |
| `/history <id>` | AI-generated narrative dossier |
| `/profile <id>` | Full behavioral fingerprint |
| `/opsec <id>` | OPSEC score analysis |
| `/watch <type> <target>` | Set a standing intelligence watch |
| `/unwatch <target>` | Remove a standing watch |

Set `WITNESS_DISCORD_TOKEN` to activate.

---

## Dashboard

React SPA with five tabs and 20 components:

- **Intelligence** — Search any entity, view fingerprint card (temporal/route/social/threat profiles), activity heatmap, event timeline, AI narrative, reputation score
- **Tactical** — Kill network graph, danger zone heatmap, active hunter streaks, corp combat rankings, assembly map
- **Compare** — Side-by-side fingerprint comparison with alt/fleet-mate detection
- **Feed & Rankings** — Live story feed + leaderboard with category switching
- **Account** — Wallet connection, EVE SSO identity, subscription management, standing watches

Live SSE ticker shows real-time kills, alerts, and system updates as they happen.

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
# Backend tests (398 passing, 80%+ coverage)
pytest tests/ -v

# Frontend tests (45 passing)
cd frontend && npx vitest run

# Lint
ruff check backend/ tests/ && ruff format backend/ tests/

# Coverage
pytest --cov=backend --cov-fail-under=80 tests/

# Seed demo data (for hackathon demos)
python scripts/seed_demo.py
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
| `WITNESS_EVE_SSO_CLIENT_ID` | (empty) | CCP EVE SSO application client ID |
| `WITNESS_EVE_SSO_SECRET_KEY` | (empty) | CCP EVE SSO application secret |
| `WITNESS_EVE_SSO_CALLBACK_URL` | (empty) | OAuth2 callback URL |

---

## Hackathon

Built for the **EVE Frontier Hackathon** (March 2026).

**Category**: Community Tools / Intelligence

**Why Witness?** EVE Frontier generates permanent on-chain data but no tools exist to make sense of it. Witness turns raw blockchain events into actionable intelligence — who's dangerous, which gates are contested, when new players appear, and whether that pilot is an alt. With the reputation system and WatcherSystem.sol, intelligence flows back on-chain to enforce community standards through Smart Assembly access control.

The chain is the source of truth. Witness is the interpreter. And now, the enforcer.

---

## License

MIT
