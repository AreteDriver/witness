"""Tests for Cycle 5 analysis — feral AI, scans, clones, crowns."""

import sqlite3
import time

from backend.analysis.c5_analysis import (
    C5Briefing,
    ZoneThreatSummary,
    analyze_zone_threat,
    get_c5_briefing,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_zone(db, zone_id="zone-1", name="Alpha Zone", tier=0):
    now = int(time.time())
    db.execute(
        "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned)"
        " VALUES (?, ?, ?, ?)",
        (zone_id, name, tier, now),
    )
    db.commit()


class TestAnalyzeZoneThreat:
    def test_returns_none_for_missing(self):
        db = _get_test_db()
        assert analyze_zone_threat(db, "nonexistent") is None

    def test_dormant_zone(self):
        db = _get_test_db()
        _seed_zone(db, tier=0)
        s = analyze_zone_threat(db, "zone-1")
        assert s.threat_level == "DORMANT"
        assert s.escalation_count == 0
        assert s.is_blind_spot is False

    def test_critical_zone(self):
        db = _get_test_db()
        _seed_zone(db, tier=3)
        s = analyze_zone_threat(db, "zone-1")
        assert s.threat_level == "CRITICAL"
        assert s.current_tier == 3

    def test_escalation_tracking(self):
        db = _get_test_db()
        now = int(time.time())
        _seed_zone(db, tier=2)
        # Two escalation events
        db.execute(
            "INSERT INTO feral_ai_events"
            " (zone_id, event_type, old_tier, new_tier, severity, timestamp)"
            " VALUES ('zone-1', 'evolution', 0, 1, 'warning', ?)",
            (now - 7200,),
        )
        db.execute(
            "INSERT INTO feral_ai_events"
            " (zone_id, event_type, old_tier, new_tier, severity, timestamp)"
            " VALUES ('zone-1', 'evolution', 1, 2, 'warning', ?)",
            (now - 3600,),
        )
        db.commit()
        s = analyze_zone_threat(db, "zone-1")
        assert s.escalation_count == 2
        assert s.last_escalation == now - 3600
        assert s.hours_at_current_tier >= 0.9

    def test_scan_activity_24h(self):
        db = _get_test_db()
        now = int(time.time())
        _seed_zone(db)
        # 3 scans: 2 CLEAR, 1 HOSTILE
        for i, result in enumerate(["CLEAR", "HOSTILE", "CLEAR"]):
            db.execute(
                "INSERT INTO scans"
                " (scan_id, zone_id, result_type, scanned_at)"
                " VALUES (?, 'zone-1', ?, ?)",
                (f"scan-{i}", result, now - 100 * i),
            )
        db.commit()
        s = analyze_zone_threat(db, "zone-1")
        assert s.scan_count_24h == 3
        assert s.hostile_scan_count_24h == 1

    def test_blind_spot_detection(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones"
            " (zone_id, name, feral_ai_tier, last_scanned)"
            " VALUES ('zone-old', 'Old Zone', 0, ?)",
            (now - 2400,),  # 40 min ago
        )
        db.commit()
        s = analyze_zone_threat(db, "zone-old")
        assert s.is_blind_spot is True

    def test_never_scanned_is_blind_spot(self):
        db = _get_test_db()
        db.execute(
            "INSERT INTO orbital_zones"
            " (zone_id, name, feral_ai_tier, last_scanned)"
            " VALUES ('zone-new', 'New Zone', 0, NULL)"
        )
        db.commit()
        s = analyze_zone_threat(db, "zone-new")
        assert s.is_blind_spot is True

    def test_to_dict(self):
        s = ZoneThreatSummary(
            zone_id="z1",
            name="Test",
            current_tier=2,
            threat_level="EVOLVED",
            escalation_count=3,
            hours_at_current_tier=1.567,
        )
        d = s.to_dict()
        assert d["threat_level"] == "EVOLVED"
        assert d["hours_at_current_tier"] == 1.6  # rounded


class TestC5Briefing:
    def test_empty_briefing(self):
        db = _get_test_db()
        b = get_c5_briefing(db)
        assert b.total_zones == 0
        assert b.zones_by_threat == {}
        assert b.total_clones == 0

    def test_zone_threat_breakdown(self):
        db = _get_test_db()
        _seed_zone(db, "z1", "Zone A", tier=0)
        _seed_zone(db, "z2", "Zone B", tier=1)
        _seed_zone(db, "z3", "Zone C", tier=3)
        b = get_c5_briefing(db)
        assert b.total_zones == 3
        assert b.zones_by_threat["DORMANT"] == 1
        assert b.zones_by_threat["ACTIVE"] == 1
        assert b.zones_by_threat["CRITICAL"] == 1

    def test_volatile_zones(self):
        db = _get_test_db()
        now = int(time.time())
        _seed_zone(db, "z1", "Volatile Zone", tier=2)
        for i in range(5):
            db.execute(
                "INSERT INTO feral_ai_events"
                " (zone_id, event_type, old_tier, new_tier,"
                " severity, timestamp)"
                " VALUES ('z1', 'evolution', ?, ?, 'warning', ?)",
                (i, i + 1, now - 1000 * i),
            )
        db.commit()
        b = get_c5_briefing(db)
        assert len(b.most_volatile_zones) == 1
        assert b.most_volatile_zones[0]["escalation_count"] == 5

    def test_blind_spots_in_briefing(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones"
            " (zone_id, name, feral_ai_tier, last_scanned)"
            " VALUES ('z-blind', 'Dark Zone', 0, ?)",
            (now - 3600,),
        )
        db.commit()
        b = get_c5_briefing(db)
        assert len(b.blind_spots) == 1
        assert b.blind_spots[0]["zone_id"] == "z-blind"

    def test_scan_coverage(self):
        db = _get_test_db()
        now = int(time.time())
        _seed_zone(db, "z1", "Zone A")
        _seed_zone(db, "z2", "Zone B")
        # Only z1 has been scanned
        db.execute(
            "INSERT INTO scans (scan_id, zone_id, result_type, scanned_at)"
            " VALUES ('s1', 'z1', 'CLEAR', ?)",
            (now - 100,),
        )
        db.commit()
        b = get_c5_briefing(db)
        assert b.scan_coverage_pct == 50.0

    def test_hostile_zones(self):
        db = _get_test_db()
        now = int(time.time())
        _seed_zone(db, "z1")
        db.execute(
            "INSERT INTO scans (scan_id, zone_id, result_type, scanned_at)"
            " VALUES ('s-hostile', 'z1', 'HOSTILE', ?)",
            (now - 100,),
        )
        db.commit()
        b = get_c5_briefing(db)
        assert "z1" in b.hostile_zones

    def test_clone_readiness(self):
        db = _get_test_db()
        now = int(time.time())
        # Owner with 3 clones (below threshold of 5)
        for i in range(3):
            db.execute(
                "INSERT INTO clones"
                " (clone_id, owner_id, owner_name, status, manufactured_at)"
                " VALUES (?, 'owner-1', 'Pilot', 'active', ?)",
                (f"clone-{i}", now),
            )
        db.commit()
        b = get_c5_briefing(db)
        assert b.total_clones == 3
        assert len(b.low_reserve_owners) == 1
        assert b.low_reserve_owners[0]["active_clones"] == 3

    def test_crown_distribution(self):
        db = _get_test_db()
        now = int(time.time())
        # 2 chars with crowns, 1 without
        db.execute(
            "INSERT INTO crowns"
            " (crown_id, character_id, crown_type, equipped_at)"
            " VALUES ('c1', 'char-1', 'Harbinger', ?)",
            (now,),
        )
        db.execute(
            "INSERT INTO crowns"
            " (crown_id, character_id, crown_type, equipped_at)"
            " VALUES ('c2', 'char-2', 'Harbinger', ?)",
            (now,),
        )
        for cid in ["char-1", "char-2", "char-3"]:
            db.execute(
                "INSERT INTO entities"
                " (entity_id, entity_type, display_name)"
                " VALUES (?, 'character', ?)",
                (cid, cid),
            )
        db.commit()
        b = get_c5_briefing(db)
        assert len(b.crown_distribution) == 1
        assert b.crown_distribution[0]["crown_type"] == "Harbinger"
        assert b.crown_distribution[0]["count"] == 2
        assert b.uncrowned_count == 1

    def test_to_dict(self):
        b = C5Briefing(
            total_zones=5,
            scan_coverage_pct=66.667,
        )
        d = b.to_dict()
        assert d["total_zones"] == 5
        assert d["scan_coverage_pct"] == 66.7
