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
from utils.ui_embeds import make_pregame_banner
from economy.EconomyManager import EconomyManager

BetSelectedCallback = Callable[[discord.Interaction, int], Any]


class BaseGameCog(commands.Cog):
    """Base mixin for Luigi's Casino game Cogs"""

    def __init__(self, bot, game_name: str, log_label: Optional[str] = None):
        self.bot = bot
        self.game_name = game_name
        self.log_label = log_label or game_name
        self.active_games: dict[int, dict[str, Any]] = {}

    async def present_wager_menu(
        self,
        interaction: discord.Interaction,
        *,
        on_bet_selected: BetSelectedCallback,
        wager_options: Optional[list[int]] = None,
        prompt: Optional[str] = None,
        ephemeral: bool = True,
    ) -> None:
        """Wager used by all game cogs"""
        player = interaction.user
        user_id = player.id
        username = player.name

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)

        balance = EconomyManager.balance(user_id, username)

        view = BetSelectView(
            user_id,
            username,
            on_bet_selected,
            wager_options=wager_options or list(DEFAULT_WAGER_OPTIONS),
        )

        banner = make_pregame_banner(self.game_name, balance, prompt=prompt)
        await interaction.followup.send(
            content=banner,
            view=view,
            ephemeral=ephemeral,
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
