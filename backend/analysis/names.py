"""Shared name resolution for entity IDs → display names."""

import sqlite3


def resolve_names(db: sqlite3.Connection, entity_ids: set[str]) -> dict[str, str]:
    """Batch-resolve entity IDs to display names.

    Returns dict mapping entity_id → display_name (or truncated ID).
    """
    if not entity_ids:
        return {}

    names: dict[str, str] = {}
    for eid in entity_ids:
        row = db.execute("SELECT display_name FROM entities WHERE entity_id = ?", (eid,)).fetchone()
        names[eid] = row["display_name"] if row and row["display_name"] else eid[:12]
    return names
