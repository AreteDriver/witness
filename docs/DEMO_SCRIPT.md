# Witness Demo Script

**Duration**: 6-8 minutes
**URL**: https://witness-evefrontier.fly.dev

---

## 1. Opening (30s)

> "Witness is the living memory of EVE Frontier. It watches the blockchain, catalogs every on-chain event, and turns raw data into actionable intelligence. But it doesn't stop there — Witness scores trust, and the chain listens."

Show the dashboard landing page. Point out the health banner showing live data counts.

## 2. Search & Entity Dossier (60s)

- Type "Asterix" in the search bar
- Click the result to load their fingerprint
- Walk through the **Intelligence** tab:
  - **Fingerprint Card**: 484 kills, threat level EXTREME, OPSEC rating POOR
  - **Activity Heatmap**: shows what hours they're active (UTC)
  - **Event Timeline**: chronological kill history
  - **Narrative Panel**: AI-generated (or template) dossier

> "Asterix is the deadliest pilot on the frontier — 484 confirmed kills, 7 kills per day. Their OPSEC is rated POOR because they're predictable. The Witness sees everything."

## 3. Alt Detection (45s)

- Switch to **Compare** tab
- Enter two entity names
- Show the similarity scores: temporal, route, social, overall
- Point out "Likely Alt?" and "Fleet Mates?" detection

> "Witness can compare behavioral fingerprints to detect alts and fleet mates. Same schedules, same routes, same associates — the chain doesn't lie."

## 4. Tactical Intelligence (60s)

- Switch to **Tactical** tab
- Show the **Kill Network**: top kill relationships, vendetta detection
- Show **Danger Zones**: IL7-JQ9 with 51K kills rated EXTREME, toggle time windows
- Show **Active Hunters**: Asterix on a 140-kill streak, Kali Anemoi at 107

> "The Tactical tab is where Witness turns raw data into battlefield awareness. Who's hunting whom, which systems are death traps, and who's currently on fire. Asterix has a 140-kill streak — 25 kills this week alone."

## 5. Feed & Leaderboards (45s)

- Switch to **Feed & Rankings** tab
- Show the **Story Feed**: auto-generated news items (engagement clusters, hunter milestones)
- Show the **Leaderboard**: switch between Top Killers, Most Deaths, Most Traveled
- Click a leaderboard entry to jump to their dossier

> "The story feed auto-generates news from chain data. No AI needed — pure event detection. Who's fighting, where, and how often."

## 6. Reputation & Trust (60s)

- Navigate to an entity dossier (Asterix or another well-known pilot)
- Show the **Trust Score** badge: overall rating (0-100)
- Walk through the **6 dimensions**:
  - **Combat Honor** — Clean kills vs ganking behavior
  - **Target Diversity** — Range of opponents (not farming the same pilot)
  - **Reciprocity** — Fair fights vs one-sided engagements
  - **Consistency** — Stable behavior over time
  - **Community** — Gate construction, assembly deployment, positive-sum actions
  - **Restraint** — Avoidance of excessive force, new player protection
- Show a contrasting entity — a builder/gate deployer with high community score vs a ganker with low restraint
- Point out the human-readable factors ("Fair fighter", "Target farming detected")
- Point out the Smart Assembly gate hint: "This score can gate docking access"

> "Every entity gets a trust score from 0 to 100, computed across six dimensions. Asterix scores high on consistency — always hunting — but low on restraint and reciprocity. A gate builder who's never fired a shot? High community, high restraint. These scores aren't cosmetic — they flow back on-chain."

**API backup**:
```bash
curl https://witness-evefrontier.fly.dev/api/entity/{id}/reputation
```

## 7. The Watcher Economy (75s)

- Point to the **Connect Wallet** button in the header
- Show the **Watcher Assembly Network** panel:
  - Live tracker of deployed "The Watcher" Smart Assemblies across the frontier
  - Online/offline status per assembly
  - System coverage map, fleet health
  - Auto-updates from chain data (30s polling cycle)
- Explain the subscription model (WatcherSystem.sol, MUD v2):
  - **Scout** (cheapest tier) — Behavioral fingerprints, reputation scores
  - **Oracle** (mid tier) — + AI narratives, standing watches, locator agent
  - **Spymaster** (top tier) — + Alt detection, kill networks, battle reports
- Payment: 7-day subscriptions paid via Smart Assembly inventory transfer (in-game items)
- Show tier gating: attempt a Spymaster endpoint without subscription to see the gate

> "Witness runs on a Smart Contract economy. WatcherSystem.sol — a MUD v2 contract — manages three subscription tiers. Pay with in-game items at any Watcher station. Scout gets you fingerprints and reputation. Oracle adds narratives and watches. Spymaster unlocks the full intelligence suite."

> "And here's the loop that closes everything: chain data flows into Witness, Witness computes reputation, reputation flows back on-chain via the contract, and Smart Assemblies enforce it. A gate deployer can set 'deny docking if trust score is below 40.' The chain writes the rules. Witness provides the judgment."

**API backup**:
```bash
# Check subscription status
curl https://witness-evefrontier.fly.dev/api/subscription/{wallet}

# View assembly network
curl https://witness-evefrontier.fly.dev/api/assemblies
curl https://witness-evefrontier.fly.dev/api/assemblies/list
```

## 8. Earned Titles (30s)

- Point out titles on entity profiles: "The Hunter", "The Marked", "The Reaper"
- Explain: deterministic, same data = same title, everyone sees the same names

> "Titles are earned, not assigned. Get 50 kills, you're The Reaper. Die 10 times, you're The Marked. The chain writes the story."

## 9. Architecture & Tech (30s)

- Briefly mention the stack:
  - Never-crash poller (30s cycle, error isolation)
  - SQLite WAL for fast reads
  - Template narratives (no API key required) + AI upgrade path
  - MUD v2 Solidity contract for on-chain subscriptions
  - 238 tests, 28 endpoints, 17 analysis modules
  - Docker + Fly.io deployment

## 10. Close (15s)

> "The chain is the source of truth. Witness is the interpreter. And now, the enforcer. Witness doesn't just watch — it remembers, and the chain listens."

---

## Key Numbers to Mention

- 4,795 killmails ingested
- 35,278 smart assemblies tracked
- 36,085 entities with behavioral fingerprints
- 190 killers with confirmed kill counts
- 170 earned titles
- 224 auto-generated story feed items
- 28 API endpoints
- 17 analysis modules
- 5 Discord slash commands
- 238 tests passing
- 6-dimension trust scoring (0-100)
- 3 paid subscription tiers
- MUD v2 Smart Assembly contract

## Backup: API Demo (if frontend has issues)

```bash
# Health
curl https://witness-evefrontier.fly.dev/api/health

# Search
curl 'https://witness-evefrontier.fly.dev/api/search?q=Asterix'

# Fingerprint
curl https://witness-evefrontier.fly.dev/api/entity/0x63b127.../fingerprint

# Leaderboard
curl https://witness-evefrontier.fly.dev/api/leaderboard/top_killers

# Narrative
curl https://witness-evefrontier.fly.dev/api/entity/0x63b127.../narrative

# Reputation
curl https://witness-evefrontier.fly.dev/api/entity/0x63b127.../reputation

# Subscription check
curl https://witness-evefrontier.fly.dev/api/subscription/{wallet}

# Assembly network
curl https://witness-evefrontier.fly.dev/api/assemblies
curl https://witness-evefrontier.fly.dev/api/assemblies/list
```
