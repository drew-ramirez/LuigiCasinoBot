###########################################################
# File: PairAGoneUI.py
#
# Description: Discord UI controls for Pair-a-Gone
###########################################################

import discord
import asyncio
from PIL import Image
import io
from casinogames.pairagone.PairAGone import PairAGone
from casinogames.pairagone.PairAGonePrint import (
    render_pair_board,
    render_pair_board_with_blanks,
    make_pair_flicker_gif,
)
from casinogames.assetloader import load_memory_faces, load_memory_backs

faces = load_memory_faces()
backs = load_memory_backs()


class PairControls(discord.ui.View):

    def __init__(self, game: PairAGone, msg: discord.Message = None):
        super().__init__(timeout=None)
        self.game = game
        self.msg = msg
        self.cols = game.COLS

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
    # button updater
    ###########################################################
    def refresh_button_states(self):
        for i, child in enumerate(self.children):
            # skip non-card buttons if you ever add others later
            if not isinstance(child, discord.ui.Button):
                continue

            has_card = i < len(self.game.board) and self.game.board[i] is not None
            if has_card:
                child.disabled = False
                child.label = str(i + 1)
            else:
                child.disabled = True
                child.label = ""

    ###########################################################
    # main flip handler
    ###########################################################
    async def handle_pair_flip(self, interaction: discord.Interaction, pos: int):
        await interaction.response.defer()

        game = self.game
        msg = self.msg or await interaction.original_response()

        # if user already picked this same card, ignore it
        if pos in game.selected:
            return

        # temporarily disable the selected button to prevent re-clicks
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == f"pair_{pos}":
                child.disabled = True
                break
        await msg.edit(view=self)

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

        # board re-enables after a failed pair.
        if not is_match:
            deck_remaining = game.remaining_in_deck()
            for i, child in enumerate(self.children):
                if not isinstance(child, discord.ui.Button):
                    continue
                if i < len(game.board) and game.board[i] is not None:
                    child.disabled = False
                    child.label = str(i + 1)
                else:
                    if deck_remaining == 0:
                        child.disabled = True
                        child.label = "\u2800"  # visually blank but valid
                    else:
                        child.disabled = False
                        child.label = str(i + 1)
            await msg.edit(content="No match!", view=self)
            return

        # disable all buttons during animation
        for child in self.children:
            child.disabled = True
        await msg.edit(view=self)

        # 1. flicker animation
        flicker_gif = make_pair_flicker_gif(game, [a, b], [sa, sb], duration=70)
        await msg.edit(
            content="Match!",
            attachments=[discord.File(flicker_gif, "pair_flicker.gif")],
            view=self,
        )
        await asyncio.sleep(0.6)

        # remove and refill
        new_cards = game.remove_and_fall([a, b])

        if not new_cards:
            final_png = render_pair_board(game)
            await msg.edit(
                content=f"Pair-a-Gone continues! (Cards remaining: {game.remaining_in_deck()})",
                attachments=[discord.File(final_png, "pair_board.png")],
                view=self,
            )
            await asyncio.sleep(0.6)
        else:
            # show blanks first
            blanks = [pos for pos, _ in new_cards]
            img_bytes = render_pair_board_with_blanks(game, blanks)
            await msg.edit(
                content="Dealer is dealing new cards...",
                attachments=[discord.File(img_bytes, "pair_board.png")],
                view=self,
            )
            await asyncio.sleep(0.4)

            # flip both cards together
            try:
                flip_gif = self.make_simultaneous_flip_gif(game, new_cards, duration=80)
                await msg.edit(
                    content=f"Dealer flips new cards! (Cards remaining: {game.remaining_in_deck()})",
                    attachments=[discord.File(flip_gif, "pair_flip.gif")],
                    view=self,
                )
                await asyncio.sleep(0.8)
            except Exception as e:
                print(f"[PairAGoneUI] flip gif failed: {e}")

            # redraw final static board 
            final_png = render_pair_board(game)
            await msg.edit(
                content=f"Pair-a-Gone continues! (Cards remaining: {game.remaining_in_deck()})",
                attachments=[discord.File(final_png, "pair_board.png")],
                view=self,
            )

        # re-enable all buttons properly but start checking if excess buttons should be disabled
        deck_remaining = game.remaining_in_deck()
        for i, child in enumerate(self.children):
            if not isinstance(child, discord.ui.Button):
                continue

            if i < len(game.board) and game.board[i] is not None:
                child.disabled = False
                child.label = str(i + 1)
            else:
                if deck_remaining == 0:
                    child.disabled = True
                    child.label = "\u2800"  # visually blanks the button
                else:
                    child.disabled = False
                    child.label = str(i + 1)

        await msg.edit(view=self)

        if game.is_board_cleared():
            game.handle_game_end(won=True)
            await msg.edit(
                content=f"Board cleared! You earned a Star! (Total Stars: {game.stars})",
                view=None,
            )
            return

        if not game.has_possible_moves():
            game.handle_game_end(won=False)
            await msg.edit(content="Too Bad. No moves left.", view=None)
            return



    #########################################################################################
    # simultaneous flip gif generator
    #########################################################################################
    def make_simultaneous_flip_gif(self, game, new_cards, duration=80) -> io.BytesIO:
        base_board = Image.open(
            render_pair_board_with_blanks(game, [pos for pos, _ in new_cards])
        ).convert("RGBA")

        frames = []

        
        frame1 = base_board.copy()
        for pos, _ in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            back = backs.get("back_full")
            frame1.paste(back, (slot_x, slot_y), mask=back)
        frames.append(frame1)

        frame2 = base_board.copy()
        for pos, _ in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            half = backs.get("back_half")
            frame2.paste(half, (slot_x, slot_y), mask=half)
        frames.append(frame2)

        frame3 = base_board.copy()
        for pos, _ in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            edge = backs.get("back_edge")
            frame3.paste(edge, (slot_x, slot_y), mask=edge)
        frames.append(frame3)

        frame4 = base_board.copy()
        for pos, sym in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            face_edge = faces.get_flip(sym)
            frame4.paste(face_edge, (slot_x, slot_y), mask=face_edge)
        frames.append(frame4)

        frame5 = base_board.copy()
        for pos, sym in new_cards:
            slot_x, slot_y, slot_w, slot_h = game.get_slot_rect(pos)
            face = faces.get_face(sym)
            frame5.paste(face, (slot_x, slot_y), mask=face)
        frames.append(frame5)

        out = io.BytesIO()
        frames[0].save(
            out,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=1,
            disposal=2,
            optimize=False,
        )
        out.seek(0)
        return out
