import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Create bot with slash command support
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # sync commands to Discord
    await bot.tree.sync()
    print(f"{bot.user} is now running.")

def run_bot():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment variables")
    bot.run(TOKEN)

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Why are you pinging me?", ephemeral=True)

