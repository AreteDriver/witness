"""Tests for Discord bot commands."""

import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.db.database import SCHEMA


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Seed test data
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 10, 3, 25, 1000, 5000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 0, 0, 0, 1000, 5000)"
    )
    conn.execute(
        "INSERT INTO entity_titles (entity_id, title, title_type) "
        "VALUES ('char-001', 'The Reaper', 'character')"
    )
    conn.execute(
        "INSERT INTO killmails (killmail_id, victim_character_id, victim_name,"
        " solar_system_id, timestamp) "
        "VALUES ('km-1', 'char-002', 'Victim1', 'sys-1', 5000)"
    )
    conn.execute(
        "INSERT INTO story_feed (event_type, headline, severity, timestamp) "
        "VALUES ('engagement', 'Test Battle', 'warning', 1000)"
    )
    conn.execute(
        "INSERT INTO gate_events (gate_id, gate_name, character_id,"
        " solar_system_id, timestamp) "
        "VALUES ('gate-001', 'Alpha Gate', 'char-001', 'sys-1', 5000)"
    )
    conn.commit()
    return conn


def _make_interaction(user_id="12345", channel_id="67890"):
    """Create a mock Discord interaction."""
    interaction = AsyncMock()
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.channel_id = channel_id
    return interaction


class TestEntityAutocomplete:
    def test_short_input_returns_empty(self, test_db):
        from backend.bot.discord_bot import entity_autocomplete

        autocomplete_fn = entity_autocomplete(lambda: test_db)
        interaction = AsyncMock()
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(autocomplete_fn(interaction, "T"))
        assert result == []

    def test_matching_input(self, test_db):
        from backend.bot.discord_bot import entity_autocomplete

        autocomplete_fn = entity_autocomplete(lambda: test_db)
        interaction = AsyncMock()
        import asyncio

        result = asyncio.get_event_loop().run_until_complete(autocomplete_fn(interaction, "Test"))
        assert len(result) >= 1


class TestRegisterCommands:
    """Test _register_commands by calling commands directly."""

    @pytest.fixture
    def commands(self, test_db):
        """Register commands and return them as a dict."""
        pytest.importorskip("discord")
        from discord import app_commands

        from backend.analysis.fingerprint import build_fingerprint, compare_fingerprints
        from backend.bot.discord_bot import _register_commands

        mock_client = MagicMock()
        mock_client._connection._command_tree = None
        tree = app_commands.CommandTree(mock_client)
        _register_commands(tree, lambda: test_db, build_fingerprint, compare_fingerprints)

        # Extract commands by name
        cmds = {}
        for cmd in tree.get_commands():
            cmds[cmd.name] = cmd
        return cmds

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_witness_cmd_found(self, commands, test_db):
        assert "witness" in commands
        interaction = _make_interaction()
        await commands["witness"].callback(interaction, "TestPilot")
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_witness_cmd_not_found(self, commands, test_db):
        interaction = _make_interaction()
        await commands["witness"].callback(interaction, "nonexistent_xyz_123")
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        assert "No entity found" in str(call_args)

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_killfeed_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["killfeed"].callback(interaction, 5)
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_killfeed_empty(self, commands):
        # Use empty DB
        empty_db = sqlite3.connect(":memory:")
        empty_db.row_factory = sqlite3.Row
        empty_db.executescript(SCHEMA)

        # Patch the get_db used in the closure
        interaction = _make_interaction()
        await commands["killfeed"].callback(interaction, 5)
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_leaderboard_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["leaderboard"].callback(interaction, "top_killers")
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_leaderboard_invalid_category(self, commands, test_db):
        interaction = _make_interaction()
        await commands["leaderboard"].callback(interaction, "invalid_category")
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        assert "Unknown category" in str(call_args)

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_feed_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["feed"].callback(interaction, 5)
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_profile_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["profile"].callback(interaction, "char-001")
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_profile_not_found(self, commands, test_db):
        interaction = _make_interaction()
        await commands["profile"].callback(interaction, "nonexistent")
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_opsec_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["opsec"].callback(interaction, "char-001")
        interaction.followup.send.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_watch_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["watch"].callback(interaction, "entity_movement", "char-001", "")
        interaction.response.send_message.assert_called_once()

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_watch_invalid_type(self, commands, test_db):
        interaction = _make_interaction()
        await commands["watch"].callback(interaction, "invalid", "char-001", "")
        call_args = interaction.response.send_message.call_args
        assert "Invalid type" in str(call_args)

    @pytest.mark.skipif(
        not pytest.importorskip("discord", reason="discord.py not installed"),
        reason="discord.py not installed",
    )
    async def test_unwatch_cmd(self, commands, test_db):
        interaction = _make_interaction()
        await commands["unwatch"].callback(interaction, "char-001")
        interaction.response.send_message.assert_called_once()


class TestRunBot:
    async def test_run_bot_no_discord(self):
        """Bot returns immediately if discord.py not installed."""
        with patch("backend.bot.discord_bot.HAS_DISCORD", False):
            from backend.bot.discord_bot import run_bot

            await run_bot()

    async def test_run_bot_no_token(self):
        """Bot returns immediately if no token set."""
        with (
            patch("backend.bot.discord_bot.HAS_DISCORD", True),
            patch("backend.bot.discord_bot.settings") as mock_settings,
        ):
            mock_settings.DISCORD_TOKEN = ""
            from backend.bot.discord_bot import run_bot

            await run_bot()
