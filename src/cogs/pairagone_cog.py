###########################################################
# File: pairagone_cog.py
#
# Description: Cog for Luigi’s Casino - Pair-A-Gone Game
###########################################################

import asyncio
import discord
from discord.ext import commands
from PIL import Image

from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import (
    render_pair_board,
    render_pair_board_with_blanks,
    make_pair_flicker_gif,
    make_deal_flip_gif,
)
from casinogames.pairagone.PairAGoneUI import make_pair_controls


class PairAGoneCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # pair-a-gone globals
        self.pair_games = {}
        self.pair_messages = {}
        self.pair_views = {}

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("PairAGoneCog loaded.")

    ###########################################################
    # COMMANDS
    ###########################################################

    ##################################################################################
    # Pair A Gone Section
    #
    #   pair_start
    #   handle_pair_flip
    ##################################################################################

    @discord.app_commands.command(name="pair_start", description="Start a Pair-a-Gone game")
    async def pair_start(self, interaction: discord.Interaction):
        game = PairAGone(interaction.user.id)
        self.pair_games[interaction.user.id] = game

        # render the starting board
        img_bytes = render_pair_board(game)
        file = discord.File(img_bytes, filename="pair_board.png")

        # build button grid
        view = make_pair_controls(game.COLS * game.ROWS, game.COLS)
        self.pair_views[interaction.user.id] = view

        await interaction.response.send_message(
            "Pair-a-Gone started!", file=file, view=view, ephemeral=True
        )

        # save reference to the message so flips can edit it
        msg = await interaction.original_response()
        self.pair_messages[interaction.user.id] = msg

    ###########################################################
    # INTERNAL LOGIC
    ###########################################################

    async def handle_pair_flip(self, interaction: discord.Interaction, pos: int):
        game = self.pair_games.get(interaction.user.id)
        msg = self.pair_messages.get(interaction.user.id)
        view = self.pair_views.get(interaction.user.id)

        if not game or not msg or not view:
            await interaction.response.send_message(
                "No Pair-a-Gone game running!", ephemeral=True
            )
            return

        # collect selections
        game.selected.append(pos)
        if len(game.selected) < 2:
            return  # wait for second click

        # two cards chosen
        a, b = game.selected
        game.selected = []

        # validate adjacency + symbol match
        if a == b:
            await msg.edit(content="❌ Pick two different cards.", view=view)
            return

        sa, sb = game.board[a], game.board[b]
        ra, ca = divmod(a, game.COLS)
        rb, cb = divmod(b, game.COLS)
        is_adjacent = abs(ra - rb) <= 1 and abs(ca - cb) <= 1
        is_match = sa == sb and is_adjacent

        if not is_match:
            await msg.edit(content="❌ No match!", view=view)
            return

        # disable buttons during animation
        for child in view.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        await msg.edit(view=view)

        # flicker animation
        positions = [a, b]
        symbols = [sa, sb]
        flicker_gif = make_pair_flicker_gif(game, positions, symbols, duration=120)
        await msg.edit(
            content="✅ Match!",
            attachments=[discord.File(flicker_gif, "pair_flicker.gif")],
            view=view,
        )
        await asyncio.sleep(1.0)

        # remove and refill
        new_cards = game.remove_and_fall(positions)

        # start with all new slots green
        blanks = [pos for pos, _ in new_cards]
        img_bytes = render_pair_board_with_blanks(game, blanks)
        await msg.edit(
            content="Dealer is dealing new cards...",
            attachments=[discord.File(img_bytes, "pair_board.png")],
            view=view,
        )

        # dealer flip one at a time
        revealed = []
        for pos, sym in new_cards:
            # blanks out all new slots except the ones already revealed
            blanks = [p for p, _ in new_cards if p not in revealed and p != pos]

            # base board: already revealed new cards face up, unrevealed new ones green
            img_bytes = render_pair_board_with_blanks(game, blanks)
            base_board = Image.open(img_bytes).convert("RGBA")

            # build flip on this custom background
            flip_gif = make_deal_flip_gif(game, pos, sym, base_board, duration=120)
            await msg.edit(
                content="Dealer flips a new card...",
                attachments=[discord.File(flip_gif, "deal_flip.gif")],
                view=view,
            )
            await asyncio.sleep(0.8)

            revealed.append(pos)

        # redraw cards
        final_png = render_pair_board(game)
        await msg.edit(
            content="Pair-a-Gone continues!",
            attachments=[discord.File(final_png, "pair_board.png")],
            view=view,
        )

        # re-enable buttons
        for child in view.children:
            if hasattr(child, "disabled"):
                child.disabled = False
        await msg.edit(view=view)

        # end conditions
        if game.is_board_cleared():
            await msg.edit(content="🎉 Board cleared!", view=None)
            return
        if not game.has_possible_moves():
            await msg.edit(content="❌ Too Bad. No moves left.", view=None)
            return


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(PairAGoneCog(bot))
