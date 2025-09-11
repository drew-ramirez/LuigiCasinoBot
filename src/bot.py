###########################################################
# File: bot.py

# Description: Discord bot entry setup and command routing
#
###########################################################

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Intents
intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

###########################################################
# Events
###########################################################

@bot.event
async def on_ready():
    # Sync commands
    synced = await bot.tree.sync()
    print(f"{bot.user} is online. Synced {len(synced)} command(s).")

###########################################################
# Commands
###########################################################

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    """Basic connectivity check."""
    await interaction.response.send_message("Pong!", ephemeral=True)


@bot.tree.command(name="help", description="Show available commands")
async def help_cmd(interaction: discord.Interaction):
    msg = (
        "``` **LuigiCasinoBot Commands** \n\n"
        "/ping - Health check\n"
        "/help - Show this menu\n"
        "/rules - Show the casino rules\n"
        "/slot_pull - Spin the slot machine \n"
        "/pair_start - Start a Pair-a-Gone game \n"
        "/balance - Check your coin balance\n"
        "/grant <amount> - Add coins (admin/dev only)\n ```"
    )
    # Note: only the user who ran the command sees the message when its Ephmeral
    await interaction.response.send_message(msg, ephemeral=True)

###########################################################
# Run Bot
###########################################################

def run_bot():
    # Entrypoint for main.py
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment variables")
    bot.run(TOKEN)
