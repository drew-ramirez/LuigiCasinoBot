###########################################################
# File: memorymatch_cog.py
#
# Description: Luigi's Casino Memory Match command logic
###########################################################

import discord
from discord.ext import commands
from cogs.base_game_cog import BaseGameCog
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image
from casinogames.memorymatch.MemoryMatchUI import make_memory_view
from utils.ui_embeds import make_game_header


class MemoryMatchCog(BaseGameCog):
    # Cog for Memory Match gameplay

    def __init__(self, bot):
        super().__init__(bot, "Memory Match", log_label="MemoryMatch")

    @commands.Cog.listener()
    async def on_ready(self):
        print("MemoryMatchCog loaded.")

    ###########################################################
    # /memory_start
    ###########################################################
    @discord.app_commands.command(
        name="memory_start", description="Start a Memory Match game"
    )
    async def memory_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id

        #defer response prevent "interaction failed" message
        #in other game cogs as well.
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        async def start_game(
            inter: discord.Interaction,
            bet_amount: int,
            new_game: MemoryMatch | None = None,
        ):
            game = new_game or MemoryMatch(user_id, bet_amount)

            board_bytes = render_board_image(game)
            board_bytes.seek(0)
            file = discord.File(board_bytes, filename="memory_board.png")

            stats = {
                "active_bet": game.bet,
                "stars_current": game.stars,
                "dealer_action": f"Attempts left: {game.remaining_attempts}",
            }
            content = make_game_header(inter.user, "Memory Match", stats)

            view = make_memory_view(
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
        )


###########################################################
# Cog SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(MemoryMatchCog(bot))
