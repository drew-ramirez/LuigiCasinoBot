import asyncio
from casinogames.card_scene import waiting_animation
###########################################################
# File: luckystars_cog.py
#
# Description: Cog for Luigi's Casino - Lucky Stars Game
###########################################################

from typing import Any, Callable, Optional

import discord
from discord.ext import commands

from cogs.base_game_cog import BaseGameCog
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import make_lucky_controls
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


class LuckyStarsCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Lucky Stars", log_label="LuckyStars")

    @staticmethod
    def _luckystars_timeout_metadata(game: LuckyStars) -> dict[str, Any]:
        left_card = getattr(game, "left_card", None)
        right_card = getattr(game, "right_card", None)
        picked = getattr(game, "picked", None)
        if picked == 0:
            player_card = left_card
            dealer_card = right_card
        elif picked == 1:
            player_card = right_card
            dealer_card = left_card
        else:
            player_card = None
            dealer_card = None

        return {
            "player_card": player_card,
            "dealer_card": dealer_card,
            "round": getattr(game, "round", None),
        }

    @staticmethod
    def _make_cleanup_renderer(view) -> Callable[[str, Optional[discord.Colour]], dict[str, Any]]:
        def renderer(status: str, colour: Optional[discord.Colour] = None) -> dict[str, Any]:
            if getattr(view, "animations_enabled", False):
                return {
                    "content": view._header_text(status),
                    "embed": None,
                    "attachments": [view._board_file(reveal=True)],
                }
            embed, files = view._embed_payload(status, reveal=True)
            if colour is not None:
                embed.colour = colour
            return {
                "content": None,
                "embed": embed,
                "attachments": files,
            }

        return renderer

    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # /casino_luckystars
    ###########################################################
    @discord.app_commands.command(name="casino_luckystars", description="Start a Lucky Stars game for Luigi's Casino")
    async def lucky_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino_luckystars")
        visibility = self.resolve_visibility(interaction)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: LuckyStars | None = None,
        ):
            if new_game is None:
                EconomyManager.reset_star_bonus(
                    user_id,
                    LuckyStars.GAME_KEY,
                    inter.user.name,
                )
                game = LuckyStars(
                    bet_amount,
                    initial_stars=0,
                )
            else:
                game = new_game
            if game.left_card is None or game.right_card is None:
                game.deal_round()
            self.log_game_start(
                inter,
                "casino_luckystars",
                bet_amount=bet_amount,
                game=game,
            )

            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )

            board_bytes = render_lucky_board(game, reveal=False)
            board_bytes.seek(0)
            if animations_on:
                board_bytes = await asyncio.to_thread(waiting_animation, game, board_bytes)
            board_file = discord.File(board_bytes, filename="lucky.gif" if animations_on else "lucky.png")

            multiplier = EconomyManager.star_bonus_multiplier(
                game.stars, LuckyStars.GAME_KEY
            )
            stats = {
                "active_bet": game.bet,
                "stars_current": game.stars,
                "dealer_action": f"Pick a card! | (⭐ bonus x{multiplier:.2f})",
            }

            view = make_lucky_controls(
                game,
                inter.user,
                self.cleanup_game,
                animations_enabled=animations_on,
                start_game_callback=start_game,
            )

            if animations_on:
                header_text = make_gif_game_header(
                    inter.user, "Lucky Stars", stats
                )
                await inter.response.edit_message(
                    content=header_text,
                    embed=None,
                    attachments=[board_file],
                    view=view,
                )
            else:
                header_embed = make_game_header(inter.user, "Lucky Stars", stats)
                header_embed.set_image(url="attachment://lucky.png")
                await inter.response.edit_message(
                    content=None,
                    embed=header_embed,
                    attachments=[board_file],
                    view=view,
                )

            message = inter.message
            if message is None:
                try:
                    message = await inter.original_response()
                except Exception:
                    message = None
            if message is not None:
                view.msg = message

            await self.register_active_game(
                user_id,
                game=game,
                message=message,
                view=view,
                timeout_metadata=self._luckystars_timeout_metadata,
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


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(LuckyStarsCog(bot))
