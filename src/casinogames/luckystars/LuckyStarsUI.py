###########################################################
# File: LuckyStarsUI.py
#
# Description: Discord UI controls and animations for Lucky Stars
###########################################################

import asyncio
import io

import discord

from casinogames.assetloader import load_memory_faces, load_memory_backs
from casinogames.luckystars.LuckyStars import LuckyStars
from casinogames.luckystars.LuckyStarsPrint import (
    make_slide_animation,
    render_lucky_board,
)
from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_game_header, make_gif_game_header
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager

faces = load_memory_faces()
backs = load_memory_backs()


class LuckyStarsView(discord.ui.View):
    def __init__(
        self,
        game: LuckyStars,
        player: discord.User,
        on_finish,
        *,
        animations_enabled: bool,
        wager_options=None,
        start_game_callback=None,
        message: discord.Message | None = None,
    ):
        super().__init__(timeout=None)
        self.game = game
        self.player = player
        self.on_finish = on_finish
        self.wager_options = (
            list(wager_options)
            if wager_options is not None
            else list(DEFAULT_WAGER_OPTIONS)
        )
        self.start_game_callback = start_game_callback
        self.msg = message
        self.animations_enabled = animations_enabled
        self._player_name = getattr(player, "name", "Unknown")
        self._star_streak = EconomyManager.star_bonus_count(
            player.id,
            LuckyStars.GAME_KEY,
            self._player_name,
        )

        self.left_button = LuckyStarsButton("Left", 0)
        self.right_button = LuckyStarsButton("Right", 1)

        self.add_item(self.left_button)
        spacer = discord.ui.Button(
            label="\u200b",  # zero-width space keeps Discord happy MUST HAVE DO NOT DELETE
            style=discord.ButtonStyle.grey,
            disabled=True,
        )
        self.add_item(spacer)
        self.add_item(self.right_button)

    ###########################################################
    # helpers
    ###########################################################
    def _board_file(self, *, reveal: bool = False, filename: str = "lucky.png") -> discord.File:
        board = render_lucky_board(self.game, reveal=reveal)
        board.seek(0)
        return discord.File(board, filename)

    def _annotate_action(self, action: str | None = None) -> str:
        multiplier = EconomyManager.star_bonus_multiplier(
            self._star_streak, LuckyStars.GAME_KEY
        )
        bonus_text = f"(⭐ bonus x{multiplier:.2f})"
        if action:
            return f"{action} | {bonus_text}"
        return bonus_text

    def _embed_payload(
        self, action: str | None = None, *, reveal: bool = False
    ) -> tuple[discord.Embed, list[discord.File]]:
        stats = {
            "active_bet": self.game.bet,
            "stars_current": self.game.stars,
            "dealer_action": self._annotate_action(action or "Pick a card!"),
        }
        embed = make_game_header(self.player, "Lucky Stars", stats)
        board_file = self._board_file(reveal=reveal)
        embed.set_image(url=f"attachment://{board_file.filename}")
        return embed, [board_file]

    def _header_text(self, action: str | None = None) -> str:
        stats = {
            "active_bet": self.game.bet,
            "stars_current": self.game.stars,
            "dealer_action": self._annotate_action(action or "Pick a card!"),
        }
        return make_gif_game_header(self.player, "Lucky Stars", stats)

    async def _disable_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and not child.disabled:
                child.disabled = True
        if self.msg:
            await self.msg.edit(view=self)

    async def _enable_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False
        if self.msg:
            await self.msg.edit(view=self)

    ###########################################################
    # main selection flow
    ###########################################################
    async def handle_pick(self, interaction: discord.Interaction, pos: int):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("Not your game!", ephemeral=True)
            return

        await interaction.response.defer()
        msg = self.msg or await interaction.original_response()
        self.msg = msg

        if self.game.picked is not None:
            return

        self.game.pick_card(pos)
        await self._disable_buttons()

        if self.animations_enabled:
            gif, _ = make_slide_animation(
                self.game, duration=70, tail_hold_ms=800
            )
            gif.seek(0)
            await msg.edit(
                content=self._header_text("Cards sliding into place..."),
                attachments=[discord.File(gif, f"luckystars_round{self.game.round}.gif")],
                view=self,
            )
            await asyncio.sleep(1.6)
        else:
            embed, files = self._embed_payload("Resolving your pick...", reveal=False)
            await msg.edit(
                content=None,
                embed=embed,
                attachments=files,
                view=self,
            )
            await asyncio.sleep(0.5)

        result = self.game.resolve_round()
        player_val = result["player_val"]
        dealer_val = result["dealer_val"]
        outcome = result["outcome"]

        summary = f"You got the {player_val}-star card. Dealer had {dealer_val}-star.\n"
        current_multiplier = EconomyManager.star_bonus_multiplier(
            self._star_streak, LuckyStars.GAME_KEY
        )
        streak_info: dict[str, float | int]

        if outcome == "win":
            base_payout = self.game.bet * 2
            payout = int(round(base_payout * current_multiplier))
            EconomyManager.payout(self.player.id, payout, self._player_name)
            summary += f"  You win {payout} coins!"
            session_id = getattr(self.game, "metrics_session_id", None)
            MetricsManager.record_game_result(
                session_id,
                result="win",
                payout=payout,
                net=int(payout - self.game.bet),
                metadata={
                    "player_card": player_val,
                    "dealer_card": dealer_val,
                    "round": self.game.round,
                },
            )
            setattr(self.game, "metrics_logged", True)
            streak_info = EconomyManager.adjust_star_bonus(
                self.player.id,
                LuckyStars.GAME_KEY,
                delta=1,
                username=self._player_name,
                career_increment=1,
            )
            self._star_streak = int(streak_info["stars"])
            self.game.stars = self._star_streak
        else:
            summary += "  You lose this round."
            session_id = getattr(self.game, "metrics_session_id", None)
            MetricsManager.record_game_result(
                session_id,
                result="loss",
                payout=0,
                net=int(-self.game.bet),
                metadata={
                    "player_card": player_val,
                    "dealer_card": dealer_val,
                    "round": self.game.round,
                },
            )
            setattr(self.game, "metrics_logged", True)
            if self._star_streak > 0:
                streak_info = EconomyManager.adjust_star_bonus(
                    self.player.id,
                    LuckyStars.GAME_KEY,
                    delta=-1,
                    username=self._player_name,
                )
                self._star_streak = int(streak_info["stars"])
            else:
                record = EconomyManager.ensure_user(self.player.id, self._player_name)
                streak_info = {
                    "stars": 0,
                    "career_total": record.get("career_stars_total", 0),
                    "multiplier": EconomyManager.star_bonus_multiplier(
                        0, LuckyStars.GAME_KEY
                    ),
                }
                self._star_streak = 0
            self.game.stars = self._star_streak

        if self.animations_enabled:
            await msg.edit(
                content=self._header_text(summary),
                attachments=[self._board_file(reveal=True)],
                view=None,
            )
        else:
            embed, files = self._embed_payload(summary, reveal=True)
            await msg.edit(
                content=None,
                embed=embed,
                attachments=files,
                view=None,
            )

        await self._show_replay(summary)

    ###########################################################
    # replay / quit menu
    ###########################################################
    async def _show_replay(self, summary: str):
        if self.on_finish is not None:
            await self.on_finish(self.player.id)

        if not self.msg:
            return

        replay_btn = discord.ui.Button(
            label="Play Again", style=discord.ButtonStyle.green
        )
        quit_btn = discord.ui.Button(label="Quit", style=discord.ButtonStyle.red)

        async def replay_cb(inter: discord.Interaction):
            if inter.user.id != self.player.id:
                await inter.response.send_message("Not your game!", ephemeral=True)
                return
            await inter.response.defer()
            if self.start_game_callback is None:
                await inter.response.send_message(
                    "Unable to start a new game right now.",
                    ephemeral=True,
                )
                return

            async def on_bet_selected(
                inner_inter: discord.Interaction, bet_amount: int
            ):
                initial_stars = EconomyManager.star_bonus_count(
                    self.player.id,
                    LuckyStars.GAME_KEY,
                    player_name,
                )
                await self.start_game_callback(
                    inner_inter,
                    bet_amount,
                    new_game=LuckyStars(
                        bet_amount,
                        initial_stars=initial_stars,
                    ),
                )

            player_name = getattr(self.player, "display_name", self.player.name)
            wager_view = BetSelectView(
                self.player.id,
                player_name,
                on_bet_selected,
                wager_options=self.wager_options,
            )

            await self.msg.edit(view=wager_view)

        async def quit_cb(inter: discord.Interaction):
            if inter.user.id != self.player.id:
                await inter.response.send_message("Not your game!", ephemeral=True)
                return
            await inter.response.defer()
            farewell = "Thanks for playing Lucky Stars!"
            if self.animations_enabled:
                await self.msg.edit(
                    content=self._header_text(farewell),
                    attachments=[self._board_file(reveal=True)],
                    view=None,
                )
            else:
                embed, files = self._embed_payload(farewell, reveal=True)
                await self.msg.edit(
                    content=None,
                    embed=embed,
                    attachments=files,
                    view=None,
                )
            if not getattr(self.game, "metrics_logged", False):
                session_id = getattr(self.game, "metrics_session_id", None)
                MetricsManager.record_game_result(
                    session_id,
                    result="quit",
                    payout=0,
                    net=0,
                    metadata={
                        "round": self.game.round,
                        "player_card": None,
                        "dealer_card": None,
                    },
                )
                setattr(self.game, "metrics_logged", True)

        replay_btn.callback = replay_cb
        quit_btn.callback = quit_cb

        replay_view = discord.ui.View()
        replay_view.add_item(replay_btn)
        replay_view.add_item(quit_btn)

        await self.msg.edit(view=replay_view)


class LuckyStarsButton(discord.ui.Button):
    def __init__(self, label: str, pos: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.pos = pos

    async def callback(self, interaction: discord.Interaction):
        view: LuckyStarsView = self.view  # type: ignore
        await view.handle_pick(interaction, self.pos)


def make_lucky_controls(
    game: LuckyStars,
    player: discord.User,
    on_finish,
    *,
    animations_enabled: bool,
    wager_options=None,
    start_game_callback=None,
    message: discord.Message | None = None,
) -> LuckyStarsView:
    return LuckyStarsView(
        game,
        player,
        on_finish,
        animations_enabled=animations_enabled,
        wager_options=wager_options,
        start_game_callback=start_game_callback,
        message=message,
    )
