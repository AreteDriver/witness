"""The Oracle — standing intelligence watches with alert delivery.

Players set watches. The Oracle monitors continuously.
When conditions are met, alerts fire to Discord webhooks.
This is the locator agent.
"""

import json
import time

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("oracle")

EVE_ORANGE = 0xFF6600
EVE_RED = 0xFF0000
EVE_YELLOW = 0xFFCC00
EVE_GREEN = 0x00FF88
EVE_PURPLE = 0x9B59B6

COOLDOWN_SECONDS = 300  # 5 min between repeated alerts for same watch
BLIND_SPOT_THRESHOLD = 1200  # 20 min without scan = blind spot
CLONE_RESERVE_THRESHOLD = 5  # configurable via conditions


async def fire_webhook(webhook_url: str, title: str, message: str, color: int = EVE_ORANGE):
    """Send a Discord webhook embed."""
    payload = {
        "username": "WatchTower Oracle",
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": color,
                "footer": {"text": "WatchTower — The Living Memory of EVE Frontier"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ],
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(webhook_url, json=payload, timeout=5)
            if r.status_code not in (200, 204):
                logger.error("Webhook failed %d: %s", r.status_code, r.text[:200])
    except Exception as e:
        logger.error("Webhook error: %s", e)


async def check_watches() -> int:
    """Evaluate all active watches against current data. Fire alerts."""
    db = get_db()
    now = int(time.time())
    fired = 0

    watches = db.execute("""SELECT * FROM watches WHERE active = 1""").fetchall()

    for watch in watches:
        # Cooldown check
        if watch["last_triggered"] and (now - watch["last_triggered"]) < COOLDOWN_SECONDS:
            continue

        triggered = False
        alert_title = ""
        alert_body = ""
        alert_color = EVE_ORANGE

        try:
            conditions = json.loads(watch["conditions"]) if watch["conditions"] else {}
        except json.JSONDecodeError:
            continue

        if watch["watch_type"] == "entity_movement":
            # Alert when a specific entity (character/corp) transits any gate
            target = watch["target_id"]
            lookback = conditions.get("lookback_seconds", 300)
            cutoff = now - lookback

            recent = db.execute(
                """SELECT gate_name, solar_system_id, timestamp FROM gate_events
                   WHERE (character_id = ? OR corp_id = ?) AND timestamp > ?
                   ORDER BY timestamp DESC LIMIT 5""",
                (target, target, cutoff),
            ).fetchall()

            if recent:
                triggered = True
                gate_info = recent[0]["gate_name"] or "unknown gate"
                alert_title = f"MOVEMENT DETECTED: {target[:16]}"
                alert_body = (
                    f"**{len(recent)}** transit(s) in the last {lookback // 60} minutes\n"
                    f"Last seen: {gate_info}"
                )
                alert_color = EVE_YELLOW

        elif watch["watch_type"] == "gate_traffic_spike":
            target = watch["target_id"]
            threshold = conditions.get("threshold", 10)
            lookback = conditions.get("lookback_seconds", 3600)
            cutoff = now - lookback

            row = db.execute(
                "SELECT COUNT(*) as cnt FROM gate_events WHERE gate_id = ? AND timestamp > ?",
                (target, cutoff),
            ).fetchone()

            if row and row["cnt"] >= threshold:
                triggered = True
                alert_title = f"TRAFFIC SPIKE: Gate {target[:16]}"
                alert_body = (
                    f"**{row['cnt']}** transits in the last "
                    f"{lookback // 60} minutes (threshold: {threshold})"
                )
                alert_color = EVE_YELLOW

        elif watch["watch_type"] == "killmail_proximity":
            target = watch["target_id"]  # solar_system_id
            lookback = conditions.get("lookback_seconds", 1800)
            cutoff = now - lookback

            kills = db.execute(
                """SELECT COUNT(*) as cnt FROM killmails
                   WHERE solar_system_id = ? AND timestamp > ?""",
                (target, cutoff),
            ).fetchone()

            if kills and kills["cnt"] > 0:
                triggered = True
                alert_title = f"KILLMAIL ALERT: System {target[:16]}"
                alert_body = f"**{kills['cnt']}** kill(s) in the last {lookback // 60} minutes"
                alert_color = EVE_RED

        elif watch["watch_type"] == "hostile_sighting":
            # Alert when any entity from a watchlist transits monitored gates
            target_corps = conditions.get("corps", [])
            gate_ids = conditions.get("gates", [])
            lookback = conditions.get("lookback_seconds", 300)
            cutoff = now - lookback

            if target_corps and gate_ids:
                placeholders_corps = ",".join("?" * len(target_corps))
                placeholders_gates = ",".join("?" * len(gate_ids))
                sightings = db.execute(
                    f"""SELECT character_id, corp_id, gate_name FROM gate_events
                        WHERE corp_id IN ({placeholders_corps})
                        AND gate_id IN ({placeholders_gates})
                        AND timestamp > ?
                        ORDER BY timestamp DESC LIMIT 5""",
                    target_corps + gate_ids + [cutoff],
                ).fetchall()

                if sightings:
                    triggered = True
                    alert_title = "HOSTILE SIGHTED"
                    corps_seen = set(s["corp_id"] for s in sightings)
                    alert_body = (
                        f"**{len(sightings)}** hostile transit(s) detected\n"
                        f"Corps: {', '.join(c[:12] for c in corps_seen)}"
                    )
                    alert_color = EVE_RED

        if triggered:
            # Store alert in DB for frontend
            severity = "critical" if alert_color == EVE_RED else "warning"
            db.execute(
                """INSERT INTO watch_alerts (watch_id, user_id, title, body, severity)
                   VALUES (?, ?, ?, ?, ?)""",
                (watch["id"], watch["user_id"], alert_title, alert_body, severity),
            )

            # Publish to SSE event bus
            try:
                from backend.api.events import event_bus

                event_bus.publish(
                    "alert",
                    {
                        "watch_id": watch["id"],
                        "user_id": watch["user_id"],
                        "title": alert_title,
                        "body": alert_body,
                        "severity": severity,
                    },
                )
            except Exception:
                pass  # SSE is best-effort

            webhook_url = watch["webhook_url"] or settings.DISCORD_WEBHOOK_URL
            if webhook_url:
                await fire_webhook(webhook_url, alert_title, alert_body, alert_color)

            db.execute(
                "UPDATE watches SET last_triggered = ? WHERE id = ?",
                (now, watch["id"]),
            )
            fired += 1

    if fired > 0:
        db.commit()
        logger.info("Oracle fired %d alerts", fired)
    return fired


# ---------- Cycle 5: System-level alerts ----------
# These fire to the global Discord webhook, not per-watch.
# Tracked via story_feed to enforce cooldown.

_C5_ALERT_COOLDOWNS: dict[str, int] = {}


async def check_c5_alerts() -> int:
    """Evaluate Cycle 5 conditions and fire Discord alerts."""
    db = get_db()
    now = int(time.time())
    webhook_url = settings.DISCORD_WEBHOOK_URL
    if not webhook_url:
        return 0

    fired = 0

    # 1. Feral AI Evolved — tier increased in recent events
    recent_evolutions = db.execute(
        """SELECT zone_id, new_tier, timestamp
           FROM feral_ai_events
           WHERE event_type = 'evolution' AND timestamp > ?
           ORDER BY timestamp DESC LIMIT 10""",
        (now - COOLDOWN_SECONDS,),
    ).fetchall()

    for evt in recent_evolutions:
        key = f"feral_evolved_{evt['zone_id']}"
        if key in _C5_ALERT_COOLDOWNS and (now - _C5_ALERT_COOLDOWNS[key]) < COOLDOWN_SECONDS:
            continue
        zone = db.execute(
            "SELECT name FROM orbital_zones WHERE zone_id = ?",
            (evt["zone_id"],),
        ).fetchone()
        zone_name = zone["name"] if zone else evt["zone_id"][:16]
        tier = evt["new_tier"]

        if tier >= 3:
            # Critical tier gets its own alert
            title = "CRITICAL FERAL AI"
            body = f"**{zone_name}** reached Tier {tier} — requires immediate response"
            color = EVE_RED
        else:
            title = "FERAL AI EVOLVED"
            body = f"**{zone_name}** reached Tier {tier}"
            color = EVE_PURPLE

        await fire_webhook(webhook_url, title, body, color)
        _C5_ALERT_COOLDOWNS[key] = now
        fired += 1

    # 2. Hostile Scan — HOSTILE result in recent scans
    hostile_scans = db.execute(
        """SELECT scan_id, zone_id, scanner_name, scanned_at
           FROM scans WHERE result_type = 'HOSTILE' AND scanned_at > ?
           ORDER BY scanned_at DESC LIMIT 10""",
        (now - COOLDOWN_SECONDS,),
    ).fetchall()

    for scan in hostile_scans:
        key = f"hostile_scan_{scan['zone_id']}"
        if key in _C5_ALERT_COOLDOWNS and (now - _C5_ALERT_COOLDOWNS[key]) < COOLDOWN_SECONDS:
            continue
        zone = db.execute(
            "SELECT name FROM orbital_zones WHERE zone_id = ?",
            (scan["zone_id"],),
        ).fetchone()
        zone_name = zone["name"] if zone else scan["zone_id"][:16]
        scanner = scan["scanner_name"] or "unknown"

        await fire_webhook(
            webhook_url,
            "HOSTILE DETECTED",
            f"**{zone_name}** — scan by {scanner}",
            EVE_RED,
        )
        _C5_ALERT_COOLDOWNS[key] = now
        fired += 1

    # 3. Blind Spot — zones not scanned in >20 min
    blind_zones = db.execute(
        """SELECT zone_id, name, last_scanned
           FROM orbital_zones
           WHERE last_scanned IS NOT NULL AND last_scanned < ?""",
        (now - BLIND_SPOT_THRESHOLD,),
    ).fetchall()

    for zone in blind_zones:
        key = f"blind_spot_{zone['zone_id']}"
        if key in _C5_ALERT_COOLDOWNS and (now - _C5_ALERT_COOLDOWNS[key]) < COOLDOWN_SECONDS:
            continue
        minutes = (now - zone["last_scanned"]) // 60
        await fire_webhook(
            webhook_url,
            "BLIND SPOT",
            f"**{zone['name'] or zone['zone_id'][:16]}** unseen for {minutes}m",
            EVE_YELLOW,
        )
        _C5_ALERT_COOLDOWNS[key] = now
        fired += 1

    # 4. Clone Reserve Low — active clones below threshold per owner
    low_reserve = db.execute(
        """SELECT owner_id, owner_name, COUNT(*) as active_count
           FROM clones WHERE status = 'active'
           GROUP BY owner_id
           HAVING active_count < ?""",
        (CLONE_RESERVE_THRESHOLD,),
    ).fetchall()

    for owner in low_reserve:
        key = f"clone_low_{owner['owner_id']}"
        if key in _C5_ALERT_COOLDOWNS and (now - _C5_ALERT_COOLDOWNS[key]) < COOLDOWN_SECONDS:
            continue
        name = owner["owner_name"] or owner["owner_id"][:16]
        await fire_webhook(
            webhook_url,
            "CLONE RESERVE LOW",
            f"**{name}** — {owner['active_count']} active clones remaining",
            EVE_ORANGE,
        )
        _C5_ALERT_COOLDOWNS[key] = now
        fired += 1

    if fired > 0:
        logger.info("C5 Oracle fired %d alerts", fired)
    return fired
