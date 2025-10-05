###########################################################
# File: pairagone_cog.py
#
# Description: Pair-a-Gone command and entry point
###########################################################

import discord
from discord.ext import commands
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import render_pair_board
from casinogames.pairagone.PairAGoneUI import PairControls


class PairAGoneCog(commands.Cog):
    #Cog for handling the Pair-a-Gone game

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("PairAGoneCog loaded.")

###########################################################
# /pair_start
###########################################################
    @discord.app_commands.command(name="pair_start", description="Start a Pair-a-Gone game")
    async def pair_start(self, interaction: discord.Interaction):
        game = PairAGone(interaction.user.id)

        img_bytes = render_pair_board(game)
        file = discord.File(img_bytes, filename="pair_board.png")

        await interaction.response.send_message(
            content="Pair-a-Gone started!", file=file, ephemeral=True
        )
        msg = await interaction.original_response()

        # create the view
        view = PairControls(game, msg)
        await msg.edit(view=view)


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(PairAGoneCog(bot))
