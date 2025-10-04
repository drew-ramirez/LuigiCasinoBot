###########################################################
# File: luckystars_cog.py
#
# Description: Cog for Luigi’s Casino - Lucky Stars Game
###########################################################

import discord
from discord.ext import commands
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import render_lucky_board
from casinogames.luckystars.LuckyStarsUI import (
    make_lucky_controls,
    reveal_lucky_cards,
    disable_left_right_enable_next,
)


class LuckyStarsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # per-user state for lucky stars
        self.lucky_games: dict[int, LuckyStars] = {}
        self.lucky_messages: dict[int, discord.Message] = {}
        self.lucky_views: dict[int, discord.ui.View] = {}

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("LuckyStarsCog loaded.")

    ###########################################################
    # COMMANDS
    ###########################################################

    ##################################################################################
    # Lucky Stars (Luigi’s Casino)
    #   lucky_start
    #   handle_lucky_pick
    #   handle_lucky_next
    ##################################################################################

    @discord.app_commands.command(name="lucky_start", description="Start a Lucky Stars game")
    async def lucky_start(self, interaction: discord.Interaction):
        game = LuckyStars()
        game.deal_round()

        img_bytes = render_lucky_board(game, reveal=False)
        file = discord.File(img_bytes, filename="lucky.png")

        # next must be disabled at the start of each round
        view = make_lucky_controls(
            on_pick=self.handle_lucky_pick, on_next=self.handle_lucky_next, next_enabled=False
        )

        await interaction.response.send_message(
            content=f"🎲 Lucky Stars started! You have {game.coins} coins.\nPick a card!",
            file=file,
            view=view,
        )
        msg = await interaction.original_response()
        uid = interaction.user.id
        self.lucky_games[uid] = game
        self.lucky_messages[uid] = msg
        self.lucky_views[uid] = view

    ###########################################################
    # INTERNAL LOGIC
    ###########################################################

    async def handle_lucky_pick(self, interaction: discord.Interaction, pos: int):
        uid = interaction.user.id
        game = self.lucky_games.get(uid)
        msg = self.lucky_messages.get(uid)
        view = self.lucky_views.get(uid)

        if not game or not msg or not view:
            await interaction.response.send_message("No Lucky Stars game running!", ephemeral=True)
            return

        # immediately freeze l/r and enable next
        await interaction.response.defer()
        await disable_left_right_enable_next(view, msg)

        # play animation and resolve
        result = await reveal_lucky_cards(game, pos, msg)
        outcome = result["outcome"]
        coins = result["coins"]

        if outcome == "win":
            text = f"✅ You win this round! Coins: {coins}\nPress **Next** to continue."
        elif outcome == "lose":
            text = f"❌ You lose this round! Coins: {coins}\nPress **Next** to continue."

        if result["finished"]:
            text = f"{text}\n\n💀 Game over! You ran out of coins."
            for c in view.children:
                if isinstance(c, discord.ui.Button):
                    c.disabled = True
            await msg.edit(content=text, view=view)
            self.lucky_games.pop(uid, None)
            self.lucky_messages.pop(uid, None)
            self.lucky_views.pop(uid, None)
        else:
            await msg.edit(content=text, view=view)

    async def handle_lucky_next(self, interaction: discord.Interaction):
        uid = interaction.user.id
        game = self.lucky_games.get(uid)
        msg = self.lucky_messages.get(uid)
        old_view = self.lucky_views.get(uid)

        if not game or not msg or not old_view:
            await interaction.response.send_message("No Lucky Stars game running!", ephemeral=True)
            return

        await interaction.response.defer()

        # deal next round and render the facedown board
        game.deal_round()
        img = render_lucky_board(game, reveal=False)
        file = discord.File(img, filename="lucky.png")

        # builds a fresh view for the new round: l/r enabled, next disabled
        new_view = make_lucky_controls(
            on_pick=self.handle_lucky_pick, on_next=self.handle_lucky_next, next_enabled=False
        )
        await msg.edit(
            content=f"Pick again! (Coins: {game.coins})", attachments=[file], view=new_view
        )
        self.lucky_views[uid] = new_view


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(LuckyStarsCog(bot))
