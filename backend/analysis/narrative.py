"""AI narrative engine — generates dossier bios and battle reports.

Uses Anthropic API. All generated content is cached by entity + event hash
to avoid redundant API calls.
"""

import hashlib
import json

import anthropic

from backend.analysis.entity_resolver import resolve_entity
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("narrative")

DOSSIER_SYSTEM = """You are the WatchTower — the living memory of EVE Frontier.
You analyze on-chain event data and write concise, evocative dossier entries
for game entities (gates, characters, corps, solar systems).

Write in the style of an intelligence briefing crossed with a history book.
Be specific — cite event counts, timestamps, patterns. Never invent data
not present in the input. Flag uncertainty when data is sparse.

Keep responses under 300 words. No markdown headers. Just prose."""

DOSSIER_USER = """Write a dossier entry for this EVE Frontier entity.

ENTITY PROFILE:
{profile_json}

RECENT TIMELINE (last 50 events):
{timeline_json}

Write a 2-3 paragraph dossier covering:
1. Who/what this entity is and their significance
2. Notable patterns, events, or behaviors
3. Current status and what to watch for"""

BATTLE_SYSTEM = """You are a tactical analyst for EVE Frontier.
You reconstruct engagements from on-chain event sequences.
Think like an NTSB investigator — methodical, evidence-based,
focused on the sequence of decisions that led to the outcome.

Always structure response as valid JSON matching the schema provided.
Never invent events not present in the data."""

BATTLE_USER = """Analyze this EVE Frontier engagement and produce a structured report.

TIMELINE ({event_count} events, {duration_seconds}s duration):
{timeline_json}

Produce JSON:
{{
  "title": "Short battle name (e.g. 'The Battle of X-7')",
  "summary": "2-3 sentence summary",
  "narrative": [
    {{"timestamp": <int>, "description": "What happened",
      "significance": "low|medium|high|critical"}}
  ],
  "key_moments": [
    {{"timestamp": <int>, "description": "Turning point or key decision"}}
  ],
  "anomalies": [
    {{"type": "timing|unknown_actor|pattern_break", "description": "What was unusual"}}
  ],
  "outcome": "Who won, what was lost, what changed",
  "lessons": ["Actionable recommendation"]
}}"""


def _get_client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _event_hash(data: dict | list) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_cached(db, entity_id: str, narrative_type: str, event_hash: str) -> str | None:
    row = db.execute(
        """SELECT content FROM narrative_cache
           WHERE entity_id = ? AND narrative_type = ? AND event_hash = ?""",
        (entity_id, narrative_type, event_hash),
    ).fetchone()
    return row["content"] if row else None


def _store_cache(db, entity_id: str, narrative_type: str, event_hash: str, content: str):
    db.execute(
        """INSERT OR REPLACE INTO narrative_cache
           (entity_id, narrative_type, event_hash, content)
           VALUES (?, ?, ?, ?)""",
        (entity_id, narrative_type, event_hash, content),
    )
    db.commit()


def _template_narrative(profile: dict) -> str:
    """Generate a template-based narrative when no AI API key is available."""
    d = profile
    name = d.get("display_name") or d.get("entity_id", "Unknown")[:16]
    etype = d.get("entity_type", "entity")
    events = d.get("event_count", 0)
    kills = d.get("kill_count", 0)
    deaths = d.get("death_count", 0)
    gates = d.get("gate_count", 0)
    titles = d.get("titles", [])
    danger = d.get("danger_rating", "unknown")

    parts = []

    if etype == "character":
        title_str = f', known as "{titles[0]}"' if titles else ""
        parts.append(
            f"{name}{title_str} has been observed across the frontier with "
            f"{events} recorded events. Their on-chain footprint spans "
            f"{gates} gate transits, {kills} confirmed kills, and {deaths} losses."
        )
        if kills > deaths and kills > 5:
            parts.append(
                f"Analysis marks this pilot as a significant combat threat "
                f"(danger rating: {danger}). Their kill-to-death ratio suggests "
                f"a seasoned hunter who chooses engagements carefully."
            )
        elif deaths > kills and deaths > 3:
            parts.append(
                "This pilot has suffered more losses than victories, suggesting "
                "either a trader navigating dangerous space or a pilot still "
                "learning the harsh realities of the frontier."
            )
        elif kills == 0 and deaths == 0 and gates > 20:
            parts.append(
                f"No combat record exists for this entity. With {gates} gate "
                f"transits and zero engagements, this appears to be a ghost — "
                f"moving through the frontier without leaving a mark."
            )
        else:
            parts.append(
                "Their activity pattern suggests a balanced operator, neither "
                "pure combatant nor pure trader."
            )
    elif etype == "gate":
        parts.append(f"Gate {name} has channeled {events} transits through its structure. ")
        if kills > 5:
            parts.append(
                f"With {kills} recorded kills in the vicinity, this gate has earned "
                f"its reputation as contested space. Pilots transiting here should "
                f"exercise caution."
            )
        else:
            parts.append(
                "Traffic flows relatively peacefully through this passage, though "
                "the frontier is never truly safe."
            )
    else:
        parts.append(f"{name} — {events} events recorded on-chain.")

    if titles:
        parts.append(f"Earned titles: {', '.join(titles)}.")

    return "\n\n".join(parts)


def generate_dossier_narrative(entity_id: str) -> str:
    """Generate a dossier entry for an entity. Uses AI when available, templates otherwise."""
    db = get_db()
    dossier = resolve_entity(db, entity_id)
    if not dossier:
        return "Entity not found."

    # Build timeline for context
    events = []
    for table, id_col in [
        ("gate_events", "gate_id"),
        ("gate_events", "character_id"),
        ("killmails", "victim_character_id"),
    ]:
        rows = db.execute(
            f"""SELECT * FROM {table} WHERE {id_col} = ?
                ORDER BY timestamp DESC LIMIT 25""",
            (entity_id,),
        ).fetchall()
        events.extend([dict(r) for r in rows])

    events.sort(key=lambda e: e.get("timestamp", 0))
    events = events[-50:]  # Last 50

    profile_data = dossier.to_dict()

    # Check cache
    eh = _event_hash({"profile": profile_data, "events": events})
    cached = _get_cached(db, entity_id, "dossier", eh)
    if cached:
        return cached

    # Fallback to template narrative if no API key
    if not settings.ANTHROPIC_API_KEY:
        content = _template_narrative(profile_data)
        _store_cache(db, entity_id, "dossier", eh, content)
        return content

    # Generate with AI
    try:
        client = _get_client()
        # Strip raw_json from events to save tokens
        clean_events = [{k: v for k, v in e.items() if k != "raw_json"} for e in events]

        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=DOSSIER_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": DOSSIER_USER.format(
                        profile_json=json.dumps(profile_data, indent=2),
                        timeline_json=json.dumps(clean_events, indent=2, default=str),
                    ),
                }
            ],
        )
        content = msg.content[0].text
        _store_cache(db, entity_id, "dossier", eh, content)
        logger.info("Generated dossier for %s", entity_id)
        return content
    except ValueError:
        logger.exception("Narrative generation error")
        return "Narrative temporarily unavailable."
    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        return _template_narrative(profile_data)


def generate_battle_report(events: list[dict]) -> dict:
    """Generate an AI battle report from a sequence of events."""
    if not events:
        return {"error": "No events provided"}

    eh = _event_hash(events)
    db = get_db()

    # Check cache using first event's entity as key
    cache_key = events[0].get("solar_system_id") or events[0].get("gate_id") or "battle"
    cached = _get_cached(db, cache_key, "battle", eh)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    try:
        client = _get_client()
        clean_events = [{k: v for k, v in e.items() if k != "raw_json"} for e in events]

        duration = events[-1].get("timestamp", 0) - events[0].get("timestamp", 0)

        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=BATTLE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": BATTLE_USER.format(
                        event_count=len(events),
                        duration_seconds=duration,
                        timeline_json=json.dumps(clean_events, indent=2, default=str),
                    ),
                }
            ],
        )

        content = msg.content[0].text
        # Parse JSON from response
        try:
            report = json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON block
            import re

            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                report = json.loads(match.group())
            else:
                return {"error": "Failed to parse battle report", "raw": content}

        _store_cache(db, cache_key, "battle", eh, json.dumps(report))
        logger.info("Generated battle report (%d events)", len(events))
        return report
    except ValueError:
        logger.exception("Battle report generation error")
        return {"error": "Battle report generation temporarily unavailable."}
    except Exception as e:
        logger.error("Battle report generation failed: %s", e)
        return {"error": "Battle report generation temporarily unavailable."}
