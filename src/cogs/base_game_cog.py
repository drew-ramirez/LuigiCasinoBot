###########################################################
# File: base_game_cog.py
#
# Description: Shared utilities for game Cogs
# Gives wager prompt helpers and active game bookkeeping
# gonna be docstringing everything here since reusable
###########################################################

from typing import Any, Callable, Optional

import discord
from discord.ext import commands

from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_gif_pregame_banner, make_pregame_banner
from utils.visibility import CommandVisibility, resolve_command_visibility
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager

BetSelectedCallback = Callable[[discord.Interaction, int], Any]


class BaseGameCog(commands.Cog):
    """Base mixin for Luigi's Casino game Cogs"""

    def __init__(self, bot, game_name: str, log_label: Optional[str] = None):
        self.bot = bot
        self.game_name = game_name
        self.log_label = log_label or game_name
        self.metrics_game_key = self._compose_metric_key(self.log_label)
        self.active_games: dict[int, dict[str, Any]] = {}

    @staticmethod
    def _compose_metric_key(label: str) -> str:
        cleaned = "".join(ch for ch in label.lower() if ch.isalnum())
        return cleaned or "game"

    def log_command_invocation(
        self,
        interaction: discord.Interaction,
        command_name: str,
        *,
        immediate: bool = False,
    ) -> None:
        MetricsManager.record_command_event(
            interaction,
            command_name,
            game_key=self.metrics_game_key,
            immediate=immediate,
        )

    def log_game_start(
        self,
        interaction: discord.Interaction,
        command_name: str,
        *,
        bet_amount: Optional[int] = None,
        extra: Optional[dict[str, Any]] = None,
        game: Any | None = None,
        immediate: bool = True,
    ) -> Optional[Any]:
        session_id = MetricsManager.record_game_start(
            interaction,
            self.metrics_game_key,
            bet_amount=bet_amount,
            source_command=command_name,
            metadata=extra,
            immediate=immediate,
        )
        if game is not None and session_id is not None:
            setattr(game, "metrics_session_id", session_id)
        return session_id

    def resolve_visibility(self, interaction: discord.Interaction) -> CommandVisibility:
        return resolve_command_visibility(interaction, self.metrics_game_key)

    async def present_wager_menu(
        self,
        interaction: discord.Interaction,
        *,
        on_bet_selected: BetSelectedCallback,
        wager_options: Optional[list[int]] = None,
        prompt: Optional[str] = None,
        visibility: Optional[CommandVisibility] = None,
        ephemeral: Optional[bool] = None,
        layout: str = "embed",
    ) -> None:
        """Wager used by all game cogs"""
        player = interaction.user
        user_id = player.id
        username = player.name

        resolved_visibility = visibility or self.resolve_visibility(interaction)
        if ephemeral is None:
            ephemeral_flag = resolved_visibility.ephemeral
        else:
            ephemeral_flag = ephemeral

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral_flag)

        balance = EconomyManager.balance(user_id, username)

        view = BetSelectView(
            user_id,
            username,
            on_bet_selected,
            wager_options=wager_options or list(DEFAULT_WAGER_OPTIONS),
        )

        if layout == "gif":
            gif_banner = make_gif_pregame_banner(
                self.game_name, balance, prompt=prompt
            )
            await interaction.followup.send(
                content=gif_banner,
                view=view,
                ephemeral=ephemeral_flag,
            )
        else:
            banner = make_pregame_banner(self.game_name, balance, prompt=prompt)
            await interaction.followup.send(
                embed=banner,
                view=view,
                ephemeral=ephemeral_flag,
            )

    def register_active_game(
        self,
        user_id: int,
        *,
        game: Any,
        message: Optional[discord.Message] = None,
    ) -> None:
        """Track the running game session for cleanup"""
        self.active_games[user_id] = {
            "game": game,
            "message": message,
        }

    async def cleanup_game(self, user_id: int):
        """Remove tracked games once they end"""
        if user_id in self.active_games:
            self.active_games.pop(user_id, None)
            print(f"[{self.log_label}] Cleaned up game for {user_id}")
