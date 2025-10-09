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
from utils.ui_embeds import make_game_header


class LuckyStarsCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Lucky Stars", log_label="LuckyStars")

    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # /casino_luckystars
    ###########################################################
    @discord.app_commands.command(name="casino_luckystars", description="Start a Lucky Stars game")
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
            game = new_game or LuckyStars(bet_amount)
            game.deal_round()
            self.log_game_start(
                inter,
                "casino_luckystars",
                bet_amount=bet_amount,
            )

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
            visibility=visibility,
        )


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(LuckyStarsCog(bot))
