"""Witness Discord bot — chain intelligence at your fingertips.

Commands:
  /witness <name>  — Look up an entity by name or address
  /killfeed         — Latest killmails
  /leaderboard      — Top killers / most deaths / most traveled
  /feed             — Recent story feed items
  /compare <a> <b>  — Compare two entity fingerprints
"""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("discord")

try:
    import discord
    from discord import app_commands

    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False


async def run_bot() -> None:
    """Start the Discord bot. Returns immediately if no token or no discord.py."""
    if not HAS_DISCORD:
        logger.info("discord.py not installed — bot disabled")
        return

    if not settings.DISCORD_TOKEN:
        logger.info("No DISCORD_TOKEN set — bot disabled")
        return

    from backend.analysis.fingerprint import build_fingerprint, compare_fingerprints
    from backend.db.database import get_db

    class WitnessBot(discord.Client):
        def __init__(self) -> None:
            intents = discord.Intents.default()
            super().__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)

        async def setup_hook(self) -> None:
            _register_commands(self.tree, get_db, build_fingerprint, compare_fingerprints)
            await self.tree.sync()
            logger.info("Slash commands synced")

        async def on_ready(self) -> None:
            logger.info("Witness bot online as %s", self.user)

    bot = WitnessBot()
    try:
        await bot.start(settings.DISCORD_TOKEN)
    except Exception as e:
        logger.error("Discord bot error: %s", e)


def _register_commands(tree, get_db, build_fingerprint, compare_fingerprints) -> None:
    """Register all slash commands."""

    @tree.command(name="witness", description="Look up an entity by name or address")
    @app_commands.describe(query="Entity name or blockchain address")
    async def witness_cmd(interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        db = get_db()

        pattern = f"%{query}%"
        row = db.execute(
            """SELECT entity_id, entity_type, display_name, kill_count,
                      death_count, event_count
               FROM entities
               WHERE entity_id LIKE ? OR display_name LIKE ?
               ORDER BY event_count DESC LIMIT 1""",
            (pattern, pattern),
        ).fetchone()

        if not row:
            await interaction.followup.send(f"No entity found matching `{query}`")
            return

        name = row["display_name"] or row["entity_id"][:20]
        embed = discord.Embed(
            title=f"{name}",
            description=f"Type: `{row['entity_type']}`",
            color=0x00FF88,
        )
        embed.add_field(name="Kills", value=str(row["kill_count"]), inline=True)
        embed.add_field(name="Deaths", value=str(row["death_count"]), inline=True)
        embed.add_field(name="Events", value=str(row["event_count"]), inline=True)

        titles = db.execute(
            "SELECT title FROM entity_titles WHERE entity_id = ?",
            (row["entity_id"],),
        ).fetchall()
        if titles:
            embed.add_field(
                name="Titles",
                value=", ".join(f'"{t["title"]}"' for t in titles),
                inline=False,
            )

        fp = build_fingerprint(db, row["entity_id"])
        if fp:
            embed.add_field(name="Threat", value=fp.threat.threat_level.upper(), inline=True)
            embed.add_field(name="OPSEC", value=fp.opsec_rating, inline=True)

        embed.set_footer(text=f"ID: {row['entity_id'][:24]}...")
        await interaction.followup.send(embed=embed)

    @tree.command(name="killfeed", description="Latest killmails")
    @app_commands.describe(count="Number of kills to show (max 10)")
    async def killfeed_cmd(interaction: discord.Interaction, count: int = 5) -> None:
        await interaction.response.defer()
        db = get_db()
        count = min(count, 10)

        kills = db.execute(
            """SELECT killmail_id, victim_name, victim_character_id, timestamp
               FROM killmails ORDER BY timestamp DESC LIMIT ?""",
            (count,),
        ).fetchall()

        if not kills:
            await interaction.followup.send("No killmails recorded yet.")
            return

        lines = []
        for k in kills:
            victim = k["victim_name"] or k["victim_character_id"][:16]
            ts = f"<t:{k['timestamp']}:R>"
            lines.append(f"**{victim}** destroyed {ts}")

        embed = discord.Embed(
            title=f"Latest {len(kills)} Killmails",
            description="\n".join(lines),
            color=0xFF4444,
        )
        await interaction.followup.send(embed=embed)

    @tree.command(name="leaderboard", description="Top entities by category")
    @app_commands.describe(category="Category: top_killers, most_deaths, most_traveled")
    @app_commands.choices(
        category=[
            app_commands.Choice(name="Top Killers", value="top_killers"),
            app_commands.Choice(name="Most Deaths", value="most_deaths"),
            app_commands.Choice(name="Most Traveled", value="most_traveled"),
        ]
    )
    async def leaderboard_cmd(
        interaction: discord.Interaction, category: str = "top_killers"
    ) -> None:
        await interaction.response.defer()
        db = get_db()

        col_map = {
            "top_killers": ("kill_count", "Kills"),
            "most_deaths": ("death_count", "Deaths"),
            "most_traveled": ("gate_count", "Transits"),
        }
        col, label = col_map.get(category, ("kill_count", "Kills"))

        rows = db.execute(
            f"""SELECT display_name, entity_id, {col} as score
                FROM entities WHERE entity_type = 'character' AND {col} > 0
                ORDER BY {col} DESC LIMIT 10"""
        ).fetchall()

        lines = []
        for i, r in enumerate(rows, 1):
            name = r["display_name"] or r["entity_id"][:16]
            lines.append(f"`{i:2d}.` **{name}** — {r['score']} {label.lower()}")

        embed = discord.Embed(
            title=f"Leaderboard: {label}",
            description="\n".join(lines) or "No data yet.",
            color=0x00FF88,
        )
        await interaction.followup.send(embed=embed)

    @tree.command(name="feed", description="Recent story feed")
    async def feed_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        db = get_db()

        items = db.execute(
            "SELECT headline, severity, timestamp FROM story_feed ORDER BY timestamp DESC LIMIT 5"
        ).fetchall()

        if not items:
            await interaction.followup.send("No stories yet.")
            return

        severity_emoji = {"critical": "\U0001f534", "warning": "\U0001f7e1", "info": "\U0001f7e2"}
        lines = []
        for item in items:
            emoji = severity_emoji.get(item["severity"], "\u26aa")
            ts = f"<t:{item['timestamp']}:R>"
            lines.append(f"{emoji} {item['headline'][:80]} {ts}")

        embed = discord.Embed(
            title="Story Feed",
            description="\n".join(lines),
            color=0xFF8800,
        )
        await interaction.followup.send(embed=embed)

    @tree.command(name="compare", description="Compare two entity fingerprints")
    @app_commands.describe(entity_1="First entity name/ID", entity_2="Second entity name/ID")
    async def compare_cmd(interaction: discord.Interaction, entity_1: str, entity_2: str) -> None:
        await interaction.response.defer()
        db = get_db()

        ids = []
        for query in (entity_1, entity_2):
            row = db.execute(
                """SELECT entity_id FROM entities
                   WHERE entity_id = ? OR display_name LIKE ?
                   ORDER BY event_count DESC LIMIT 1""",
                (query, f"%{query}%"),
            ).fetchone()
            if not row:
                await interaction.followup.send(f"Entity not found: `{query}`")
                return
            ids.append(row["entity_id"])

        fp1 = build_fingerprint(db, ids[0])
        fp2 = build_fingerprint(db, ids[1])
        if not fp1 or not fp2:
            await interaction.followup.send("Could not build fingerprints for comparison.")
            return

        result = compare_fingerprints(fp1, fp2)
        embed = discord.Embed(title="Fingerprint Comparison", color=0x00AAFF)
        embed.add_field(name="Entity 1", value=entity_1, inline=True)
        embed.add_field(name="Entity 2", value=entity_2, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(
            name="Overall Similarity",
            value=f"{result['overall_similarity']:.0%}",
            inline=True,
        )
        embed.add_field(
            name="Likely Alt?",
            value="Yes" if result["likely_alt"] else "No",
            inline=True,
        )
        embed.add_field(
            name="Fleet Mates?",
            value="Yes" if result["likely_fleet_mate"] else "No",
            inline=True,
        )
        await interaction.followup.send(embed=embed)
