###########################################################
# File: poker_cog.py
#
# Description: Draw Poker slash command wiring.
###########################################################

from typing import Any, Callable, Optional

import discord
from discord.ext import commands

from cogs.base_game_cog import BaseGameCog
from casinogames.poker.Poker import Poker
from casinogames.poker.PokerUI import PokerView, make_cleanup_renderer
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


class PokerCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Poker", log_label="Poker")

    @staticmethod
    def _poker_timeout_metadata(game: Poker) -> dict[str, Any]:
        return {
            "player_rank": getattr(game, "player_rank", None),
            "dealer_rank": getattr(game, "dealer_rank", None),
        }

    @staticmethod
    def _make_cleanup_renderer(view: PokerView) -> Callable[[str, Optional[discord.Colour]], dict[str, Any]]:
        return make_cleanup_renderer(view)

    @commands.Cog.listener()
    async def on_ready(self):
        print("PokerCog loaded.")

    @discord.app_commands.command(
        name="casino_poker",
        description="Play 5-card draw Poker in Luigi's Casino",
    )
    async def poker_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino_poker")
        visibility = self.resolve_visibility(interaction)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: Poker | None = None,
        ):
            game = new_game or Poker(bet_amount)
            self.log_game_start(
                inter,
                "casino_poker",
                bet_amount=bet_amount,
                game=game,
            )

            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )
            use_embed = not animations_on

            multiplier = EconomyManager.star_bonus_multiplier(
                getattr(game, "stars", 0),
                Poker.GAME_KEY,
            )
            stats = {
                "active_bet": game.bet,
                "stars_current": getattr(game, "stars", 0),
                "dealer_action": f"Select cards to discard, then Stand. (⭐ bonus x{multiplier:.2f})",
            }

            view = PokerView(
                game,
                inter.user,
                self.cleanup_game,
                start_game_callback=start_game,
                use_embed=use_embed,
            )

            if animations_on:
                header_text = make_gif_game_header(
                    inter.user,
                    "Poker",
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
                timeout_metadata=self._poker_timeout_metadata,
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
    await bot.add_cog(PokerCog(bot))
