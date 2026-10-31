import asyncio
from casinogames.card_scene import waiting_animation
###########################################################
# File: memorymatch_cog.py
#
# Description: Luigi's Casino Memory Match command logic
###########################################################

from typing import Any, Callable, Optional

import discord
from discord.ext import commands
from cogs.base_game_cog import BaseGameCog
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image
from casinogames.memorymatch.MemoryMatchUI import make_memory_view
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


class MemoryMatchCog(BaseGameCog):
    # Cog for Memory Match gameplay

    def __init__(self, bot):
        super().__init__(bot, "Memory Match", log_label="MemoryMatch")

    @staticmethod
    def _memorymatch_timeout_metadata(game: MemoryMatch) -> dict[str, Any]:
        return {
            "remaining_attempts": getattr(game, "remaining_attempts", None),
            "session_stars": getattr(
                game,
                "session_stars",
                getattr(game, "stars", None),
            ),
        }

    @staticmethod
    def _make_cleanup_renderer(view) -> Callable[[str, Optional[discord.Colour]], dict[str, Any]]:
        def renderer(status: str, colour: Optional[discord.Colour] = None) -> dict[str, Any]:
            if getattr(view, "animations_enabled", False):
                content = view._status_text(status)
                files = [view._board_file()]
                return {
                    "content": content,
                    "embed": None,
                    "attachments": files,
                }
            embed, files = view._status_payload(status)
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
        print("MemoryMatchCog loaded.")

    ###########################################################
    # /casino_memorymatch
    ###########################################################
    @discord.app_commands.command(
        name="casino_memorymatch", description="Start a Memory Match game for Luigi's Casino"
    )
    async def memory_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino_memorymatch")
        visibility = self.resolve_visibility(interaction)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: MemoryMatch | None = None,
        ):
            if new_game is None:
                EconomyManager.reset_star_bonus(
                    user_id,
                    MemoryMatch.GAME_KEY,
                    inter.user.name,
                )
                game = MemoryMatch(
                    user_id,
                    bet_amount,
                    initial_stars=0,
                )
            else:
                game = new_game
            self.log_game_start(
                inter,
                "casino_memorymatch",
                bet_amount=bet_amount,
                game=game,
            )

            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )

            board_bytes = render_board_image(game)
            board_bytes.seek(0)
            if animations_on:
                board_bytes = await asyncio.to_thread(waiting_animation, game, board_bytes)
            board_file = discord.File(board_bytes, filename="memory_board.gif" if animations_on else "memory_board.png")

            multiplier = EconomyManager.star_bonus_multiplier(
                game.stars, MemoryMatch.GAME_KEY
            )
            stats = {
                "active_bet": game.bet,
                "stars_current": game.stars,
                "dealer_action": f"Attempts left: {game.remaining_attempts} | (⭐ bonus x{multiplier:.2f})",
            }

            view = make_memory_view(
                game,
                inter.user,
                self.cleanup_game,
                animations_enabled=animations_on,
                start_game_callback=start_game,
            )

            if animations_on:
                header_text = make_gif_game_header(
                    inter.user, "Memory Match", stats
                )
                await inter.response.edit_message(
                    content=header_text,
                    embed=None,
                    attachments=[board_file],
                    view=view,
                )
            else:
                header_embed = make_game_header(inter.user, "Memory Match", stats)
                header_embed.set_image(url="attachment://memory_board.png")
                await inter.response.edit_message(
                    content=None,
                    embed=header_embed,
                    attachments=[board_file],
                    view=view,
                )

            message = await inter.original_response()
            view.msg = message

            await self.register_active_game(
                user_id,
                game=game,
                message=message,
                view=view,
                timeout_metadata=self._memorymatch_timeout_metadata,
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
# Cog SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(MemoryMatchCog(bot))
