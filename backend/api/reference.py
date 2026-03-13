"""Reference data API — ships, types, constellations, gate links from World API."""

from fastapi import APIRouter

from backend.db.database import get_db

router = APIRouter()


@router.get("/ships")
def list_ships(limit: int = 50, class_name: str | None = None):
    """List ship reference data with optional class filter."""
    db = get_db()
    if class_name:
        rows = db.execute(
            "SELECT * FROM ships WHERE class_name = ? ORDER BY name LIMIT ?",
            (class_name, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM ships ORDER BY name LIMIT ?", (limit,)
        ).fetchall()
    return {
        "ships": [
            {
                "ship_id": r["ship_id"],
                "name": r["name"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "armor": r["armor"],
                "shield": r["shield"],
                "structure": r["structure"],
                "high_slots": r["high_slots"],
                "medium_slots": r["medium_slots"],
                "low_slots": r["low_slots"],
                "cpu_output": r["cpu_output"],
                "powergrid_output": r["powergrid_output"],
                "max_velocity": r["max_velocity"],
                "fuel_capacity": r["fuel_capacity"],
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/ships/{ship_id}")
def get_ship(ship_id: str):
    """Get detailed ship stats."""
    db = get_db()
    r = db.execute("SELECT * FROM ships WHERE ship_id = ?", (ship_id,)).fetchone()
    if not r:
        return {"error": "Ship not found"}, 404
    return {
        "ship_id": r["ship_id"],
        "name": r["name"],
        "class_id": r["class_id"],
        "class_name": r["class_name"],
        "armor": r["armor"],
        "shield": r["shield"],
        "structure": r["structure"],
        "high_slots": r["high_slots"],
        "medium_slots": r["medium_slots"],
        "low_slots": r["low_slots"],
        "cpu_output": r["cpu_output"],
        "powergrid_output": r["powergrid_output"],
        "max_velocity": r["max_velocity"],
        "fuel_capacity": r["fuel_capacity"],
    }


@router.get("/types")
def list_types(limit: int = 50, category: str | None = None):
    """List item type reference data with optional category filter."""
    db = get_db()
    if category:
        rows = db.execute(
            "SELECT * FROM item_types WHERE category = ? ORDER BY name LIMIT ?",
            (category, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM item_types ORDER BY name LIMIT ?", (limit,)
        ).fetchall()
    return {
        "types": [
            {
                "type_id": r["type_id"],
                "name": r["name"],
                "category": r["category"],
                "group_name": r["group_name"],
                "volume": r["volume"],
                "mass": r["mass"],
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/constellations")
def list_constellations(limit: int = 100, region_id: str | None = None):
    """List constellations with optional region filter."""
    db = get_db()
    if region_id:
        rows = db.execute(
            "SELECT * FROM constellations WHERE region_id = ? ORDER BY name LIMIT ?",
            (region_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM constellations ORDER BY name LIMIT ?", (limit,)
        ).fetchall()
    return {
        "constellations": [
            {
                "constellation_id": r["constellation_id"],
                "name": r["name"],
                "region_id": r["region_id"],
            }
            for r in rows
        ],
        "total": len(rows),
    }


@router.get("/topology")
def get_topology(system_id: str | None = None, limit: int = 200):
    """Get gate link topology. Optionally filter by system."""
    db = get_db()
    if system_id:
        rows = db.execute(
            """SELECT * FROM gate_links
               WHERE source_system_id = ? OR destination_system_id = ?
               ORDER BY gate_name LIMIT ?""",
            (system_id, system_id, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM gate_links ORDER BY source_system_id LIMIT ?",
            (limit,),
        ).fetchall()
    return {
        "links": [
            {
                "gate_id": r["gate_id"],
                "gate_name": r["gate_name"],
                "source_system_id": r["source_system_id"],
                "destination_system_id": r["destination_system_id"],
                "x": r["x"],
                "y": r["y"],
                "z": r["z"],
            }
            for r in rows
        ],
        "total": len(rows),
    }
