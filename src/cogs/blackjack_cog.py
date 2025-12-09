###########################################################
# File: blackjack_cog.py
#
# Description: Blackjack command wiring.
###########################################################

from typing import Any, Callable, Optional

import discord
from discord.ext import commands

from cogs.base_game_cog import BaseGameCog
from casinogames.blackjack.Blackjack import Blackjack
from casinogames.blackjack.BlackjackUI import BlackjackView, make_blackjack_view, make_cleanup_renderer
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


class BlackjackCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Blackjack", log_label="Blackjack")

    @staticmethod
    def _bj_timeout_metadata(game: Blackjack) -> dict[str, Any]:
        p_total = getattr(game, "player_total_cached", None)
        d_total = getattr(game, "dealer_total_cached", None)
        return {
            "player_total": p_total,
            "dealer_total": d_total,
            "doubled": getattr(game, "doubled", False),
        }

    @staticmethod
    def _make_cleanup_renderer(view: BlackjackView) -> Callable[[str, Optional[discord.Colour]], dict[str, Any]]:
        return make_cleanup_renderer(view)

    @commands.Cog.listener()
    async def on_ready(self):
        print("BlackjackCog loaded.")

    @discord.app_commands.command(
        name="casino_blackjack",
        description="Play traditional Blackjack in Luigi's Casino",
    )
    async def blackjack_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino_blackjack")
        visibility = self.resolve_visibility(interaction)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: Blackjack | None = None,
        ):
            if new_game is None:
                game = Blackjack(bet_amount)
            else:
                game = new_game

            self.log_game_start(
                inter,
                "casino_blackjack",
                bet_amount=bet_amount,
                game=game,
            )

            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )
            use_embed = not animations_on

            multiplier = EconomyManager.star_bonus_multiplier(
                getattr(game, "stars", 0),
                Blackjack.GAME_KEY,
            )
            stats = {
                "active_bet": game.base_bet,
                "stars_current": getattr(game, "stars", 0),
                "dealer_action": f"Hit / Stand / Double | (⭐ bonus x{multiplier:.2f})",
            }

            view = make_blackjack_view(
                game,
                inter.user,
                self.cleanup_game,
                start_game_callback=start_game,
                use_embed=use_embed,
            )

            if animations_on:
                header_text = make_gif_game_header(
                    inter.user,
                    "Blackjack",
                    stats,
                )
                await inter.response.edit_message(
                    content=header_text,
                    embed=None,
                    view=view,
                )
            else:
                payload = view._status_payload(stats["dealer_action"], hide_dealer=True, view=view)
                await inter.response.edit_message(**payload)

            message = inter.message
            if message is None:
                try:
                    message = await inter.original_response()
                except Exception:
                    message = None
            if message is not None:
                view.msg = message

            await self.register_active_game(
                inter.user.id,
                game=game,
                message=message,
                view=view,
                timeout_metadata=self._bj_timeout_metadata,
                cleanup_renderer=self._make_cleanup_renderer(view),
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


async def setup(bot):
    await bot.add_cog(BlackjackCog(bot))
