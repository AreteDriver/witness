# The Watcher — Smart Assembly Setup Guide

Deploy Watcher subscription stations across EVE Frontier to sell oracle intel services in-game.

## Prerequisites

- EVE Frontier account with a character ("The Watcher" or similar)
- Items/fuel for deploying Smart Assemblies
- Node.js 18+ and pnpm for contract deployment
- Foundry toolchain (`forge`, `cast`)

## Step 1: Create The Watcher Character

1. Log into EVE Frontier
2. Create or designate a character — this is your service provider identity
3. Note the character's wallet address (visible in-game or via blockchain explorer)
4. Set `WATCHTOWER_WATCHER_OWNER_ADDRESS=0xYourAddress` in your `.env`

## Step 2: Deploy the Smart Contract

```bash
cd contracts/

# Install dependencies
pnpm install

# Build the MUD tables and systems
pnpm mud build

# Deploy to testnet (use garnet or pyrope depending on current chain)
WORLD_ADDRESS=0x... pnpm mud deploy --profile=garnet
```

Note the deployed System address — you'll need it for the DApp configuration.

## Step 3: Deploy Smart Assemblies In-Game

### Choosing Locations

Deploy assemblies in high-traffic systems for maximum visibility:

1. **Trade hubs** — wherever players congregate
2. **Gate chokepoints** — systems with the most gate transits (check your WatchTower hotzones data)
3. **Combat zones** — near dangerous systems where intel is most valuable
4. **Spawn areas** — where new players start

Use the WatchTower `/hotzones` endpoint to identify the busiest systems.

### Deploying an Assembly

1. Obtain a Smart Storage Unit (SSU) blueprint or item
2. Travel to target system
3. Deploy the SSU at desired coordinates
4. Anchor it and bring it online
5. Fuel it (keeps it active)
6. Configure it with the Watcher contract address

### Assembly Naming Convention

Name your assemblies for discoverability:
- `[WATCHTOWER] Oracle Station — {System Name}`
- `[WATCHTOWER] The Watcher's Eye`
- `[WATCHTOWER] Intel Service`

## Step 4: Configure Subscription Tiers

The contract supports three paid tiers:

| Tier | Cost | Duration | What They Get |
|------|------|----------|---------------|
| Scout (1) | 50 items | 7 days | Fingerprints, reputation scores |
| Oracle (2) | 200 items | 7 days | Locator agent, narratives, watches |
| Spymaster (3) | 500 items | 7 days | Alt detection, kill networks, battle reports |

### Setting Ratios (if using SSU vending)

In your DApp frontend or via direct contract call:
```
// Set exchange ratio: player deposits X items, gets tier Y access
setRatio(itemTypeId, 50, TIER_SCOUT)
setRatio(itemTypeId, 200, TIER_ORACLE)
setRatio(itemTypeId, 500, TIER_SPYMASTER)
```

## Step 5: Monitor Your Fleet

The WatchTower dashboard auto-tracks your assemblies:
- Visit the **Tactical** tab → **Watcher Network** panel
- Shows online/offline status, system locations, fleet health
- Updates automatically every 30 seconds (same as poller cycle)

### Assembly Health Checks

- **Fuel**: Keep assemblies fueled or they go offline
- **Destruction**: If an assembly is destroyed, it drops off the tracker automatically
- **Redeployment**: Deploy a new one and the tracker picks it up on next poll

## Step 6: Promote Your Service

### In-Game Advertising

1. Deploy assemblies in as many systems as possible — each one is a billboard
2. The assembly name itself advertises the service
3. Players who interact see what's available

### On the WatchTower Dashboard

The **Watcher Network** panel shows all your stations:
- Green dot = online and serving
- Red dot = offline (needs fuel or destroyed)
- Total systems covered = your reach

### Word of Mouth

Players who get value from the intel will tell others. The reputation system
itself generates conversation: "What's your trust score?"

## Operational Tips

1. **Start with 3-5 assemblies** in the highest-traffic systems
2. **Check fuel daily** — offline stations don't earn
3. **Use WatchTower data to choose locations** — deploy where the kills happen
4. **Monitor the story feed** — if a system goes hot, deploy there
5. **Keep The Watcher character active** — occasional gate transits build presence
6. **Respond to destruction** — if someone blows up your station, that's content. Redeploy.

## Troubleshooting

### Assembly not appearing on dashboard
- Check that `WATCHTOWER_WATCHER_OWNER_ADDRESS` matches your in-game wallet
- Wait for next poller cycle (30 seconds)
- Verify the assembly is anchored and online

### Contract deployment fails
- Ensure `WORLD_ADDRESS` is set correctly for your target chain
- Check that Foundry is installed: `forge --version`
- Verify chain RPC is accessible

### Subscription not registering
- Check the transaction on the block explorer
- Verify the contract event was emitted
- The backend caches subscription checks for 5 minutes
