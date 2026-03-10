# CLAUDE.md — witness

## Project Overview

The Living Memory of EVE Frontier — chain archaeology, AI intelligence, locator agent

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 143 across 6 languages
- **Lines**: 25,428

## Architecture

```
witness/
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

## Tech Stack

- **Language**: Python, TypeScript, CSS, JavaScript, HTML, Shell
- **Framework**: fastapi
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Test Frameworks**: pytest
- **Runtime**: Docker
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 73 characters

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
- AI
- Alt Detection
- Assembly Guide
- Behavioral Fingerprints
- CCP
- CSS
- Chain Archaeology
- Chain Economy
- Chain Trust Scoring
- Character Titles

### API Endpoints
- `/alerts`
- `/alerts/{alert_id}/read`
- `/assemblies`
- `/assemblies/list`
- `/battle-report`
- `/clones`
- `/clones/queue`
- `/corp/{corp_id}`
- `/corps`
- `/corps/rivalries`
- `/crowns`
- `/crowns/roster`
- `/cycle`
- `/entities`
- `/entity/{entity_id}`

### Enums/Constants
- `ANTHROPIC_API_KEY`
- `BASE`
- `BATTLE_SYSTEM`
- `BATTLE_USER`
- `CYCLE_NAME`
- `DISCORD_TOKEN`
- `DISCORD_WEBHOOK_URL`
- `DOSSIER_SYSTEM`
- `DOSSIER_USER`
- `EVE_SESSION_KEY`

## AI Skills

**Installed**: 122 skills in `~/.claude/skills/`
- `a11y`, `accessibility-checker`, `agent-teams-orchestrator`, `align-debug`, `api-client`, `api-docs`, `api-tester`, `apple-dev-best-practices`, `arch`, `backup`, `brand-voice-architect`, `build`, `changelog`, `ci`, `cicd-pipeline`
- ... and 107 more

**Recommended bundles**: `api-integration`, `full-stack-dev`

**Recommended skills** (not yet installed):
- `api-integration`
- `full-stack-dev`

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

## Data Flow

```
World API (polling) → Poller → SQLite → Entity Resolver → Naming Engine
                                   ↓              ↓              ↓
                              FastAPI API    AI Narratives   Story Feed
                                   ↓              ↓              ↓
                              Dashboard     Discord Bot     Webhook Alerts
                                   ↓
                         Reputation → On-Chain (WatcherSystem.sol)
```

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

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
