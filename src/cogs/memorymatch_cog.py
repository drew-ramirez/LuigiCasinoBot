###########################################################
# File: memorymatch_cog.py
#
# Description: Luigi's Casino Memory Match command logic
###########################################################

import discord
from discord.ext import commands
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import render_board_image
from casinogames.memorymatch.MemoryMatchUI import make_memory_view
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_game_header
from economy.EconomyManager import EconomyManager


class MemoryMatchCog(commands.Cog):
    # Cog for Memory Match gameplay

    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("MemoryMatchCog loaded.")

    @discord.app_commands.command(
        name="memory_start", description="Start a Memory Match game"
    )
    async def memory_start(self, interaction: discord.Interaction):
        player = interaction.user
        user_id = player.id
        username = player.name

        #defer response prevent "interaction failed" message
        #in other game cogs as well.
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        responder = interaction.followup.send

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
                wager_options=DEFAULT_WAGER_OPTIONS,
                start_game_callback=start_game,
            )

            await inter.response.edit_message(
                content=content,
                attachments=[file],
                view=view,
            )

            message = await inter.original_response()
            view.msg = message

            self.active_games[user_id] = {
                "game": game,
                "message": message,
            }

        balance = EconomyManager.balance(user_id, username)

        view = BetSelectView(
            user_id,
            username,
            start_game,
            wager_options=DEFAULT_WAGER_OPTIONS,
        )

        await responder(
            content=(
                f"╔═════════════════════════╗\n"
                f"🎰 Luigi’s Casino — Memory Match\n"
                f" ══════════════════════════\n"
                f"💰 Balance: {balance:,} coins\n"
                f" ══════════════════════════\n"
                f"Select your wager amount to begin:\n"
                f"╚═════════════════════════╝\n"
            ),
            view=view,
            ephemeral=True,
        )

    async def cleanup_game(self, user_id: int):
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[MemoryMatch] Cleaned up game for {user_id}")


###########################################################
# Cog SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(MemoryMatchCog(bot))
