###########################################################
# File: bot.py
#
# Description: Discord bot entry setup and cog loader
###########################################################

import os
import asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands

# load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CASINO_CHANNEL_ID = int(os.getenv("CASINO_CHANNEL_ID", "1424904415160045589"))

# intents (enable content for debugging)
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def casino_channel_only(interaction: discord.Interaction):
    if not CASINO_CHANNEL_ID:
        return True

    channel_id = interaction.channel_id
    parent_id = getattr(interaction.channel, "parent_id", None)
    if channel_id != CASINO_CHANNEL_ID and parent_id != CASINO_CHANNEL_ID:
        target = (
            interaction.guild.get_channel(CASINO_CHANNEL_ID)
            if interaction.guild
            else None
        )
        channel_mention = target.mention if target else f"<#{CASINO_CHANNEL_ID}>"
        raise app_commands.CheckFailure(
            f"Sorry we're isolated testing in {channel_mention} only :)"
        )
    return True


bot.tree.interaction_check = casino_channel_only


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: Exception
):
    if isinstance(error, app_commands.CheckFailure) and CASINO_CHANNEL_ID:
        target = (
            interaction.guild.get_channel(CASINO_CHANNEL_ID)
            if interaction.guild
            else None
        )
        channel_mention = target.mention if target else f"<#{CASINO_CHANNEL_ID}>"
        message = f"Sorry we're isolated testing in {channel_mention} only :)."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
        return
    raise error

###########################################################
# EVENTS
###########################################################

@bot.event
async def on_ready():
    # sync commands once the bot is ready (has application_id)
    synced = await bot.tree.sync()
    print(f"{bot.user} is online. Synced {len(synced)} command(s).")

###########################################################
# COG LOADER
###########################################################

COGS = [
    "cogs.user_cog",
    "cogs.admin_cog",
    "cogs.test_cog",
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

