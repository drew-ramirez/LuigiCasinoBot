###########################################################
# File: picturepoker_cog.py
#
# Description: Cog for Luigi's Casino - Picture Poker Game
###########################################################

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

    @commands.Cog.listener()
    async def on_ready(self):
        print("PicturePokerCog loaded.")

    ###########################################################
    # /casino_picturepoker
    ###########################################################
    @discord.app_commands.command(
        name="casino_picturepoker", description="Start a Picture Poker game"
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
            entry = self.active_games.get(user_id) or {}
            existing_game = entry.get("game") if isinstance(entry, dict) else None
            target_game = new_game or existing_game or PicturePoker()
            target_game.start_round(forced_bet=bet_amount)
            self.log_game_start(
                inter,
                "casino_picturepoker",
                bet_amount=bet_amount,
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

            stats = {
                "active_bet": target_game.bet,
                "stars_current": target_game.stars,
                "round": target_game.round,
                "multiplier": 1.0,
                "dealer_action": "New game started! \nSelect cards to discard then submit.",
            }

            view = make_poker_view(
                target_game,
                user_id,
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

            self.register_active_game(user_id, game=target_game, message=message)

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
