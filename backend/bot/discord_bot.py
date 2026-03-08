"""Witness Discord bot — chain intelligence at your fingertips.

Commands:
  /witness <name>  — Look up an entity by name or address
  /killfeed         — Latest killmails
  /leaderboard      — Top killers / most deaths / most traveled
  /feed             — Recent story feed items
  /compare <a> <b>  — Compare two entity fingerprints
  /locate <id>      — Full entity lookup with danger rating
  /history <id>     — AI-generated narrative dossier
  /watch            — Set a standing intelligence watch
  /unwatch          — Remove a standing watch
  /profile <id>     — Full behavioral fingerprint
  /opsec <id>       — OPSEC score analysis
"""

from __future__ import annotations

import json
import time

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
    """Start the Discord bot. Returns immediately if no token or discord.py."""
    if not HAS_DISCORD:
        logger.info("discord.py not installed — bot disabled")
        return

    if not settings.DISCORD_TOKEN:
        logger.info("No DISCORD_TOKEN set — bot disabled")
        return

    from backend.analysis.fingerprint import (
        build_fingerprint,
        compare_fingerprints,
    )
    from backend.db.database import get_db

    class WitnessBot(discord.Client):
        def __init__(self) -> None:
            intents = discord.Intents.default()
            super().__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)

        async def setup_hook(self) -> None:
            _register_commands(
                self.tree,
                get_db,
                build_fingerprint,
                compare_fingerprints,
            )
            await self.tree.sync()
            logger.info("Slash commands synced")

        async def on_ready(self) -> None:
            logger.info("Witness bot online as %s", self.user)

    bot = WitnessBot()
    try:
        await bot.start(settings.DISCORD_TOKEN)
    except Exception as e:
        logger.error("Discord bot error: %s", e)


def entity_autocomplete(get_db):
    """Build an autocomplete callback with injected get_db."""

    async def _autocomplete(
        interaction,
        current: str,
    ) -> list:
        if len(current) < 2:
            return []
        db = get_db()
        rows = db.execute(
            """SELECT entity_id, display_name, entity_type
               FROM entities
               WHERE entity_id LIKE ? OR display_name LIKE ?
               ORDER BY event_count DESC LIMIT 10""",
            (f"%{current}%", f"%{current}%"),
        ).fetchall()
        if not HAS_DISCORD:
            return [
                {
                    "name": (
                        f"[{r['entity_type'][:4].upper()}] "
                        f"{r['display_name'] or r['entity_id'][:20]}"
                    ),
                    "value": r["entity_id"],
                }
                for r in rows
            ]
        return [
            app_commands.Choice(
                name=(
                    f"[{r['entity_type'][:4].upper()}] {r['display_name'] or r['entity_id'][:20]}"
                ),
                value=r["entity_id"],
            )
            for r in rows
        ]

    return _autocomplete


def _register_commands(
    tree,
    get_db,
    build_fingerprint,
    compare_fingerprints,
) -> None:
    """Register all slash commands with dependency injection."""

    autocomplete_fn = entity_autocomplete(get_db)

    # ---- /witness ----

    @tree.command(
        name="witness",
        description="Look up an entity by name or address",
    )
    @app_commands.describe(query="Entity name or blockchain address")
    async def witness_cmd(interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        db = get_db()

        pattern = f"%{query}%"
        row = db.execute(
            """SELECT entity_id, entity_type, display_name,
                      kill_count, death_count, event_count
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
            embed.add_field(
                name="Threat",
                value=fp.threat.threat_level.upper(),
                inline=True,
            )
            embed.add_field(name="OPSEC", value=fp.opsec_rating, inline=True)

        embed.set_footer(text=f"ID: {row['entity_id'][:24]}...")
        await interaction.followup.send(embed=embed)

    # ---- /killfeed ----

    @tree.command(name="killfeed", description="Latest killmails")
    @app_commands.describe(count="Number of kills to show (max 10)")
    async def killfeed_cmd(interaction: discord.Interaction, count: int = 5) -> None:
        await interaction.response.defer()
        db = get_db()
        count = min(count, 10)

        kills = db.execute(
            """SELECT killmail_id, victim_name,
                      victim_character_id, timestamp
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

    # ---- /leaderboard ----

    @tree.command(name="leaderboard", description="Top entities by category")
    @app_commands.describe(
        category=(
            "Category: top_killers, most_deaths, most_traveled, deadliest_gates, most_active_gates"
        )
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="Top Killers", value="top_killers"),
            app_commands.Choice(name="Most Deaths", value="most_deaths"),
            app_commands.Choice(name="Most Traveled", value="most_traveled"),
            app_commands.Choice(name="Deadliest Gates", value="deadliest_gates"),
            app_commands.Choice(name="Most Active Gates", value="most_active_gates"),
        ]
    )
    async def leaderboard_cmd(
        interaction: discord.Interaction,
        category: str = "top_killers",
    ) -> None:
        await interaction.response.defer()
        db = get_db()

        queries = {
            "deadliest_gates": (
                "Deadliest Gates",
                "entity_type = 'gate'",
                "kill_count DESC",
                "kill_count",
            ),
            "most_active_gates": (
                "Most Active Gates",
                "entity_type = 'gate'",
                "event_count DESC",
                "event_count",
            ),
            "top_killers": (
                "Top Killers",
                "entity_type = 'character' AND kill_count > 0",
                "kill_count DESC",
                "kill_count",
            ),
            "most_deaths": (
                "Most Deaths",
                "entity_type = 'character' AND death_count > 0",
                "death_count DESC",
                "death_count",
            ),
            "most_traveled": (
                "Most Traveled",
                "entity_type = 'character'",
                "gate_count DESC",
                "gate_count",
            ),
        }

        if category not in queries:
            await interaction.followup.send(
                f"Unknown category. Choose: {', '.join(queries.keys())}"
            )
            return

        title, where, order, stat_col = queries[category]
        rows = db.execute(
            f"""SELECT entity_id, display_name, {stat_col} as score
                FROM entities WHERE {where}
                ORDER BY {order} LIMIT 10"""
        ).fetchall()

        if not rows:
            await interaction.followup.send("No data yet.")
            return

        lines = []
        for i, r in enumerate(rows, 1):
            name = r["display_name"] or r["entity_id"][:16]
            lines.append(f"`{i:2d}.` **{name}** — {r['score']}")

        embed = discord.Embed(
            title=f"Leaderboard: {title}",
            description="\n".join(lines),
            color=0x00FF88,
        )
        await interaction.followup.send(embed=embed)

    # ---- /feed ----

    @tree.command(name="feed", description="Recent story feed")
    @app_commands.describe(count="Number of items (default 5)")
    async def feed_cmd(interaction: discord.Interaction, count: int = 5) -> None:
        await interaction.response.defer()
        db = get_db()
        count = min(count, 10)

        items = db.execute(
            """SELECT headline, severity, timestamp
               FROM story_feed ORDER BY timestamp DESC LIMIT ?""",
            (count,),
        ).fetchall()

        if not items:
            await interaction.followup.send("No stories yet.")
            return

        severity_emoji = {
            "critical": "\U0001f534",
            "warning": "\U0001f7e1",
            "info": "\U0001f7e2",
        }
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

    # ---- /compare ----

    @tree.command(
        name="compare",
        description="Compare two entity fingerprints",
    )
    @app_commands.describe(
        entity_1="First entity name/ID",
        entity_2="Second entity name/ID",
    )
    async def compare_cmd(
        interaction: discord.Interaction,
        entity_1: str,
        entity_2: str,
    ) -> None:
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
        overall = result["overall_similarity"]
        color = 0xFF0000 if overall > 0.7 else 0xFFCC00 if overall > 0.4 else 0x00FF88

        embed = discord.Embed(
            title="Fingerprint Comparison",
            description=(
                f"`{entity_1[:16]}` vs `{entity_2[:16]}`\n**Overall Similarity: {overall:.1%}**"
            ),
            color=color,
        )
        embed.add_field(
            name="Temporal",
            value=f"{result['temporal_similarity']:.1%}",
            inline=True,
        )
        embed.add_field(
            name="Route",
            value=f"{result['route_similarity']:.1%}",
            inline=True,
        )
        embed.add_field(
            name="Social",
            value=f"{result['social_similarity']:.1%}",
            inline=True,
        )

        verdicts = []
        if result["likely_alt"]:
            verdicts.append("LIKELY ALT ACCOUNT")
        if result["likely_fleet_mate"]:
            verdicts.append("LIKELY FLEET MATE")
        if not verdicts:
            verdicts.append("Distinct entities")

        embed.add_field(
            name="Verdict",
            value="\n".join(verdicts),
            inline=False,
        )
        embed.set_footer(text="Witness — Behavioral Intelligence")
        await interaction.followup.send(embed=embed)

    # ---- /locate ----

    @tree.command(
        name="locate",
        description="Look up any entity — gate, character, corp",
    )
    @app_commands.describe(entity_id="Entity ID or name to look up")
    async def locate_cmd(interaction: discord.Interaction, entity_id: str) -> None:
        await interaction.response.defer()

        from backend.analysis.entity_resolver import resolve_entity

        db = get_db()
        dossier = resolve_entity(db, entity_id)
        if not dossier:
            row = db.execute(
                "SELECT entity_id FROM entities WHERE display_name LIKE ? LIMIT 1",
                (f"%{entity_id}%",),
            ).fetchone()
            if row:
                dossier = resolve_entity(db, row["entity_id"])

        if not dossier:
            await interaction.followup.send(f"Entity `{entity_id}` not found.")
            return

        d = dossier.to_dict()
        title_str = f' "{d["titles"][0]}"' if d["titles"] else ""

        danger_colors = {
            "extreme": 0xFF0000,
            "high": 0xFF4400,
            "moderate": 0xFFCC00,
            "low": 0x00FF88,
        }
        color = danger_colors.get(d.get("danger_rating", ""), 0xFF6600)

        embed = discord.Embed(
            title=f"{d['display_name']}{title_str}",
            description=(f"Type: {d['entity_type']} | ID: `{d['entity_id'][:20]}`"),
            color=color,
        )
        embed.add_field(
            name="Events",
            value=str(d["event_count"]),
            inline=True,
        )
        embed.add_field(
            name="Kills",
            value=str(d["kill_count"]),
            inline=True,
        )
        embed.add_field(
            name="Deaths",
            value=str(d["death_count"]),
            inline=True,
        )
        embed.add_field(
            name="Gates",
            value=str(d["gate_count"]),
            inline=True,
        )

        if d["danger_rating"] != "unknown":
            embed.add_field(
                name="Danger",
                value=d["danger_rating"].upper(),
                inline=True,
            )
        if d["unique_pilots"]:
            embed.add_field(
                name="Unique Pilots",
                value=str(d["unique_pilots"]),
                inline=True,
            )
        if d["associated_corps"]:
            embed.add_field(
                name="Associated Corps",
                value="\n".join(c[:16] for c in d["associated_corps"][:5]),
                inline=False,
            )
        if d["titles"]:
            embed.add_field(
                name="Titles",
                value=", ".join(d["titles"]),
                inline=False,
            )

        first_seen = d.get("first_seen", 0)
        last_seen = d.get("last_seen", 0)
        if first_seen and last_seen:
            fs = time.strftime("%Y-%m-%d %H:%M", time.gmtime(first_seen))
            ls = time.strftime("%Y-%m-%d %H:%M", time.gmtime(last_seen))
            embed.set_footer(text=(f"First seen: {fs} UTC | Last seen: {ls} UTC"))
        else:
            embed.set_footer(text="Witness — The Living Memory of EVE Frontier")
        await interaction.followup.send(embed=embed)

    # ---- /history ----

    @tree.command(
        name="history",
        description="AI-generated narrative for an entity",
    )
    @app_commands.describe(entity_id="Entity ID to analyze")
    async def history_cmd(interaction: discord.Interaction, entity_id: str) -> None:
        await interaction.response.defer()

        from backend.analysis.narrative import (
            generate_dossier_narrative,
        )

        narrative = generate_dossier_narrative(entity_id)
        embed = discord.Embed(
            title=f"Dossier: {entity_id[:20]}",
            description=narrative[:4000],
            color=0xFF6600,
        )
        embed.set_footer(text="Witness — AI-generated from on-chain evidence")
        await interaction.followup.send(embed=embed)

    # ---- /watch ----

    @tree.command(
        name="watch",
        description="Set a standing intelligence watch",
    )
    @app_commands.describe(
        watch_type=(
            "Type: entity_movement, gate_traffic_spike, killmail_proximity, hostile_sighting"
        ),
        target_id="Entity/gate/system ID to watch",
        webhook_url=("Discord webhook URL for alerts (optional, uses channel if not set)"),
    )
    async def watch_cmd(
        interaction: discord.Interaction,
        watch_type: str,
        target_id: str,
        webhook_url: str = "",
    ) -> None:
        valid_types = {
            "entity_movement",
            "gate_traffic_spike",
            "killmail_proximity",
            "hostile_sighting",
        }
        if watch_type not in valid_types:
            await interaction.response.send_message(
                f"Invalid type. Choose from: {', '.join(sorted(valid_types))}",
                ephemeral=True,
            )
            return

        db = get_db()
        db.execute(
            """INSERT INTO watches
               (user_id, watch_type, target_id,
                conditions, webhook_url, channel_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(interaction.user.id),
                watch_type,
                target_id,
                json.dumps({"lookback_seconds": 300}),
                webhook_url,
                str(interaction.channel_id),
            ),
        )
        db.commit()

        await interaction.response.send_message(
            f"Watch set: **{watch_type}** on"
            f" `{target_id[:20]}`\n"
            f"You'll be alerted when conditions trigger.",
            ephemeral=True,
        )

    # ---- /unwatch ----

    @tree.command(
        name="unwatch",
        description="Remove a standing watch",
    )
    @app_commands.describe(target_id="Entity ID to stop watching")
    async def unwatch_cmd(interaction: discord.Interaction, target_id: str) -> None:
        db = get_db()
        db.execute(
            "UPDATE watches SET active = 0 WHERE user_id = ? AND target_id = ? AND active = 1",
            (str(interaction.user.id), target_id),
        )
        db.commit()
        await interaction.response.send_message(
            f"Watch removed for `{target_id[:20]}`",
            ephemeral=True,
        )

    # ---- /profile ----

    @tree.command(
        name="profile",
        description="Full behavioral fingerprint for any entity",
    )
    @app_commands.describe(entity_id="Character or gate ID to profile")
    async def profile_cmd(interaction: discord.Interaction, entity_id: str) -> None:
        await interaction.response.defer()
        db = get_db()
        fp = build_fingerprint(db, entity_id)
        if not fp:
            await interaction.followup.send(
                f"Entity `{entity_id[:20]}` not found.",
                ephemeral=True,
            )
            return

        color = (
            0xFF0000
            if fp.threat.threat_level in ("extreme", "high")
            else 0xFFCC00
            if fp.threat.threat_level == "moderate"
            else 0x00FF88
        )
        embed = discord.Embed(
            title=f"Behavioral Profile: {entity_id[:20]}",
            description=(
                f"**OPSEC: {fp.opsec_score}/100**"
                f" ({fp.opsec_rating})\n"
                f"**Threat: {fp.threat.threat_level.upper()}**"
                f" (K/D ratio: {fp.threat.kill_ratio:.2f})"
            ),
            color=color,
        )
        t = fp.temporal
        embed.add_field(
            name="Activity Pattern",
            value=(
                f"Peak: **{t.peak_hour:02d}:00 UTC**"
                f" ({t.peak_hour_pct:.0f}% of activity)\n"
                f"Active hours: {t.active_hours}/24\n"
                f"Predictability:"
                f" {t.to_dict()['predictability']}"
            ),
            inline=False,
        )
        r = fp.route
        embed.add_field(
            name="Movement",
            value=(
                f"Unique gates: **{r.unique_gates}**"
                f" | Systems: **{r.unique_systems}**\n"
                f"Top gate: {r.top_gate[:16]}"
                f" ({r.top_gate_pct:.0f}%)\n"
                f"Route predictability:"
                f" {r.to_dict()['predictability']}"
            ),
            inline=False,
        )
        if fp.entity_type == "character" and fp.social.unique_associates > 0:
            s = fp.social
            embed.add_field(
                name="Social",
                value=(
                    f"Known associates:"
                    f" **{s.unique_associates}**\n"
                    f"Top associate: {s.top_associate[:16]}"
                    f" ({s.top_associate_count} co-transits)\n"
                    f"Solo ratio: {s.solo_ratio:.0f}%"
                ),
                inline=False,
            )
        embed.set_footer(text="Witness — Behavioral Intelligence")
        await interaction.followup.send(embed=embed)

    # ---- /opsec ----

    @tree.command(
        name="opsec",
        description="Check operational security score",
    )
    @app_commands.describe(entity_id="Character, corp, or gate ID")
    async def opsec_cmd(interaction: discord.Interaction, entity_id: str) -> None:
        await interaction.response.defer()
        db = get_db()
        fp = build_fingerprint(db, entity_id)
        if not fp:
            await interaction.followup.send(
                f"Entity `{entity_id[:20]}` not found.",
                ephemeral=True,
            )
            return

        if fp.event_count < 20:
            await interaction.followup.send(
                f"Not enough data for OPSEC score. Need at least 20 events, have {fp.event_count}."
            )
            return

        color = 0x00FF88 if fp.opsec_score >= 60 else 0xFFCC00 if fp.opsec_score >= 40 else 0xFF0000
        embed = discord.Embed(
            title=f"OPSEC Score: {entity_id[:16]}",
            description=(f"**{fp.opsec_score}/100** — {fp.opsec_rating}"),
            color=color,
        )
        t = fp.temporal
        embed.add_field(
            name="Time Predictability",
            value=(f"{t.peak_hour_pct:.0f}% in peak hour ({t.peak_hour:02d}:00 UTC)"),
            inline=False,
        )
        r = fp.route
        embed.add_field(
            name="Route Predictability",
            value=f"{r.top_gate_pct:.0f}% through top gate",
            inline=False,
        )
        embed.add_field(
            name="Gate Diversity",
            value=f"{r.unique_gates} unique gates used",
            inline=False,
        )
        embed.set_footer(text="Witness Oracle — Counter-Intelligence Analysis")
        await interaction.followup.send(embed=embed)

    # ---- Autocomplete bindings ----

    locate_cmd.autocomplete("entity_id")(autocomplete_fn)
    history_cmd.autocomplete("entity_id")(autocomplete_fn)
    profile_cmd.autocomplete("entity_id")(autocomplete_fn)
    opsec_cmd.autocomplete("entity_id")(autocomplete_fn)
    compare_cmd.autocomplete("entity_1")(autocomplete_fn)
    compare_cmd.autocomplete("entity_2")(autocomplete_fn)
