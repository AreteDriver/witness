"""Story feed generator — auto-generates intel narratives from on-chain events.

Runs periodically, detects notable events, creates feed items.
Rule-based detection with narrative-style template rendering.
"""

import json
import time

from backend.analysis.names import resolve_names
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("story_feed")


def _post_story(
    db,
    event_type: str,
    headline: str,
    body: str,
    entity_ids: list[str],
    severity: str = "info",
    timestamp: int | None = None,
):
    """Insert a story into the feed if not duplicate."""
    ts = timestamp or int(time.time())
    # Dedup: same headline within 1 hour
    existing = db.execute(
        """SELECT id FROM story_feed
           WHERE headline = ? AND timestamp > ?""",
        (headline, ts - 3600),
    ).fetchone()
    if existing:
        return

    db.execute(
        """INSERT INTO story_feed (event_type, headline, body, entity_ids, severity, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, headline, body, json.dumps(entity_ids), severity, ts),
    )


def _resolve_system_name(db, system_id: str) -> str:
    """Resolve a solar system ID to a display name."""
    if not system_id:
        return "unknown space"
    row = db.execute(
        "SELECT solar_system_name FROM smart_assemblies WHERE solar_system_id = ? LIMIT 1",
        (system_id,),
    ).fetchone()
    if row and row["solar_system_name"]:
        return row["solar_system_name"]
    # Fallback: check killmails raw_json for system name, or truncate ID
    return system_id[:16]


def _get_cluster_actors(db, system_id: str, cutoff: int) -> dict:
    """Get victim and attacker names for a killmail cluster."""
    rows = db.execute(
        """SELECT victim_character_id, victim_name, attacker_character_ids
           FROM killmails
           WHERE solar_system_id = ? AND timestamp > ?
           ORDER BY timestamp DESC LIMIT 20""",
        (system_id, cutoff),
    ).fetchall()

    victim_ids: set[str] = set()
    attacker_ids: set[str] = set()
    for row in rows:
        if row["victim_character_id"]:
            victim_ids.add(row["victim_character_id"])
        try:
            attackers = json.loads(row["attacker_character_ids"] or "[]")
            for a in attackers:
                aid = a["address"] if isinstance(a, dict) else a
                if aid:
                    attacker_ids.add(aid)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    all_ids = victim_ids | attacker_ids
    names = resolve_names(db, all_ids) if all_ids else {}

    return {
        "victim_names": [names.get(v, v[:12]) for v in list(victim_ids)[:5]],
        "attacker_names": [names.get(a, a[:12]) for a in list(attacker_ids)[:5]],
        "victim_count": len(victim_ids),
        "attacker_count": len(attacker_ids),
    }


def detect_killmail_clusters(db, lookback_seconds: int = 3600) -> int:
    """Detect groups of killmails in the same system within a time window."""
    now = int(time.time())
    cutoff = now - lookback_seconds

    clusters = db.execute(
        """SELECT solar_system_id, COUNT(*) as cnt, MIN(timestamp) as first_ts,
                  MAX(timestamp) as last_ts
           FROM killmails
           WHERE timestamp > ? AND solar_system_id != ''
           GROUP BY solar_system_id
           HAVING cnt >= 3
           ORDER BY cnt DESC
           LIMIT 50""",
        (cutoff,),
    ).fetchall()

    count = 0
    for cluster in clusters:
        duration = cluster["last_ts"] - cluster["first_ts"]
        duration_min = max(1, duration // 60)
        severity = (
            "critical" if cluster["cnt"] >= 8 else "warning" if cluster["cnt"] >= 5 else "info"
        )

        system_name = _resolve_system_name(db, cluster["solar_system_id"])
        actors = _get_cluster_actors(db, cluster["solar_system_id"], cutoff)

        # Build narrative headline
        if cluster["cnt"] >= 8:
            headline = (
                f"Major engagement in {system_name} — "
                f"{cluster['cnt']} ships destroyed in {duration_min} minutes"
            )
        elif cluster["cnt"] >= 5:
            headline = (
                f"Firefight erupted in {system_name} — "
                f"{cluster['cnt']} kills confirmed over {duration_min} minutes"
            )
        else:
            headline = (
                f"Skirmish detected near {system_name} — "
                f"{cluster['cnt']} kills in {duration_min} minutes"
            )

        # Build narrative body
        body_parts = []
        if actors["victim_names"]:
            victims = ", ".join(actors["victim_names"][:3])
            if actors["victim_count"] > 3:
                victims += f" and {actors['victim_count'] - 3} others"
            body_parts.append(f"Confirmed losses: {victims}.")
        if actors["attacker_names"]:
            attackers = ", ".join(actors["attacker_names"][:3])
            if actors["attacker_count"] > 3:
                attackers += f" and {actors['attacker_count'] - 3} others"
            body_parts.append(f"Aggressors include {attackers}.")
        if actors["attacker_count"] >= 5:
            body_parts.append("Fleet-scale coordination detected.")

        body = " ".join(body_parts)

        _post_story(
            db,
            "engagement",
            headline,
            body,
            [cluster["solar_system_id"]],
            severity,
            cluster["last_ts"],
        )
        count += 1
    return count


def detect_new_entities(db, lookback_seconds: int = 3600) -> int:
    """Detect entities appearing on-chain for the first time."""
    now = int(time.time())
    cutoff = now - lookback_seconds

    new_entities = db.execute(
        """SELECT entity_id, entity_type, display_name, corp_id
           FROM entities
           WHERE first_seen > ? AND event_count <= 3""",
        (cutoff,),
    ).fetchall()

    count = 0
    for entity in new_entities:
        if entity["entity_type"] == "character":
            name = entity["display_name"] or entity["entity_id"][:12]
            corp_name = ""
            if entity["corp_id"]:
                corp_names = resolve_names(db, {entity["corp_id"]})
                corp_name = corp_names.get(entity["corp_id"], entity["corp_id"][:12])

            if corp_name:
                headline = (
                    f"{name} emerged from the void — first on-chain signature, "
                    f"flying under {corp_name}"
                )
            else:
                headline = (
                    f"{name} emerged from the void — "
                    "first on-chain signature detected"
                )

            body = "No prior behavioral record. Dossier initialized."

            _post_story(db, "new_entity", headline, body, [entity["entity_id"]], "info")
            count += 1
    return count


def detect_gate_milestones(db) -> int:
    """Detect gates hitting transit milestones."""
    milestones = [100, 500, 1000, 5000, 10000]
    count = 0

    for milestone in milestones:
        gates = db.execute(
            """SELECT entity_id, display_name, event_count FROM entities
               WHERE entity_type = 'gate' AND event_count >= ?
               AND event_count < ? + 50""",
            (milestone, milestone),
        ).fetchall()

        for gate in gates:
            name = gate["display_name"] or gate["entity_id"][:12]
            if milestone >= 5000:
                headline = (
                    f"Gate {name} crossed {milestone:,} transits — a major corridor of the frontier"
                )
            elif milestone >= 1000:
                headline = (
                    f"Gate {name} logged its {milestone:,}th transit — a well-traveled passage"
                )
            else:
                headline = f"Gate {name} reached {milestone:,} transits"

            body = f"Current count: {gate['event_count']:,} recorded passages."

            _post_story(db, "milestone", headline, body, [gate["entity_id"]], "info")
            count += 1
    return count


def detect_title_changes(db) -> int:
    """Post stories when entities earn new titles."""
    now = int(time.time())
    cutoff = now - 3600

    new_titles = db.execute(
        """SELECT t.entity_id, t.title, e.entity_type, e.display_name
           FROM entity_titles t
           JOIN entities e ON t.entity_id = e.entity_id
           WHERE t.computed_at > ?""",
        (cutoff,),
    ).fetchall()

    count = 0
    for t in new_titles:
        name = t["display_name"] or t["entity_id"][:12]
        entity_type = t["entity_type"].title()
        title = t["title"]

        headline = (
            f'{name} earned the title "{title}" — '
            "pattern confirmed from chain behavior"
        )
        body = (
            f"{entity_type} designation. "
            "Title derived from on-chain activity analysis, not self-assigned."
        )

        _post_story(db, "title", headline, body, [t["entity_id"]], "info")
        count += 1
    return count


def detect_streak_milestones(db) -> int:
    """Post stories when entities hit kill streak milestones."""
    from backend.analysis.streaks import compute_streaks

    milestones = [5, 10, 20, 50, 100]
    entities = db.execute(
        """SELECT entity_id, display_name FROM entities
           WHERE entity_type = 'character' AND kill_count >= 5
           ORDER BY kill_count DESC LIMIT 50"""
    ).fetchall()

    count = 0
    for entity in entities:
        info = compute_streaks(db, entity["entity_id"])
        if info.current_streak <= 0:
            continue

        for m in milestones:
            if info.current_streak >= m:
                name = entity["display_name"] or entity["entity_id"][:12]
                severity = "critical" if m >= 20 else "warning" if m >= 10 else "info"

                if m >= 50:
                    headline = (
                        f"{name} is on a {info.current_streak}-kill streak — "
                        "apex predator active on the frontier"
                    )
                elif m >= 20:
                    headline = (
                        f"{name} has claimed {info.current_streak} consecutive kills — "
                        "threat level escalating"
                    )
                elif m >= 10:
                    headline = (
                        f"{name} continues a {info.current_streak}-kill streak — "
                        "sustained aggression detected"
                    )
                else:
                    headline = (
                        f"{name} is building momentum — {info.current_streak} kills and counting"
                    )

                body = (
                    f"{info.kills_7d} kills in the last 7 days. "
                    f"Operational status: {info.status.upper()}."
                )

                _post_story(
                    db,
                    "streak",
                    headline,
                    body,
                    [entity["entity_id"]],
                    severity,
                )
                count += 1
                break  # only post highest milestone
    return count


def generate_feed_items() -> int:
    """Run all detectors and generate new story feed items."""
    db = get_db()
    total = 0
    total += detect_killmail_clusters(db)
    total += detect_new_entities(db)
    total += detect_gate_milestones(db)
    total += detect_title_changes(db)
    total += detect_streak_milestones(db)

    if total > 0:
        db.commit()
        logger.info("Generated %d new story feed items", total)
    return total


def generate_historical_feed() -> int:
    """One-time: generate feed items from all historical data."""
    db = get_db()
    total = 0

    # All-time killmail clusters (systems with 5+ kills)
    clusters = db.execute(
        """SELECT solar_system_id, COUNT(*) as cnt, MIN(timestamp) as first_ts,
                  MAX(timestamp) as last_ts
           FROM killmails WHERE solar_system_id != ''
           GROUP BY solar_system_id
           HAVING cnt >= 5
           ORDER BY cnt DESC
           LIMIT 30"""
    ).fetchall()

    for cluster in clusters:
        duration_days = max(1, (cluster["last_ts"] - cluster["first_ts"]) // 86400)
        severity = (
            "critical" if cluster["cnt"] >= 50 else "warning" if cluster["cnt"] >= 20 else "info"
        )
        system_name = _resolve_system_name(db, cluster["solar_system_id"])

        if cluster["cnt"] >= 50:
            headline = (
                f"{system_name} is a graveyard — "
                f"{cluster['cnt']} ships destroyed over {duration_days} days"
            )
        elif cluster["cnt"] >= 20:
            headline = (
                f"Prolonged conflict zone: {system_name} — "
                f"{cluster['cnt']} kills across {duration_days} days"
            )
        else:
            headline = (
                f"Recurring hostilities near {system_name} — "
                f"{cluster['cnt']} kills over {duration_days} days"
            )

        body = f"{cluster['cnt']} confirmed ship losses spanning {duration_days} days of activity."
        _post_story(
            db,
            "engagement",
            headline,
            body,
            [cluster["solar_system_id"]],
            severity,
            cluster["last_ts"],
        )
        total += 1

    # Top killers
    top_killers = db.execute(
        """SELECT entity_id, display_name, kill_count
           FROM entities WHERE kill_count >= 10
           ORDER BY kill_count DESC LIMIT 10"""
    ).fetchall()
    for k in top_killers:
        name = k["display_name"] or k["entity_id"][:16]
        headline = f"{name} — {k['kill_count']} confirmed kills on the frontier"
        body = "Ranked among the deadliest entities in the chain record."
        _post_story(db, "milestone", headline, body, [k["entity_id"]], "warning", int(time.time()))
        total += 1

    # Most died
    top_deaths = db.execute(
        """SELECT entity_id, display_name, death_count
           FROM entities WHERE death_count >= 20
           ORDER BY death_count DESC LIMIT 10"""
    ).fetchall()
    for d in top_deaths:
        name = d["display_name"] or d["entity_id"][:16]
        headline = (
            f"{name} has fallen {d['death_count']} times — "
            "the chain remembers every loss"
        )
        body = (
            "Persistent presence despite repeated destruction. "
            "Behavioral pattern suggests high-risk operations."
        )
        _post_story(db, "milestone", headline, body, [d["entity_id"]], "warning", int(time.time()))
        total += 1

    # Title stories
    total += detect_title_changes(db)

    if total > 0:
        db.commit()
        logger.info("Generated %d historical feed items", total)
    return total
