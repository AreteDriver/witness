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
- **Tests**: 456 passing, 80%+ coverage (pytest)

### Data Flow

```
World API (30s poll) → Poller → SQLite → Entity Resolver → Naming Engine
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

---

## World API Status

`blockchain-gateway-stillness.live.tech.evefrontier.com` → NXDOMAIN (as of March 12, 2026). Between-cycles shutdown by CCP. All variant hostnames (utopia, nova, bare gateway) also dead. No alternate endpoint in docs.

- Poller runs every 30s, fails silently, auto-resumes when DNS resolves
- Current cycle data frozen: 33 entities, 60 killmails, 43 stories
- Previous cycle (archived): 36K entities, 4.7K killmails, 170 titles
- **+10% deploy bonus window: April 1–15** (after March 31 submission deadline)

Do NOT use previous cycle numbers as current. Submit March 31, deploy live April 1–15.

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
│   ├── ingestion/     # poller (World API → SQLite)
│   └── warden/        # autonomous threat detection loop
├── contracts/sui/     # Move reputation oracle
├── frontend/src/
│   ├── components/    # 28 React components
│   ├── contexts/      # AuthContext (wallet)
│   └── hooks/         # useEventStream (SSE)
├── tests/             # 456 tests
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

## Judging Criteria

| Category | Fit | Strategy |
|---|---|---|
| Most Creative | **Primary target** | Chain archaeology + earned titles + "living memory" |
| Best Technical | Strong | Poller, fingerprint engine, AI pipeline, 456 tests |
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
