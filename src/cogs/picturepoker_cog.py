###########################################################
# File: picturepoker_cog.py
#
# Description: Cog for Luigi’s Casino - Picture Poker Game
###########################################################

import discord
from discord.ext import commands
import asyncio
from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import render_board
from casinogames.picturepoker.PicturePokerUI import make_poker_view
from utils.ui_embeds import make_game_header


class PicturePokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("PicturePokerCog loaded.")

    ###########################################################
    # Slash command: start game
    ###########################################################
    @discord.app_commands.command(name="poker_start", description="Start a Picture Poker game")
    async def poker_start(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        game = PicturePoker()
        game.start_round()

        ###########################################################
        # Acknowledge immediately to avoid timeout
        ###########################################################
        await interaction.response.defer(thinking=False)

        ###########################################################
        # Prepare starting content and image
        ###########################################################
        img_bytes = render_board(game, reveal=False)
        file = discord.File(img_bytes, filename="poker.png")

        content = make_game_header(
            interaction.user,
            "Picture Poker",
            active_bet=game.bet,
            stars_current=game.stars,
            multiplier=1.0,
        ) + "\nNew game started! Select cards to discard then submit."

        ###########################################################
        # Send the game board and buttons together
        ###########################################################
        msg = await interaction.followup.send(
            content=content,
            file=file,
            view=make_poker_view(game, user_id, self.cleanup_game),
            wait=True,
        )

        ###########################################################
        # Store active session
        ###########################################################
        self.active_games[user_id] = {
            "game": game,
            "message": msg
        }

    ###########################################################
    # Cleanup
    ###########################################################
    async def cleanup_game(self, user_id: int):
        #removes finished games from memory.
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[PicturePoker] Cleaned up game for {user_id}")


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(PicturePokerCog(bot))
