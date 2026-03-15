# CLAUDE.md — witness

## Project Overview

The Living Memory of EVE Frontier — chain archaeology, AI intelligence, locator agent

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 194 across 6 languages
- **Lines**: 42,378

## Architecture

```
witness/
├── .github/
│   └── workflows/
├── .vercel/
├── backend/
│   ├── analysis/
│   ├── api/
│   ├── bot/
│   ├── core/
│   ├── db/
│   ├── ingestion/
│   └── warden/
├── contracts/
│   ├── src/
│   └── sui/
├── data/
├── docs/
├── frontend/
│   ├── .vercel/
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
├── requirements-dev.txt
├── requirements.lock
├── requirements.txt
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
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 76 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# coverage
pytest --cov=src/ tests/

# docker CMD
["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
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
- `C5Briefing`
- `ChallengeResponse`
- `CheckoutRequest`
- `CorpProfile`
- `EntityDossier`
- `ErrorBoundary`
- `EventBus`
- `Fingerprint`
- `Hotzone`
- `Hypothesis`
- `KillEdge`
- `KillGraphNode`
- `NexusSubscribeRequest`
- `ReputationScore`

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
- `/admin/analytics`
- `/admin/backfill-stories`
- `/admin/sync-prices`
- `/alerts`
- `/alerts/{alert_id}/read`
- `/assemblies`
- `/assemblies/list`
- `/battle-report`
- `/briefing`
- `/checkout/create`
- `/clones`
- `/clones/queue`
- `/constellations`
- `/corp/{corp_id}`
- `/corps`

### Enums/Constants
- `ADMIN_CAP`
- `ADMIN_SUI_ADDR`
- `ADMIN_WALLET`
- `ANTHROPIC_API_KEY`
- `API_BASE`
- `BASE`
- `BATTLE_SYSTEM`
- `BATTLE_USER`
- `CHARACTERS_QUERY`
- `CONFIG`

### Outstanding Items
- **NOTE**: World API is dead (NXDOMAIN since March 11, 2026). (`backend/ingestion/poller.py`)

## AI Skills

**Installed**: 122 skills in `~/.claude/skills/`
- `a11y`, `accessibility-checker`, `agent-teams-orchestrator`, `align-debug`, `api-client`, `api-docs`, `api-tester`, `apple-dev-best-practices`, `arch`, `backup`, `brand-voice-architect`, `build`, `changelog`, `ci`, `cicd-pipeline`
- ... and 107 more

**Recommended bundles**: `api-integration`, `full-stack-dev`

**Recommended skills** (not yet installed):
- `api-integration`
- `full-stack-dev`

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
