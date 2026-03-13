"""Tests for Discord bot commands.

Mocks the discord module at the backend.bot.discord_bot namespace level
so all command callbacks can be tested without discord.py installed.
"""

import json
import sqlite3
import time
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.db.database import SCHEMA

# ---------------------------------------------------------------------------
# Lightweight discord fakes — just enough for _register_commands to work
# ---------------------------------------------------------------------------


class _FakeColor:
    """Fake discord.Color."""

    def __init__(self, value: int) -> None:
        self.value = value


class _FakeField:
    """Fake embed field."""

    def __init__(self, name: str, value: str, inline: bool = True) -> None:
        self.name = name
        self.value = value
        self.inline = inline


class _FakeFooter:
    """Fake embed footer."""

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeEmbed:
    """Fake discord.Embed supporting title, description, color, fields, footer."""

    def __init__(
        self,
        *,
        title: str = "",
        description: str = "",
        color: int = 0,
    ) -> None:
        self.title = title
        self.description = description
        self.color = _FakeColor(color)
        self.fields: list[_FakeField] = []
        self.footer = _FakeFooter("")

    def add_field(self, *, name: str, value: str, inline: bool = True) -> "_FakeEmbed":
        self.fields.append(_FakeField(name, value, inline))
        return self

    def set_footer(self, *, text: str) -> "_FakeEmbed":
        self.footer = _FakeFooter(text)
        return self


class _FakeChoice:
    """Fake app_commands.Choice."""

    def __init__(self, *, name: str, value: str) -> None:
        self.name = name
        self.value = value


class _FakeIntents:
    """Fake discord.Intents."""

    @staticmethod
    def default():
        return _FakeIntents()


class _FakeClient:
    """Fake discord.Client."""

    def __init__(self, *, intents=None) -> None:
        self.intents = intents
        self.user = MagicMock()


def _passthrough_decorator(*args, **kwargs):
    """Decorator that returns the function unchanged."""

    def wrapper(fn):
        return fn

    return wrapper


def _build_mock_discord_module() -> ModuleType:
    """Build a fake 'discord' module with Embed, Intents, Client, Interaction, app_commands."""
    discord_mod = ModuleType("discord")
    discord_mod.Embed = _FakeEmbed
    discord_mod.Intents = _FakeIntents
    discord_mod.Client = _FakeClient
    discord_mod.Interaction = MagicMock  # type annotation only

    app_commands_mod = ModuleType("discord.app_commands")
    app_commands_mod.Choice = _FakeChoice
    app_commands_mod.CommandTree = MagicMock
    app_commands_mod.describe = _passthrough_decorator
    app_commands_mod.choices = _passthrough_decorator

    discord_mod.app_commands = app_commands_mod
    return discord_mod, app_commands_mod


# ---------------------------------------------------------------------------
# Mock tree that captures registered commands
# ---------------------------------------------------------------------------


def _build_mock_tree():
    """Build a mock tree that captures commands via tree.command()."""
    commands: dict = {}

    def fake_command(*, name: str, description: str = ""):
        def decorator(func):
            commands[name] = func
            mock_cmd = MagicMock()
            mock_cmd.callback = func
            mock_cmd.autocomplete = lambda param_name: lambda ac_func: ac_func
            commands[f"_cmd_{name}"] = mock_cmd
            return mock_cmd

        return decorator

    tree = MagicMock()
    tree.command = fake_command
    tree._captured = commands
    return tree


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """In-memory test database."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture()
def seeded_db(db):
    """Database with entities, killmails, story feed, gate events, titles."""
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen)"
        " VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 10, 3, 25, 1000, 5000)"
    )
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen)"
        " VALUES ('char-002', 'character', 'RivalPilot',"
        " 25, 3, 5, 15, 3000, 7000)"
    )
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen)"
        " VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 5, 0, 0, 1000, 5000)"
    )
    db.execute(
        "INSERT INTO entity_titles (entity_id, title, title_type)"
        " VALUES ('char-001', 'The Reaper', 'character')"
    )
    now = int(time.time())
    for i in range(3):
        db.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id,"
            " victim_name, solar_system_id, timestamp)"
            " VALUES (?, ?, ?, ?, ?)",
            (f"km-{i}", f"vic-{i}", f"Victim{i}", "sys-1", now - i * 60),
        )
    db.execute(
        "INSERT INTO story_feed (event_type, headline, body, severity, timestamp)"
        " VALUES ('engagement', 'Test Battle', 'body', 'warning', ?)",
        (now,),
    )
    db.execute(
        "INSERT INTO story_feed (event_type, headline, body, severity, timestamp)"
        " VALUES ('kill_streak', 'Critical Alert', '', 'critical', ?)",
        (now - 100,),
    )
    db.execute(
        "INSERT INTO story_feed (event_type, headline, body, severity, timestamp)"
        " VALUES ('intel', 'Green Notice', '', 'info', ?)",
        (now - 200,),
    )
    db.execute(
        "INSERT INTO gate_events (gate_id, gate_name, character_id,"
        " solar_system_id, timestamp)"
        " VALUES ('gate-001', 'Alpha Gate', 'char-001', 'sys-1', ?)",
        (now,),
    )
    db.commit()
    return db


def _make_interaction(user_id: int = 12345, channel_id: int = 99999):
    """Create a mock Discord interaction."""
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


def _make_fingerprint(**overrides):
    """Build a mock fingerprint with sensible defaults."""
    from backend.analysis.fingerprint import (
        Fingerprint,
        RouteProfile,
        SocialProfile,
        TemporalProfile,
        ThreatProfile,
    )

    defaults = {
        "entity_id": "char-001",
        "entity_type": "character",
        "event_count": 50,
        "opsec_score": 75,
        "opsec_rating": "GOOD",
    }
    defaults.update(overrides)

    threat_level = overrides.get("threat_level", "moderate")
    kill_ratio = overrides.get("kill_ratio", 0.83)

    return Fingerprint(
        entity_id=defaults["entity_id"],
        entity_type=defaults["entity_type"],
        event_count=defaults["event_count"],
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
        opsec_score=defaults["opsec_score"],
        opsec_rating=defaults["opsec_rating"],
    )


@pytest.fixture()
def discord_patched():
    """Patch discord + app_commands into backend.bot.discord_bot namespace.

    Returns (discord_mod, app_commands_mod) and restores originals after test.
    """
    discord_mod, app_commands_mod = _build_mock_discord_module()
    import backend.bot.discord_bot as bot_mod

    orig_discord = getattr(bot_mod, "discord", None)
    orig_ac = getattr(bot_mod, "app_commands", None)
    orig_has = bot_mod.HAS_DISCORD

    bot_mod.discord = discord_mod
    bot_mod.app_commands = app_commands_mod
    bot_mod.HAS_DISCORD = True

    yield discord_mod, app_commands_mod

    # Restore
    if orig_discord is not None:
        bot_mod.discord = orig_discord
    elif hasattr(bot_mod, "discord"):
        delattr(bot_mod, "discord")
    if orig_ac is not None:
        bot_mod.app_commands = orig_ac
    elif hasattr(bot_mod, "app_commands"):
        delattr(bot_mod, "app_commands")
    bot_mod.HAS_DISCORD = orig_has


@pytest.fixture()
def registered_cmds(discord_patched, seeded_db):
    """Register commands using mock discord and return (commands_dict, db).

    Uses a mock fingerprint that always returns data.
    """
    from backend.bot.discord_bot import _register_commands

    fp = _make_fingerprint()
    tree = _build_mock_tree()

    def mock_build_fp(db, eid):
        return fp

    def mock_compare_fp(fp1, fp2):
        return {
            "overall_similarity": 0.85,
            "temporal_similarity": 0.9,
            "route_similarity": 0.8,
            "social_similarity": 0.75,
            "likely_alt": True,
            "likely_fleet_mate": False,
        }

    _register_commands(tree, lambda: seeded_db, mock_build_fp, mock_compare_fp)
    return tree._captured, seeded_db


def _cmd(fixture, name):
    """Extract command callback and db from registered_cmds fixture."""
    cmds, db = fixture
    return cmds[name], db


# ---------------------------------------------------------------------------
# entity_autocomplete tests
# ---------------------------------------------------------------------------


class TestEntityAutocomplete:
    """Test the autocomplete factory function."""

    async def test_short_input_returns_empty(self, db):
        from backend.bot.discord_bot import entity_autocomplete

        ac = entity_autocomplete(lambda: db)
        result = await ac(MagicMock(), "T")
        assert result == []

    async def test_matching_input(self, seeded_db, discord_patched):
        from backend.bot.discord_bot import entity_autocomplete

        ac = entity_autocomplete(lambda: seeded_db)
        result = await ac(MagicMock(), "Test")
        assert len(result) >= 1

    async def test_no_matches_returns_empty(self, seeded_db):
        from backend.bot.discord_bot import entity_autocomplete

        ac = entity_autocomplete(lambda: seeded_db)
        result = await ac(MagicMock(), "zzz_nomatch")
        assert result == []

    async def test_gate_type_label(self, seeded_db, discord_patched):
        from backend.bot.discord_bot import entity_autocomplete

        ac = entity_autocomplete(lambda: seeded_db)
        result = await ac(MagicMock(), "Alpha")
        assert len(result) >= 1
        name = result[0].name if hasattr(result[0], "name") else result[0]["name"]
        assert "GATE" in name

    async def test_display_name_fallback(self, seeded_db, discord_patched):
        """Autocomplete uses entity_id[:20] when display_name is None."""
        seeded_db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name,"
            " event_count) VALUES ('0xabc123deadbeef9999', 'character', NULL, 10)"
        )
        seeded_db.commit()
        from backend.bot.discord_bot import entity_autocomplete

        ac = entity_autocomplete(lambda: seeded_db)
        result = await ac(MagicMock(), "0xabc123")
        assert len(result) >= 1
        name = result[0].name if hasattr(result[0], "name") else result[0]["name"]
        assert "0xabc123" in name

    async def test_has_discord_choice_objects(self, seeded_db, discord_patched):
        """When HAS_DISCORD is True, returns Choice objects (not dicts)."""
        from backend.bot.discord_bot import entity_autocomplete

        ac = entity_autocomplete(lambda: seeded_db)
        result = await ac(MagicMock(), "Test")
        assert len(result) >= 1
        assert isinstance(result[0], _FakeChoice)

    async def test_no_discord_returns_dicts(self, seeded_db):
        """When HAS_DISCORD is False, returns plain dicts."""
        import backend.bot.discord_bot as bot_mod

        orig = bot_mod.HAS_DISCORD
        bot_mod.HAS_DISCORD = False
        try:
            ac = bot_mod.entity_autocomplete(lambda: seeded_db)
            result = await ac(MagicMock(), "Test")
            assert len(result) >= 1
            assert isinstance(result[0], dict)
            assert "name" in result[0]
            assert "value" in result[0]
        finally:
            bot_mod.HAS_DISCORD = orig


# ---------------------------------------------------------------------------
# /watchtower tests
# ---------------------------------------------------------------------------


class TestWatchtowerCmd:
    async def test_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watchtower")
        interaction = _make_interaction()
        await cmd(interaction, "TestPilot")

        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "TestPilot" in embed.title

    async def test_not_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watchtower")
        interaction = _make_interaction()
        await cmd(interaction, "nonexistent_zzz_999")

        msg = interaction.followup.send.call_args[0][0]
        assert "No entity found" in msg

    async def test_with_titles(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watchtower")
        interaction = _make_interaction()
        await cmd(interaction, "TestPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Titles" in field_names

    async def test_embed_fields(self, registered_cmds):
        """Embed includes Kills, Deaths, Events fields."""
        cmd, db = _cmd(registered_cmds, "watchtower")
        interaction = _make_interaction()
        await cmd(interaction, "TestPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Kills" in field_names
        assert "Deaths" in field_names
        assert "Events" in field_names

    async def test_with_fingerprint_threat(self, registered_cmds):
        """Embed includes Threat and OPSEC from fingerprint."""
        cmd, db = _cmd(registered_cmds, "watchtower")
        interaction = _make_interaction()
        await cmd(interaction, "TestPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Threat" in field_names
        assert "OPSEC" in field_names

    async def test_footer_has_id(self, registered_cmds):
        """Footer shows truncated entity ID."""
        cmd, db = _cmd(registered_cmds, "watchtower")
        interaction = _make_interaction()
        await cmd(interaction, "TestPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "ID:" in embed.footer.text

    async def test_no_fingerprint(self, discord_patched, seeded_db):
        """When build_fingerprint returns None, no Threat/OPSEC fields."""
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["watchtower"]

        interaction = _make_interaction()
        await cmd(interaction, "TestPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Threat" not in field_names
        assert "OPSEC" not in field_names

    async def test_no_titles(self, discord_patched, seeded_db):
        """When entity has no titles, Titles field is absent."""
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["watchtower"]

        # char-002 has no titles
        interaction = _make_interaction()
        await cmd(interaction, "RivalPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Titles" not in field_names

    async def test_display_name_fallback_to_id(self, discord_patched, seeded_db):
        """Uses entity_id[:20] when display_name is None."""
        from backend.bot.discord_bot import _register_commands

        seeded_db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name,"
            " event_count, kill_count, death_count, gate_count)"
            " VALUES ('0xdeadbeef12345678abcdef', 'character', NULL, 5, 0, 0, 0)"
        )
        seeded_db.commit()

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["watchtower"]

        interaction = _make_interaction()
        await cmd(interaction, "0xdeadbeef")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "0xdeadbeef" in embed.title


# ---------------------------------------------------------------------------
# /killfeed tests
# ---------------------------------------------------------------------------


class TestKillfeedCmd:
    async def test_with_kills(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "killfeed")
        interaction = _make_interaction()
        await cmd(interaction, 5)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Killmails" in embed.title
        assert "Victim" in embed.description

    async def test_empty(self, discord_patched, db):
        """No killmails shows message."""
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["killfeed"]

        interaction = _make_interaction()
        await cmd(interaction, 5)

        msg = interaction.followup.send.call_args[0][0]
        assert "No killmails" in msg

    async def test_caps_at_10(self, discord_patched, seeded_db):
        """Count is clamped to 10."""
        from backend.bot.discord_bot import _register_commands

        now = int(time.time())
        for i in range(15):
            seeded_db.execute(
                "INSERT INTO killmails (killmail_id, victim_character_id,"
                " victim_name, solar_system_id, timestamp)"
                " VALUES (?, ?, ?, ?, ?)",
                (f"km-extra-{i}", f"vic-extra-{i}", f"Extra{i}", "sys-1", now - i),
            )
        seeded_db.commit()

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["killfeed"]

        interaction = _make_interaction()
        await cmd(interaction, 20)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        lines = [line for line in embed.description.split("\n") if line.strip()]
        assert len(lines) <= 10

    async def test_victim_name_fallback(self, discord_patched, db):
        """Uses character_id[:16] when victim_name is None."""
        from backend.bot.discord_bot import _register_commands

        db.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id,"
            " victim_name, solar_system_id, timestamp)"
            " VALUES ('km-noname', '0xaabbccddee112233', NULL, 'sys-1', 5000)"
        )
        db.commit()

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["killfeed"]

        interaction = _make_interaction()
        await cmd(interaction, 5)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "0xaabbccddee11" in embed.description


# ---------------------------------------------------------------------------
# /leaderboard tests
# ---------------------------------------------------------------------------


class TestLeaderboardCmd:
    async def test_top_killers(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "leaderboard")
        interaction = _make_interaction()
        await cmd(interaction, "top_killers")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Top Killers" in embed.title
        assert "TestPilot" in embed.description

    async def test_most_deaths(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "leaderboard")
        interaction = _make_interaction()
        await cmd(interaction, "most_deaths")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Most Deaths" in embed.title

    async def test_most_traveled(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "leaderboard")
        interaction = _make_interaction()
        await cmd(interaction, "most_traveled")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Most Traveled" in embed.title

    async def test_deadliest_gates(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "leaderboard")
        interaction = _make_interaction()
        await cmd(interaction, "deadliest_gates")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Deadliest Gates" in embed.title

    async def test_most_active_gates(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "leaderboard")
        interaction = _make_interaction()
        await cmd(interaction, "most_active_gates")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Most Active Gates" in embed.title

    async def test_invalid_category(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "leaderboard")
        interaction = _make_interaction()
        await cmd(interaction, "nonsense_category")

        msg = interaction.followup.send.call_args[0][0]
        assert "Unknown category" in msg

    async def test_empty_data(self, discord_patched, db):
        """Empty DB shows 'No data' message."""
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["leaderboard"]

        interaction = _make_interaction()
        await cmd(interaction, "top_killers")

        msg = interaction.followup.send.call_args[0][0]
        assert "No data" in msg

    async def test_display_name_fallback(self, discord_patched, db):
        """Uses entity_id[:16] when display_name is None."""
        from backend.bot.discord_bot import _register_commands

        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name,"
            " event_count, kill_count, death_count, gate_count)"
            " VALUES ('0xaabbccddee112233aabb', 'character', NULL, 5, 3, 0, 0)"
        )
        db.commit()

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["leaderboard"]

        interaction = _make_interaction()
        await cmd(interaction, "top_killers")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "0xaabbccddee1122" in embed.description


# ---------------------------------------------------------------------------
# /feed tests
# ---------------------------------------------------------------------------


class TestFeedCmd:
    async def test_with_items(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "feed")
        interaction = _make_interaction()
        await cmd(interaction, 5)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Story Feed" in embed.title

    async def test_empty(self, discord_patched, db):
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["feed"]

        interaction = _make_interaction()
        await cmd(interaction, 5)

        msg = interaction.followup.send.call_args[0][0]
        assert "No stories" in msg

    async def test_caps_at_10(self, discord_patched, db):
        from backend.bot.discord_bot import _register_commands

        now = int(time.time())
        for i in range(15):
            db.execute(
                "INSERT INTO story_feed (event_type, headline, body, severity, timestamp)"
                " VALUES (?, ?, ?, ?, ?)",
                ("test", f"Story {i}", "", "info", now - i * 60),
            )
        db.commit()

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["feed"]

        interaction = _make_interaction()
        await cmd(interaction, 20)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        lines = [line for line in embed.description.split("\n") if line.strip()]
        assert len(lines) <= 10

    async def test_severity_emojis(self, registered_cmds):
        """Critical severity uses red circle emoji."""
        cmd, db = _cmd(registered_cmds, "feed")
        interaction = _make_interaction()
        await cmd(interaction, 5)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        # We seeded critical, warning, and info items
        assert "\U0001f534" in embed.description  # red circle for critical
        assert "\U0001f7e1" in embed.description  # yellow for warning
        assert "\U0001f7e2" in embed.description  # green for info

    async def test_unknown_severity_default_emoji(self, discord_patched, db):
        """Unknown severity uses white circle."""
        from backend.bot.discord_bot import _register_commands

        db.execute(
            "INSERT INTO story_feed (event_type, headline, body, severity, timestamp)"
            " VALUES ('test', 'Mystery Event', '', 'unknown', 5000)"
        )
        db.commit()

        tree = _build_mock_tree()
        _register_commands(tree, lambda: db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["feed"]

        interaction = _make_interaction()
        await cmd(interaction, 5)

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "\u26aa" in embed.description  # white circle fallback


# ---------------------------------------------------------------------------
# /compare tests
# ---------------------------------------------------------------------------


class TestCompareCmd:
    async def test_both_found_high_similarity(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Fingerprint Comparison" in embed.title
        assert "85.0%" in embed.description

    async def test_entity_1_not_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "nonexistent_zzz", "char-001")

        msg = interaction.followup.send.call_args[0][0]
        assert "not found" in msg

    async def test_entity_2_not_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "nonexistent_zzz")

        msg = interaction.followup.send.call_args[0][0]
        assert "not found" in msg

    async def test_alt_verdict(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        verdicts = [f.value for f in embed.fields if f.name == "Verdict"]
        assert any("ALT" in v for v in verdicts)

    async def test_distinct_verdict(self, discord_patched, seeded_db):
        """Low similarity shows 'Distinct entities'."""
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint()
        tree = _build_mock_tree()
        _register_commands(
            tree,
            lambda: seeded_db,
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
        cmd = tree._captured["compare"]
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        verdicts = [f.value for f in embed.fields if f.name == "Verdict"]
        assert any("Distinct" in v for v in verdicts)
        # Low similarity should use green color
        assert embed.color.value == 0x00FF88

    async def test_fleet_mate_verdict(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint()
        tree = _build_mock_tree()
        _register_commands(
            tree,
            lambda: seeded_db,
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
        cmd = tree._captured["compare"]
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        verdicts = [f.value for f in embed.fields if f.name == "Verdict"]
        assert any("FLEET MATE" in v for v in verdicts)
        # Mid similarity should use yellow color
        assert embed.color.value == 0xFFCC00

    async def test_no_fingerprints(self, discord_patched, seeded_db):
        """Returns message when fingerprints can't be built."""
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["compare"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        msg = interaction.followup.send.call_args[0][0]
        assert "Could not build fingerprints" in msg

    async def test_similarity_fields(self, registered_cmds):
        """Embed has Temporal, Route, Social fields."""
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Temporal" in field_names
        assert "Route" in field_names
        assert "Social" in field_names

    async def test_high_similarity_red_color(self, registered_cmds):
        """Overall > 0.7 uses red color."""
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0xFF0000

    async def test_footer(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "char-001", "char-002")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Behavioral Intelligence" in embed.footer.text

    async def test_by_display_name(self, registered_cmds):
        """Compare resolves entities by display_name LIKE search."""
        cmd, db = _cmd(registered_cmds, "compare")
        interaction = _make_interaction()
        await cmd(interaction, "TestPilot", "RivalPilot")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Fingerprint Comparison" in embed.title


# ---------------------------------------------------------------------------
# /locate tests
# ---------------------------------------------------------------------------


class TestLocateCmd:
    async def test_found_by_id(self, registered_cmds):
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")
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
            associated_corps=["CorpAlpha", "CorpBeta"],
            unique_pilots=42,
        )

        with patch(
            "backend.analysis.entity_resolver.resolve_entity",
            return_value=dossier,
        ):
            await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "TestPilot" in embed.title
        assert "The Hunter" in embed.title
        field_names = [f.name for f in embed.fields]
        assert "Events" in field_names
        assert "Kills" in field_names
        assert "Deaths" in field_names
        assert "Gates" in field_names
        assert "Danger" in field_names
        assert "Unique Pilots" in field_names
        assert "Associated Corps" in field_names
        assert "Titles" in field_names

    async def test_not_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "locate")
        interaction = _make_interaction()

        with patch(
            "backend.analysis.entity_resolver.resolve_entity",
            return_value=None,
        ):
            await cmd(interaction, "nonexistent")

        msg = interaction.followup.send.call_args[0][0]
        assert "not found" in msg

    async def test_name_fallback(self, registered_cmds):
        """Falls back to display_name LIKE search when ID not found."""
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")
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

    async def test_default_footer_no_timestamps(self, registered_cmds):
        """Uses default footer when first_seen/last_seen are 0."""
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")
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

    async def test_timestamps_footer(self, registered_cmds):
        """Shows first/last seen timestamps in footer."""
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")
        interaction = _make_interaction()

        dossier = EntityDossier(
            entity_id="char-001",
            entity_type="character",
            display_name="TestPilot",
            first_seen=1000,
            last_seen=5000,
            event_count=50,
            kill_count=0,
            death_count=0,
            gate_count=0,
            corp_id=None,
        )

        with patch(
            "backend.analysis.entity_resolver.resolve_entity",
            return_value=dossier,
        ):
            await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "First seen" in embed.footer.text
        assert "Last seen" in embed.footer.text
        assert "UTC" in embed.footer.text

    async def test_danger_colors(self, registered_cmds):
        """Different danger ratings produce different embed colors."""
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")

        for danger, expected_color in [
            ("extreme", 0xFF0000),
            ("high", 0xFF4400),
            ("moderate", 0xFFCC00),
            ("low", 0x00FF88),
        ]:
            dossier = EntityDossier(
                entity_id="char-001",
                entity_type="character",
                display_name="TestPilot",
                first_seen=1000,
                last_seen=5000,
                event_count=50,
                kill_count=10,
                death_count=2,
                gate_count=30,
                corp_id=None,
                danger_rating=danger,
            )

            interaction = _make_interaction()
            with patch(
                "backend.analysis.entity_resolver.resolve_entity",
                return_value=dossier,
            ):
                await cmd(interaction, "char-001")

            embed = interaction.followup.send.call_args.kwargs["embed"]
            assert embed.color.value == expected_color, f"Failed for danger={danger}"

    async def test_unknown_danger_hides_field(self, registered_cmds):
        """Danger field omitted when rating is 'unknown'."""
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")
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
        field_names = [f.name for f in embed.fields]
        assert "Danger" not in field_names

    async def test_no_titles_no_corps_no_pilots(self, registered_cmds):
        """Omits optional fields when empty."""
        from backend.analysis.entity_resolver import EntityDossier

        cmd, db = _cmd(registered_cmds, "locate")
        interaction = _make_interaction()

        dossier = EntityDossier(
            entity_id="char-001",
            entity_type="character",
            display_name="TestPilot",
            first_seen=1000,
            last_seen=5000,
            event_count=50,
            kill_count=0,
            death_count=0,
            gate_count=0,
            corp_id=None,
            danger_rating="low",
            titles=[],
            associated_corps=[],
            unique_pilots=0,
        )

        with patch(
            "backend.analysis.entity_resolver.resolve_entity",
            return_value=dossier,
        ):
            await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Titles" not in field_names
        assert "Associated Corps" not in field_names
        assert "Unique Pilots" not in field_names


# ---------------------------------------------------------------------------
# /history tests
# ---------------------------------------------------------------------------


class TestHistoryCmd:
    async def test_returns_narrative(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "history")
        interaction = _make_interaction()

        with patch(
            "backend.analysis.narrative.generate_dossier_narrative",
            return_value="This pilot terrorizes the frontier.",
        ):
            await cmd(interaction, "char-001")

        interaction.response.defer.assert_awaited_once()
        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Dossier" in embed.title
        assert "terrorizes" in embed.description

    async def test_truncates_long_narrative(self, registered_cmds):
        """Narratives over 4000 chars get truncated."""
        cmd, db = _cmd(registered_cmds, "history")
        interaction = _make_interaction()

        long_text = "A" * 5000
        with patch(
            "backend.analysis.narrative.generate_dossier_narrative",
            return_value=long_text,
        ):
            await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert len(embed.description) == 4000

    async def test_footer(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "history")
        interaction = _make_interaction()

        with patch(
            "backend.analysis.narrative.generate_dossier_narrative",
            return_value="Story text",
        ):
            await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "AI-generated" in embed.footer.text


# ---------------------------------------------------------------------------
# /watch tests
# ---------------------------------------------------------------------------


class TestWatchCmd:
    async def test_valid_entity_movement(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "entity_movement", "gate-001", "")

        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "Watch set" in msg
        assert "entity_movement" in msg

        row = db.execute("SELECT * FROM watches").fetchone()
        assert row["target_id"] == "gate-001"
        assert row["watch_type"] == "entity_movement"

    async def test_valid_gate_traffic_spike(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "gate_traffic_spike", "gate-001", "")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Watch set" in msg

    async def test_valid_killmail_proximity(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "killmail_proximity", "sys-001", "")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Watch set" in msg

    async def test_valid_hostile_sighting(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "hostile_sighting", "char-001", "")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Watch set" in msg

    async def test_invalid_type(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "bad_type", "gate-001", "")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Invalid type" in msg
        assert db.execute("SELECT * FROM watches").fetchone() is None

    async def test_with_webhook_url(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(
            interaction, "entity_movement", "gate-001", "https://discord.com/api/webhooks/test"
        )

        row = db.execute("SELECT * FROM watches").fetchone()
        assert row["webhook_url"] == "https://discord.com/api/webhooks/test"

    async def test_stores_channel_id(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction(channel_id=77777)
        await cmd(interaction, "entity_movement", "gate-001", "")

        row = db.execute("SELECT * FROM watches").fetchone()
        assert row["channel_id"] == "77777"

    async def test_stores_user_id(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction(user_id=54321)
        await cmd(interaction, "entity_movement", "gate-001", "")

        row = db.execute("SELECT * FROM watches").fetchone()
        assert row["user_id"] == "54321"

    async def test_conditions_json(self, registered_cmds):
        """Conditions field stores JSON with lookback_seconds."""
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "entity_movement", "gate-001", "")

        row = db.execute("SELECT * FROM watches").fetchone()
        conditions = json.loads(row["conditions"])
        assert conditions["lookback_seconds"] == 300

    async def test_ephemeral(self, registered_cmds):
        """Watch response is ephemeral."""
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        await cmd(interaction, "entity_movement", "gate-001", "")

        kwargs = interaction.response.send_message.call_args.kwargs
        assert kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# /unwatch tests
# ---------------------------------------------------------------------------


class TestUnwatchCmd:
    async def test_deactivates_watch(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "unwatch")
        # Insert an active watch
        db.execute(
            "INSERT INTO watches (user_id, watch_type, target_id,"
            " conditions, webhook_url, channel_id, active)"
            " VALUES ('12345', 'entity_movement', 'gate-001', '{}', '', '99999', 1)"
        )
        db.commit()

        interaction = _make_interaction(user_id=12345)
        await cmd(interaction, "gate-001")

        row = db.execute("SELECT active FROM watches").fetchone()
        assert row["active"] == 0

    async def test_response_message(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "unwatch")
        interaction = _make_interaction()
        await cmd(interaction, "gate-001")

        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "Watch removed" in msg

    async def test_ephemeral(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "unwatch")
        interaction = _make_interaction()
        await cmd(interaction, "gate-001")

        kwargs = interaction.response.send_message.call_args.kwargs
        assert kwargs.get("ephemeral") is True

    async def test_only_deactivates_own_watches(self, registered_cmds):
        """Only deactivates watches for the requesting user."""
        cmd, db = _cmd(registered_cmds, "unwatch")
        db.execute(
            "INSERT INTO watches (user_id, watch_type, target_id,"
            " conditions, webhook_url, channel_id, active)"
            " VALUES ('other_user', 'entity_movement', 'gate-001', '{}', '', '99999', 1)"
        )
        db.commit()

        interaction = _make_interaction(user_id=12345)
        await cmd(interaction, "gate-001")

        # Other user's watch should still be active
        row = db.execute("SELECT active FROM watches WHERE user_id = 'other_user'").fetchone()
        assert row["active"] == 1


# ---------------------------------------------------------------------------
# /profile tests
# ---------------------------------------------------------------------------


class TestProfileCmd:
    async def test_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "profile")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        interaction.response.defer.assert_awaited_once()
        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Behavioral Profile" in embed.title
        assert "OPSEC" in embed.description
        assert "Threat" in embed.description

    async def test_not_found(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "nonexistent")

        msg = interaction.followup.send.call_args[0][0]
        assert "not found" in msg

    async def test_activity_pattern_field(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "profile")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Activity Pattern" in field_names

    async def test_movement_field(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "profile")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Movement" in field_names

    async def test_social_field_when_associates(self, registered_cmds):
        """Social field shown when character has associates."""
        cmd, db = _cmd(registered_cmds, "profile")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Social" in field_names

    async def test_no_social_when_zero_associates(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint()
        fp.social.unique_associates = 0

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Social" not in field_names

    async def test_no_social_for_gate(self, discord_patched, seeded_db):
        """Social field hidden for non-character entities."""
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(entity_type="gate")

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "gate-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Social" not in field_names

    async def test_extreme_threat_red(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(threat_level="extreme")

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0xFF0000

    async def test_high_threat_red(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(threat_level="high")

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0xFF0000

    async def test_moderate_threat_yellow(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(threat_level="moderate")

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0xFFCC00

    async def test_low_threat_green(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(threat_level="low")

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0x00FF88

    async def test_footer(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "profile")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Behavioral Intelligence" in embed.footer.text

    async def test_not_found_ephemeral(self, discord_patched, seeded_db):
        """Not found message is ephemeral."""
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["profile"]

        interaction = _make_interaction()
        await cmd(interaction, "nonexistent")

        kwargs = interaction.followup.send.call_args.kwargs
        assert kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# /opsec tests
# ---------------------------------------------------------------------------


class TestOpsecCmd:
    async def test_found(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "opsec")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "OPSEC Score" in embed.title
        assert "75/100" in embed.description

    async def test_not_found(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["opsec"]

        interaction = _make_interaction()
        await cmd(interaction, "nonexistent")

        msg = interaction.followup.send.call_args[0][0]
        assert "not found" in msg

    async def test_insufficient_data(self, discord_patched, seeded_db):
        """Rejects entities with < 20 events."""
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(event_count=10)

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["opsec"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        msg = interaction.followup.send.call_args[0][0]
        assert "Not enough data" in msg
        assert "20" in msg

    async def test_green_color_high_score(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(opsec_score=80)

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["opsec"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0x00FF88

    async def test_yellow_color_mid_score(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(opsec_score=50)

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["opsec"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0xFFCC00

    async def test_red_color_low_score(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        fp = _make_fingerprint(opsec_score=20)

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: fp, lambda a, b: {})
        cmd = tree._captured["opsec"]

        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert embed.color.value == 0xFF0000

    async def test_fields(self, registered_cmds):
        """Opsec embed has time, route, gate diversity fields."""
        cmd, db = _cmd(registered_cmds, "opsec")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        field_names = [f.name for f in embed.fields]
        assert "Time Predictability" in field_names
        assert "Route Predictability" in field_names
        assert "Gate Diversity" in field_names

    async def test_footer(self, registered_cmds):
        cmd, db = _cmd(registered_cmds, "opsec")
        interaction = _make_interaction()
        await cmd(interaction, "char-001")

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "Counter-Intelligence" in embed.footer.text

    async def test_not_found_ephemeral(self, discord_patched, seeded_db):
        from backend.bot.discord_bot import _register_commands

        tree = _build_mock_tree()
        _register_commands(tree, lambda: seeded_db, lambda d, e: None, lambda a, b: {})
        cmd = tree._captured["opsec"]

        interaction = _make_interaction()
        await cmd(interaction, "nonexistent")

        kwargs = interaction.followup.send.call_args.kwargs
        assert kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# run_bot tests
# ---------------------------------------------------------------------------


class TestRunBot:
    async def test_no_discord_returns_early(self):
        with patch("backend.bot.discord_bot.HAS_DISCORD", False):
            from backend.bot.discord_bot import run_bot

            await run_bot()

    async def test_no_token_returns_early(self):
        with (
            patch("backend.bot.discord_bot.HAS_DISCORD", True),
            patch("backend.bot.discord_bot.settings") as mock_settings,
        ):
            mock_settings.DISCORD_TOKEN = ""
            from backend.bot.discord_bot import run_bot

            await run_bot()

    async def test_bot_start_exception(self, discord_patched):
        """Bot logs error and returns when start() raises."""
        import backend.bot.discord_bot as bot_mod

        discord_mod, app_commands_mod = discord_patched

        # Make Client support subclassing — start() raises to test error path
        class TestableClient:
            def __init__(self, *, intents=None):
                self.intents = intents
                self.user = "TestBot#0001"

            async def start(self, token):
                raise ConnectionError("Auth failed")

        # CommandTree mock that captures sync
        mock_tree = MagicMock()
        mock_tree.sync = AsyncMock()

        discord_mod.Client = TestableClient
        app_commands_mod.CommandTree = lambda self: mock_tree

        with (
            patch("backend.bot.discord_bot.settings") as mock_settings,
            patch.object(bot_mod, "logger") as mock_logger,
        ):
            mock_settings.DISCORD_TOKEN = "fake-token"
            await bot_mod.run_bot()

            mock_logger.error.assert_called_once()
            assert "Auth failed" in str(mock_logger.error.call_args)

    async def test_bot_start_success_path(self, discord_patched):
        """Bot calls start() with token — covers lines 46-73."""
        import backend.bot.discord_bot as bot_mod

        discord_mod, app_commands_mod = discord_patched

        started_with_token = []

        class TestableClient:
            def __init__(self, *, intents=None):
                self.intents = intents
                self.user = "TestBot#0001"
                self.tree = MagicMock()
                self.tree.sync = AsyncMock()

            async def start(self, token):
                started_with_token.append(token)

        discord_mod.Client = TestableClient
        app_commands_mod.CommandTree = lambda self: MagicMock(sync=AsyncMock())

        with patch("backend.bot.discord_bot.settings") as mock_settings:
            mock_settings.DISCORD_TOKEN = "test-token-123"
            await bot_mod.run_bot()

        assert started_with_token == ["test-token-123"]


# ---------------------------------------------------------------------------
# _register_commands registration test
# ---------------------------------------------------------------------------


class TestRegisterCommands:
    def test_all_commands_registered(self, registered_cmds):
        cmds, db = registered_cmds
        expected = [
            "watchtower",
            "killfeed",
            "leaderboard",
            "feed",
            "compare",
            "locate",
            "history",
            "watch",
            "unwatch",
            "profile",
            "opsec",
        ]
        for name in expected:
            assert name in cmds, f"Command {name} not registered"

    def test_all_commands_are_callable(self, registered_cmds):
        cmds, db = registered_cmds
        for name in [
            "watchtower",
            "killfeed",
            "leaderboard",
            "feed",
            "compare",
            "locate",
            "history",
            "watch",
            "unwatch",
            "profile",
            "opsec",
        ]:
            assert callable(cmds[name])

    async def test_watch_default_webhook(self, registered_cmds):
        """Watch works with default empty webhook_url parameter."""
        cmd, db = _cmd(registered_cmds, "watch")
        interaction = _make_interaction()
        # The actual signature has webhook_url="" as default
        await cmd(interaction, "entity_movement", "gate-001")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Watch set" in msg
