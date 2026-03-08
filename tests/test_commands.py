"""Tests for Discord bot slash commands (discord_bot.py).

Tests the _register_commands() function via dependency injection
and the entity_autocomplete factory. Each command is tested by
calling the registered callback directly.
"""

import sqlite3
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.analysis.entity_resolver import EntityDossier
from backend.analysis.fingerprint import (
    Fingerprint,
    RouteProfile,
    SocialProfile,
    TemporalProfile,
    ThreatProfile,
)
from backend.bot.discord_bot import HAS_DISCORD
from backend.db.database import SCHEMA

needs_discord = pytest.mark.skipif(not HAS_DISCORD, reason="discord.py not installed")

# ---- Helpers ----


def _get_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_entities(db):
    """Seed entities table with test data."""
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen)"
        " VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 5, 0, 0, 1000, 5000)"
    )
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen)"
        " VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 10, 2, 30, 2000, 6000)"
    )
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen)"
        " VALUES ('char-002', 'character', 'RivalPilot',"
        " 25, 3, 5, 15, 3000, 7000)"
    )
    db.commit()


def _seed_killmails(db, count=3):
    """Seed killmails table."""
    now = int(time.time())
    for i in range(count):
        db.execute(
            "INSERT INTO killmails"
            " (killmail_id, victim_name,"
            "  victim_character_id, timestamp)"
            " VALUES (?, ?, ?, ?)",
            (f"km-{i}", f"Victim{i}", f"v-{i}", now - i * 60),
        )
    db.commit()


def _seed_story_feed(db, count=3):
    """Seed story_feed with test headlines."""
    now = int(time.time())
    for i in range(count):
        db.execute(
            "INSERT INTO story_feed"
            " (event_type, headline, body, severity, timestamp)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                "kill_streak",
                f"Headline {i}",
                f"Body {i}",
                "info",
                now - i * 3600,
            ),
        )
    db.commit()


def _seed_watches(db, user_id="12345", target_id="gate-001"):
    """Seed an active watch."""
    db.execute(
        "INSERT INTO watches"
        " (user_id, watch_type, target_id, conditions,"
        " webhook_url, channel_id, active)"
        " VALUES (?, ?, ?, ?, ?, ?, 1)",
        (user_id, "entity_movement", target_id, "{}", "", "99999"),
    )
    db.commit()


def _make_interaction(user_id=12345, channel_id=99999):
    """Create a mock discord.Interaction."""
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.channel_id = channel_id
    return interaction


def _make_fingerprint(
    entity_id="char-001",
    entity_type="character",
    event_count=50,
    opsec_score=75,
    opsec_rating="GOOD",
    threat_level="moderate",
    kill_ratio=0.83,
):
    """Build a Fingerprint with sensible defaults."""
    return Fingerprint(
        entity_id=entity_id,
        entity_type=entity_type,
        event_count=event_count,
        temporal=TemporalProfile(
            peak_hour=14,
            peak_hour_pct=35.0,
            active_hours=12,
            entropy=3.2,
        ),
        route=RouteProfile(
            top_gate="gate-001",
            top_gate_pct=40.0,
            unique_gates=8,
            unique_systems=5,
            route_entropy=2.5,
        ),
        social=SocialProfile(
            top_associate="char-002",
            top_associate_count=15,
            unique_associates=6,
            solo_ratio=60.0,
        ),
        threat=ThreatProfile(
            kill_ratio=kill_ratio,
            threat_level=threat_level,
        ),
        opsec_score=opsec_score,
        opsec_rating=opsec_rating,
    )


# ---- Fixtures ----


@pytest.fixture()
def db():
    """In-memory test database."""
    return _get_test_db()


@pytest.fixture()
def seeded_db(db):
    """Test database with entities seeded."""
    _seed_entities(db)
    return db


@pytest.fixture()
def mock_tree():
    """Mock CommandTree that captures registered commands."""
    tree = MagicMock()
    commands = {}

    def fake_command(**kwargs):
        def decorator(func):
            commands[kwargs["name"]] = func
            # Support chaining .autocomplete() on the returned cmd
            cmd = MagicMock()
            cmd.callback = func

            def make_autocomplete(param_name):
                def register_ac(ac_func):
                    commands[f"_ac_{kwargs['name']}_{param_name}"] = ac_func
                    return ac_func

                return register_ac

            cmd.autocomplete = make_autocomplete
            commands[f"_cmd_{kwargs['name']}"] = cmd
            return cmd

        return decorator

    tree.command = fake_command
    tree._commands = commands
    return tree


@pytest.fixture()
def registered(mock_tree, seeded_db):
    """Register commands and return (commands_dict, db)."""
    if not HAS_DISCORD:
        pytest.skip("discord.py not installed")
    from backend.bot.discord_bot import _register_commands

    mock_fp = _make_fingerprint()

    def mock_build_fp(db, eid):
        return mock_fp

    def mock_compare_fp(fp1, fp2):
        return {
            "overall_similarity": 0.85,
            "temporal_similarity": 0.9,
            "route_similarity": 0.8,
            "social_similarity": 0.75,
            "likely_alt": True,
            "likely_fleet_mate": False,
        }

    _register_commands(
        mock_tree,
        lambda: seeded_db,
        mock_build_fp,
        mock_compare_fp,
    )
    return mock_tree._commands, seeded_db


def _get_cmd(registered_fixture, name):
    """Get command callback from registered fixture."""
    cmds, db = registered_fixture
    return cmds[name], db


# ---- entity_autocomplete ----


@pytest.mark.asyncio
async def test_autocomplete_short_input(db):
    """Return empty for inputs shorter than 2 chars."""
    from backend.bot.discord_bot import entity_autocomplete

    ac = entity_autocomplete(lambda: db)
    result = await ac(MagicMock(), "a")
    assert result == []


@pytest.mark.asyncio
async def test_autocomplete_returns_choices(seeded_db):
    """Return matching entities as Choice objects."""
    from backend.bot.discord_bot import entity_autocomplete

    ac = entity_autocomplete(lambda: seeded_db)
    result = await ac(MagicMock(), "Test")
    assert len(result) == 1
    item = result[0]
    val = item["value"] if isinstance(item, dict) else item.value
    name = item["name"] if isinstance(item, dict) else item.name
    assert val == "char-001"
    assert "CHAR" in name


@pytest.mark.asyncio
async def test_autocomplete_no_matches(db):
    """Return empty when no entities match."""
    from backend.bot.discord_bot import entity_autocomplete

    ac = entity_autocomplete(lambda: db)
    result = await ac(MagicMock(), "zzz_nomatch")
    assert result == []


@pytest.mark.asyncio
async def test_autocomplete_gate_type_label(seeded_db):
    """Gate entities show GATE prefix."""
    from backend.bot.discord_bot import entity_autocomplete

    ac = entity_autocomplete(lambda: seeded_db)
    result = await ac(MagicMock(), "Alpha")
    assert len(result) == 1
    name = result[0]["name"] if isinstance(result[0], dict) else result[0].name
    assert "GATE" in name


# ---- /witness ----


@pytest.mark.asyncio
async def test_witness_found(registered):
    """Witness returns embed for matching entity."""
    cmd, db = _get_cmd(registered, "witness")
    interaction = _make_interaction()
    await cmd(interaction, "TestPilot")

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_awaited_once()
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "TestPilot" in embed.title


@pytest.mark.asyncio
async def test_witness_not_found(registered):
    """Witness reports when entity not found."""
    cmd, db = _get_cmd(registered, "witness")
    interaction = _make_interaction()
    await cmd(interaction, "nonexistent_zzz")

    msg = interaction.followup.send.call_args[0][0]
    assert "No entity found" in msg


@pytest.mark.asyncio
async def test_witness_with_titles(registered):
    """Witness shows titles when present."""
    cmd, db = _get_cmd(registered, "witness")
    db.execute(
        "INSERT INTO entity_titles"
        " (entity_id, title, title_type)"
        " VALUES ('char-001', 'The Hunter', 'kill')"
    )
    db.commit()
    interaction = _make_interaction()
    await cmd(interaction, "TestPilot")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    field_names = [f.name for f in embed.fields]
    assert "Titles" in field_names


# ---- /killfeed ----


@pytest.mark.asyncio
async def test_killfeed_with_kills(registered):
    """Killfeed returns kills embed."""
    cmd, db = _get_cmd(registered, "killfeed")
    _seed_killmails(db, count=3)
    interaction = _make_interaction()
    await cmd(interaction, 5)

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Killmails" in embed.title
    assert "Victim" in embed.description


@pytest.mark.asyncio
async def test_killfeed_empty(registered):
    """Killfeed handles no killmails."""
    cmd, db = _get_cmd(registered, "killfeed")
    interaction = _make_interaction()
    await cmd(interaction, 5)

    msg = interaction.followup.send.call_args[0][0]
    assert "No killmails" in msg


@pytest.mark.asyncio
async def test_killfeed_caps_at_10(registered):
    """Killfeed clamps count to 10."""
    cmd, db = _get_cmd(registered, "killfeed")
    _seed_killmails(db, count=15)
    interaction = _make_interaction()
    await cmd(interaction, 20)

    embed = interaction.followup.send.call_args.kwargs["embed"]
    lines = [line for line in embed.description.split("\n") if line.strip()]
    assert len(lines) <= 10


# ---- /leaderboard ----


@pytest.mark.asyncio
async def test_leaderboard_top_killers(registered):
    """Leaderboard top_killers returns embed."""
    cmd, db = _get_cmd(registered, "leaderboard")
    interaction = _make_interaction()
    await cmd(interaction, "top_killers")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Top Killers" in embed.title
    assert "TestPilot" in embed.description


@pytest.mark.asyncio
async def test_leaderboard_most_deaths(registered):
    """Leaderboard most_deaths returns embed."""
    cmd, db = _get_cmd(registered, "leaderboard")
    interaction = _make_interaction()
    await cmd(interaction, "most_deaths")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Most Deaths" in embed.title


@pytest.mark.asyncio
async def test_leaderboard_most_traveled(registered):
    """Leaderboard most_traveled returns embed."""
    cmd, db = _get_cmd(registered, "leaderboard")
    interaction = _make_interaction()
    await cmd(interaction, "most_traveled")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Most Traveled" in embed.title


@pytest.mark.asyncio
async def test_leaderboard_most_active_gates(registered):
    """Leaderboard most_active_gates returns embed."""
    cmd, db = _get_cmd(registered, "leaderboard")
    interaction = _make_interaction()
    await cmd(interaction, "most_active_gates")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Most Active Gates" in embed.title


@pytest.mark.asyncio
async def test_leaderboard_deadliest_gates(registered):
    """Leaderboard deadliest_gates returns embed."""
    cmd, db = _get_cmd(registered, "leaderboard")
    interaction = _make_interaction()
    await cmd(interaction, "deadliest_gates")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Deadliest Gates" in embed.title


@pytest.mark.asyncio
async def test_leaderboard_invalid_category(registered):
    """Leaderboard rejects unknown categories."""
    cmd, db = _get_cmd(registered, "leaderboard")
    interaction = _make_interaction()
    await cmd(interaction, "nonsense")

    msg = interaction.followup.send.call_args[0][0]
    assert "Unknown category" in msg


@pytest.mark.asyncio
async def test_leaderboard_empty(registered):
    """Leaderboard shows message when no matching data."""
    cmd, _ = _get_cmd(registered, "leaderboard")
    # Use a fresh empty DB
    empty_db = _get_test_db()
    from backend.bot.discord_bot import _register_commands

    tree2 = MagicMock()
    cmds2 = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds2[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds2[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree2.command = fake_command
    _register_commands(tree2, lambda: empty_db, lambda d, e: None, lambda a, b: {})

    interaction = _make_interaction()
    await cmds2["leaderboard"](interaction, "top_killers")
    msg = interaction.followup.send.call_args[0][0]
    assert "No data" in msg


# ---- /feed ----


@pytest.mark.asyncio
async def test_feed_with_items(registered):
    """Feed returns story headlines."""
    cmd, db = _get_cmd(registered, "feed")
    _seed_story_feed(db, count=3)
    interaction = _make_interaction()
    await cmd(interaction, 5)

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Story Feed" in embed.title
    assert "Headline" in embed.description


@pytest.mark.asyncio
async def test_feed_empty(registered):
    """Feed shows message when no stories."""
    cmd, db = _get_cmd(registered, "feed")
    interaction = _make_interaction()
    await cmd(interaction, 5)

    msg = interaction.followup.send.call_args[0][0]
    assert "No stories" in msg


@pytest.mark.asyncio
async def test_feed_caps_at_10(registered):
    """Feed clamps count to max 10."""
    cmd, db = _get_cmd(registered, "feed")
    _seed_story_feed(db, count=15)
    interaction = _make_interaction()
    await cmd(interaction, 20)

    embed = interaction.followup.send.call_args.kwargs["embed"]
    lines = [line for line in embed.description.split("\n") if line.strip()]
    assert len(lines) <= 10


@pytest.mark.asyncio
async def test_feed_severity_emojis(registered):
    """Feed uses severity-based emojis."""
    cmd, db = _get_cmd(registered, "feed")
    now = int(time.time())
    db.execute(
        "INSERT INTO story_feed"
        " (event_type, headline, body, severity, timestamp)"
        " VALUES ('test', 'Critical Event', '', 'critical', ?)",
        (now,),
    )
    db.commit()
    interaction = _make_interaction()
    await cmd(interaction, 5)

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "\U0001f534" in embed.description


# ---- /compare ----


@pytest.mark.asyncio
async def test_compare_both_found(registered):
    """Compare returns similarity embed."""
    cmd, db = _get_cmd(registered, "compare")
    interaction = _make_interaction()
    await cmd(interaction, "char-001", "char-002")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Fingerprint Comparison" in embed.title
    assert "85.0%" in embed.description


@pytest.mark.asyncio
async def test_compare_entity_not_found(registered):
    """Compare reports when entity not found."""
    cmd, db = _get_cmd(registered, "compare")
    interaction = _make_interaction()
    await cmd(interaction, "nonexistent_zzz", "char-001")

    msg = interaction.followup.send.call_args[0][0]
    assert "not found" in msg


@pytest.mark.asyncio
async def test_compare_verdict_alt(registered):
    """Compare shows ALT verdict for high similarity."""
    cmd, db = _get_cmd(registered, "compare")
    interaction = _make_interaction()
    await cmd(interaction, "char-001", "char-002")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    verdicts = [f.value for f in embed.fields if f.name == "Verdict"]
    assert any("ALT" in v for v in verdicts)


@needs_discord
@pytest.mark.asyncio
async def test_compare_no_fingerprints():
    """Compare handles missing fingerprints gracefully."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["compare"](interaction, "char-001", "char-002")

    msg = interaction.followup.send.call_args[0][0]
    assert "Could not build fingerprints" in msg


# ---- /locate ----


@pytest.mark.asyncio
async def test_locate_found(registered):
    """Locate returns embed when entity found."""
    cmd, db = _get_cmd(registered, "locate")
    interaction = _make_interaction()

    dossier = EntityDossier(
        entity_id="char-001",
        entity_type="character",
        display_name="TestPilot",
        first_seen=2000,
        last_seen=6000,
        event_count=50,
        kill_count=10,
        death_count=2,
        gate_count=30,
        corp_id="corp-001",
        danger_rating="high",
        titles=["The Hunter"],
        associated_corps=["CorpA"],
    )

    with patch(
        "backend.analysis.entity_resolver.resolve_entity",
        return_value=dossier,
    ):
        await cmd(interaction, "char-001")

    interaction.response.defer.assert_awaited_once()
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "TestPilot" in embed.title
    assert "The Hunter" in embed.title


@pytest.mark.asyncio
async def test_locate_not_found(registered):
    """Locate sends 'not found' when entity missing."""
    cmd, db = _get_cmd(registered, "locate")
    interaction = _make_interaction()

    with patch(
        "backend.analysis.entity_resolver.resolve_entity",
        return_value=None,
    ):
        await cmd(interaction, "nonexistent")

    msg = interaction.followup.send.call_args[0][0]
    assert "not found" in msg


@pytest.mark.asyncio
async def test_locate_name_fallback(registered):
    """Locate falls back to name search."""
    cmd, db = _get_cmd(registered, "locate")
    interaction = _make_interaction()

    dossier = EntityDossier(
        entity_id="char-001",
        entity_type="character",
        display_name="TestPilot",
        first_seen=2000,
        last_seen=6000,
        event_count=50,
        kill_count=10,
        death_count=2,
        gate_count=30,
        corp_id=None,
    )

    with patch(
        "backend.analysis.entity_resolver.resolve_entity",
        side_effect=[None, dossier],
    ):
        await cmd(interaction, "TestPilot")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "TestPilot" in embed.title


@pytest.mark.asyncio
async def test_locate_default_footer(registered):
    """Locate uses default footer when no timestamps."""
    cmd, db = _get_cmd(registered, "locate")
    interaction = _make_interaction()

    dossier = EntityDossier(
        entity_id="char-001",
        entity_type="character",
        display_name="TestPilot",
        first_seen=0,
        last_seen=0,
        event_count=50,
        kill_count=0,
        death_count=0,
        gate_count=0,
        corp_id=None,
        danger_rating="unknown",
    )

    with patch(
        "backend.analysis.entity_resolver.resolve_entity",
        return_value=dossier,
    ):
        await cmd(interaction, "char-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Living Memory" in embed.footer.text


@pytest.mark.asyncio
async def test_locate_gate_with_pilots(registered):
    """Locate gate shows unique pilots and corps."""
    cmd, db = _get_cmd(registered, "locate")
    interaction = _make_interaction()

    dossier = EntityDossier(
        entity_id="gate-001",
        entity_type="gate",
        display_name="Alpha Gate",
        first_seen=1000,
        last_seen=5000,
        event_count=150,
        kill_count=5,
        death_count=0,
        gate_count=0,
        corp_id=None,
        danger_rating="moderate",
        unique_pilots=42,
        associated_corps=["CorpA", "CorpB"],
    )

    with patch(
        "backend.analysis.entity_resolver.resolve_entity",
        return_value=dossier,
    ):
        await cmd(interaction, "gate-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    field_names = [f.name for f in embed.fields]
    assert "Unique Pilots" in field_names
    assert "Associated Corps" in field_names


# ---- /history ----


@pytest.mark.asyncio
async def test_history(registered):
    """History returns AI narrative embed."""
    cmd, db = _get_cmd(registered, "history")
    interaction = _make_interaction()

    with patch(
        "backend.analysis.narrative.generate_dossier_narrative",
        return_value="This pilot is a menace.",
    ):
        await cmd(interaction, "char-001")

    interaction.response.defer.assert_awaited_once()
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Dossier" in embed.title
    assert "menace" in embed.description


# ---- /watch ----


@pytest.mark.asyncio
async def test_watch_valid_type(registered):
    """Watch inserts watch for valid type."""
    cmd, db = _get_cmd(registered, "watch")
    interaction = _make_interaction()
    await cmd(interaction, "entity_movement", "gate-001")

    interaction.response.send_message.assert_awaited_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "Watch set" in msg

    row = db.execute("SELECT * FROM watches").fetchone()
    assert row["target_id"] == "gate-001"
    assert row["watch_type"] == "entity_movement"


@pytest.mark.asyncio
async def test_watch_invalid_type(registered):
    """Watch rejects invalid watch types."""
    cmd, db = _get_cmd(registered, "watch")
    interaction = _make_interaction()
    await cmd(interaction, "bad_type", "gate-001")

    msg = interaction.response.send_message.call_args[0][0]
    assert "Invalid type" in msg
    assert db.execute("SELECT * FROM watches").fetchone() is None


# ---- /unwatch ----


@pytest.mark.asyncio
async def test_unwatch(registered):
    """Unwatch deactivates matching watches."""
    cmd, db = _get_cmd(registered, "unwatch")
    _seed_watches(db, user_id="12345", target_id="gate-001")
    interaction = _make_interaction(user_id=12345)
    await cmd(interaction, "gate-001")

    row = db.execute("SELECT active FROM watches").fetchone()
    assert row["active"] == 0


# ---- /profile ----


@pytest.mark.asyncio
async def test_profile_found(registered):
    """Profile returns behavioral embed."""
    cmd, db = _get_cmd(registered, "profile")
    interaction = _make_interaction()
    await cmd(interaction, "char-001")

    interaction.response.defer.assert_awaited_once()
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Behavioral Profile" in embed.title
    assert "OPSEC" in embed.description


@needs_discord
@pytest.mark.asyncio
async def test_profile_not_found():
    """Profile shows not found for unknown entity."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["profile"](interaction, "nonexistent")

    msg = interaction.followup.send.call_args[0][0]
    assert "not found" in msg


@pytest.mark.asyncio
async def test_profile_no_social(registered):
    """Profile omits social when no associates."""
    # Re-register with fp that has no social
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint()
    fp.social.unique_associates = 0

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: fp, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["profile"](interaction, "char-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    field_names = [f.name for f in embed.fields]
    assert "Social" not in field_names


@needs_discord
@pytest.mark.asyncio
async def test_profile_extreme_threat_color():
    """Profile uses red for extreme threat."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint(threat_level="extreme")

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: fp, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["profile"](interaction, "char-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert embed.color.value == 0xFF0000


# ---- /opsec ----


@pytest.mark.asyncio
async def test_opsec_found(registered):
    """Opsec returns score embed."""
    cmd, db = _get_cmd(registered, "opsec")
    interaction = _make_interaction()
    await cmd(interaction, "char-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "OPSEC Score" in embed.title
    assert "75/100" in embed.description


@needs_discord
@pytest.mark.asyncio
async def test_opsec_not_found():
    """Opsec shows not found for unknown entity."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["opsec"](interaction, "nonexistent")

    msg = interaction.followup.send.call_args[0][0]
    assert "not found" in msg


@needs_discord
@pytest.mark.asyncio
async def test_opsec_insufficient_data():
    """Opsec rejects entities with < 20 events."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint(event_count=10)

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: fp, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["opsec"](interaction, "char-001")

    msg = interaction.followup.send.call_args[0][0]
    assert "Not enough data" in msg


@needs_discord
@pytest.mark.asyncio
async def test_opsec_color_green():
    """Opsec uses green for score >= 60."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint(opsec_score=80)

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: fp, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["opsec"](interaction, "char-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert embed.color.value == 0x00FF88


@needs_discord
@pytest.mark.asyncio
async def test_opsec_color_red():
    """Opsec uses red for score < 40."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint(opsec_score=20)

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(tree, lambda: db, lambda d, e: fp, lambda a, b: {})

    interaction = _make_interaction()
    await cmds["opsec"](interaction, "char-001")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert embed.color.value == 0xFF0000


# ---- run_bot ----


@pytest.mark.asyncio
async def test_run_bot_no_discord():
    """run_bot returns early when discord.py not installed."""
    with patch("backend.bot.discord_bot.HAS_DISCORD", False):
        from backend.bot.discord_bot import run_bot

        await run_bot()  # should not raise


@pytest.mark.asyncio
async def test_run_bot_no_token():
    """run_bot returns early without DISCORD_TOKEN."""
    with (
        patch("backend.bot.discord_bot.HAS_DISCORD", True),
        patch("backend.bot.discord_bot.settings") as mock_settings,
    ):
        mock_settings.DISCORD_TOKEN = ""
        from backend.bot.discord_bot import run_bot

        await run_bot()  # should not raise


# ---- Distinct verdict in compare ----


@needs_discord
@pytest.mark.asyncio
async def test_compare_distinct():
    """Compare shows 'Distinct' for low similarity."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint()

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(
        tree,
        lambda: db,
        lambda d, e: fp,
        lambda a, b: {
            "overall_similarity": 0.2,
            "temporal_similarity": 0.1,
            "route_similarity": 0.15,
            "social_similarity": 0.3,
            "likely_alt": False,
            "likely_fleet_mate": False,
        },
    )

    interaction = _make_interaction()
    await cmds["compare"](interaction, "char-001", "char-002")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    verdicts = [f.value for f in embed.fields if f.name == "Verdict"]
    assert any("Distinct" in v for v in verdicts)


@needs_discord
@pytest.mark.asyncio
async def test_compare_fleet_mate():
    """Compare shows fleet mate verdict."""
    from backend.bot.discord_bot import _register_commands

    db = _get_test_db()
    _seed_entities(db)

    fp = _make_fingerprint()

    tree = MagicMock()
    cmds = {}

    def fake_command(**kwargs):
        def decorator(func):
            cmds[kwargs["name"]] = func
            cmd_mock = MagicMock()
            cmd_mock.callback = func
            cmd_mock.autocomplete = lambda p: lambda f: f
            cmds[f"_cmd_{kwargs['name']}"] = cmd_mock
            return cmd_mock

        return decorator

    tree.command = fake_command
    _register_commands(
        tree,
        lambda: db,
        lambda d, e: fp,
        lambda a, b: {
            "overall_similarity": 0.55,
            "temporal_similarity": 0.6,
            "route_similarity": 0.5,
            "social_similarity": 0.7,
            "likely_alt": False,
            "likely_fleet_mate": True,
        },
    )

    interaction = _make_interaction()
    await cmds["compare"](interaction, "char-001", "char-002")

    embed = interaction.followup.send.call_args.kwargs["embed"]
    verdicts = [f.value for f in embed.fields if f.name == "Verdict"]
    assert any("FLEET MATE" in v for v in verdicts)
