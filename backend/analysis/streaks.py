"""Streak & momentum tracker — kill streaks, dormancy detection.

Derives streak data from killmail timestamps per entity.
Feeds into story feed for milestone notifications.
"""

import json
import sqlite3
import time
from dataclasses import dataclass

from backend.analysis.names import resolve_names
from backend.core.logger import get_logger

logger = get_logger("streaks")

# A streak breaks if no kills within this window (seconds)
STREAK_WINDOW = 7 * 86400  # 7 days

# Dormancy threshold
DORMANT_AFTER = 14 * 86400  # 14 days without activity


@dataclass
class StreakInfo:
    """Kill streak and momentum data for an entity."""

    entity_id: str
    current_streak: int = 0
    longest_streak: int = 0
    current_streak_start: int = 0
    longest_streak_start: int = 0
    longest_streak_end: int = 0
    last_kill_time: int = 0
    status: str = "inactive"  # active, hot, dormant, inactive
    kills_7d: int = 0
    kills_30d: int = 0
    avg_kills_per_week: float = 0.0

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "current_streak_start": self.current_streak_start,
            "longest_streak_start": self.longest_streak_start,
            "longest_streak_end": self.longest_streak_end,
            "last_kill_time": self.last_kill_time,
            "status": self.status,
            "kills_7d": self.kills_7d,
            "kills_30d": self.kills_30d,
            "avg_kills_per_week": round(self.avg_kills_per_week, 2),
        }


def _get_kill_timestamps(db: sqlite3.Connection, entity_id: str) -> list[int]:
    """Get all kill timestamps for an entity, sorted ascending."""
    rows = db.execute(
        """SELECT timestamp, attacker_character_ids FROM killmails
           WHERE attacker_character_ids LIKE ?
           ORDER BY timestamp ASC""",
        (f'%"{entity_id}"%',),
    ).fetchall()

    # Verify entity is actually in the attacker list (LIKE can false-match)
    timestamps = []
    for row in rows:
        try:
            attackers = json.loads(row["attacker_character_ids"])
            for a in attackers:
                addr = str(a.get("address") or a.get("characterId") or a.get("id", ""))
                if addr == entity_id:
                    timestamps.append(row["timestamp"])
                    break
        except (json.JSONDecodeError, TypeError):
            continue
    return timestamps


def compute_streaks(
    db: sqlite3.Connection,
    entity_id: str,
) -> StreakInfo:
    """Compute kill streak and momentum data for an entity."""
    info = StreakInfo(entity_id=entity_id)
    timestamps = _get_kill_timestamps(db, entity_id)

    if not timestamps:
        return info

    now = int(time.time())
    info.last_kill_time = timestamps[-1]

    # Count recent kills
    info.kills_7d = sum(1 for t in timestamps if t >= now - 7 * 86400)
    info.kills_30d = sum(1 for t in timestamps if t >= now - 30 * 86400)

    # Average kills per week over active period
    first_kill = timestamps[0]
    active_weeks = max(1, (now - first_kill) / (7 * 86400))
    info.avg_kills_per_week = len(timestamps) / active_weeks

    # Compute streaks: a streak is consecutive kills within STREAK_WINDOW
    streaks: list[tuple[int, int, int]] = []  # (start_ts, end_ts, count)
    streak_start = timestamps[0]
    streak_count = 1
    prev_ts = timestamps[0]

    for ts in timestamps[1:]:
        if ts - prev_ts <= STREAK_WINDOW:
            streak_count += 1
        else:
            streaks.append((streak_start, prev_ts, streak_count))
            streak_start = ts
            streak_count = 1
        prev_ts = ts

    # Final streak
    streaks.append((streak_start, prev_ts, streak_count))

    # Find longest
    longest = max(streaks, key=lambda s: s[2])
    info.longest_streak = longest[2]
    info.longest_streak_start = longest[0]
    info.longest_streak_end = longest[1]

    # Current streak: is the last streak still active?
    last_streak = streaks[-1]
    if now - last_streak[1] <= STREAK_WINDOW:
        info.current_streak = last_streak[2]
        info.current_streak_start = last_streak[0]
    else:
        info.current_streak = 0

    # Status
    if now - info.last_kill_time <= 7 * 86400:
        info.status = "hot" if info.current_streak >= 5 else "active"
    elif now - info.last_kill_time <= DORMANT_AFTER:
        info.status = "cooling"
    else:
        info.status = "dormant"

    return info


def get_hot_streaks(
    db: sqlite3.Connection,
    limit: int = 10,
) -> list[dict]:
    """Get entities currently on kill streaks, ranked by streak length."""
    # Get all entities with kills
    entities = db.execute(
        """SELECT entity_id FROM entities
           WHERE entity_type = 'character' AND kill_count > 0
           ORDER BY kill_count DESC LIMIT 100"""
    ).fetchall()

    streaks = []
    for row in entities:
        info = compute_streaks(db, row["entity_id"])
        if info.current_streak > 0 or info.kills_7d > 0:
            streaks.append(info)

    # Sort by current streak, then kills_7d
    streaks.sort(key=lambda s: (s.current_streak, s.kills_7d), reverse=True)
    streaks = streaks[:limit]

    # Resolve display names
    ids = {s.entity_id for s in streaks}
    names = resolve_names(db, ids)

    result = []
    for s in streaks:
        d = s.to_dict()
        d["display_name"] = names.get(s.entity_id, s.entity_id[:12])
        result.append(d)
    return result
