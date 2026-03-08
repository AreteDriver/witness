"""On-chain reputation scoring — trust derived from behavioral patterns.

Computes a 0-100 trust score from kill patterns, target diversity,
streak behavior, vendetta participation, and activity consistency.
Designed for Smart Assembly contract gating: "deny docking if trust < 40".
"""

import json
import math
import sqlite3
from dataclasses import dataclass, field

from backend.core.logger import get_logger

logger = get_logger("reputation")

# --- Score weights (must sum to 1.0) ---
W_COMBAT_HONOR = 0.25  # Fair fighter vs serial ganker
W_TARGET_DIVERSITY = 0.15  # Variety of targets (not farming one person)
W_RECIPROCITY = 0.20  # Participates in mutual fights (vendettas)
W_CONSISTENCY = 0.15  # Stable activity pattern over time
W_COMMUNITY = 0.15  # Group play, corp participation
W_RESTRAINT = 0.10  # Not killing excessively relative to population


@dataclass
class ReputationScore:
    """Trust score breakdown for an entity."""

    entity_id: str
    trust_score: int = 50  # 0-100
    rating: str = "neutral"
    combat_honor: float = 0.0
    target_diversity: float = 0.0
    reciprocity: float = 0.0
    consistency: float = 0.0
    community: float = 0.0
    restraint: float = 0.0
    kills: int = 0
    deaths: int = 0
    unique_victims: int = 0
    unique_attackers: int = 0
    vendettas: int = 0
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "trust_score": self.trust_score,
            "rating": self.rating,
            "breakdown": {
                "combat_honor": round(self.combat_honor, 1),
                "target_diversity": round(self.target_diversity, 1),
                "reciprocity": round(self.reciprocity, 1),
                "consistency": round(self.consistency, 1),
                "community": round(self.community, 1),
                "restraint": round(self.restraint, 1),
            },
            "stats": {
                "kills": self.kills,
                "deaths": self.deaths,
                "unique_victims": self.unique_victims,
                "unique_attackers": self.unique_attackers,
                "vendettas": self.vendettas,
            },
            "factors": self.factors,
        }


def _trust_rating(score: int) -> str:
    """Human-readable trust rating."""
    if score >= 80:
        return "trusted"
    if score >= 60:
        return "reputable"
    if score >= 40:
        return "neutral"
    if score >= 20:
        return "suspicious"
    return "dangerous"


def _extract_ids(raw_list: list) -> list[str]:
    """Normalize attacker list — handles both plain strings and dicts."""
    ids = []
    for item in raw_list:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and "address" in item:
            ids.append(item["address"])
    return ids


def _get_kill_victims(db: sqlite3.Connection, entity_id: str) -> list[str]:
    """Get all victim IDs where entity was an attacker."""
    rows = db.execute(
        "SELECT victim_character_id, attacker_character_ids FROM killmails",
    ).fetchall()
    victims = []
    for row in rows:
        try:
            raw = json.loads(row["attacker_character_ids"] or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        attacker_ids = _extract_ids(raw)
        if entity_id in attacker_ids:
            victims.append(row["victim_character_id"])
    return victims


def _get_death_attackers(db: sqlite3.Connection, entity_id: str) -> list[str]:
    """Get all attacker IDs from kills where entity was victim."""
    rows = db.execute(
        "SELECT attacker_character_ids FROM killmails WHERE victim_character_id = ?",
        (entity_id,),
    ).fetchall()
    attackers = []
    for row in rows:
        try:
            raw = json.loads(row["attacker_character_ids"] or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        attackers.extend(_extract_ids(raw))
    return attackers


def _combat_honor_score(kills: int, deaths: int) -> float:
    """Fair fighter score. Balanced K/D = higher honor.

    Pure gankers (high kills, zero deaths) score low.
    Balanced fighters score high. Pure victims score moderate.
    """
    total = kills + deaths
    if total == 0:
        return 50.0  # No combat data = neutral

    ratio = kills / total  # 0.0 (all deaths) to 1.0 (all kills)

    # Bell curve centered at 0.5 (balanced K/D)
    # Score peaks at 50/50 ratio, drops at extremes
    honor = 100.0 * math.exp(-((ratio - 0.5) ** 2) / 0.08)

    # Small bonus for having combat experience at all
    experience_bonus = min(10.0, total * 0.5)

    return min(100.0, honor + experience_bonus)


def _target_diversity_score(victims: list[str]) -> float:
    """Score based on variety of targets. Farming one person = low score."""
    if not victims:
        return 50.0  # No kills = neutral

    unique = len(set(victims))
    total = len(victims)

    # Ratio of unique victims to total kills
    diversity_ratio = unique / total  # 1.0 = all different, low = farming

    # Shannon entropy of victim distribution
    from collections import Counter

    counts = Counter(victims)
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    max_entropy = math.log2(max(1, unique))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

    return min(100.0, (diversity_ratio * 50) + (normalized_entropy * 50))


def _reciprocity_score(
    entity_id: str,
    victims: list[str],
    attackers: list[str],
) -> tuple[float, int]:
    """Score based on mutual fights (vendettas). Higher = more honorable.

    Returns (score, vendetta_count).
    """
    victim_set = set(victims)
    attacker_set = set(attackers)

    # Vendettas = entities who are both your victims and your killers
    mutual = victim_set & attacker_set
    vendetta_count = len(mutual)

    total_unique = len(victim_set | attacker_set)
    if total_unique == 0:
        return 50.0, 0

    # Higher ratio of mutual combatants = more honorable
    mutual_ratio = vendetta_count / total_unique
    score = min(100.0, mutual_ratio * 200)  # Cap at 100, boost mutual fights

    return score, vendetta_count


def _consistency_score(db: sqlite3.Connection, entity_id: str) -> float:
    """Score based on activity consistency over time.

    Entities active across many days/weeks score higher than
    burst-active entities.
    """
    entity = db.execute(
        "SELECT first_seen, last_seen, event_count FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if not entity:
        return 50.0

    first = entity["first_seen"] or 0
    last = entity["last_seen"] or 0
    events = entity["event_count"] or 0

    if first == 0 or last == 0 or events < 2:
        return 50.0  # Not enough data

    span_days = max(1, (last - first) / 86400)
    events_per_day = events / span_days

    # Moderate, sustained activity scores best
    # Too bursty (>20 events/day avg) or too sparse (<0.1) score lower
    if events_per_day > 20:
        return max(30.0, 100.0 - (events_per_day - 20) * 2)
    if events_per_day < 0.1:
        return max(20.0, events_per_day * 500)

    # Sweet spot: 0.5-5 events/day
    return min(100.0, 40.0 + events_per_day * 12)


def _community_score(db: sqlite3.Connection, entity_id: str) -> float:
    """Score based on group participation.

    Corp membership + co-transit with others = community engagement.
    """
    entity = db.execute(
        "SELECT corp_id, gate_count FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if not entity:
        return 50.0

    score = 50.0  # Base

    # Corp membership bonus
    if entity["corp_id"]:
        score += 20.0

    # Gate activity suggests engagement with the world
    gate_count = entity["gate_count"] or 0
    if gate_count > 0:
        score += min(30.0, gate_count * 2)

    return min(100.0, score)


def _restraint_score(
    db: sqlite3.Connection,
    kills: int,
) -> float:
    """Score based on not being excessively lethal relative to population.

    Checks if this entity's kills are disproportionate to the
    overall kill distribution.
    """
    if kills == 0:
        return 80.0  # No kills = showing restraint

    # Get average kills per entity
    row = db.execute(
        "SELECT AVG(kill_count) as avg_k, MAX(kill_count) as max_k "
        "FROM entities WHERE kill_count > 0",
    ).fetchone()
    if not row or not row["avg_k"]:
        return 50.0

    avg_kills = row["avg_k"]

    # How many standard deviations above average?
    ratio = kills / max(1, avg_kills)

    if ratio <= 1.0:
        return 90.0  # Below average kills
    if ratio <= 2.0:
        return 70.0
    if ratio <= 5.0:
        return 50.0
    if ratio <= 10.0:
        return 30.0
    return 10.0  # Extremely prolific killer


def compute_reputation(
    db: sqlite3.Connection,
    entity_id: str,
) -> ReputationScore:
    """Compute trust/reputation score for an entity.

    Returns a ReputationScore with 0-100 trust_score and breakdown.
    """
    rep = ReputationScore(entity_id=entity_id)

    entity = db.execute(
        "SELECT * FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if not entity:
        rep.factors.append("Entity not found — default neutral score")
        return rep

    rep.kills = entity["kill_count"] or 0
    rep.deaths = entity["death_count"] or 0

    # Gather combat data
    victims = _get_kill_victims(db, entity_id)
    attackers = _get_death_attackers(db, entity_id)
    rep.unique_victims = len(set(victims))
    rep.unique_attackers = len(set(attackers))

    # Compute sub-scores
    rep.combat_honor = _combat_honor_score(rep.kills, rep.deaths)
    rep.target_diversity = _target_diversity_score(victims)
    rep.reciprocity, rep.vendettas = _reciprocity_score(entity_id, victims, attackers)
    rep.consistency = _consistency_score(db, entity_id)
    rep.community = _community_score(db, entity_id)
    rep.restraint = _restraint_score(db, rep.kills)

    # Weighted aggregate
    raw = (
        rep.combat_honor * W_COMBAT_HONOR
        + rep.target_diversity * W_TARGET_DIVERSITY
        + rep.reciprocity * W_RECIPROCITY
        + rep.consistency * W_CONSISTENCY
        + rep.community * W_COMMUNITY
        + rep.restraint * W_RESTRAINT
    )
    rep.trust_score = max(0, min(100, int(raw)))
    rep.rating = _trust_rating(rep.trust_score)

    # Generate human-readable factors
    if rep.combat_honor >= 70:
        rep.factors.append("Fair fighter — balanced kill/death ratio")
    elif rep.combat_honor < 30:
        rep.factors.append("Asymmetric combatant — heavily skewed K/D")

    if rep.target_diversity >= 70:
        rep.factors.append("Diverse targeting — no target farming")
    elif rep.target_diversity < 30 and rep.kills > 3:
        rep.factors.append("Target farming detected — repeat victims")

    if rep.vendettas >= 3:
        rep.factors.append(f"{rep.vendettas} active vendettas — mutual combatant")
    elif rep.vendettas == 0 and rep.kills > 5:
        rep.factors.append("No mutual fights — one-directional aggression")

    if rep.consistency >= 70:
        rep.factors.append("Consistent presence — reliable activity pattern")

    if rep.restraint < 30:
        rep.factors.append("Excessive lethality — far above average kills")

    return rep
