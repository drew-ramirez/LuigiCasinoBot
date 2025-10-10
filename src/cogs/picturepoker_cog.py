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
from utils.ui_embeds import make_game_header
from cogs.casino_app_group import casino_group, ensure_group_registered


class PicturePokerCog(BaseGameCog):
    def __init__(self, bot):
        super().__init__(bot, "Picture Poker", log_label="PicturePoker")

    @commands.Cog.listener()
    async def on_ready(self):
        print("PicturePokerCog loaded.")

    ###########################################################
    # /casino_picturepoker
    ###########################################################
    @casino_group.command(
        name="picturepoker", description="Start a Picture Poker game"
    )
    async def poker_start(self, interaction: discord.Interaction):

        user_id = interaction.user.id

        self.log_command_invocation(interaction, "casino picturepoker")
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
                "casino picturepoker",
                bet_amount=bet_amount,
            )

            img_bytes = render_board(target_game, reveal=False)
            if hasattr(img_bytes, "seek"):
                try:
                    img_bytes.seek(0)
                except Exception:
                    pass
            file = discord.File(img_bytes, filename="poker.png")

            stats = {
                "active_bet": target_game.bet,
                "stars_current": target_game.stars,
                "round": target_game.round,
                "multiplier": 1.0,
                "dealer_action": "New game started! \nSelect cards to discard then submit.",
            }

            header_embed = make_game_header(
                inter.user,
                "Picture Poker",
                stats,
            )

            view = make_poker_view(
                target_game,
                user_id,
                self.cleanup_game,
                start_game_callback=start_game,
            )

            await inter.response.edit_message(
                content=None,
                embed=header_embed,
                attachments=[file],
                view=view,
            )

            message = inter.message
            if message is None:
                try:
                    message = await inter.original_response()
                except Exception:
                    message = None

            self.register_active_game(user_id, game=target_game, message=message)

        await self.present_wager_menu(
            interaction,
            on_bet_selected=start_game,
            visibility=visibility,
        )


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    ensure_group_registered(bot.tree)
    await bot.add_cog(PicturePokerCog(bot))
