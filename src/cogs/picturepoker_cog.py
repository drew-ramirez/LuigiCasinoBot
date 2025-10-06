###########################################################
# File: picturepoker_cog.py
#
# Description: Cog for Luigi's Casino - Picture Poker Game
###########################################################

import discord
from discord.ext import commands
import asyncio
from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import render_board
from casinogames.picturepoker.PicturePokerUI import make_poker_view
from utils.bet_selector import BetSelectView
from utils.ui_embeds import make_game_header
from economy.EconomyManager import EconomyManager


class PicturePokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("PicturePokerCog loaded.")

    ###########################################################
    # Start game command
    ###########################################################
    @discord.app_commands.command(
        name="poker_start", description="Start a Picture Poker game"
    )
    async def poker_start(self, interaction: discord.Interaction):

        # needed to stop timeout
        responder = (
            interaction.followup.send
            if interaction.response.is_done()
            else interaction.response.send_message
        )

        user_id = interaction.user.id
        username = interaction.user.name
        game = PicturePoker()

        ###########################################################
        # Callback: when a bet is selected
        ###########################################################
        async def on_bet_selected(inter: discord.Interaction, bet_amount: int):
            # deduct wager and initialize round
            game.bet = bet_amount
            game.start_round()

            # Prepare starting content and image
            img_bytes = render_board(game, reveal=False)
            if hasattr(img_bytes, "seek"):
                try:
                    img_bytes.seek(0)
                except Exception:
                    pass
            file = discord.File(img_bytes, filename="poker.png")

            # JSON-header compatible stats dict
            stats = {
                "active_bet": game.bet,
                "stars_current": game.stars,
                "round": game.round,
                "multiplier": 1.0,
                "dealer_action": "New game started! \nSelect cards to discard then submit.",
            }

            # build top-of-message header
            content = make_game_header(
                inter.user,
                "Picture Poker",
                stats,
            )

            # send the game board and buttons together
            view = make_poker_view(game, user_id, self.cleanup_game)
            await inter.response.edit_message(
                content=content,
                attachments=[file],
                view=view,
            )

            # store active session
            message = inter.message
            if message is None:
                try:
                    message = await inter.original_response()
                except Exception:
                    message = None
            self.active_games[user_id] = {
                "game": game,
                "message": message,
            }
        # user for bet selection
        balance = EconomyManager.balance(user_id, username)

        view = BetSelectView(user_id, username, on_bet_selected, wager_options=[1, 5, 10, 25, 50, 100, 150, 200, 250, 500])

        await responder(
            content=(
                f"╔═════════════════════════╗\n"
                f"🎰 Luigi’s Casino — Picture Poker\n"
                f" ══════════════════════════\n"
                f"💰 Balance: {balance:,} coins\n"
                f" ══════════════════════════\n"
                f"Select your wager amount to begin:\n"
                f"╚═════════════════════════╝\n"
            ),
            view=view,
            ephemeral=True,
        )

    ###########################################################
    # Cleanup
    ###########################################################
    async def cleanup_game(self, user_id: int):
        # removes finished games from memory.
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[PicturePoker] Cleaned up game for {user_id}")


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(PicturePokerCog(bot))
