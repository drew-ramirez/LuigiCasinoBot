###########################################################
# File: memorymatch_cog.py
#
# Description: Cog for Luigi’s Casino - Memory Match Game
###########################################################

import io
import asyncio
from PIL import Image
import discord
from discord.ext import commands
from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.memorymatch.MemoryMatch import MemoryMatch
from casinogames.memorymatch.MemoryMatchPrint import (
    render_board_image,
    make_board_flip_gif,
    make_board_reverse_flip_gif,
)
from casinogames.memorymatch.MemoryMatchUI import (
    update_controls_for_match,
    make_flip_controls,
    update_controls_for_unmatch,
)


class MemoryMatchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # MemoryMatch Globals
        self.memory_games = {}
        self.memory_messages = {}
        self.memory_views = {}

    ###########################################################
    # Events
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("MemoryMatchCog loaded.")

    ###########################################################
    # Commands
    ###########################################################

    ##################################################################################
    # MemoryMatch Section
    #
    #   memory_start
    #   memory_flip
    #   test_memory_all
    #   handle_memory_flip
    #
    ##################################################################################

    @discord.app_commands.command(name="memory_start", description="Start a Memory Match game")
    async def memory_start(self, interaction: discord.Interaction):
        game = MemoryMatch(interaction.user.id)
        self.memory_games[interaction.user.id] = game

        img_bytes = render_board_image(game)
        file = discord.File(img_bytes, filename="board.png")

        # Makes button grid
        viewUpdate = make_flip_controls(len(game.board))
        self.memory_views[interaction.user.id] = viewUpdate

        await interaction.response.send_message(
            f"Memory Match started!\nCoins: {game.remaining_coins}",
            file=file,
            view=viewUpdate,
            ephemeral=True,
        )

        # Save reference to this original board message
        msg = await interaction.original_response()
        self.memory_messages[interaction.user.id] = msg

    @discord.app_commands.command(name="memory_flip", description="Flip a card by position")
    async def memory_flip(self, interaction: discord.Interaction, pos: int):
        await self.handle_memory_flip(interaction, pos)

    @discord.app_commands.command(
        name="test_memory_all", description="Show all memory match faces and flips"
    )
    async def test_memory_all(self, interaction: discord.Interaction):
        faces = load_memory_faces()
        cards = []
        labels = []

        # Iterate through all defined faces
        for name, (col, row) in faces.faces.items():
            face = faces.get_face(name)
            flip = faces.get_flip(name)
            cards.append(face)
            cards.append(flip)
            labels.append(f"{name}_face")
            labels.append(f"{name}_flip")

        # Layout: 2 cols (face | flip)
        cols = 2
        rows = len(cards) // cols
        card_w, card_h = 133, 193  # full card size
        margin = 10

        canvas_w = cols * (card_w + margin) - margin
        canvas_h = rows * (card_h + margin) - margin

        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 128, 0, 255))

        for i, sprite in enumerate(cards):
            col = i % cols
            row = i // cols
            x = col * (card_w + margin)
            y = row * (card_h + margin)
            canvas.paste(sprite, (x, y), mask=sprite)

        out = io.BytesIO()
        canvas.save(out, format="PNG")
        out.seek(0)

        file = discord.File(out, filename="memory_all.png")
        await interaction.response.send_message(file=file, ephemeral=True)

    ###########################################################
    # Internal Logic
    ###########################################################

    async def handle_memory_flip(self, interaction: discord.Interaction, pos: int):
        game = self.memory_games.get(interaction.user.id)
        board_msg = self.memory_messages.get(interaction.user.id)
        view = self.memory_views.get(interaction.user.id)

        if not game or not board_msg or not view:
            await interaction.response.send_message(
                "No game running or controls missing!", ephemeral=True
            )
            return

        if not game.flip_card(pos):
            await interaction.response.send_message("Invalid flip.", ephemeral=True)
            return

        symbol, _, _ = game.board[pos]

        # This disables buttons during animation.
        for child in view.children:
            child.disabled = True
        await board_msg.edit(view=view)

        # 1. Show board flip animation
        gif = make_board_flip_gif(game, pos, symbol, duration=120)
        gif_file = discord.File(gif, filename=f"board_flip_{pos}.gif")
        await board_msg.edit(
            content=f"Coins: {game.remaining_coins}", attachments=[gif_file]
        )

        await asyncio.sleep(0.6)

        # 2. Update static board
        img_bytes = render_board_image(game)
        png_file = discord.File(img_bytes, filename="board.png")
        await board_msg.edit(
            content=f"Coins: {game.remaining_coins}", attachments=[png_file]
        )

        # 3. Check match logic
        if len(game.revealed) % 2 == 0:
            matched = game.check_match()
            if not matched:
                # No match = pause so player sees both
                await asyncio.sleep(1.0)

                a, b = game.revealed[-2], game.revealed[-1]
                symbols = [game.board[a][0], game.board[b][0]]

                # Play reverse flip GIF
                gif = make_board_reverse_flip_gif(game, [a, b], symbols, duration=120)
                gif_file = discord.File(gif, filename="board_unflip.gif")
                await board_msg.edit(
                    content=f"Coins: {game.remaining_coins}", attachments=[gif_file]
                )

                await asyncio.sleep(0.6)

                # Actually hide them in game state
                game.hide_unmatched()

                # Update static PNG after hiding
                img_bytes = render_board_image(game)
                png_file = discord.File(img_bytes, filename="board.png")
                await board_msg.edit(
                    content=f"Coins: {game.remaining_coins}", attachments=[png_file]
                )
                await update_controls_for_unmatch(view, [a, b], board_msg)

            else:
                # Match = mark buttons
                await update_controls_for_match(view, game.revealed[-2:], board_msg)

                if game.is_board_cleared():

                    game.next_level()

                    # Re-render board for the new level
                    img_bytes = render_board_image(game)
                    png_file = discord.File(img_bytes, filename="board.png")
                    await board_msg.edit(
                        content=f"Board Cleared | Stars: {game.stars} | Coins: {game.remaining_coins}",
                        attachments=[png_file],
                    )

                    # Resetting controls for the new board size incase it ups
                    new_view = make_flip_controls(len(game.board))
                    self.memory_views[interaction.user.id] = new_view
                    await board_msg.edit(view=new_view)
                    return

        # Re-enable all still-active buttons
        for i, child in enumerate(view.children):
            if i < len(game.board):
                symbol, flipped, matched = game.board[i]
                child.disabled = matched  # keep disabled if matched
            else:
                child.disabled = True
        await board_msg.edit(view=view)


###########################################################
# Cog Registration
###########################################################

async def setup(bot):
    await bot.add_cog(MemoryMatchCog(bot))
