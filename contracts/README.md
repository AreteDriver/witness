# The Watcher — Smart Assembly Contract

On-chain subscription system for WatchTower oracle services.
Players pay items to access tiered intelligence features.

## Architecture

```
Player → Smart Assembly (in-game) → Pay items → Subscription recorded on-chain
                                                        ↓
WatchTower Backend ← verifies subscription ← Blockchain Gateway API
                                                        ↓
                                              Gated API endpoints unlock
```

## Tiers

| Tier | ID | Cost (items) | Access |
|------|----|-------------|--------|
| Free | 0 | 0 | Public leaderboards, hotzones, feed |
| Scout | 1 | 50 | Entity fingerprint, reputation score |
| Oracle | 2 | 200 | Locator agent, narrative dossiers, watches |
| Spymaster | 3 | 500 | Alt detection, vendetta network, battle reports |

## Setup

```bash
# Install dependencies
pnpm install

# Build contracts
pnpm mud build

# Deploy to testnet
pnpm run deploy:garnet
```

## In-Game Setup Guide

See `../docs/ASSEMBLY_GUIDE.md` for step-by-step instructions on:
- Creating the Watcher character
- Deploying Smart Assemblies across systems
- Configuring subscription tiers
- Managing assembly fleet
