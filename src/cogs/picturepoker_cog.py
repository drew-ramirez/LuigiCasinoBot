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
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
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
        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: PicturePoker | None = None,
        ):
            nonlocal game

            target_game = new_game or game
            target_game.start_round(forced_bet=bet_amount)

            img_bytes = render_board(target_game, reveal=False)
            if hasattr(img_bytes, "seek"):
                try:
                    img_bytes.seek(0)
                except Exception:
                    pass
            file = discord.File(img_bytes, filename="poker.png")

            stats = {
                "active_bet": target_game.bet,
                "stars_current": target_game.stars,
                "round": target_game.round,
                "multiplier": 1.0,
                "dealer_action": "New game started! \nSelect cards to discard then submit.",
            }

            content = make_game_header(
                inter.user,
                "Picture Poker",
                stats,
            )

            view = make_poker_view(
                target_game,
                user_id,
                self.cleanup_game,
                wager_options=DEFAULT_WAGER_OPTIONS,
                start_game_callback=start_game,
            )

            await inter.response.edit_message(
                content=content,
                attachments=[file],
                view=view,
            )

            message = inter.message
            if message is None:
                try:
                    message = await inter.original_response()
                except Exception:
                    message = None
            self.active_games[user_id] = {
                "game": target_game,
                "message": message,
            }
            game = target_game

        balance = EconomyManager.balance(user_id, username)

        view = BetSelectView(
            user_id,
            username,
            lambda inter, amount: start_game(inter, amount),
            wager_options=DEFAULT_WAGER_OPTIONS,
        )

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
