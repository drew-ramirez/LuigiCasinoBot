###########################################################
# File: pairagone_cog.py
#
# Description: Pair-a-Gone command and entry point
###########################################################

import discord
from discord.ext import commands
from cogs.base_game_cog import BaseGameCog
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import render_pair_board
from casinogames.pairagone.PairAGoneUI import make_pair_view
from utils.ui_embeds import make_game_header


class PairAGoneCog(BaseGameCog):
    # Cog for handling the Pair-a-Gone game

    def __init__(self, bot):
        super().__init__(bot, "Pair-a-Gone", log_label="PairAGone")

    @commands.Cog.listener()
    async def on_ready(self):
        print("PairAGoneCog loaded.")

    ###########################################################
    # /pair_start
    ###########################################################
    @discord.app_commands.command(name="pair_start", description="Start a Pair-a-Gone game")
    async def pair_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

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
                start_game_callback=start_game,
            )

            await inter.response.edit_message(
                content=content,
                attachments=[file],
                view=view,
            )

            message = await inter.original_response()
            view.msg = message

            self.register_active_game(user_id, game=game, message=message)

        await self.present_wager_menu(
            interaction,
            on_bet_selected=start_game,
        )


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(PairAGoneCog(bot))
