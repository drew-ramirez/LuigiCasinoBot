###########################################################
# File: luckystars_cog.py
#
# Description: Cog for Luigi’s Casino - Lucky Stars Game
###########################################################

import discord
from discord.ext import commands
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import make_lucky_controls, LuckyStarsView


class LuckyStarsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ###########################################################
    # EVENTS
    ###########################################################
    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # COMMANDS
    ###########################################################
    @discord.app_commands.command(
        name="lucky_start", description="Start a Lucky Stars game"
    )
    async def lucky_start(self, interaction: discord.Interaction):
        game = LuckyStars()
        game.deal_round()

        img_bytes = render_lucky_board(game, reveal=False)
        file = discord.File(img_bytes, filename="lucky.png")


        view = make_lucky_controls(game, interaction.user.id, self.handle_lucky_next)
        await interaction.response.send_message(
            content=f"🎲 Lucky Stars started! You have {game.coins} coins.\nPick a card!",
            file=discord.File(render_lucky_board(game, reveal=False), filename="lucky.png"),
            view=view,
        )


    ###########################################################
    # CALLBACK (next round)
    ###########################################################
    async def handle_lucky_next(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        view: LuckyStarsView = interaction.message.components  # not strictly needed here
        await interaction.response.defer()

        # retrieve game from the view object
        game = interaction.message.view.game
        game.deal_round()

        img = render_lucky_board(game, reveal=False)
        file = discord.File(img, filename="lucky.png")

        # rebuild fresh view
        new_view = LuckyStarsView(game, user_id, self.handle_lucky_next)
        await interaction.message.edit(
            content=f"Pick again! (Coins: {game.coins})",
            attachments=[file],
            view=new_view,
        )


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(LuckyStarsCog(bot))
