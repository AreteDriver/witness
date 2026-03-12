# Technical Debt Audit — WatchTower

**Project**: WatchTower — The Living Memory of EVE Frontier
**Audit Date**: 2026-03-12 (updated from March 10 audit)
**Context**: EVE Frontier x Sui Hackathon 2026 (deadline March 31)
**Stats**: 476 tests passing, 80.96% coverage, 1,320+ live characters from Sui GraphQL

---

## Post-Sui Migration Issues (March 12)

### CRITICAL — Affects Demo/Judges

| # | Issue | Location | Fix |
|---|---|---|---|
| S1 | **HACKATHON_MODE must be True in prod** — judges won't get Spymaster tier | `config.py:39` defaults False | Verify Fly.io secret `HACKATHON_MODE=true` |
| S2 | **System names empty everywhere** — hotzones, system dossiers, feed all show hex IDs | `hotzones.py:79`, `HotzoneMap.tsx:70` | Need system name mapping from Sui or static data |
| S3 | **Auth has no signature verification** — anyone can POST any wallet | `auth.py:5,71` (explicit TODO) | Implement Sui wallet sig verify |

### HIGH — Data Quality

| # | Issue | Location | Fix |
|---|---|---|---|
| S4 | **Dead World API calls every cycle** — tribes, C5 endpoints all NXDOMAIN | `poller.py:938,642,712-717` | Remove or gate behind flag |
| S5 | **Warden entity_ids as bare string, not JSON array** — breaks feed entity links | `warden.py:458` | `json.dumps([entity_id])` |
| S6 | **`_hypothesize_hunting_patterns` queries victims not killers** — wrong framing | `warden.py:341-348` | Query attacker_character_ids |
| S7 | **Sui assemblies have no location data** — AssemblyCreatedEvent lacks solar_system | `sui_graphql.py:243-250` | Query Assembly objects directly |

### MEDIUM — Coverage & Cleanup

| # | Issue | Location | Fix |
|---|---|---|---|
| S8 | Discord bot at 10% test coverage | `discord_bot.py` — 249/276 uncovered | Add discord.py mocks |
| S9 | Oracle C5 alerts untested | `oracle.py:222-333` at 62% | Add test cases |
| S10 | `gate_created`/`gate_linked` declared but never polled | `sui_graphql.py:31-33` | Add poll methods or remove |
| S11 | StoryFeed.tsx bypasses api.ts for pagination | `StoryFeed.tsx:63-71` | Use api.ts feed method |
| S12 | Timeline URL construction bug — undefined in query params | `api.ts:414` | Conditional param building |
| S13 | Killmail names always empty at ingest — rely on post-hoc enrichment | `sui_graphql.py:164-165` | Periodic bootstrap (not just once) |
| S14 | `_ingest_subscriptions` receives no data from Sui | `poller.py:223-258` | Remove call or implement |

---

## Original Audit (March 10)

---

## Category Scores

| Category | Score | Weight | Weighted |
|---|---|---|---|
| Security | 8/10 | blocker | no block |
| Correctness | 8/10 | 2x | 16 |
| Infrastructure | 8/10 | 2x | 16 |
| Maintainability | 7/10 | 1x | 7 |
| Documentation | 9/10 | 1x | 9 |
| Freshness | 9/10 | 0.5x | 4.5 |
| **Weighted Total** | | **6.5x** | **52.5** |
| **Weighted Average** | | | **8.1** |
| **Final (adjusted)** | | | **7.8** |

Adjustment: -0.3 for plaintext access tokens in DB + 3 lint failures in CI.

---

## 1. Security (8/10)

### Findings

| Severity | Finding | Location |
|---|---|---|
| **MEDIUM** | EVE SSO access/refresh tokens stored as plaintext in `eve_sessions` table | `backend/db/database.py:139-140`, `backend/api/auth.py:160-163` |
| **MEDIUM** | In-memory OAuth state store (`_pending_states`) not bounded; potential memory leak under attack | `backend/api/auth.py:34` |
| **LOW** | CORS allows `allow_headers=["*"]` — should whitelist specific headers | `backend/api/app.py:87` |
| **LOW** | 3 ruff lint violations (line too long) in `tests/test_cycle5.py` — CI lint job will fail | `tests/test_cycle5.py:30,47,52` |
| **INFO** | `sk-test-key` in test file — harmless mock value | `tests/test_narrative.py:238,262,279` |

### What's Clean

- **No hardcoded secrets** in source (regex scan confirmed — only test mocks)
- **`.env` properly gitignored** — only `.env.example` tracked (confirmed via `git ls-files`)
- **No .db files in git** — `data/*.db` in `.gitignore`, confirmed no DB files tracked
- **`.pem`, `.key`, `.p12` patterns** all in `.gitignore`
- **All credentials via `pydantic-settings`** with `WATCHTOWER_` env prefix
- **Parameterized SQL throughout** — no string interpolation in queries with user input
- **SSRF prevention** on webhook URLs — private IP regex + domain allowlist (Discord only)
- **Path traversal protection** — `is_relative_to(FRONTEND_DIR)` check in static file serving
- **Security headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
- **Rate limiting** — slowapi on all sensitive endpoints (fingerprint, compare, narrative, battle-report, watches, subscribe)
- **Tier gating** — subscription-based access control on premium endpoints
- **CORS locked to specific origins** — localhost:5173, 127.0.0.1:5173, fly.dev (NOT wildcard)
- **CI security pipeline** — pip-audit, gitleaks (--no-git mode), CodeQL (weekly + PR)
- **Dependabot** configured for pip and GitHub Actions
- **OAuth state validation** — CSRF protection with 5-min TTL on OAuth states
- **Session tokens** — `secrets.token_urlsafe(32)` + SHA-256 hash stored (not raw token)
- **Error masking** — `raise ... from None` prevents stack trace leakage to clients

---

## 2. Correctness (8/10)

### Test Results

```
383 passed, 42 skipped, 0 failed
Coverage gate: fail_under = 80%
Test matrix: Python 3.11 + 3.12
```

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **MEDIUM** | `discord_bot.py` (752 lines) — tests exist but 42 skipped tests may relate to mocking complexity | `tests/test_bot.py` (256 lines), `tests/test_commands.py` (1,221 lines) |
| **LOW** | `_ingest_killmails` count always increments even on `INSERT OR IGNORE` (no-op) | `backend/ingestion/poller.py:124` — `count += 1` fires regardless of actual insert |
| **LOW** | `_update_entities` accumulates `event_count` on every poll cycle (double-counting) | `backend/ingestion/poller.py:273` — `event_count = entities.event_count + excluded.event_count` |
| **LOW** | 3 ruff E501 violations in tests — CI lint job currently fails | `tests/test_cycle5.py:30,47,52` |
| **INFO** | `pytest-asyncio==1.3.0` in lockfile but `>=0.24.0` in pyproject.toml | Version mismatch in lock vs spec — lock has newer version |

### What's Solid

- **383 tests across 26 test files** — comprehensive coverage
- **26 backend modules, all tested** — including analysis, API, bot, ingestion, database
- **Test isolation** — each test gets its own in-memory SQLite
- **`respx` for HTTP mocking** — proper async HTTP client testing
- **Pydantic request validation** — `SubscribeRequest` uses regex pattern for wallet addresses
- **Query parameter validation** — `min_length`, `max_length`, `le` constraints on all Query params
- **Sort injection prevention** — `_ALLOWED_SORTS` frozenset whitelist
- **Async/sync correct** — async routes, sync analysis functions, proper `check_same_thread=False`
- **Entry point verified** — Dockerfile CMD matches `backend.api.app:app`

---

## 3. Infrastructure (8/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **MEDIUM** | No SQLite backup strategy (Litestream or similar) | `fly.toml` has persistent volume but no backup |
| **LOW** | `docker-compose.yml` has `restart: unless-stopped` but no healthcheck | Would improve container orchestration |
| **LOW** | `fly.toml` `min_machines_running = 0` — cold starts on first request | Acceptable for hackathon; problematic for production |
| **INFO** | `node_modules/` exists at project root (not in `.gitignore` path for root) | `.gitignore` has `node_modules/` which covers it |

### What's Solid

- **CI pipeline** — 4 jobs: lint (ruff check + format), test (matrix 3.11/3.12 with coverage), frontend (npm ci/test/build), security (pip-audit + gitleaks)
- **CodeQL workflow** — weekly schedule + push/PR triggers, Python language
- **Dependabot** — pip + github-actions, weekly cadence
- **Dockerfile** — `python:3.12-slim`, `--no-cache-dir`, copies only needed dirs
- **`requirements.lock`** — pinned versions for reproducible builds (56 packages)
- **Fly.io config** — persistent volume mount at `/app/data`, `force_https = true`, `auto_stop_machines`
- **Docker Compose** — env_file, volume mount for data persistence
- **Frontend build** — Vite 7 + TypeScript strict, built into `frontend/dist/` and served by FastAPI
- **Separate frontend CI** — Node 22, npm ci, test, build

---

## 4. Maintainability (7/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **MEDIUM** | `discord_bot.py` — 752 lines | Largest file; commands, autocomplete, views all in one. Should split by command group |
| **MEDIUM** | `poller.py` — 629 lines | 8 ingest functions + run loop. Could split `_ingest_*` into `ingestion/ingesters.py` |
| **LOW** | `routes.py` — 558 lines, 31 route functions | Could split into domain routers (entity, feed, intel, corp, subscription) |
| **LOW** | `fingerprint.py` — 489 lines | Complex but cohesive; borderline acceptable |
| **LOW** | `names.py` — 18 lines, only constants | Could merge into `naming_engine.py` to reduce module count |
| **INFO** | Global `_connection` singleton in `database.py` | Standard pattern for SQLite; works for single-process |

### What's Clean

- **Zero TODO/FIXME/HACK markers** — confirmed via grep across all `.py` files
- **Zero bare `except:` handlers** — all exception handlers catch specific types
- **Zero `print()` calls** — proper `logging` module throughout via `get_logger()`
- **Clean module structure** — 6 packages: `analysis/` (14 modules), `api/` (6), `bot/` (1), `core/` (2), `db/` (1), `ingestion/` (1)
- **Consistent naming** — snake_case throughout Python, proper `__init__.py` in all packages
- **`pathlib.Path` everywhere** — no `os.path` usage
- **No mutable default arguments** — `conditions: dict = {}` in Pydantic model is safe (Pydantic copies)
- **No commented-out code** in any file
- **Docstrings coverage** — ~399 docstring markers across 26 backend files (module + function level)
- **170 function definitions** with good ratio of documentation
- **Well-organized imports** — stdlib, third-party, local separation

---

## 5. Documentation (9/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **LOW** | No CHANGELOG.md | Conventional commits exist but no formal changelog |
| **LOW** | README stats outdated — says "362 tests" but 383 now passing | `README.md:26` |
| **INFO** | No OpenAPI endpoint descriptions beyond docstrings | FastAPI auto-docs work but sparse |

### What's Excellent

- **README.md** — 324 lines, hackathon-showcase quality:
  - Live demo link
  - ASCII architecture diagram showing full data flow
  - Full API endpoint table (33 endpoints)
  - Quick start, Docker, and configuration tables
  - Feature breakdown organized by tier (Free/Tactical/Reputation)
  - Earned titles with criteria tables
  - Discord bot command reference (11 commands)
  - Smart Contract subscription tier table
  - Tech stack and design principles
  - Hackathon context and "why WatchTower?"
- **LICENSE** — MIT, proper copyright
- **CLAUDE.md** — comprehensive project context with anti-patterns
- **`.env.example`** — commented with confirmed API base URL
- **docs/** — 4 documents: DEMO_SCRIPT.md, ASSEMBLY_GUIDE.md, api-notes.md, C5 task list
- **Module-level docstrings** on all 26 Python files
- **Function docstrings** on all public functions and route handlers

---

## 6. Freshness (9/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **INFO** | Last commit: 2026-03-10 01:39:19 | Less than 24 hours old |
| **INFO** | `discord.py` `audioop` deprecation | Will break on Python 3.13+ |

### Stack Versions (from `requirements.lock`)

| Component | Locked Version | Status |
|---|---|---|
| Python | 3.12.3 | Current stable |
| FastAPI | 0.135.1 | Current |
| Pydantic | 2.12.5 | Current |
| uvicorn | 0.41.0 | Current |
| httpx | 0.28.1 | Current |
| anthropic | 0.84.0 | Current |
| discord.py | 2.7.1 | Current (audioop deprecation) |
| React | 19.2.0 | Current |
| Vite | 7.3.1 | Current |
| Tailwind CSS | 4.2.1 | Current |
| TypeScript | 5.9.3 | Current |

All 56 locked Python dependencies are recent versions. No stale or abandoned packages. Frontend deps all on latest majors.

---

## Fix Recommendations (Ordered by ROI: impact / effort)

### Tier 1: High Impact / Low Effort (Do Before Hackathon)

| # | Fix | Effort | Impact | Category |
|---|---|---|---|---|
| 1 | Fix 3 ruff E501 violations in `tests/test_cycle5.py` | 5 min | CI lint passes | Correctness |
| 2 | Update README test count (362 -> 383) | 2 min | Accuracy | Documentation |
| 3 | Cap `_pending_states` dict size (e.g., max 1000 entries) | 5 min | Memory safety | Security |

### Tier 2: Medium Impact / Medium Effort (During Hackathon)

| # | Fix | Effort | Impact | Category |
|---|---|---|---|---|
| 4 | Fix `_ingest_killmails` count logic — check `lastrowid` or cursor changes | 15 min | Data accuracy | Correctness |
| 5 | Fix `_update_entities` event_count double-counting on repeated polls | 30 min | Data accuracy | Correctness |
| 6 | Add healthcheck to `docker-compose.yml` | 5 min | Container reliability | Infrastructure |
| 7 | Encrypt or omit EVE SSO access/refresh tokens in `eve_sessions` (or store only session hash) | 30 min | Token security | Security |
| 8 | Whitelist CORS `allow_headers` instead of `["*"]` | 5 min | Security hygiene | Security |

### Tier 3: Low Impact / Higher Effort (Post-Hackathon)

| # | Fix | Effort | Impact | Category |
|---|---|---|---|---|
| 9 | Split `discord_bot.py` (752 lines) into command groups | 1-2 hrs | Maintainability | Maintainability |
| 10 | Split `routes.py` (558 lines) into domain routers | 1-2 hrs | Maintainability | Maintainability |
| 11 | Split `poller.py` ingest functions into separate module | 1 hr | Maintainability | Maintainability |
| 12 | Add Litestream for SQLite WAL backup to S3 | 2-3 hrs | Data durability | Infrastructure |
| 13 | Add CHANGELOG.md with conventional commit parsing | 30 min | Documentation | Documentation |
| 14 | Set `min_machines_running = 1` in fly.toml for production | 2 min | Latency | Infrastructure |
| 15 | Investigate 42 skipped tests — ensure they're intentional | 1-2 hrs | Coverage confidence | Correctness |

---

## What's Done Well

1. **Test discipline** — 383 tests, 80%+ coverage gate enforced in CI, Python 3.11/3.12 matrix
2. **Security layers** — rate limiting, SSRF prevention, path traversal protection, security headers, CORS locked to specific origins, tier-gated access control
3. **CI/CD pipeline** — 4-job workflow (lint, test, frontend, security) + CodeQL + Dependabot
4. **Architecture** — clean separation: ingestion -> analysis (14 modules) -> API -> presentation (React + Discord)
5. **Resilience** — poller designed to never crash; all errors caught, logged, continued
6. **Smart caching** — AI narrative cache by entity + event hash avoids redundant Anthropic API calls
7. **Template fallback** — narrative engine works without API key via rule-based generation
8. **Full stack delivery** — Python backend + React frontend + Solidity contract + Discord bot + Fly.io deployment
9. **Modern, pinned stack** — all 56 Python deps locked, all on current versions
10. **Code hygiene** — zero TODOs, zero bare excepts, zero print statements, zero commented-out code, proper logging

---

*Original audit: 2026-03-10. Updated 2026-03-12 with post-Sui migration findings.*
