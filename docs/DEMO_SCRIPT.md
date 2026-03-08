# Witness Demo Script

**Duration**: 4-6 minutes
**URL**: https://witness-evefrontier.fly.dev

---

## 1. Opening (30s)

> "Witness is the living memory of EVE Frontier. It watches the blockchain, catalogs every on-chain event, and turns raw data into actionable intelligence."

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

## 6. Earned Titles (30s)

- Point out titles on entity profiles: "The Hunter", "The Marked", "The Reaper"
- Explain: deterministic, same data = same title, everyone sees the same names

> "Titles are earned, not assigned. Get 50 kills, you're The Reaper. Die 10 times, you're The Marked. The chain writes the story."

## 7. Architecture & Tech (30s)

- Briefly mention the stack:
  - Never-crash poller (30s cycle, error isolation)
  - SQLite WAL for fast reads
  - Template narratives (no API key required) + AI upgrade path
  - 185 tests
  - Docker + Fly.io deployment

## 8. Close (15s)

> "The chain is the source of truth. Witness is the interpreter. Free lore for the community. Paid intelligence for those who need an edge."

---

## Key Numbers to Mention

- 4,795 killmails ingested
- 35,350 smart assemblies tracked
- 36,000+ entities with behavioral fingerprints
- 190 killers with confirmed kill counts
- 170 earned titles
- 220 auto-generated story feed items
- 22 API endpoints
- 5 Discord slash commands
- 185 tests passing

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
```
