###########################################################
# File: bot.py
#
# Description: Discord bot entry setup and cog loader
###########################################################

import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

from metrics.metrics_manager import MetricsRollups
from config import CasinoConfigManager
from config.settings import fallback_allowed_channels

# load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

FALLBACK_ALLOWED_CHANNELS = fallback_allowed_channels()

# intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


###########################################################
# Channel Extraction Helper
###########################################################
def _extract_parent_ids(interaction: discord.Interaction) -> set[int]:
    ids: set[int | None] = set()
    channel = getattr(interaction, "channel", None)
    ids.add(getattr(channel, "id", None))
    ids.add(getattr(channel, "parent_id", None))
    parent = getattr(channel, "parent", None)
    if parent is not None:
        ids.add(getattr(parent, "id", None))
        grand_parent = getattr(parent, "parent", None)
        if grand_parent is not None:
            ids.add(getattr(grand_parent, "id", None))
    ids.add(getattr(interaction, "channel_id", None))
    ids.discard(None)
    return ids


###########################################################
# Global Interaction Check
###########################################################
async def casino_channel_only(interaction: discord.Interaction) -> bool:
    guild = interaction.guild
    if guild is None:
        return True

    related_ids = _extract_parent_ids(interaction)

    decision = CasinoConfigManager.resolve_visibility(
        guild_id=guild.id,
        channel_id=interaction.channel_id,
        command_key=None,
        fallback_channels=FALLBACK_ALLOWED_CHANNELS,
    )

    if decision.config.all_public_channels:
        if decision.config.all_public_channels.intersection(related_ids):
            return True
        # allow execution but leave messaging to command logic
        return True

    # legacy fallback: if no config stored but env channels provided
    if FALLBACK_ALLOWED_CHANNELS:
        if FALLBACK_ALLOWED_CHANNELS.intersection(related_ids):
            return True

        # otherwise build mention text for allowed channels
        allowed_mentions = []
        for cid in FALLBACK_ALLOWED_CHANNELS:
            ch = guild.get_channel(cid)
            mention = ch.mention if ch else f"<#{cid}>"
            allowed_mentions.append(mention)
        channel_mention = ", ".join(allowed_mentions)
        
        # respond immediately to avoid expiration
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"Sorry, we're isolated testing in {channel_mention} only :).",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"Sorry, we're isolated testing in {channel_mention} only :).",
                    ephemeral=True,
                )
        except Exception as e:
            print(f"[WARN] Failed to send isolation message: {e}")
        return False

    return True


# register the global check
bot.tree.interaction_check = casino_channel_only


###########################################################
# Error Handling
###########################################################
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    # CheckFailure from global channel check is expected, ignore it silently
    if isinstance(error, app_commands.CheckFailure):
        return
    print(f"[ERROR] Unhandled command error: {error}")


###########################################################
# EVENTS
###########################################################
@bot.event
async def on_ready():
    synced = await bot.tree.sync()
    print(f"{bot.user} is online. Synced {len(synced)} command(s).")


###########################################################
# COG LOADER
###########################################################
COGS = [
    "cogs.user_cog",
    #"cogs.admin_cog",
    #"cogs.test_cog",
    "cogs.casino_config_cog",
    "cogs.memorymatch_cog",
    "cogs.pairagone_cog",
    "cogs.luckystars_cog",
    "cogs.picturepoker_cog",
    "cogs.casino_machines_cog",
]


async def setup_bot():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
        except Exception as e:
            print(f"Failed to load {cog}: {e}")

    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment variables")

    async def rollup_worker():
        await bot.wait_until_ready()
        while not bot.is_closed():
            try:
                now = datetime.now(timezone.utc)
                MetricsRollups.record_economy_snapshot(as_of=now)
                MetricsRollups.record_guild_snapshot(as_of=now)
                MetricsRollups.record_user_guild_affinity(as_of=now)
            except Exception as exc:
                print(f"[WARN] Rollup worker failed: {exc}")
            await asyncio.sleep(24 * 60 * 60)

    asyncio.create_task(rollup_worker())

    await bot.start(TOKEN)


###########################################################
# ENTRYPOINT
###########################################################
if __name__ == "__main__":
    try:
        asyncio.run(setup_bot())
    except KeyboardInterrupt:
        print("\nLuigiCasinoBot shutting down")
