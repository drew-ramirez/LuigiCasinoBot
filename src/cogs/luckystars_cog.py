###########################################################
# File: luckystars_cog.py
#
# Description: Cog for Luigi's Casino - Lucky Stars Game
###########################################################

import discord
from discord.ext import commands

from cogs.base_game_cog import BaseGameCog
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import make_lucky_controls
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager
from cogs.casino_app_group import casino_group, ensure_group_registered


class LuckyStarsCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Lucky Stars", log_label="LuckyStars")

    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # /casino_luckystars
    ###########################################################
    @casino_group.command(name="luckystars", description="Start a Lucky Stars game")
    async def lucky_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        self.log_command_invocation(interaction, "casino luckystars")
        visibility = self.resolve_visibility(interaction)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: LuckyStars | None = None,
        ):
            game = new_game or LuckyStars(bet_amount)
            game.deal_round()
            self.log_game_start(
                inter,
                "casino luckystars",
                bet_amount=bet_amount,
            )

            animations_on = EconomyManager.animations_enabled(
                inter.user.id, inter.user.name
            )

            board_bytes = render_lucky_board(game, reveal=False)
            board_bytes.seek(0)
            board_file = discord.File(board_bytes, filename="lucky.png")

            stats = {
                "active_bet": game.bet,
                "stars_current": 0,
                "dealer_action": "Pick a card!",
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

            message = await inter.original_response()
            view.msg = message

            self.register_active_game(user_id, game=game, message=message)

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
    ensure_group_registered(bot.tree)
    await bot.add_cog(LuckyStarsCog(bot))
