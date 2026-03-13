# CLAUDE.md — WatchTower

**WatchTower** is the Living Memory of EVE Frontier.
Chain archaeology + AI intelligence platform. Reads the blockchain → entity dossiers, behavioral fingerprints, earned titles, reputation scoring, auto-generated story feeds.

**Track:** General Track — EVE Frontier × Sui Hackathon 2026
**Live:** https://watchtower-evefrontier.vercel.app/ (frontend) / https://watchtower-evefrontier.fly.dev (backend)
**Submission:** https://www.deepsurge.xyz/projects/72145312-4889-4150-ae53-2c00748a0476
**Repo:** https://github.com/AreteDriver/watchtower

---

## Tech Stack

- **Backend**: FastAPI + SQLite WAL + Pydantic v2 (Python 3.12)
- **Frontend**: React 19 + Vite + Tailwind CSS v4 (TypeScript strict)
- **Contracts**: Sui Move (WatcherSystem reputation oracle)
- **AI**: Anthropic API via httpx (narrative generation)
- **Bot**: Discord webhooks
- **Deploy**: Fly.io (backend) + Vercel (frontend)
- **Tests**: 495 passing, 80%+ coverage (pytest)

### Data Flow

```
Sui GraphQL (30s poll) → Poller → SQLite → Entity Resolver → Naming Engine
                                      ↓              ↓              ↓
                                 FastAPI API    AI Narratives   Story Feed
                                      ↓              ↓              ↓
                                 React SPA     Discord Bot     SSE/Webhooks
```

---

## Common Commands

```bash
pytest tests/ -v                              # test
pytest --cov=backend --cov-fail-under=80      # coverage
ruff check backend/ tests/                    # lint
ruff format backend/ tests/                   # format
cd frontend && npm run build                  # frontend build
/home/arete/.fly/bin/flyctl deploy            # deploy backend
cd frontend && npx vercel --prod              # deploy frontend
```

---

## Critical Rules

- **POLLER MUST NEVER CRASH** — all errors logged, never raised
- Attacker data can be strings OR dicts with "address" key — always normalize with `isinstance(a, str)` check
- SQLite `check_same_thread=False` required for FastAPI lifespan threading
- `threat_level` is derived, not stored — compute from `feral_ai_tier` at query time
- Killmails are FIRST-CLASS data — only durable positional signal post-coordinate-privacy
- Cache AI narratives — same entity + same event hash = cached response
- Fingerprint logic is pure functions — no side effects, fully testable
- All C5 endpoints return `{ cycle: 5, reset_at: "...", data: [...] }` envelope
- HACKATHON_MODE + HACKATHON_ENDS env vars gate Spymaster-for-all with date-based auto-revert
- Auth uses challenge-response: `/wallet/challenge` → sign with dapp-kit → `/wallet/connect` verifies Ed25519 sig
- Sui signature format: `scheme_byte || raw_sig || public_key` (base64). PersonalMessage intent: `[3,0,0]` + BCS(msg) → Blake2b-256 → Ed25519 verify
- Address derived from Blake2b-256(scheme_byte || public_key) — must match claimed wallet

---

## World API Status — DEAD BY DESIGN

**Confirmed by Scetrov [REAP], March 11 2026:** Dynamic data (killmails, entities, gates) was intentionally removed from the World API. CCP migrated all dynamic data to the **Sui GraphQL API**. The World API now serves static world data only.

- `blockchain-gateway-stillness.live.tech.evefrontier.com` → NXDOMAIN
- Static data docs: `https://world-api-stillness.live.tech.evefrontier.com/docs/index.html`
- **This is NOT a temporary outage.** The poller is hitting a permanently dead endpoint.
- World API static data serves solar system names (24,502 systems) via `/v2/solarsystems`
- **Live data restored via Sui GraphQL**: 1,320+ characters, 18+ killmails, 500+ assemblies (and growing)
- Previous cycle (archived): 36K entities, 4.7K killmails, 170 titles
- Solar system names bootstrapped from World API static endpoint on first poll cycle

### Sui GraphQL Migration — COMPLETE

**Migrated March 12, 2026.** Poller now reads from `https://graphql.testnet.sui.io/graphql`.

- [x] Endpoint: `graphql.testnet.sui.io/graphql`
- [x] Package: `0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c`
- [x] Killmail indexer → `KillmailCreatedEvent`
- [x] Character indexer → `CharacterCreatedEvent` + bulk Character object query (1,320 names)
- [x] Assembly indexer → `AssemblyCreatedEvent`
- [x] Gate jump indexer → `JumpEvent` (wired, no events yet this cycle)
- [x] Character name resolution → `metadata.name` on Character objects
- [x] Solar system name resolution → World API static `/v2/solarsystems` (24,502 names)
- [x] Dead World API calls removed (tribes, C5 endpoints)
- [x] Periodic name re-bootstrap every 100 cycles
- [x] Live data confirmed flowing (18+ kills, 500+ assemblies, 1,320 characters)

Key Sui data shapes:
- Killmail: `key.item_id` → killmail_id, `killer_id.item_id` / `victim_id.item_id`, `solar_system_id.item_id`, `kill_timestamp` (unix str)
- Character: `character_address` (wallet), `key.item_id` (in-game), `metadata.name`, `tribe_id`
- Assembly: `assembly_id` (Sui obj), `type_id`, sender = owner
- Entities match on BOTH `smart_characters.address` and `smart_characters.character_id`

---

## Architecture

```
witness/
├── backend/
│   ├── analysis/      # fingerprint, hotzones, kill_graph, narrative, reputation, streaks, story_feed, names
│   ├── api/           # routes, tier_gate, rate_limit, events (SSE)
│   ├── bot/           # discord webhooks
│   ├── core/          # config, logger
│   ├── db/            # database schema, migrations
│   ├── ingestion/     # poller (Sui GraphQL → SQLite), sui_graphql adapter
│   └── warden/        # autonomous threat detection loop
├── contracts/sui/     # Move reputation oracle
├── frontend/src/
│   ├── components/    # 28 React components
│   ├── contexts/      # AuthContext (wallet)
│   └── hooks/         # useEventStream (SSE)
├── tests/             # 495 tests
├── Dockerfile
├── fly.toml
└── frontend/vercel.json
```

### Key API Endpoints

| Endpoint | Description |
|---|---|
| `GET /entity/{id}` | Full dossier (kills, deaths, titles, danger, tribe) |
| `GET /entity/{id}/fingerprint` | Behavioral fingerprint (temporal, route, social, threat) |
| `GET /entity/{id}/reputation` | Trust score with 6-factor breakdown |
| `GET /entity/{id}/narrative` | AI-generated intelligence narrative |
| `GET /entity/{id}/streak` | Kill streak and momentum |
| `GET /system/{id}` | System-level dossier (top combatants, stories, infrastructure) |
| `GET /search?q=` | Entity + system search |
| `GET /feed` | Intel story feed with cursor pagination |
| `GET /hotzones` | Kill density by system (24h/7d/30d/all windows) |
| `GET /kill-graph` | Who-kills-whom graph with vendetta detection |
| `GET /leaderboard/{category}` | Top killers, most deaths, most traveled, etc. |

### Frontend Routes

| Route | Component |
|---|---|
| `/` | Dashboard (Intel/Tactical/C5/Compare/Feed/Account/Admin tabs) |
| `/entity/:entityId` | EntityPage — full dossier with fingerprint, titles, reputation |
| `/system/:systemId` | SystemDossier — system-level threat assessment |
| `/title/:entityId/:title` | TitleCard — shareable earned title card |

---

## Competitive Position

WatchTower's lane is **uncontested on intelligence depth**. Only submission doing behavioral fingerprinting, earned titles, AI narrative feed, and reputation scoring.

| Competitor | Threat | Notes |
|---|---|---|
| CradleOS ([REAP] Raw) | Medium | 3D starmap, Route Planner, Defense Policy v2. Broad but shallow. No behavioral intel. Their blacklist needs our reputation API. |
| Powerlay Frontier | Low | Vision-heavy, no live demo. In-game overlay tool. |
| Others | None | Ministry of Passage, Learn Move, Pawn Shop — zero overlap. |

**Frame as complementary:** WatchTower is the intelligence feed that makes tools like CradleOS Defense Policy smart. We inform decisions, they execute them.

---

## Judging & Schedule

**Prize pool:** $80K total. 1st: $15K + $10K SUI + FanFest. 2nd: $7.5K + $5K SUI. 3rd: $5K + $2.5K SUI. Category champions (5x): $5K + $1K SUI each.

| Date | Milestone |
|---|---|
| March 31 | Submission deadline |
| April 1–15 | Stillness deploy window (+10% bonus) + community voting |
| April 15–22 | Judging |
| April 24 | Winners announced |

| Category | Fit | Strategy |
|---|---|---|
| Most Creative | **Primary target** | Chain archaeology + earned titles + "living memory" |
| Best Technical | Strong | Poller, fingerprint engine, AI pipeline, 495 tests |
| Most Utility | Strong | Entity dossiers, reputation API, story feed |
| Best Live Integration | Clear path | +10% bonus via April 1–15 deploy window |

---

## Community Validation

Discord `#hackathon-build-requests` that WatchTower already answers:

- **TDZ [WOLF]** — Highway heatmap, pilot tracker → Kill density + entity dossiers
- **Kadian11C** — Scanner database with timestamps → Void Scan Feed + behavioral fingerprints
- **Vycaris [BFG]** — Player standings / reputation API → **WatchTower reputation scores ARE this API**
- **[TriEx] Hecate** — Event notifications → Story Feed + Discord webhooks + SSE

---

## Aegis Stack

WatchTower is Track 1 of the Aegis Stack — six coordinated hackathon projects:

- **WatchTower** (this) — Chain archaeology + AI intel
- **Witness Protocol** — NEXUS behavioral reputation marketplace
- The Black Box, The Sovereign, Silk Road Protocol, The Warden System — supporting infrastructure

---

## Deferred: Temperature-Based Accessibility Scoring

**Source:** Community research (Anteris/Ergod [AWAR], Jan 28 2026). R²=0.9936 power law:
```
jump_range(T) = 2.21e9 / T^2.613
```
System temperature explains ~99% of jump range variance. High-temp systems are harder to reach — activity there signals committed actors, not opportunists. Add to system dossier as "accessibility rating" once World API provides per-system temperature data. Complements CradleOS Route Planner (they use cargo/heat sliders on the same underlying mechanic).

**Blocked on:** World API (temperature per system not available until API returns).

---

## Coding Standards

- **Python**: snake_case, double quotes, type hints, absolute imports, pathlib, ruff
- **TypeScript**: strict mode, PascalCase components, camelCase utilities
- **Line length**: 100 (ruff configured)
- **Commits**: Conventional (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- **Tests**: Run before committing. 80%+ coverage required.

## Anti-Patterns

- No `any` type — define interfaces
- No bare `except:` — catch specific exceptions
- No `print()` — use `logging` module
- No mutable default arguments
- No raw dicts from endpoints — use Pydantic models
- No secrets in Dockerfiles or commits
