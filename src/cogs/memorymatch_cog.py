###########################################################
# File: memorymatch_cog.py
#
# Description: Luigi’s Casino Memory Match command logic
###########################################################

import discord
from discord.ext import commands
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image
from casinogames.memorymatch.MemoryMatchUI import MemoryMatchControls


class MemoryMatchCog(commands.Cog):
    #Cog for Memory Match gameplay

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("MemoryMatchCog loaded.")

    @discord.app_commands.command(name="memory_start", description="Start a Memory Match game")
    async def memory_start(self, interaction: discord.Interaction):
        game = MemoryMatch(interaction.user.id)
        img_bytes = render_board_image(game)
        file = discord.File(img_bytes, filename="board.png")

        await interaction.response.send_message(
            content=f"Memory Match started!\nCoins: {game.remaining_coins}",
            file=file,
            ephemeral=True,
        )
        msg = await interaction.original_response()

        view = MemoryMatchControls(game, msg)
        await msg.edit(view=view)


###########################################################
# Cog SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(MemoryMatchCog(bot))
