# CLAUDE.md — WatchTower

# EVE Frontier × Sui Hackathon 2026

## Project Identity

**WatchTower** is the Living Memory of EVE Frontier.
Chain archaeology + AI intelligence platform that reads the blockchain to generate entity dossiers, behavioral fingerprints, earned titles, reputation scoring, and auto-generated story feeds.

**Tagline:** "The Living Memory of EVE Frontier"
**Track:** General Track — EVE Frontier × Sui Hackathon 2026
**Live URL:** https://watchtower-evefrontier.vercel.app/
**Submission:** https://www.deepsurge.xyz/projects/72145312-4889-4150-ae53-2c00748a0476
**Owner:** James C. Young (@AreteDriver)

---

## Current State

- **Version**: 0.1.0
- **Language**: Python, TypeScript, CSS, JavaScript, HTML, Shell
- **Files**: 143 across 6 languages
- **Lines**: 25,428
- **Tests**: 457 (80%+ coverage)

### Live Metrics (as of March 12, 2026)

- 36,085 entities fingerprinted
- 4,795 killmails analyzed
- 170 earned titles generated

These are live numbers from real chain data. They are the primary proof of scale and must be surfaced prominently in the UI and demo.

---

## Core Feature Set

### 1. Entity Dossiers
Per-entity intelligence profiles generated from on-chain behavior. Each dossier includes:
- Behavioral fingerprint (activity patterns, combat style, region presence)
- Kill/loss history
- Active systems and regions
- Reputation score
- Earned titles

The dossier page is the **demo centerpiece**. It must read like a classified intelligence file.

### 2. Behavioral Fingerprints
On-chain behavior analysis that characterizes how an entity operates — solo vs. fleet, aggressor vs. defender, active time zones, preferred ship classes, geographic clustering. This is the core IP of WatchTower. No competitor is doing this.

### 3. Earned Titles
170 titles generated from chain event patterns. Examples: "Gatekeeper," "The Watcher," "Void Runner." Titles are earned, not assigned — they emerge from behavioral data. Must be visible, shareable, and legible to non-technical judges.

### 4. Reputation Scoring
Quantified behavioral reputation derived from killmail data, transaction patterns, and chain event history. Feeds into the NEXUS intel marketplace concept (Witness Protocol track).

### 5. Story Feed (Priority Build)
Auto-generated narrative events that turn chain data into readable intel stories. This is the highest-differentiation feature not yet fully built. Target format:

> "On March 11, char-pike-vanguard crossed into hostile territory near J47-4PK and was destroyed by a coordinated fleet of 12. Three members of that fleet have been active in this region for 30 consecutive days."

The story feed is what makes WatchTower feel like a **living civilization** rather than a data dashboard. Build this before the demo.

### 6. Kill/Activity Heatmap
Spatial view of conflict clustering and entity activity. Shows where the frontier is hot right now. Gives the dashboard its "living" quality.

---

## Architecture

```
watchtower/
├── .github/
│   └── workflows/
├── backend/
│   ├── analysis/
│   ├── api/
│   ├── bot/
│   ├── core/
│   ├── db/
│   └── ingestion/
├── contracts/
│   └── src/
├── data/
├── docs/
├── frontend/
│   ├── public/
│   └── src/
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── DEBT.md
├── Dockerfile
├── LICENSE
├── README.md
├── docker-compose.yml
├── fly.toml
├── pyproject.toml
├── requirements.lock
```

### Tech Stack

- **Backend**: FastAPI + SQLite (WAL mode) + Pydantic v2
- **Frontend**: React 19 + Vite + Tailwind CSS v4
- **Contracts**: MUD v2 Solidity (WatcherSystem.sol)
- **AI**: Anthropic API via httpx (narrative generation, fingerprint summaries)
- **Bot**: Discord (webhook alerts)
- **Package Manager**: pip (backend), npm (frontend)
- **Linters/Formatters**: ruff (backend)
- **Test Frameworks**: pytest (backend), vitest (frontend)
- **Runtime**: Docker
- **CI/CD**: GitHub Actions
- **Deploy**: Fly.io (backend) + Vercel (frontend)

### Data Flow

```
World API (polling) → Poller → SQLite → Entity Resolver → Naming Engine
                                   ↓              ↓              ↓
                              FastAPI API    AI Narratives   Story Feed
                                   ↓              ↓              ↓
                              Dashboard     Discord Bot     Webhook Alerts
                                   ↓
                         Reputation → On-Chain (WatcherSystem.sol)
```

### Environment Variables

```
NEXT_PUBLIC_APP_URL=https://watchtower-evefrontier.vercel.app
ANTHROPIC_API_KEY=           # Claude API for narrative generation
SUI_RPC_URL=                 # Sui testnet RPC endpoint
CHAIN_INDEXER_URL=           # Internal indexer API base URL
DISCORD_TOKEN=
DISCORD_WEBHOOK_URL=
EVE_SESSION_KEY=
```

---

## Competitive Position

WatchTower is the **only submission** in the EVE Frontier × Sui 2026 Hackathon doing:
- Behavioral fingerprinting from chain data
- Earned title generation
- AI-generated narrative story feed
- Entity reputation scoring

### Competitor Map (as of March 12, 2026)

| Project | What It Does | Overlap | Threat Level |
|---|---|---|---|
| CradleOS (Raw) | Corp ops console, DEX, tribe coin, infra pegging, **interactive starmap (24,502 systems)**, **Defense Policy v2 (GREEN/YELLOW/RED alert states, aggression detect, tribe blacklisting, passage intel log)** | Spatial + defense execution | Medium — they execute decisions, WatchTower informs them |
| Powerlay Frontier | Tribe coordination overlay, production planning | None | Low — in-game tool |
| Ministry of Passage | Identity confirmation dApp | Thematic only | None |
| Learn Move | Move language tutorials | None | None |
| EVE Frontier Pawn Shop | Multi-SSU pawn shop smart contracts | None | None |

**WatchTower's lane is uncontested on intelligence depth.** CradleOS now has a starmap (cartography layer) but zero behavioral intelligence. They show the galaxy. WatchTower tells you what the galaxy means.

### CradleOS Starmap — Specific Counter

CradleOS starmap: 24,502 systems, color-coded, interactive, scroll-to-zoom.
WatchTower counter: **system-level dossiers**. Same spatial awareness, but with intelligence layered on top.

When a user clicks or searches a system in WatchTower they get:
- Top entities behaviorally active in that system
- Recent killmail story feed entries anchored to that system
- Threat level score derived from killmail density and entity reputation
- Tribal/corp behavioral presence fingerprint

This is the differentiator: CradleOS renders space. WatchTower interprets it.

### CradleOS Defense Policy — Positioning Opportunity

CradleOS Defense Policy v2 lets corps set GREEN/YELLOW/RED alert states and manage tribe blacklists. It executes defense decisions but has no intelligence layer — it cannot tell you *who* an entity is before you decide to blacklist them.

WatchTower fills that gap directly:
- Reputation scores → blacklist inputs for CradleOS Defense Policy
- Behavioral fingerprints → threat classification before hostile contact
- Passage Intel Log events → cross-referenced with WatchTower entity dossiers

**Frame this in the demo:** WatchTower is the intelligence feed that makes tools like CradleOS Defense Policy smart. We are the layer beneath the decision, not competing with the decision.

### Differentiation vs. EVE-Prism (historical analog)
EVE-Prism (EVE Online Classic) was the closest historical reference — kill feed, pilot profiles, fitting tool, operative report. WatchTower exceeds it by adding AI narrative generation, earned titles, and behavioral fingerprinting. EVE-Prism had no blockchain layer.

---

## Demo Sequence (90 seconds)

Build and record in this order:

1. **Story Feed** — Open to live narrative events. Show civilization writing itself in real time.
2. **Entity Dossier** — Click an entity. Show behavioral fingerprint, reputation score, kill history.
3. **Earned Title** — Show a generated title and explain it emerged from chain behavior, not manual assignment.
4. **Scale proof** — Pull up the stats: 36K entities, 4.7K killmails, 170 titles. Let the numbers speak.

Do not demo raw blockchain data or code. Demo the intelligence layer on top of it.

---

## Build Priorities (Remaining Hackathon Sprint)

### Must Ship Before Demo
- [ ] Story feed — at least 10 real narrative entries visible on load
- [ ] Earned titles visible on entity dossier page
- [ ] Dossier page polished to "classified intel file" aesthetic

### High Value
- [ ] Kill/activity heatmap (spatial view)
- [ ] **System-level dossier** — search/click a system, get: top active entities, recent story feed entries, threat level score, tribal presence fingerprint. Direct counter to CradleOS starmap — they render space, WatchTower interprets it.
- [ ] Entity search that returns a dossier immediately (no loading states visible in demo)
- [ ] Title shareable link (one URL = one earned title card)

### Defer
- [ ] Sui write integration (belongs to Witness Protocol, not WatchTower)
- [ ] User authentication / login
- [ ] Mobile optimization

---

## Critical Rules

- POLLER MUST NEVER CRASH — all errors logged, never raised
- Schema confirmed against blockchain-gateway-stillness.live.tech.evefrontier.com v2 API (2026-03-07)
- API returns paginated results with {data: [], metadata: {total, limit, offset}}
- Killmails are FIRST-CLASS data — only durable positional signal post-coordinate-privacy
- Coordinates are hackathon-only — don't build core features on them
- Cache AI narratives — same entity + same event hash = cached response
- Attacker data can be strings OR dicts with "address" key — always normalize with _extract_ids()
- SQLite check_same_thread=False required for FastAPI lifespan threading
- `threat_level` is derived, not stored — compute from feral_ai_tier at query time
- Run `explore_sandbox.py` first on any new table before writing schema
- Test Discord webhooks with `--dry-run` flag before live deployment
- All AI narrative calls go through a single `narrativeEngine.js` module — do not scatter Claude API calls
- Fingerprint logic is pure functions — no side effects, fully testable
- Keep chain indexer decoupled from frontend — it should be deployable independently

---

## Coding Standards

- **Naming**: snake_case (Python), PascalCase (components), camelCase (JS utilities)
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 73 characters
- Component files: PascalCase (`EntityDossier.jsx`, `StoryFeed.jsx`)
- Utility files: camelCase (`chainIndexer.js`, `reputationScore.js`)

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check backend/ tests/
# format
ruff format backend/ tests/
# coverage
pytest --cov=backend --cov-fail-under=80 tests/

# docker CMD
["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

---

## Domain Context

### Key Models/Classes
- `BattleReportRequest`
- `CorpProfile`
- `EntityDossier`
- `ErrorBoundary`
- `EventBus`
- `Fingerprint`
- `Hotzone`
- `KillEdge`
- `KillGraphNode`
- `ReputationScore`
- `RouteProfile`
- `Settings`
- `SocialProfile`
- `StreakInfo`
- `SubscribeRequest`

### Domain Terms
- AI, Alt Detection, Assembly Guide, Behavioral Fingerprints
- Chain Archaeology, Chain Economy, Chain Trust Scoring, Character Titles

### API Endpoints
- `/alerts`, `/alerts/{alert_id}/read`
- `/assemblies`, `/assemblies/list`
- `/battle-report`
- `/clones`, `/clones/queue`
- `/corp/{corp_id}`, `/corps`, `/corps/rivalries`
- `/crowns`, `/crowns/roster`
- `/cycle`
- `/entities`, `/entity/{entity_id}`

### Enums/Constants
- `ANTHROPIC_API_KEY`, `BASE`, `BATTLE_SYSTEM`, `BATTLE_USER`
- `CYCLE_NAME`, `DISCORD_TOKEN`, `DISCORD_WEBHOOK_URL`
- `DOSSIER_SYSTEM`, `DOSSIER_USER`, `EVE_SESSION_KEY`

---

## Dependencies

### Core
- fastapi
- uvicorn

### Dev
- pytest
- pytest-asyncio
- pytest-cov
- respx
- ruff

---

## Cycle 5: Shroud of Fear (March 11-31)

**Task list**: `docs/FRONTIER_WATCH_C5_TASKS.md`

New systems: orbital zones + feral AI, void scanning, clone manufacturing, crowns/identity.
All new endpoints must return `{ cycle: 5, reset_at: "...", data: [...] }` envelope.

### New Tables (9)
orbital_zones, feral_ai_events, scans, scan_intel, clones, clone_blueprints, crowns, smart_characters, tribes

### New Endpoints (11)
/api/cycle, /api/orbital-zones, /api/orbital-zones/{zone_id}/history, /api/orbital-zones/{zone_id}/threat, /api/scans, /api/scans/feed, /api/clones, /api/clones/queue, /api/crowns, /api/crowns/roster, /api/briefing

### New Discord Alerts (5)
Feral AI Evolved, Hostile Scan, Blind Spot, Clone Reserve Low, AI Critical

### New Frontend Panels (5)
Cycle Banner (header), Orbital Zones, Void Scan Feed, Clone Status, Crown Roster

---

## Aegis Stack Context

WatchTower is the **Track 1 external analytics submission** of the Aegis Stack — six coordinated EVE Frontier hackathon projects built under one umbrella:

- **WatchTower** (this project) — Chain archaeology + AI intel platform
- **Witness Protocol** — Chain indexer + NEXUS behavioral reputation marketplace
- **The Black Box** — Forensic engine
- **The Sovereign** — On-chain governance
- **The Silk Road Protocol** — Autonomous trade contracts
- **The Warden System** — Autonomous defense

WatchTower and Witness Protocol are the two submission-facing surfaces. The other four are supporting infrastructure and portfolio pieces.

---

## Philosophy

WatchTower is not a dashboard. It is a memory system.

Every entity that has ever acted on the EVE Frontier blockchain leaves a trace. WatchTower reads those traces, finds the patterns, and turns them into identity — dossiers, reputations, titles, stories. The blockchain is the source of truth. WatchTower is the interpreter.

This is the "Toolkit for Civilization" answered literally: civilizations need historians. WatchTower is the historian.

> "The Living Memory of EVE Frontier."

---

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
