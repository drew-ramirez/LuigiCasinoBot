###########################################################
# File: picturepoker_cog.py
#
# Description: Cog for Luigi’s Casino - Picture Poker Game
###########################################################

import io
import asyncio
import discord
from discord.ext import commands
from collections import Counter
from PIL import Image

from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import (
    render_board,
    render_board_with_hidden,
    make_deal_flip_gif,
    reveal_final,
    make_discard_flicker_gif,
    make_final_reveal_gif,
)
from casinogames.picturepoker.PicturePokerUI import (
    poker_games,
    poker_messages,
    poker_views,
    PokerControls,
)


class PicturePokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # track active games for picture poker
        self.poker_games = {}
        self.poker_messages = {}
        self.poker_views = {}

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("PicturePokerCog loaded.")

    ###########################################################
    # COMMANDS
    ###########################################################

    # ----------------------
    # Picture Poker commands
    # ----------------------

    @discord.app_commands.command(name="poker_start", description="Start a Picture Poker game")
    async def poker_start(self, interaction: discord.Interaction):
        game = PicturePoker()
        game.start_round()

        img_bytes = render_board(game, reveal=False)
        file = discord.File(img_bytes, filename="poker.png")

        await interaction.response.send_message(
            content=f"🎴 Picture Poker started! Coins: {game.coins}, Stars: {game.stars}\nSelect cards to discard then submit.",
            file=file,
        )
        msg = await interaction.original_response()

        uid = interaction.user.id
        self.poker_games[uid] = game
        self.poker_messages[uid] = msg

        controls = PokerControls(uid)
        self.poker_views[uid] = controls
        await msg.edit(view=controls)

    ###########################################################
    # INTERNAL LOGIC
    ###########################################################

    async def handle_poker_discard(self, interaction, user_id: int, discards: list[int]):
        game = self.poker_games[user_id]
        msg = self.poker_messages[user_id]
        view = self.poker_views[user_id]

        await interaction.response.defer()

        if not discards:
            await msg.edit(content="❌ No cards selected to discard.")
            return

        game.player_discard(discards)

        # show facedown
        img_hidden = render_board_with_hidden(game, hidden_player=discards)
        await msg.edit(
            content="Your new cards are dealt facedown...",
            attachments=[discord.File(img_hidden, "poker.png")],
            view=view,
        )
        await asyncio.sleep(0.8)

        # flip 1-by-1 and keep them face-up
        base = Image.open(img_hidden).convert("RGBA")
        for idx, i in enumerate(discards):
            symbol = game.player_hand[i]
            gif = make_deal_flip_gif(game, i, symbol, base, dealer=False)
            await msg.edit(
                content=f"Flipping your card {i+1}...",
                attachments=[discord.File(gif, f"player_flip_{i}.gif")],
                view=view,
            )
            await asyncio.sleep(0.8)

            still_hidden = discards[idx + 1 :]
            base = Image.open(
                render_board_with_hidden(game, hidden_player=still_hidden)
            ).convert("RGBA")

        # disable discard buttons, keep stand
        for child in view.children:
            if "Card" in child.label or "submit" in child.label.lower():
                child.disabled = True

        final_png = render_board(game, reveal=False)
        await msg.edit(
            content="Your redraw is complete. Press **Stand** to let Luigi play.",
            attachments=[discord.File(final_png, "poker.png")],
            view=view,
        )

    async def handle_poker_stand(self, interaction, user_id: int):
        game = self.poker_games[user_id]
        msg = self.poker_messages[user_id]

        await interaction.response.defer()

        # luigi logic
        counts = Counter(game.luigi_hand)
        keep = {s for s, c in counts.items() if c > 1}
        luigi_discards = [i for i, c in enumerate(game.luigi_hand) if c not in keep]
        game.luigi_discard()

        # show luigi’s new cards facedown
        img_hidden = render_board_with_hidden(game, hidden_dealer=luigi_discards)
        await msg.edit(
            content="Luigi discards some cards...",
            attachments=[discord.File(img_hidden, "poker.png")],
            view=None,
        )
        await asyncio.sleep(0.8)

        # flicker only (no immediate flip-in for luigi)
        base = Image.open(img_hidden).convert("RGBA")
        for idx, i in enumerate(luigi_discards):
            flicker_gif = make_discard_flicker_gif(game, i, base, dealer=True)
            await msg.edit(
                content=f"Luigi discards card {i+1}...",
                attachments=[discord.File(flicker_gif, f"luigi_discard_{i}.gif")],
                view=None,
            )
            await asyncio.sleep(0.8)

            still_hidden = luigi_discards[idx + 1 :]
            base = Image.open(
                render_board_with_hidden(game, hidden_dealer=still_hidden)
            ).convert("RGBA")

        # outcome + final reveal
        result = game.resolve_round()
        final_gif = make_final_reveal_gif(game)
        text = (
            f"Round complete! Outcome: {result['outcome']}\n"
            f"Coins: {result['coins']} | Stars: {result['stars']}"
        )
        await msg.edit(
            content=text,
            attachments=[discord.File(final_gif, "final_reveal.gif")],
            view=None,
        )


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(PicturePokerCog(bot))
