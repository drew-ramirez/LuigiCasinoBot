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

        img_bytes = render_board(game, reveal=False)
        file = discord.File(img_bytes, filename="poker.png")

        await interaction.response.send_message(
            content=f"Picture Poker started! Coins: {game.coins}, Stars: {game.stars}\nSelect cards to discard then submit.",
            file=file,
        )
        msg = await interaction.original_response()

        # persistent view with callback
        view = make_poker_view(game, user_id, self.cleanup_game)
        await msg.edit(view=view)
        self.active_games[user_id] = {"game": game, "message": msg}

    ###########################################################
    # Cleanup
    ###########################################################
    async def cleanup_game(self, user_id: int):
        """Removes finished games from memory."""
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[PicturePoker] Cleaned up game for {user_id}")


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(PicturePokerCog(bot))
