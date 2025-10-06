###########################################################
# File: luckystars_cog.py
#
# Description: Cog for Luigi's Casino - Lucky Stars Game
###########################################################

import discord
from discord.ext import commands

from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import make_lucky_controls
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_game_header
from economy.EconomyManager import EconomyManager


class LuckyStarsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games: dict[int, dict[str, object]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # Slash command: start game
    ###########################################################
    @discord.app_commands.command(name="lucky_start", description="Start a Lucky Stars game")
    async def lucky_start(self, interaction: discord.Interaction):
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
            new_game: LuckyStars | None = None,
        ):
            game = new_game or LuckyStars(bet_amount)
            game.deal_round()

            board_bytes = render_lucky_board(game, reveal=False)
            board_bytes.seek(0)
            file = discord.File(board_bytes, filename="lucky.png")

            stats = {
                "active_bet": game.bet,
                "stars_current": 0,
                "dealer_action": "Pick a card!",
            }
            content = make_game_header(inter.user, "Lucky Stars", stats)

            view = make_lucky_controls(
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
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[LuckyStars] Cleaned up game for {user_id}")


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(LuckyStarsCog(bot))
