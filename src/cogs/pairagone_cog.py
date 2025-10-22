###########################################################
# File: pairagone_cog.py
#
# Description: Pair-a-Gone command and entry point
###########################################################

from typing import Any

import discord
from discord.ext import commands
from cogs.base_game_cog import BaseGameCog
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import render_pair_board
from casinogames.pairagone.PairAGoneUI import make_pair_view
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


class PairAGoneCog(BaseGameCog):
    # Cog for handling the Pair-a-Gone game

    def __init__(self, bot):
        super().__init__(bot, "Pair-a-Gone", log_label="PairAGone")

    @staticmethod
    def _pairagone_timeout_metadata(game: PairAGone) -> dict[str, Any]:
        remaining = None
        if hasattr(game, "remaining_in_deck"):
            try:
                remaining = game.remaining_in_deck()
            except Exception:
                remaining = None
        return {
            "remaining_deck": remaining,
            "session_stars": getattr(
                game,
                "session_stars",
                getattr(game, "stars", None),
            ),
        }

    @commands.Cog.listener()
    async def on_ready(self):
        print("PairAGoneCog loaded.")

    ###########################################################
    # /casino_pairagone
    ###########################################################
    @discord.app_commands.command(name="casino_pairagone", description="Start a Pair-a-Gone game for Luigi's Casino")
    async def pair_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino_pairagone")
        visibility = self.resolve_visibility(interaction)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: PairAGone | None = None,
        ):
            if new_game is None:
                initial_stars = EconomyManager.star_bonus_count(
                    user_id,
                    PairAGone.GAME_KEY,
                    inter.user.name,
                )
                game = PairAGone(
                    user_id,
                    bet_amount,
                    initial_stars=initial_stars,
                )
            else:
                game = new_game
            self.log_game_start(
                inter,
                "casino_pairagone",
                bet_amount=bet_amount,
                game=game,
            )
            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )

            board_bytes = render_pair_board(game)
            board_bytes.seek(0)
            board_file = discord.File(board_bytes, filename="pair_board.png")

            multiplier = EconomyManager.star_bonus_multiplier(
                getattr(game, "session_stars", game.stars),
                PairAGone.GAME_KEY,
            )
            stats = {
                "active_bet": game.bet,
                "stars_current": getattr(game, "session_stars", game.stars),
                "dealer_action": f"Select two adjacent matching cards! | (⭐ bonus x{multiplier:.2f})",
            }

            view = make_pair_view(
                game,
                inter.user,
                self.cleanup_game,
                animations_enabled=animations_on,
                start_game_callback=start_game,
            )

            if animations_on:
                header_text = make_gif_game_header(
                    inter.user,
                    "Pair-a-Gone",
                    stats,
                )
                await inter.response.edit_message(
                    content=header_text,
                    embed=None,
                    attachments=[board_file],
                    view=view,
                )
            else:
                header_embed = make_game_header(inter.user, "Pair-a-Gone", stats)
                header_embed.set_image(
                    url=f"attachment://{board_file.filename}"
                )
                await inter.response.edit_message(
                    content=None,
                    embed=header_embed,
                    attachments=[board_file],
                    view=view,
                )

            message = await inter.original_response()
            if message is not None:
                view.msg = message

            await self.register_active_game(
                user_id,
                game=game,
                message=message,
                view=view,
                timeout_metadata=self._pairagone_timeout_metadata,
            )

        layout_mode = (
            "gif"
            if EconomyManager.animations_enabled(user_id, player.name)
            else "embed"
        )

        await self.present_wager_menu(
            interaction,
            on_bet_selected=start_game,
            visibility=visibility,
            layout=layout_mode,
        )


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(PairAGoneCog(bot))
