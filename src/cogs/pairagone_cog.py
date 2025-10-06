###########################################################
# File: pairagone_cog.py
#
# Description: Pair-a-Gone command and entry point
###########################################################

import discord
from discord.ext import commands
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import render_pair_board
from casinogames.pairagone.PairAGoneUI import make_pair_view
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_game_header
from economy.EconomyManager import EconomyManager


class PairAGoneCog(commands.Cog):
    # Cog for handling the Pair-a-Gone game

    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("PairAGoneCog loaded.")

    ###########################################################
    # /pair_start
    ###########################################################
    @discord.app_commands.command(name="pair_start", description="Start a Pair-a-Gone game")
    async def pair_start(self, interaction: discord.Interaction):
        responder = (
            interaction.followup.send
            if interaction.response.is_done()
            else interaction.response.send_message
        )

        player = interaction.user
        user_id = player.id
        username = player.name

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: PairAGone | None = None,
        ):
            game = new_game or PairAGone(user_id, bet_amount)

            board_bytes = render_pair_board(game)
            board_bytes.seek(0)
            file = discord.File(board_bytes, filename="pair_board.png")

            stats = {
                "active_bet": game.bet,
                "stars_current": game.stars,
                "dealer_action": "Select two adjacent matching cards!",
            }
            content = make_game_header(inter.user, "Pair-a-Gone", stats)

            view = make_pair_view(
                game,
                inter.user,
                self.cleanup_game,
                wager_options=DEFAULT_WAGER_OPTIONS,
                start_game_callback=start_game,
            )

            await inter.response.edit_message(
                content=content,
                attachments=[file],
                view=view,
            )

            message = await inter.original_response()
            view.msg = message

            self.active_games[user_id] = {
                "game": game,
                "message": message,
            }

        balance = EconomyManager.balance(user_id, username)

        view = BetSelectView(
            user_id,
            username,
            start_game,
            wager_options=DEFAULT_WAGER_OPTIONS,
        )

        await responder(
            content=(
                f"╔═════════════════════════╗\n"
                f"🎰 Luigi’s Casino — Memory Match\n"
                f" ══════════════════════════\n"
                f"💰 Balance: {balance:,} coins\n"
                f" ══════════════════════════\n"
                f"Select your wager amount to begin:\n"
                f"╚═════════════════════════╝\n"
            ),
            view=view,
            ephemeral=True,
        )

    async def cleanup_game(self, user_id: int):
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[PairAGone] Cleaned up game for {user_id}")


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(PairAGoneCog(bot))
