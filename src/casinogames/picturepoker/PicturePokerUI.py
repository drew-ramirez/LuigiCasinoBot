###########################################################
# File: PicturePokerUI.py
#
# Description: Discord UI controls for Picture Poker
# TODO: need to make a shorter msg.edit that has defaults,
# so we can just override what we want each time.
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
from utils.bet_selector import DEFAULT_WAGER_OPTIONS, BetSelectView
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager


###########################################################
# Helper: Round Summary Formatter
###########################################################
def format_round_summary(result, delta_symbol=""):
    dealer_name = result["luigi_rank"].replace("_", " ").title()
    player_name = result["player_rank"].replace("_", " ").title()
    outcome = result["outcome"].upper()
    delta_symbol = delta_symbol
    coins = result["coins"]
    return f"DEALER: {dealer_name}  🆚  PLAYER: {player_name} \n  🏆 {outcome} 💰  ({delta_symbol}{coins})"


###########################################################
# Picture Poker View
###########################################################
class PicturePokerView(discord.ui.View):
    def __init__(
        self,
        game: PicturePoker,
        user_id: int,
        on_finish,
        *,
        animations_enabled: bool,
        wager_options=None,
        start_game_callback=None,
        message: discord.Message | None = None,
    ):
        super().__init__(timeout=None)
        self.game = game
        self.user_id = user_id
        self.selected_discards = set()
        self.on_finish = on_finish  # callback to Cog cleanup/restart
        self.wager_options = wager_options or list(DEFAULT_WAGER_OPTIONS)
        self.start_game_callback = start_game_callback
        self.animations_enabled = animations_enabled
        self.msg = message

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
    # helpers
    ###########################################################
    def _header_payload(
        self,
        user: discord.abc.User,
        stats: dict,
        *,
        attachment_filename: str | None = None,
    ) -> tuple[str | None, discord.Embed | None]:
        if self.animations_enabled:
            return make_gif_game_header(user, "Picture Poker", stats), None
        embed = make_game_header(user, "Picture Poker", stats)
        if attachment_filename:
            embed.set_image(url=f"attachment://{attachment_filename}")
        return None, embed

    async def _apply_status(
        self,
        msg: discord.Message,
        user: discord.abc.User,
        stats: dict,
        attachments: list[discord.File] | None = None,
        *,
        view: discord.ui.View | None,
    ) -> None:
        attachment_filename = None
        if attachments:
            attachment_filename = attachments[0].filename
        content, embed = self._header_payload(
            user,
            stats,
            attachment_filename=attachment_filename,
        )
        edit_kwargs: dict[str, object] = {
            "content": content,
            "embed": embed,
            "view": view,
        }
        if attachments is not None:
            edit_kwargs["attachments"] = attachments
        await msg.edit(**edit_kwargs)

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
        msg = self.msg or await interaction.original_response()
        self.msg = msg

        def base_stats(extra=None):
            stats = {
                "active_bet": self.game.bet,
                "stars_current": self.game.stars,
            }
            if extra:
                stats.update(extra)
            return stats

        if not self.selected_discards:
            stats = base_stats({"dealer_action": "❌ No cards selected to discard."})
            img_bytes = render_board(self.game, reveal=False)
            file = discord.File(img_bytes, "poker.png")
            await self._apply_status(
                msg,
                interaction.user,
                stats,
                attachments=[file],
                view=self,
            )
            return

        discards = sorted(self.selected_discards)
        self.game.player_discard(discards)

        # A) show facedown cards
        img_hidden = render_board_with_hidden(self.game, hidden_player=discards)
        hidden_file = discord.File(img_hidden, "poker.png")
        stats = base_stats({"dealer_action": "Your new cards are dealt facedown..."})
        await self._apply_status(
            msg,
            interaction.user,
            stats,
            attachments=[hidden_file],
            view=self,
        )
        await asyncio.sleep(0.6 if self.animations_enabled else 0.25)

        # B) flip cards one by one
        base = None
        if self.animations_enabled:
            img_hidden.seek(0)
            base = Image.open(img_hidden).convert("RGBA")
        for idx, i in enumerate(discards):
            symbol = self.game.player_hand[i]
            stats = base_stats({"dealer_action": f"Flipping your card {i+1}..."})
            if self.animations_enabled and base is not None:
                gif = make_deal_flip_gif(self.game, i, symbol, base, dealer=False)
                file = discord.File(gif, f"flip_{i}.gif")
                await self._apply_status(
                    msg,
                    interaction.user,
                    stats,
                    attachments=[file],
                    view=self,
                )
                await asyncio.sleep(0.6)

                still_hidden = discards[idx + 1 :]
                next_board = render_board_with_hidden(
                    self.game, hidden_player=still_hidden
                )
                next_board.seek(0)
                base = (
                    Image.open(next_board).convert("RGBA")
                    if still_hidden
                    else None
                )
            else:
                still_hidden = discards[idx + 1 :]
                board_stream = render_board_with_hidden(
                    self.game, hidden_player=still_hidden
                )
                file = discord.File(board_stream, "poker.png")
                await self._apply_status(
                    msg,
                    interaction.user,
                    stats,
                    attachments=[file],
                    view=self,
                )
                await asyncio.sleep(0.25)

        # Disable discard-related buttons
        for child in self.children:
            if "Card" in child.label or "Submit" in child.label:
                child.disabled = True

        final_png = render_board(self.game, reveal=False)
        stats = base_stats(
            {
                "dealer_action": "Your redraw is complete.\n Press **Stand** to let Luigi play."
            }
        )
        final_file = discord.File(final_png, "poker.png")
        await self._apply_status(
            msg,
            interaction.user,
            stats,
            attachments=[final_file],
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
        msg = self.msg or await interaction.original_response()
        self.msg = msg

        def base_stats(extra=None):
            stats = {
                "active_bet": self.game.bet,
                "stars_current": self.game.stars,
            }
            if extra:
                stats.update(extra)
            return stats

        # Luigi discards
        counts = Counter(self.game.luigi_hand)
        keep = {s for s, c in counts.items() if c > 1}
        luigi_discards = [
            i for i, c in enumerate(self.game.luigi_hand) if c not in keep
        ]
        self.game.luigi_discard()

        # A) Luigi's facedown cards
        img_hidden = render_board_with_hidden(self.game, hidden_dealer=luigi_discards)
        hidden_file = discord.File(img_hidden, "poker.png")
        stats = base_stats({"dealer_action": "Luigi discards some cards..."})
        await self._apply_status(
            msg,
            interaction.user,
            stats,
            attachments=[hidden_file],
            view=None,
        )
        await asyncio.sleep(0.6 if self.animations_enabled else 0.25)

        # B) Flicker animation
        base_board = None
        if self.animations_enabled:
            img_hidden.seek(0)
            base_board = Image.open(img_hidden).convert("RGBA")
        for idx, i in enumerate(luigi_discards):
            stats = base_stats({"dealer_action": f"Luigi discards card {i+1}..."})
            if self.animations_enabled and base_board is not None:
                flicker_gif = make_discard_flicker_gif(
                    self.game, i, base_board, dealer=True
                )
                file = discord.File(flicker_gif, f"luigi_discard_{i}.gif")
                await self._apply_status(
                    msg,
                    interaction.user,
                    stats,
                    attachments=[file],
                    view=None,
                )
                await asyncio.sleep(0.6)
            else:
                board_stream = render_board_with_hidden(
                    self.game, hidden_dealer=luigi_discards
                )
                file = discord.File(board_stream, "poker.png")
                await self._apply_status(
                    msg,
                    interaction.user,
                    stats,
                    attachments=[file],
                    view=None,
                )
                await asyncio.sleep(0.25)

        await asyncio.sleep(0.3 if self.animations_enabled else 0.15)

        # C) Final reveal + payout logic
        try:
            result = self.game.resolve_round()
        except Exception as e:
            print(f"[ERROR] resolve_round() failed: {e}")
            return

        user = interaction.user
        coins = result.get("coins", 0)
        outcome = result.get("outcome", "").lower()
        bet_amount = result.get("bet", self.game.bet)
        delta_symbol = ""
        coins_display = coins

        if outcome == "win":
            payout_total = bet_amount + coins
            EconomyManager.payout(user.id, payout_total, user.name)
            delta_symbol = "+"
        elif outcome == "lose":
            delta_symbol = "-"
            coins_display = bet_amount
        else:
            EconomyManager.payout(user.id, bet_amount, user.name)
            coins_display = bet_amount
            delta_symbol = "+"

        summary_result = dict(result)
        summary_result["coins"] = coins_display

        summary = format_round_summary(summary_result, delta_symbol)

        stats = base_stats(
            {
                "stars_current": result.get("stars", self.game.stars),
                "dealer_action": summary,
                "active_bet": bet_amount,
            }
        )

        if self.animations_enabled:
            final_gif = make_final_reveal_gif(self.game)
            final_gif.seek(0)
            attachment = discord.File(final_gif, "final_reveal.gif")
        else:
            final_png = render_board(self.game, reveal=True)
            attachment = discord.File(final_png, "final_reveal.png")

        await self._apply_status(
            msg,
            interaction.user,
            stats,
            attachments=[attachment],
            view=None,
        )

        # D) Replay / Quit buttons
        replay_btn = discord.ui.Button(
            label="Play Again", style=discord.ButtonStyle.green
        )
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.user_id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()

            def make_wager_callback():
                new_game = PicturePoker()

                async def on_bet_selected(
                    inner_inter: discord.Interaction, bet_amount: int
                ):
                    if self.start_game_callback is None:
                        await inner_inter.response.send_message(
                            "Unable to start new game right now.", ephemeral=True
                        )
                        return

                    await self.start_game_callback(
                        inner_inter, bet_amount, new_game=new_game
                    )

                return on_bet_selected

            wager_view = BetSelectView(
                self.user_id,
                btn_inter.user.name,
                make_wager_callback(),
                wager_options=self.wager_options,
            )

            await msg.edit(view=wager_view)

        async def quit_cb(btn_inter: discord.Interaction):
            if btn_inter.user.id != self.user_id:
                await btn_inter.response.send_message("Not your game!", ephemeral=True)
                return
            await btn_inter.response.defer()
            stats = {
                "active_bet": self.game.bet,
                "stars_current": self.game.stars,
                "dealer_action": "Thanks for playing Picture Poker!",
            }
            await self._apply_status(
                msg,
                btn_inter.user,
                stats,
                attachments=None,
                view=None,
            )
            await self.on_finish(self.user_id)

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

        await msg.edit(view=replay_view)


###########################################################
# Factory
###########################################################
def make_poker_view(
    game: PicturePoker,
    user_id: int,
    on_finish,
    *,
    animations_enabled: bool,
    wager_options=None,
    start_game_callback=None,
    message: discord.Message | None = None,
) -> PicturePokerView:
    return PicturePokerView(
        game,
        user_id,
        on_finish,
        animations_enabled=animations_enabled,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
        message=message,
    )
