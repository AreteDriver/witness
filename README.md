# Witness — The Living Memory of EVE Frontier

**Chain archaeology meets locator agent intelligence.**

Witness reads the blockchain like a history book. Every gate transit, every killmail, every entity that appears on-chain gets cataloged, analyzed, and woven into a living narrative. Free lore for the community. Paid intelligence for those who need an edge.

## What It Does

### Free Layer — Chain Archaeology
- **Entity Dossiers** — Full profiles for gates, characters, corps. Stats, timelines, danger ratings.
- **Earned Titles** — Deterministic titles from on-chain stats. "The Meatgrinder" for deadly gates. "The Ghost" for untouchable pilots. Everyone sees the same names.
- **Story Feed** — Auto-generated news: killmail clusters, new entity appearances, milestone events.
- **AI Narratives** — Battle reports and entity histories generated from chain data.
- **Leaderboards** — Deadliest gates, top killers, most traveled pilots.

### Paid Layer — The Oracle (Locator Agent)
- **Standing Watches** — Monitor entities, gates, systems. Get Discord alerts when conditions trigger.
- **Movement Detection** — Know when a target transits any gate.
- **Traffic Spikes** — Alert on unusual gate activity.
- **Killmail Proximity** — Instant notification when ships die in monitored systems.
- **Hostile Sighting** — Watch for specific corps at specific gates.
- **OPSEC Scoring** — Analyze a corp's operational security from their transit patterns.

## Architecture

```
World API (polling) → Poller → SQLite WAL → Entity Resolver → Naming Engine
                                    ↓              ↓              ↓
                               FastAPI API    AI Narratives   Story Feed
                                    ↓              ↓              ↓
                               Dashboard     Discord Bot     Webhook Alerts
```

- **Backend**: Python, FastAPI, SQLite WAL
- **Intelligence**: Anthropic API for narrative generation
- **Interface**: Discord bot (primary), REST API, React dashboard (coming)
- **Ingestion**: Polling EVE Frontier World API with never-crash design

## Quick Start

```bash
# Clone and install
git clone https://github.com/AreteDriver/witness.git
cd witness
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run tests
pytest tests/ -v

# Start the server
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
docker compose up -d
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service health + table counts |
| `GET /api/entity/{id}` | Full entity dossier |
| `GET /api/entities` | List entities (filter by type, sort, paginate) |
| `GET /api/entity/{id}/timeline` | Unified event timeline |
| `GET /api/feed` | Story feed (auto-generated news) |
| `GET /api/leaderboard/{category}` | Rankings by category |
| `GET /api/titles` | Entities with earned titles |
| `GET /api/search?q=` | Search entities by name/ID |
| `GET /api/entity/{id}/narrative` | AI-generated entity narrative |
| `POST /api/battle-report` | AI battle analysis |
| `POST /api/watches` | Create standing watch |
| `DELETE /api/watches/{id}` | Remove watch |

## Discord Commands

| Command | Description |
|---|---|
| `/locate <entity_id>` | Look up any entity's dossier |
| `/history <entity_id>` | AI-generated narrative history |
| `/watch <type> <target>` | Set a standing intelligence watch |
| `/unwatch <target>` | Remove a watch |
| `/feed [count]` | Show recent story feed |
| `/opsec <corp_id>` | Corp OPSEC security score |
| `/leaderboard [category]` | View top entities |

## Development

```bash
# Lint
ruff check . && ruff format .

# Test
pytest tests/ -v

# Explore API (run on March 11 to confirm field names)
python scripts/explore_api.py
```

## Hackathon

Built for the EVE Frontier hackathon (March 11-31, 2026).

- **Week 1**: Live data flowing, entity resolver, basic stats
- **Week 2**: AI narratives, naming engine, story feed, Discord bot
- **Week 3**: React dashboard, polish, demo video

## License

MIT
