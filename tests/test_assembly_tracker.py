"""Tests for Watcher assembly tracker."""

import sqlite3
from unittest.mock import patch

import pytest

from backend.analysis.assembly_tracker import get_assembly_stats, get_watcher_assemblies
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture
def seeded_db(db):
    """DB with smart assemblies."""
    db.execute(
        "INSERT INTO smart_assemblies "
        "(assembly_id, assembly_type, owner_address, owner_name, "
        "solar_system_id, solar_system_name, x, y, z, state, name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "asm-1",
            "SSU",
            "0xWatcher",
            "The Watcher",
            "sys-001",
            "Alpha System",
            1.0,
            2.0,
            3.0,
            "online",
            "[WITNESS] Oracle Station",
        ),
    )
    db.execute(
        "INSERT INTO smart_assemblies "
        "(assembly_id, assembly_type, owner_address, owner_name, "
        "solar_system_id, solar_system_name, x, y, z, state, name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "asm-2",
            "SSU",
            "0xWatcher",
            "The Watcher",
            "sys-002",
            "Beta System",
            4.0,
            5.0,
            6.0,
            "online",
            "[WITNESS] Intel Hub",
        ),
    )
    db.execute(
        "INSERT INTO smart_assemblies "
        "(assembly_id, assembly_type, owner_address, owner_name, "
        "solar_system_id, solar_system_name, x, y, z, state, name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "asm-3",
            "Gate",
            "0xOther",
            "Someone Else",
            "sys-003",
            "Gamma System",
            7.0,
            8.0,
            9.0,
            "online",
            "Random Gate",
        ),
    )
    db.execute(
        "INSERT INTO smart_assemblies "
        "(assembly_id, assembly_type, owner_address, owner_name, "
        "solar_system_id, solar_system_name, x, y, z, state, name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "asm-4",
            "SSU",
            "0xWatcher",
            "The Watcher",
            "sys-001",
            "Alpha System",
            10.0,
            11.0,
            12.0,
            "offline",
            "[WITNESS] Down Station",
        ),
    )
    db.commit()
    return db


class TestGetWatcherAssemblies:
    def test_empty_db(self, db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = ""
            result = get_watcher_assemblies(db)
        assert result == []

    def test_filter_by_owner(self, seeded_db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = "0xWatcher"
            result = get_watcher_assemblies(seeded_db)
        assert len(result) == 3  # asm-1, asm-2, asm-4 (not asm-3)
        ids = {a["assembly_id"] for a in result}
        assert "asm-3" not in ids

    def test_no_owner_returns_all(self, seeded_db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = ""
            result = get_watcher_assemblies(seeded_db)
        assert len(result) == 4  # All assemblies

    def test_assembly_structure(self, seeded_db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = "0xWatcher"
            result = get_watcher_assemblies(seeded_db)
        asm = result[0]
        assert "assembly_id" in asm
        assert "type" in asm
        assert "solar_system_id" in asm
        assert "solar_system_name" in asm
        assert "state" in asm
        assert "position" in asm
        assert "x" in asm["position"]


class TestGetAssemblyStats:
    def test_empty_db(self, db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = ""
            stats = get_assembly_stats(db)
        assert stats["total"] == 0
        assert stats["online"] == 0

    def test_stats_with_data(self, seeded_db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = "0xWatcher"
            stats = get_assembly_stats(seeded_db)
        assert stats["total"] == 3
        assert stats["online"] == 2
        assert stats["offline"] == 1
        assert stats["systems_covered"] == 2  # sys-001 and sys-002
        assert "SSU" in stats["by_type"]
        assert stats["by_type"]["SSU"] == 3
        assert len(stats["assemblies"]) == 3

    def test_all_assemblies_no_filter(self, seeded_db):
        with patch("backend.analysis.assembly_tracker.settings") as mock:
            mock.WATCHER_OWNER_ADDRESS = ""
            stats = get_assembly_stats(seeded_db)
        assert stats["total"] == 4
        assert stats["online"] == 3
