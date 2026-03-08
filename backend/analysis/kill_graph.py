"""Kill graph — who kills whom, how often.

Builds an adjacency graph from killmail data to surface
vendettas, hunting patterns, and coordinated ganks.
"""

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from backend.analysis.names import resolve_names
from backend.core.logger import get_logger

logger = get_logger("kill_graph")


@dataclass
class KillEdge:
    """A directed edge: attacker killed victim N times."""

    attacker_id: str
    victim_id: str
    count: int = 0
    systems: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "attacker": self.attacker_id,
            "victim": self.victim_id,
            "count": self.count,
            "systems": self.systems[:5],
        }


@dataclass
class KillGraphNode:
    """A node in the kill graph with aggregate stats."""

    entity_id: str
    display_name: str
    kills_out: int = 0  # edges where this entity is attacker
    deaths_in: int = 0  # edges where this entity is victim

    def to_dict(self) -> dict:
        return {
            "id": self.entity_id,
            "name": self.display_name,
            "kills": self.kills_out,
            "deaths": self.deaths_in,
        }


def build_kill_graph(
    db: sqlite3.Connection,
    entity_id: str | None = None,
    min_kills: int = 1,
    limit: int = 50,
) -> dict:
    """Build a kill graph centered on an entity or globally.

    Returns nodes + edges suitable for force-directed visualization.
    """
    # Collect all edges: attacker → victim → count
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)
    edge_systems: dict[tuple[str, str], set[str]] = defaultdict(set)

    if entity_id:
        # Get killmails where entity is involved (as victim or attacker)
        rows = db.execute(
            """SELECT victim_character_id, attacker_character_ids, solar_system_id
               FROM killmails
               WHERE victim_character_id = ?
                  OR attacker_character_ids LIKE ?""",
            (entity_id, f'%"{entity_id}"%'),
        ).fetchall()
    else:
        # Global: all killmails
        rows = db.execute(
            """SELECT victim_character_id, attacker_character_ids, solar_system_id
               FROM killmails"""
        ).fetchall()

    for row in rows:
        victim = row["victim_character_id"]
        system = row["solar_system_id"] or ""
        if not victim:
            continue

        try:
            attackers = json.loads(row["attacker_character_ids"])
        except (json.JSONDecodeError, TypeError):
            continue

        for a in attackers:
            attacker_id = str(a.get("address") or a.get("characterId") or a.get("id", ""))
            if not attacker_id or attacker_id == victim:
                continue
            key = (attacker_id, victim)
            edge_counts[key] += 1
            if system:
                edge_systems[key].add(system)

    # Filter by min_kills and sort by count
    edges = [
        KillEdge(
            attacker_id=k[0],
            victim_id=k[1],
            count=v,
            systems=sorted(edge_systems[k]),
        )
        for k, v in edge_counts.items()
        if v >= min_kills
    ]
    edges.sort(key=lambda e: e.count, reverse=True)
    edges = edges[:limit]

    # Build node set from edges
    node_ids: set[str] = set()
    node_kills: dict[str, int] = defaultdict(int)
    node_deaths: dict[str, int] = defaultdict(int)
    for e in edges:
        node_ids.add(e.attacker_id)
        node_ids.add(e.victim_id)
        node_kills[e.attacker_id] += e.count
        node_deaths[e.victim_id] += e.count

    # Batch-resolve display names
    names = resolve_names(db, node_ids)

    nodes = []
    for nid in node_ids:
        nodes.append(
            KillGraphNode(
                entity_id=nid,
                display_name=names.get(nid, nid[:12]),
                kills_out=node_kills.get(nid, 0),
                deaths_in=node_deaths.get(nid, 0),
            )
        )

    # Add names to edges
    edge_dicts = []
    for e in edges:
        d = e.to_dict()
        d["attacker_name"] = names.get(e.attacker_id, e.attacker_id[:12])
        d["victim_name"] = names.get(e.victim_id, e.victim_id[:12])
        edge_dicts.append(d)

    # Detect vendettas: mutual kills
    vendettas = []
    seen_pairs: set[tuple[str, str]] = set()
    for e in edges:
        reverse = (e.victim_id, e.attacker_id)
        if reverse in edge_counts and reverse not in seen_pairs:
            pair = tuple(sorted([e.attacker_id, e.victim_id]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                vendettas.append(
                    {
                        "entity_1": e.attacker_id,
                        "entity_1_name": names.get(e.attacker_id, e.attacker_id[:12]),
                        "entity_2": e.victim_id,
                        "entity_2_name": names.get(e.victim_id, e.victim_id[:12]),
                        "kills_1_to_2": e.count,
                        "kills_2_to_1": edge_counts[reverse],
                        "total": e.count + edge_counts[reverse],
                    }
                )

    vendettas.sort(key=lambda v: v["total"], reverse=True)

    return {
        "nodes": [n.to_dict() for n in nodes],
        "edges": edge_dicts,
        "vendettas": vendettas[:10],
        "total_edges": len(edges),
        "total_nodes": len(nodes),
    }
