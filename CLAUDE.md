# CLAUDE.md — witness

## Project Overview

The Living Memory of EVE Frontier — chain archaeology, AI intelligence, locator agent

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 72 across 6 languages
- **Lines**: 10,992

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
├── Dockerfile
├── README.md
├── docker-compose.yml
├── pyproject.toml
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
- **Semicolons**: mixed
- **Line Length (p95)**: 79 characters

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

## Critical Rules

- POLLER MUST NEVER CRASH — all errors logged, never raised
- Schema confirmed against blockchain-gateway-stillness.live.tech.evefrontier.com v2 API (2026-03-07)
- API returns paginated results with {data: [], metadata: {total, limit, offset}}
- Killmails are FIRST-CLASS data — only durable positional signal post-coordinate-privacy
- Coordinates are hackathon-only — don't build core features on them
- Cache AI narratives — same entity + same event hash = cached response

## Data Flow

```
World API (polling) → Poller → SQLite → Entity Resolver → Naming Engine
                                   ↓              ↓              ↓
                              FastAPI API    AI Narratives   Story Feed
                                   ↓              ↓              ↓
                              Dashboard     Discord Bot     Webhook Alerts
```

## Hackathon Timeline

- Pre-March 11: Scaffold, API explorer, DB schema, poller skeleton
- Week 1 (Mar 11-17): Live data flowing, entity resolver, basic stats
- Week 2 (Mar 18-24): AI narratives, naming engine, story feed, Discord bot
- Week 3 (Mar 25-31): React dashboard, polish, demo video

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models

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
- `EntityDossier`
- `Fingerprint`
- `ProfileActions`
- `RouteProfile`
- `Settings`
- `SocialProfile`
- `TemporalProfile`
- `ThreatProfile`
- `WatchRequest`
- `WitnessBot`

### Domain Terms
- AI
- Chain Archaeology
- DELETE
- Dashboard Discord Bot Webhook Alerts
- Discord Commands
- EVE
- Earned Titles
- Entity Dossiers
- Entity Resolver
- Free Layer

### API Endpoints
- `/battle-report`
- `/entities`
- `/entity/{entity_id}`
- `/entity/{entity_id}/fingerprint`
- `/entity/{entity_id}/narrative`
- `/entity/{entity_id}/timeline`
- `/feed`
- `/fingerprint/compare`
- `/health`
- `/leaderboard/{category}`
- `/search`
- `/titles`
- `/watches`
- `/watches/{target_id}`
- `/{path:path}`

### Enums/Constants
- `ANTHROPIC_API_KEY`
- `BASE`
- `BATTLE_SYSTEM`
- `BATTLE_USER`
- `DISCORD_WEBHOOK_URL`
- `DOSSIER_SYSTEM`
- `DOSSIER_USER`
- `SCHEMA`

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
