###########################################################
# File: PicturePokerUI.py
#
# Description: Discord UI controls for Picture Poker
# Clean modular version — now uses dynamic header lines
###########################################################

import discord
import asyncio
from PIL import Image
from collections import Counter
from casinogames.picturepoker.PicturePoker import PicturePoker
from casinogames.picturepoker.PicturePokerPrint import (
    render_board,
    render_board_with_hidden,
    make_deal_flip_gif,
    make_discard_flicker_gif,
    make_final_reveal_gif,
)
from utils.ui_embeds import make_game_header


###########################################################
# Helper: Round Summary Formatter
###########################################################
def format_round_summary(result):
    dealer_name = result["luigi_rank"].replace("_", " ").title()
    player_name = result["player_rank"].replace("_", " ").title()
    outcome = result["outcome"].upper()
    coins = result["coins"]

    return f"DEALER: {dealer_name}   🆚   PLAYER: {player_name}   🏆 {outcome} (💰 {coins})"


###########################################################
# Picture Poker View
###########################################################
class PicturePokerView(discord.ui.View):
    def __init__(self, game: PicturePoker, user_id: int, on_finish):
        super().__init__(timeout=None)
        self.game = game
        self.user_id = user_id
        self.selected_discards = set()
        self.on_finish = on_finish  # callback to Cog cleanup/restart

        ###########################################################
        # Card toggle buttons
        ###########################################################
        for i in range(5):
            btn = discord.ui.Button(
                label=f"Card {i+1}",
                style=discord.ButtonStyle.secondary,
                row=0,
                custom_id=f"poker_card_{i}",
            )
            btn.callback = self._make_toggle(i, btn)
            self.add_item(btn)

        ###########################################################
        # Action buttons
        ###########################################################
        submit_btn = discord.ui.Button(
            label="Submit Discards",
            style=discord.ButtonStyle.green,
            row=1,
            custom_id="submit_discards",
        )
        submit_btn.callback = self._submit
        self.add_item(submit_btn)

        stand_btn = discord.ui.Button(
            label="Stand",
            style=discord.ButtonStyle.blurple,
            row=1,
            custom_id="stand",
        )
        stand_btn.callback = self._stand
        self.add_item(stand_btn)

    ###########################################################
    # Toggle factory
    ###########################################################
    def _make_toggle(self, idx: int, btn: discord.ui.Button):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "Not your game!", ephemeral=True
                )
                return

            if idx in self.selected_discards:
                self.selected_discards.remove(idx)
                btn.style = discord.ButtonStyle.secondary
            else:
                self.selected_discards.add(idx)
                btn.style = discord.ButtonStyle.danger

            await interaction.response.edit_message(view=self)

        return callback

    ###########################################################
    # Submit discards
    ###########################################################
    async def _submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        await interaction.response.defer()
        msg = await interaction.original_response()

        if not self.selected_discards:
            content = make_game_header(
                interaction.user,
                "Picture Poker",
                active_bet=self.game.bet,
                stars_current=self.game.stars,
                dealer_action="❌ No cards selected to discard.",
            )
            img_bytes = render_board(self.game, reveal=False)
            await msg.edit(
                content=content,
                attachments=[discord.File(img_bytes, "poker.png")],
                view=self,
            )
            return

        discards = sorted(self.selected_discards)
        self.game.player_discard(discards)

        # A) show facedown cards
        img_hidden = render_board_with_hidden(self.game, hidden_player=discards)
        content = make_game_header(
            interaction.user,
            "Picture Poker",
            active_bet=self.game.bet,
            stars_current=self.game.stars,
            dealer_action="Your new cards are dealt facedown...",
        )
        await msg.edit(
            content=content,
            attachments=[discord.File(img_hidden, "poker.png")],
            view=self,
        )
        await asyncio.sleep(0.6)

        # B) flip cards one by one
        img_hidden.seek(0)
        base = Image.open(img_hidden).convert("RGBA")
        for idx, i in enumerate(discards):
            symbol = self.game.player_hand[i]
            gif = make_deal_flip_gif(self.game, i, symbol, base, dealer=False)
            content = make_game_header(
                interaction.user,
                "Picture Poker",
                active_bet=self.game.bet,
                stars_current=self.game.stars,
                dealer_action=f"Flipping your card {i+1}...",
            )
            await msg.edit(
                content=content,
                attachments=[discord.File(gif, f"flip_{i}.gif")],
                view=self,
            )
            await asyncio.sleep(0.6)

            still_hidden = discards[idx + 1 : ]
            new_bytes = render_board_with_hidden(self.game, hidden_player=still_hidden)
            new_bytes.seek(0)
            base = Image.open(new_bytes).convert("RGBA")

        # C) disable discard-related buttons
        for child in self.children:
            if "Card" in child.label or "Submit" in child.label:
                child.disabled = True

        final_png = render_board(self.game, reveal=False)
        content = make_game_header(
            interaction.user,
            "Picture Poker",
            active_bet=self.game.bet,
            stars_current=self.game.stars,
            dealer_action="Your redraw is complete. Press **Stand** to let Luigi play.",
        )
        await msg.edit(
            content=content,
            attachments=[discord.File(final_png, "poker.png")],
            view=self,
        )
        self.selected_discards.clear()

    ###########################################################
    # Stand logic (Luigi plays)
    ###########################################################
    async def _stand(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        await interaction.response.defer()
        msg = await interaction.original_response()

        # Luigi AI chooses which cards to discard
        counts = Counter(self.game.luigi_hand)
        keep = {s for s, c in counts.items() if c > 1}
        luigi_discards = [i for i, c in enumerate(self.game.luigi_hand) if c not in keep]
        self.game.luigi_discard()

        # A) Luigi's facedown cards
        img_hidden = render_board_with_hidden(self.game, hidden_dealer=luigi_discards)
        content = make_game_header(
            interaction.user,
            "Picture Poker",
            active_bet=self.game.bet,
            stars_current=self.game.stars,
            dealer_action="Luigi discards some cards...",
        )
        await msg.edit(
            content=content,
            attachments=[discord.File(img_hidden, "poker.png")],
            view=None,
        )
        await asyncio.sleep(0.6)

        # B) Flicker animation for Luigi
        base_board = Image.open(img_hidden).convert("RGBA")
        for idx, i in enumerate(luigi_discards):
            flicker_gif = make_discard_flicker_gif(self.game, i, base_board, dealer=True)
            content = make_game_header(
                interaction.user,
                "Picture Poker",
                active_bet=self.game.bet,
                stars_current=self.game.stars,
                dealer_action=f"Luigi discards card {i+1}...",
            )
            await msg.edit(
                content=content,
                attachments=[discord.File(flicker_gif, f"luigi_discard_{i}.gif")],
                view=None,
            )
            await asyncio.sleep(0.6)

            # update board state for remaining hidden cards
            if idx < len(luigi_discards) - 1:
                still_hidden = luigi_discards[idx + 1 :]
                base_board = Image.open(
                    render_board_with_hidden(self.game, hidden_dealer=still_hidden)
                ).convert("RGBA")

        await asyncio.sleep(0.3)

        # C) Final reveal
        try:
            result = self.game.resolve_round()
        except Exception as e:
            print(f"[ERROR] resolve_round() failed: {e}")
            return

        final_gif = make_final_reveal_gif(self.game)
        final_gif.seek(0)

        summary = format_round_summary(result)
        content = make_game_header(
            interaction.user,
            "Picture Poker",
            active_bet=self.game.bet,
            stars_current=result.get("stars", self.game.stars),
            round_summary=summary,
        )

        await msg.edit(
            content=content,
            attachments=[discord.File(final_gif, "final_reveal.gif")],
            view=None,
        )

        # D) Replay / Quit buttons
        replay_btn = discord.ui.Button(label="Play Again", style=discord.ButtonStyle.green)
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.user_id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            new_game = PicturePoker()
            new_game.start_round()
            new_view = PicturePokerView(new_game, self.user_id, self.on_finish)
            new_board = render_board(new_game, reveal=False)
            content = make_game_header(
                btn_inter.user,
                "Picture Poker",
                active_bet=new_game.bet,
                stars_current=new_game.stars,
                dealer_action="New game started! Select cards to discard then submit.",
            )
            await msg.edit(
                content=content,
                attachments=[discord.File(new_board, "poker.png")],
                view=new_view,
            )

        async def quit_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.user_id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            await msg.edit(content="Thanks for playing Picture Poker!", view=None)
            await self.on_finish(self.user_id)

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

        await msg.edit(content=content, view=replay_view)


###########################################################
# Factory
###########################################################
def make_poker_view(game: PicturePoker, user_id: int, on_finish) -> PicturePokerView:
    return PicturePokerView(game, user_id, on_finish)
