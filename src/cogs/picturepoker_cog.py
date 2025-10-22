###########################################################
# File: picturepoker_cog.py
#
# Description: Cog for Luigi's Casino - Picture Poker Game
###########################################################

from typing import Any, Callable

import discord
from discord.ext import commands

from cogs.base_game_cog import BaseGameCog
from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import render_board
from casinogames.picturepoker.PicturePokerUI import make_poker_view
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


class PicturePokerCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Picture Poker", log_label="PicturePoker")

    @staticmethod
    def _picturepoker_timeout_metadata(game: PicturePoker) -> dict[str, Any]:
        player_rank = None
        dealer_rank = None
        try:
            player_hand = getattr(game, "player_hand", None)
            if player_hand:
                _, player_rank = game.evaluate_hand(player_hand)
        except Exception:
            player_rank = None

        try:
            dealer_hand = getattr(game, "luigi_hand", None)
            if dealer_hand:
                _, dealer_rank = game.evaluate_hand(dealer_hand)
        except Exception:
            dealer_rank = None

        return {
            "player_rank": player_rank,
            "dealer_rank": dealer_rank,
            "round": getattr(game, "round", None),
        }

    @staticmethod
    def _make_cleanup_renderer(view) -> Callable[[str], dict[str, Any]]:
        def renderer(status: str) -> dict[str, Any]:
            stats = {
                "active_bet": view.game.bet,
                "stars_current": getattr(view.game, "stars", 0),
                "dealer_action": status,
            }
            board_bytes = render_board(view.game, reveal=True)
            if hasattr(board_bytes, "seek"):
                try:
                    board_bytes.seek(0)
                except Exception:
                    pass
            board_file = discord.File(board_bytes, "poker.png")
            content, embed = view._header_payload(
                view.player,
                stats,
                attachment_filename=board_file.filename,
            )
            return {
                "content": content,
                "embed": embed,
                "attachments": [board_file],
            }

        return renderer

    @commands.Cog.listener()
    async def on_ready(self):
        print("PicturePokerCog loaded.")

    ###########################################################
    # /casino_picturepoker
    ###########################################################
    @discord.app_commands.command(
        name="casino_picturepoker", description="Start a Picture Poker game for Luigi's Casino"
    )
    async def poker_start(self, interaction: discord.Interaction):

        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino_picturepoker")
        visibility = self.resolve_visibility(interaction)

        ###########################################################
        # Callback: when a bet is selected
        ###########################################################
        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: PicturePoker | None = None,
        ):
            if new_game is None:
                EconomyManager.reset_star_bonus(
                    user_id,
                    PicturePoker.GAME_KEY,
                    inter.user.name,
                )
                target_game = PicturePoker()
            else:
                target_game = new_game
            target_game.start_round(forced_bet=bet_amount)
            self.log_game_start(
                inter,
                "casino_picturepoker",
                bet_amount=bet_amount,
                game=target_game,
            )
            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )

            board_bytes = render_board(target_game, reveal=False)
            if hasattr(board_bytes, "seek"):
                try:
                    board_bytes.seek(0)
                except Exception:
                    pass
            board_file = discord.File(board_bytes, filename="poker.png")

            multiplier = EconomyManager.star_bonus_multiplier(
                target_game.stars, PicturePoker.GAME_KEY
            )
            stats = {
                "active_bet": target_game.bet,
                "stars_current": target_game.stars,
                "round": target_game.round,
                "multiplier": multiplier,
                "dealer_action": (
                    "New game started! \n Select cards to discard then submit.\n"
                    f" (⭐ bonus x{multiplier:.2f})"
                ),
            }

            view = make_poker_view(
                target_game,
                inter.user,
                self.cleanup_game,
                animations_enabled=animations_on,
                start_game_callback=start_game,
            )

            if animations_on:
                header_text = make_gif_game_header(
                    inter.user,
                    "Picture Poker",
                    stats,
                )
                await inter.response.edit_message(
                    content=header_text,
                    embed=None,
                    attachments=[board_file],
                    view=view,
                )
            else:
                header_embed = make_game_header(
                    inter.user,
                    "Picture Poker",
                    stats,
                )
                header_embed.set_image(url=f"attachment://{board_file.filename}")
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
                inter.user.id,
                game=target_game,
                message=message,
                view=view,
                timeout_metadata=self._picturepoker_timeout_metadata,
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
    await bot.add_cog(PicturePokerCog(bot))
