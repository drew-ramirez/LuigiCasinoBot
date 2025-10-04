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

# load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# intents (enable content for debugging)
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

###########################################################
# EVENTS
###########################################################

@bot.event
async def on_ready():
    # sync commands once the bot is ready (has application_id)
    synced = await bot.tree.sync()
    print(f"{bot.user} is online. Synced {len(synced)} command(s).")

###########################################################
# ASYNC COG LOADER
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

