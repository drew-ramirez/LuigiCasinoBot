import asyncio
import os

import discord
from discord.ext import commands

#was gonna use this for dev overrides but idk now
TOKEN = os.environ['DISCORD_TOKEN']
DEV_GUILD = int(os.environ.get('DEV_GUILD_ID', '0')) or None

intents = discord.Intents.none()
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    try:
        if DEV_GUILD:
            guild = discord.Object(id=DEV_GUILD)
            await bot.tree.sync(guild=guild)
            print(f'Synced commands in guild {DEV_GUILD}')
        else:
            await bot.tree.sync()
            print('Synced global commands')
    finally:
        await bot.close()


async def main():
    async with bot:
        await bot.start(TOKEN)

asyncio.run(main())

