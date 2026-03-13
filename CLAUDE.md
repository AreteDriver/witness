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
- **Contracts**: Sui Move (subscription, reputation, titles)
- **AI**: Anthropic API (narrative generation + token usage tracking)
- **Bot**: Discord webhooks
- **Deploy**: Fly.io (backend) + Vercel (frontend)
- **Tests**: 712 passing (31 test files), 80%+ coverage (pytest)
- **Codebase**: 217 source files, ~47K lines (Python + TypeScript + Move)
- **Data sources**: Sui GraphQL (dynamic), World API static (system names)

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
- AI token usage tracked in `ai_usage` table — `_track_usage()` in narrative.py, exposed via `/admin/analytics`
- Fingerprint logic is pure functions — no side effects, fully testable
- All C5 endpoints return `{ cycle: 5, reset_at: "...", data: [...] }` envelope
- HACKATHON_MODE + HACKATHON_ENDS env vars gate Spymaster-for-all with date-based auto-revert
- Auth uses challenge-response: `/wallet/challenge` → sign with dapp-kit → `/wallet/connect` verifies Ed25519 sig
- Frontend uses `useSignPersonalMessage()` from @mysten/dapp-kit for signing
- Full flow: POST /auth/wallet/challenge → sign with dApp kit → POST /auth/wallet/connect with {wallet_address, signature, message}
- Backend verifies Ed25519 signature, derives address from Blake2b-256(scheme_byte || public_key)
- Session persists across refresh via localStorage + /wallet/me verification
- Session TTL: 7 days, Challenge TTL: 5 minutes
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
- [x] Assembly locations → `LocationRevealedEvent` backfills solar_system + coordinates
- [x] Dead World API calls removed (tribes, C5 endpoints)
- [x] Periodic name re-bootstrap every 100 cycles
- [x] All DEBT items S1-S14 resolved (except S8, S9 coverage)
- [x] Live data confirmed flowing (18+ kills, 500+ assemblies, 1,320 characters)

Key Sui data shapes:
- Killmail: `key.item_id` → killmail_id, `killer_id.item_id` / `victim_id.item_id`, `solar_system_id.item_id`, `kill_timestamp` (unix str)
- Character: `character_address` (wallet), `key.item_id` (in-game), `metadata.name`, `tribe_id`
- Assembly: `assembly_id` (Sui obj), `type_id`, sender = owner (location from LocationRevealedEvent)
- LocationReveal: `assembly_id`, `solarsystem` (u64), `x`/`y`/`z` (strings)
- Entities match on BOTH `smart_characters.address` and `smart_characters.character_id`

---

## Architecture

```
witness/
├── backend/
│   ├── analysis/      # fingerprint, hotzones, kill_graph, narrative, reputation, streaks, story_feed, names, nexus, oracle, subscriptions, assembly_tracker, c5_analysis, corp_intel, naming_engine
│   ├── api/           # routes, auth, pricing, stripe_webhook, tier_gate, rate_limit, events (SSE), cycle5
│   ├── bot/           # discord webhooks
│   ├── core/          # config, logger
│   ├── db/            # database schema (SQLite WAL)
│   ├── ingestion/     # poller (Sui GraphQL → SQLite), sui_graphql adapter
│   └── warden/        # autonomous threat detection loop + doctrine
├── contracts/sui/sources/  # Move: subscription, reputation, titles
├── frontend/src/
│   ├── components/    # 31 React components
│   ├── contexts/      # AuthContext (wallet)
│   └── hooks/         # useEventStream (SSE), useSubscribe (Sui tx), usePricing (oracle)
├── tests/             # 712 tests (31 test files)
├── Dockerfile
├── fly.toml
└── frontend/vercel.json
```

### Key API Endpoints

| Endpoint | Description |
|---|---|
| **Entity Intelligence** | |
| `GET /entity/{id}` | Full dossier (kills, deaths, titles, danger, tribe) |
| `GET /entity/{id}/fingerprint` | Behavioral fingerprint (temporal, route, social, threat) |
| `GET /entity/{id}/reputation` | Trust score with 6-factor breakdown |
| `GET /entity/{id}/narrative` | AI-generated intelligence narrative |
| `GET /entity/{id}/streak` | Kill streak and momentum |
| `GET /entity/{id}/timeline` | Unified timeline of all events (kills + gate transits) |
| `GET /entities` | Paginated entity list with sort/filter |
| **System Intelligence** | |
| `GET /system/{id}` | System-level dossier (top combatants, stories, infrastructure) |
| `GET /system/{id}/narrative` | AI-generated system narrative |
| `GET /hotzones` | Kill density by system (24h/7d/30d/all windows) |
| `GET /hotzones/{solar_system_id}` | Detailed kill activity for a specific system |
| **Corporation Intelligence** | |
| `GET /corps` | Corporation leaderboard by combat activity |
| `GET /corps/rivalries` | Inter-corporation rivalries (mutual kills) |
| `GET /corp/{corp_id}` | Detailed corporation profile |
| **Feed & Discovery** | |
| `GET /feed` | Intel story feed with cursor pagination |
| `GET /search?q=` | Entity + system search |
| `GET /kill-graph` | Who-kills-whom graph with vendetta detection |
| `GET /leaderboard/{category}` | Top killers, most deaths, most traveled, etc. |
| `GET /titles` | Titled entities ranked by inscription count |
| `GET /streaks` | Entities currently on kill streaks |
| **Assemblies** | |
| `GET /assemblies` | Live Watcher Smart Assembly locations |
| `GET /assemblies/list` | All Watcher assembly locations |
| **Payment & Subscription** | |
| `GET /pricing` | Dynamic SUI/USD pricing for all tiers (CoinGecko/Binance oracle) |
| `GET /subscription/{wallet}` | Check subscription status for a wallet |
| `POST /subscribe` | Record subscription (chain event / demo) |
| `POST /checkout/create` | Create Stripe Checkout Session |
| `POST /webhooks/stripe` | Stripe webhook handler |
| **Watches & Alerts** | |
| `GET /watches` | List active watches for a user |
| `POST /watches` | Create a watch (SSRF-validated webhook) |
| `DELETE /watches/{target_id}` | Deactivate a watch |
| `GET /alerts` | List recent watch alerts |
| `POST /alerts/{id}/read` | Mark alert as read |
| **NEXUS (Builder Webhooks)** | |
| `POST /nexus/subscribe` | Register webhook subscription |
| `GET /nexus/subscriptions` | List subscriptions by API key |
| `PUT /nexus/subscriptions/{id}` | Update subscription filters/status |
| `DELETE /nexus/subscriptions/{id}` | Delete subscription |
| `GET /nexus/deliveries` | List recent delivery attempts |
| `GET /nexus/quota` | NEXUS quota usage for wallet |
| **Auth** | |
| `POST /auth/wallet/challenge` | Get challenge nonce to sign |
| `POST /auth/wallet/connect` | Submit signature, get session token |
| `GET /auth/wallet/me` | Verify current session |
| `POST /auth/wallet/disconnect` | End session |
| **Cycle 5** | |
| `GET /cycle` | Current cycle info |
| `GET /orbital-zones` | Orbital zone data |
| `GET /orbital-zones/{id}/history` | Zone history |
| `GET /orbital-zones/{id}/threat` | Zone threat analysis |
| `GET /scans` | Void scan data |
| `GET /scans/feed` | Void scan feed |
| `GET /clones` | Clone data |
| `GET /clones/queue` | Clone queue |
| `GET /crowns` | Crown data |
| `GET /crowns/roster` | Crown roster |
| `GET /briefing` | C5 intelligence briefing |
| **SSE** | |
| `GET /events` | Server-Sent Events stream |
| `GET /events/status` | SSE connection status |
| **Admin** | |
| `GET /admin/analytics` | Full analytics dashboard (admin wallets only) |
| `POST /admin/backfill-stories` | Regenerate story feed (admin only) |
| `POST /battle-report` | Generate AI battle report from events |
| `GET /health` | Health check with table counts |

### Frontend Components (31)

AccountPage, ActivityHeatmap, AdminAnalytics, AegisEcosystem, AssemblyMap, ChainIntegrity, CloneStatus, CompareView, CorpIntel, CrownRoster, CycleBanner, EntityPage, EntityTimeline, ErrorBoundary, FingerprintCard, HealthBanner, HotzoneMap, KillGraph, Leaderboard, NarrativePanel, NexusCard, OrbitalZones, ReputationBadge, SearchBar, StoryFeed, StreakTracker, SystemDossier, TierGate, TitleCard, VoidScanFeed, WalletConnect

### Frontend Hooks

- `useEventStream` — SSE real-time event stream
- `useSubscribe` — Sui on-chain subscription via `useSignAndExecuteTransaction`
- `usePricing` — Dynamic SUI/USD pricing from `/api/pricing` endpoint

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
| Best Technical | Strong | Poller, fingerprint engine, AI pipeline, 712 tests |
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

## Payment System

Hybrid SUI + Stripe + LUX payment architecture. Three payment channels funnel into one `watcher_subscriptions` table via `record_subscription()`.

### Pricing Oracle

- **Backend**: `backend/api/pricing.py` — `GET /api/pricing` returns dynamic SUI/USD conversion for all tiers
- **Price sources**: CoinGecko primary, Binance fallback, hard fallback at $3.00
- **Caching**: 60s TTL, stale threshold at 5 minutes, `is_stale` flag in response
- **Frontend**: `usePricing` hook polls `/api/pricing`, displays SUI amounts in payment UI
- **On-chain sync**: `update_prices()` Move entry function allows admin to push price updates to `SubscriptionConfig`

### Tier Pricing (USD source of truth)

| Tier | USD/week | Move constant |
|---|---|---|
| Scout (1) | $4.99 | `price_scout` |
| Oracle (2) | $9.99 | `price_oracle` |
| Spymaster (3) | $19.99 | `price_spymaster` |

### Payment Channels

- **Move contract**: `contracts/sui/sources/subscription.move` — `subscribe()` (SUI), `renew()` (extend existing), `credit_lux_payment()` (LUX via admin), `grant_subscription()` (comp), `update_prices()` (oracle)
- **On-chain payment**: "Pay with SUI" buttons use `useSignAndExecuteTransaction` from dApp kit → `watchtower::subscription::subscribe` entry function
- **SubscriptionCap**: Owned object minted on purchase — on-chain proof of subscription held in user's wallet, verifiable without backend via `is_active()`
- **Renewal**: `renew()` extends from current expiry (rewards early renewal), updates both `SubscriptionCap` and registry
- **Stripe checkout**: `POST /api/checkout/create` creates Stripe Checkout Session → redirects to Stripe → webhook processes payment
- **Stripe webhook**: `POST /api/webhooks/stripe` — signature verification, tier mapping, `record_subscription()`
- **DB columns**: `stripe_customer_id`, `stripe_subscription_id`, `payment_channel` on `watcher_subscriptions`
- **Config**: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (env prefix `WATCHTOWER_`)
- **Sui subscription events**: polled via `poll_subscriptions()` in poller

### Sui Contract Objects (Testnet)

**Modules**: `subscription.move`, `reputation.move`, `titles.move`

- Package: `0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca`
- SubscriptionConfig (shared, mutable prices): `0x7bd0e266d3c26665b13c432f70d9b7e5ecc266de993094f8ac8290020283be9d`
- SubscriptionRegistry (shared): `0x4bb5a6999fadd2039b8cfcb7a1b3de0f07973fe0ec74181b024edaaa6069d160`
- AdminCap (owned by deployer): `0x5af68eea339255f184218108fa52859a08b572e2f906940bafbed436cbbeaaae`
- ReputationRegistry: `0xf0cd2f096992dcc5ad532bc79e84332b5a3efe77cb6d46dffc6a9ccbac406e5c`
- TitleRegistry: `0x66ec6ab2e06c9f84854e643d7142efccada8124465b3b56a959414783cb80219`
- UpgradeCap: `0x5cce0badb147cba27b633f72f781a978637bb00ae35ddbd188e4ee8b90fc8ab7`
- TitleOracleCap: `0xaa18e829073dca0154b2b5672faed36043e4168f1b6f8f6a93ebb8810d1133f8`
- OracleCap (reputation): `0x9f6dfabb32c37b9ce5caf85600613b6cfb17e01b65216d890f4bfe8b5eefbdc7`

**Key contract types**:
- `SubscriptionConfig` — shared, holds mutable tier prices in MIST. Updated by admin via `update_prices()`
- `SubscriptionRegistry` — shared, tracks all subscription records + total revenue + treasury address
- `SubscriptionCap` — owned by subscriber, proof of active subscription (tier + expiry). Verifiable on-chain via `is_active()`
- `AdminCap` — owned by deployer, required for `update_prices()`, `grant_subscription()`, `credit_lux_payment()`, `update_treasury()`

**Move entry functions**: `subscribe()`, `renew()`, `update_prices()`, `grant_subscription()`, `credit_lux_payment()`, `update_treasury()`, `has_tier()`, `is_active()`, `config_price()`, `get_subscription()`

---

## NEXUS Scroll Behavior

NexusCard navigates to `/account#nexus`. AccountPage scrolls NEXUS section to center on mount when hash is `#nexus`.

---

## Aegis Stack

WatchTower is Track 1 of the Aegis Stack — six coordinated hackathon projects:

- **WatchTower** (this) — Chain archaeology + AI intel
- **Witness Protocol** — NEXUS behavioral reputation marketplace
- The Black Box, The Sovereign, Silk Road Protocol, The Warden System — supporting infrastructure

WatchTower displays live Monolith Chain Integrity metrics (events, anomalies, critical, high, bug reports) via polling `monolith-evefrontier.fly.dev/api/health` every 60s.

---

## Deferred: Temperature-Based Accessibility Scoring

**Source:** Community research (Anteris/Ergod [AWAR], Jan 28 2026). R²=0.9936 power law:
```
jump_range(T) = 2.21e9 / T^2.613
```
System temperature explains ~99% of jump range variance. High-temp systems are harder to reach — activity there signals committed actors, not opportunists. Add to system dossier as "accessibility rating" once World API provides per-system temperature data. Complements CradleOS Route Planner (they use cargo/heat sliders on the same underlying mechanic).

**Blocked on:** World API (temperature per system not available until API returns).

---

## C5 Alert Suppression

Cycle 5 (Shroud of Fear) alert types can be suppressed via env var when stale data causes noise:

```
WATCHTOWER_C5_ALERT_SUPPRESS="blind_spot,clone_reserve"
```

Valid types: `feral_evolved`, `hostile_scan`, `blind_spot`, `clone_reserve`. Currently `blind_spot` and `clone_reserve` are suppressed in production (World API dynamic data is dead, tables have stale data).

---

## NEXUS Dispatcher

Full webhook delivery system for builder integrations. Wired into the poller ingestion loop.

- **Schema**: `nexus_subscriptions` + `nexus_deliveries` tables
- **Dispatcher**: `backend/analysis/nexus.py` — filter matching, HMAC signing, retry with backoff, circuit breaker
- **Routes**: CRUD at `/api/nexus/*` (subscribe, list, update, delete, deliveries, quota)
- **Poller wire**: `dispatch_batch()` called after killmail + gate event ingestion
- **Quotas**: Tier-based (Oracle: 2 subs/100 day, Spymaster: 10 subs/1K day), hackathon mode grants Spymaster

---

## Environment Variables

All prefixed with `WATCHTOWER_` (pydantic-settings, loaded from `.env`).

| Variable | Default | Description |
|---|---|---|
| `WORLD_API_BASE` | `https://blockchain-gateway-stillness...` | Dynamic World API (DEAD — NXDOMAIN) |
| `WORLD_API_STATIC` | `https://world-api-stillness...` | Static World API (system names) |
| `POLL_INTERVAL_SECONDS` | `30` | Sui GraphQL poll frequency |
| `POLL_TIMEOUT_SECONDS` | `10.0` | HTTP timeout for poll requests |
| `DB_PATH` | `data/watchtower.db` | SQLite database path |
| `DISCORD_TOKEN` | `""` | Discord bot token |
| `DISCORD_WEBHOOK_URL` | `""` | Discord webhook for alerts |
| `STRIPE_SECRET_KEY` | `""` | Stripe API key (USD payments) |
| `STRIPE_WEBHOOK_SECRET` | `""` | Stripe webhook signature secret |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key (AI narratives) |
| `WATCHER_OWNER_ADDRESS` | `""` | Sui address for assembly tracker |
| `ADMIN_ADDRESSES` | `""` | Comma-separated admin wallet addresses |
| `HACKATHON_MODE` | `false` | Grant Spymaster tier to all users |
| `HACKATHON_ENDS` | `2026-04-01` | Auto-revert date for hackathon mode |
| `C5_ALERT_SUPPRESS` | `""` | Comma-separated C5 alert types to suppress |
| `WARDEN_ENABLED` | `true` | Enable autonomous threat detection loop |
| `WARDEN_MAX_ITERATIONS` | `10` | Max warden iterations per cycle |
| `WARDEN_MAX_DURATION_HOURS` | `24` | Max warden runtime |
| `WARDEN_INTERVAL_SECONDS` | `300` | Seconds between warden cycles |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |

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
