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

COOLDOWN_SECONDS = 300  # 5 min between repeated alerts for same watch


async def fire_webhook(webhook_url: str, title: str, message: str, color: int = EVE_ORANGE):
    """Send a Discord webhook embed."""
    payload = {
        "username": "Witness Oracle",
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": color,
                "footer": {"text": "Witness — The Living Memory of EVE Frontier"},
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
