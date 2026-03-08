"""Watcher Assembly tracker — live map of deployed Watcher stations.

Reads from the existing smart_assemblies table (already ingested by poller)
and filters by the Watcher owner address. Auto-updates as assemblies
are deployed or destroyed.
"""

import sqlite3

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("assembly_tracker")


def get_watcher_assemblies(db: sqlite3.Connection) -> list[dict]:
    """Get all active Smart Assemblies owned by the Watcher.

    Returns list of assembly locations with status.
    Uses WATCHER_OWNER_ADDRESS from config to filter.
    """
    owner = settings.WATCHER_OWNER_ADDRESS
    if not owner:
        # Return all assemblies if no owner configured (demo mode)
        rows = db.execute(
            """SELECT assembly_id, assembly_type, owner_address, owner_name,
                      solar_system_id, solar_system_name,
                      x, y, z, state, ingested_at
               FROM smart_assemblies
               ORDER BY ingested_at DESC""",
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT assembly_id, assembly_type, owner_address, owner_name,
                      solar_system_id, solar_system_name,
                      x, y, z, state, ingested_at
               FROM smart_assemblies
               WHERE owner_address = ?
               ORDER BY ingested_at DESC""",
            (owner,),
        ).fetchall()

    assemblies = []
    for row in rows:
        assemblies.append(
            {
                "assembly_id": row["assembly_id"],
                "type": row["assembly_type"],
                "solar_system_id": row["solar_system_id"],
                "solar_system_name": row["solar_system_name"] or "",
                "state": row["state"],
                "position": {
                    "x": row["x"],
                    "y": row["y"],
                    "z": row["z"],
                },
                "deployed_at": row["ingested_at"],
            }
        )

    return assemblies


def get_assembly_stats(db: sqlite3.Connection) -> dict:
    """Summary stats for Watcher assembly fleet."""
    assemblies = get_watcher_assemblies(db)

    online = sum(1 for a in assemblies if a["state"] == "online")
    total = len(assemblies)
    systems = len({a["solar_system_id"] for a in assemblies})

    type_counts: dict[str, int] = {}
    for a in assemblies:
        t = a["type"] or "unknown"
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "total": total,
        "online": online,
        "offline": total - online,
        "systems_covered": systems,
        "by_type": type_counts,
        "assemblies": assemblies,
    }
