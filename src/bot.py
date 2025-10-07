###########################################################
# File: bot.py
#
# Description: Discord bot entry setup and cog loader
###########################################################

import os
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands

# load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

_channels_env = os.getenv("CASINO_CHANNEL_IDS")
if _channels_env:
    ALLOWED_CHANNEL_IDS = {
        int(v.strip()) for v in _channels_env.split(",") if v.strip().isdigit()
    }
else:
    single_channel = os.getenv("CASINO_CHANNEL_ID", "1424904415160045589")
    try:
        ALLOWED_CHANNEL_IDS = {int(single_channel)}
    except ValueError:
        ALLOWED_CHANNEL_IDS = set()

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
# Global Interaction Check (safe + synchronous)
###########################################################
async def casino_channel_only(interaction: discord.Interaction) -> bool:
    # allow all if unrestricted
    if not ALLOWED_CHANNEL_IDS:
        return True

    related_ids = _extract_parent_ids(interaction)

    # allow ephemeral
    if not related_ids or interaction.guild is None:
        return True

    # allow if current or parent channel is permitted
    if ALLOWED_CHANNEL_IDS.intersection(related_ids):
        return True

    # otherwise build mention text for allowed channels
    allowed_mentions = []
    for cid in ALLOWED_CHANNEL_IDS:
        ch = interaction.guild.get_channel(cid)
        mention = ch.mention if ch else f"<#{cid}>"
        allowed_mentions.append(mention)
    channel_mention = ", ".join(allowed_mentions)

    try:
        # respond immediately to avoid expiration
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

    # returning False stops the command from executing
    return False


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
    # "cogs.admin_cog",
    # "cogs.test_cog",
    "cogs.memorymatch_cog",
    "cogs.pairagone_cog",
    "cogs.luckystars_cog",
    "cogs.picturepoker_cog",
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

    await bot.start(TOKEN)


###########################################################
# ENTRYPOINT
###########################################################
if __name__ == "__main__":
    try:
        asyncio.run(setup_bot())
    except KeyboardInterrupt:
        print("\nLuigiCasinoBot shutting down")
