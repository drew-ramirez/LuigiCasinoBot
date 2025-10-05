###########################################################
# File: MemoryMatchUI.py
#
# Description: Discord UI controls for Luigi’s Casino Memory Match
# Converted to a persistent View subclass.
###########################################################

import discord
import asyncio
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import (
    render_board_image,
    make_board_flip_gif,
    make_board_reverse_flip_gif,
)
from PIL import Image


class MemoryMatchControls(discord.ui.View):
    #persistent view for Memory Match with per-card callbacks

    def __init__(self, game: MemoryMatch, msg: discord.Message = None):
        super().__init__(timeout=None)
        self.game = game
        self.msg = msg

        ###########################################################
        # build button grid
        ###########################################################
        for i in range(len(game.board)):
            btn = discord.ui.Button(
                label=str(i + 1),
                style=discord.ButtonStyle.secondary,
                custom_id=f"memory_{i}",
                row=i // 4,
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    ###########################################################
    # callback factory
    ###########################################################
    def _make_callback(self, pos: int):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()  # acknowledge button click immediately
            await self.handle_memory_flip(interaction, pos)
        return callback

    ###########################################################
    # main flip handler
    ###########################################################
    async def handle_memory_flip(self, interaction: discord.Interaction, pos: int):
        game = self.game
        msg = self.msg or await interaction.original_response()

        if not game.flip_card(pos):
            await msg.edit(content="Invalid flip.", view=self)
            return

        symbol, _, _ = game.board[pos]

        # disable buttons during animation
        for child in self.children:
            child.disabled = True
        await msg.edit(view=self)

        ###########################################################
        # flip animation
        ###########################################################
        gif = make_board_flip_gif(game, pos, symbol, duration=120)
        await msg.edit(
            content=f"Coins: {game.remaining_coins}",
            attachments=[discord.File(gif, filename=f"board_flip_{pos}.gif")],
        )
        await asyncio.sleep(0.6)

        ###########################################################
        # update static board
        ###########################################################
        png = render_board_image(game)
        await msg.edit(
            content=f"Coins: {game.remaining_coins}",
            attachments=[discord.File(png, "board.png")],
        )

        ###########################################################
        # match check
        ###########################################################
        if len(game.revealed) % 2 == 0:
            matched = game.check_match()
            if not matched:
                # no match → show both then reverse flip
                await asyncio.sleep(1.0)
                a, b = game.revealed[-2], game.revealed[-1]
                symbols = [game.board[a][0], game.board[b][0]]

                gif = make_board_reverse_flip_gif(game, [a, b], symbols, duration=120)
                await msg.edit(
                    content=f"Coins: {game.remaining_coins}",
                    attachments=[discord.File(gif, "board_unflip.gif")],
                )

                await asyncio.sleep(0.6)
                game.hide_unmatched()

                png = render_board_image(game)
                await msg.edit(
                    content=f"Coins: {game.remaining_coins}",
                    attachments=[discord.File(png, "board.png")],
                )
                await self.update_controls_for_unmatch([a, b], msg)
            else:
                await self.update_controls_for_match(game.revealed[-2:], msg)

                if game.is_board_cleared():
                    game.next_level()
                    png = render_board_image(game)
                    await msg.edit(
                        content=f"Board Cleared | Stars: {game.stars} | Coins: {game.remaining_coins}",
                        attachments=[discord.File(png, "board.png")],
                    )

                    # rebuild view for new board size
                    new_view = MemoryMatchControls(game, msg)
                    await msg.edit(view=new_view)
                    return

        ###########################################################
        # re-enable buttons
        ###########################################################
        for i, child in enumerate(self.children):
            if i < len(game.board):
                _, _, matched = game.board[i]
                child.disabled = matched
            else:
                child.disabled = True
        await msg.edit(view=self)

    ###########################################################
    # UI updates for matched cards
    ###########################################################
    async def update_controls_for_match(self, positions: list[int], message: discord.Message):
        for child in self.children:
            if hasattr(child, "custom_id"):
                idx = int(child.custom_id.split("_")[-1])
                if idx in positions:
                    child.label = "✅"
                    child.disabled = True
        await message.edit(view=self)

    ###########################################################
    # UI updates for unmatched cards
    ###########################################################
    async def update_controls_for_unmatch(self, positions: list[int], message: discord.Message):
        for child in self.children:
            if hasattr(child, "custom_id"):
                idx = int(child.custom_id.split("_")[-1])
                if idx in positions:
                    child.label = str(idx + 1)
                    child.disabled = False
        await message.edit(view=self)
