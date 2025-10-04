##############################################################
# File: PairAGoneUI.py
#
# Description: Discord UI controls for Pair-a-Gone
# persistent View subclass instead of dynamic globals in bot.py
###############################################################

import discord
import asyncio
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import (
    render_pair_board,
    render_pair_board_with_blanks,
    make_pair_flicker_gif,
    make_deal_flip_gif,
)
from PIL import Image


class PairControls(discord.ui.View):
    #persistent view for Pair-a-Gone with per-button callbacks

    def __init__(self, game: PairAGone, msg: discord.Message = None):
        super().__init__(timeout=None)  # persistent so buttons work after restart
        self.game = game
        self.msg = msg
        self.cols = game.COLS

        # build buttons dynamically
        for i in range(game.COLS * game.ROWS):
            btn = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.secondary,
                custom_id=f"pair_{i}",
                row=i // self.cols,
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    ###########################################################
    # callback factory
    ###########################################################
    def _make_callback(self, pos: int):
        async def callback(interaction: discord.Interaction):
            await self.handle_pair_flip(interaction, pos)
        return callback

    ###########################################################
    # main flip handler (was previously in bot.py)
    ###########################################################
    async def handle_pair_flip(self, interaction: discord.Interaction, pos: int):
        await interaction.response.defer()  # acknowledge the click IMPORTANT

        game = self.game
        msg = self.msg or await interaction.original_response()

        game.selected.append(pos)
        if len(game.selected) < 2:
            return

        a, b = game.selected
        game.selected = []

        sa, sb = game.board[a], game.board[b]
        ra, ca = divmod(a, game.COLS)
        rb, cb = divmod(b, game.COLS)
        is_adjacent = abs(ra - rb) <= 1 and abs(ca - cb) <= 1
        is_match = sa == sb and is_adjacent

        if not is_match:
            await msg.edit(content="No match!", view=self)
            return

        # disable buttons during animation
        for child in self.children:
            child.disabled = True
        await msg.edit(view=self)

        # flicker animation
        flicker_gif = make_pair_flicker_gif(game, [a, b], [sa, sb], duration=120)
        await msg.edit(
            content="Match!",
            attachments=[discord.File(flicker_gif, "pair_flicker.gif")],
            view=self,
        )
        await asyncio.sleep(1.0)

        # remove and refill
        new_cards = game.remove_and_fall([a, b])
        blanks = [pos for pos, _ in new_cards]
        img_bytes = render_pair_board_with_blanks(game, blanks)
        await msg.edit(
            content="Dealer is dealing new cards...",
            attachments=[discord.File(img_bytes, "pair_board.png")],
            view=self,
        )

        # dealer flips one at a time
        revealed = []
        for pos, sym in new_cards:
            blanks = [p for p, _ in new_cards if p not in revealed and p != pos]
            img_bytes = render_pair_board_with_blanks(game, blanks)
            base_board = Image.open(img_bytes).convert("RGBA")

            flip_gif = make_deal_flip_gif(game, pos, sym, base_board, duration=120)
            await msg.edit(
                content="Dealer flips a new card...",
                attachments=[discord.File(flip_gif, "deal_flip.gif")],
                view=self,
            )
            await asyncio.sleep(0.8)
            revealed.append(pos)

        # redraw static board
        final_png = render_pair_board(game)
        await msg.edit(
            content="Pair-a-Gone continues!",
            attachments=[discord.File(final_png, "pair_board.png")],
            view=self,
        )

        # re-enable all buttons
        for child in self.children:
            child.disabled = False
        await msg.edit(view=self)

        # end conditions
        if game.is_board_cleared():
            await msg.edit(content="Board cleared!", view=None)
            return
        if not game.has_possible_moves():
            await msg.edit(content="Too Bad. No moves left.", view=None)
            return
