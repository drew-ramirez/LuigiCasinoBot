###########################################################
# File: luckystars_cog.py
#
# Description: Cog for Luigi’s Casino - Lucky Stars Game
###########################################################

import discord
from discord.ext import commands
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import make_lucky_controls


class LuckyStarsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # Slash command: start game
    ###########################################################
    @discord.app_commands.command(
        name="lucky_start",
        description="Start a Lucky Stars game"
    )
    async def lucky_start(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        try:
            # Prevent multiple concurrent games for same user
            if user_id in self.active_games:
                await interaction.response.send_message(
                    "You already have a Lucky Stars game running!",
                    ephemeral=True
                )
                return

            # Create game instance
            game = LuckyStars()
            game.deal_round()

            # Render initial board image
            img_bytes = render_lucky_board(game, reveal=False)
            file = discord.File(img_bytes, filename="lucky.png")

            # Build the View
            view = make_lucky_controls(game, user_id, self.cleanup_game)

            # Respond immediately (required to avoid timeout)
            await interaction.response.send_message(
                content=f"🎲 Lucky Stars started! You have {game.coins} coins.\nPick a card!",
                file=file,
                view=view,
            )

            # Store active game info
            msg = await interaction.original_response()
            self.active_games[user_id] = {"game": game, "message": msg}
            print(f"[LuckyStars] Game started for user {user_id}")

        except Exception as e:
            print(f"[LuckyStars ERROR] {type(e).__name__}: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "Error starting Lucky Stars game.",
                        ephemeral=True
                    )
            except Exception:
                pass

    ###########################################################
    # Cleanup
    ###########################################################
    async def cleanup_game(self, user_id: int):
        """Remove game after user finishes or quits."""
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[LuckyStars] Cleaned up game for {user_id}")


###########################################################
# Cog setup
###########################################################
async def setup(bot):
    await bot.add_cog(LuckyStarsCog(bot))
