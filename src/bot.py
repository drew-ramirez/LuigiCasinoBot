import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()
# Read token
TOKEN = os.getenv("DISCORD_TOKEN")

# Creates bot with slash command support
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} is now running!")

def run_bot():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment variables")
    bot.run(TOKEN)
