###########################################################
# File: base_game_cog.py
#
# Description: Shared utilities for game Cogs
# Gives wager prompt helpers and active game bookkeeping
# gonna be docstringing everything here since reusable
###########################################################

import asyncio
from typing import Any, Callable, Optional, Dict

import discord
from discord.ext import commands

from utils.bet_selector import BetSelectView, DEFAULT_WAGER_OPTIONS
from utils.ui_embeds import make_gif_pregame_banner, make_pregame_banner
from utils.visibility import CommandVisibility, resolve_command_visibility
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager

BetSelectedCallback = Callable[[discord.Interaction, int], Any]
TimeoutMetadataCallback = Callable[[Any], dict[str, Any]]
CleanupPayload = Dict[str, Any]
CleanupRenderer = Callable[[str, Optional[discord.Colour]], Any]


class BaseGameCog(commands.Cog):
    """Base mixin for Luigi's Casino game Cogs"""

    DEFAULT_SESSION_TIMEOUT_SECONDS = 480

    def __init__(
        self,
        bot,
        game_name: str,
        log_label: Optional[str] = None,
        *,
        session_timeout_seconds: Optional[int] = None,
    ):
        self.bot = bot
        self.game_name = game_name
        self.log_label = log_label or game_name
        self.metrics_game_key = self._compose_metric_key(self.log_label)
        self.session_timeout_seconds = (
            self.DEFAULT_SESSION_TIMEOUT_SECONDS
            if session_timeout_seconds is None
            else session_timeout_seconds
        )
        self.active_games: dict[int, dict[str, Any]] = {}
        self._timeout_tasks: dict[int, asyncio.Task[Any]] = {}

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

    async def register_active_game(
        self,
        user_id: int,
        *,
        game: Any,
        message: Optional[discord.Message] = None,
        view: Optional[discord.ui.View] = None,
        timeout_metadata: Optional[TimeoutMetadataCallback] = None,
        cleanup_renderer: Optional[CleanupRenderer] = None,
    ) -> None:
        """Track the running game session for cleanup"""
        existing_entry = self.active_games.pop(user_id, None)
        if existing_entry:
            self._cancel_timeout(user_id)
            await self._abandon_active_game(
                user_id,
                existing_entry,
            )

        self.active_games[user_id] = {
            "game": game,
            "message": message,
            "view": view,
            "metadata": timeout_metadata,
            "cleanup_renderer": cleanup_renderer,
        }
        self._schedule_timeout(user_id)

    async def cleanup_game(self, user_id: int):
        """Remove tracked games once they end"""
        self._cancel_timeout(user_id)
        entry = self.active_games.pop(user_id, None)
        if entry:
            self._stop_view(entry.get("view"))
            print(f"[{self.log_label}] Cleaned up game for {user_id}")

    def _schedule_timeout(self, user_id: int) -> None:
        timeout = self.session_timeout_seconds
        if timeout is None or timeout <= 0:
            return
        self._cancel_timeout(user_id)
        task = asyncio.create_task(self._auto_timeout_game(user_id, timeout))
        self._timeout_tasks[user_id] = task

    def _cancel_timeout(self, user_id: int) -> None:
        task = self._timeout_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

    def _collect_timeout_metadata(
        self,
        game: Any,
        metadata_provider: Optional[TimeoutMetadataCallback] = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for attr in (
            "remaining_attempts",
            "session_stars",
            "stars",
            "round",
            "turn",
            "turns",
            "score",
        ):
            value = getattr(game, attr, None)
            if isinstance(value, (int, float, str)):
                metadata[attr] = value
        if metadata_provider is not None:
            try:
                extra = metadata_provider(game)
                if isinstance(extra, dict):
                    metadata.update(extra)
            except Exception as exc:  # pragma: no cover - defensive log
                print(
                    f"[{self.log_label}] Failed to gather timeout metadata: {exc}"
                )
        return metadata

    def _finalize_timeout_cleanup(
        self,
        user_id: int,
        entry: dict[str, Any],
        *,
        reason: str,
    ) -> None:
        current_entry = self.active_games.get(user_id)
        if current_entry is entry:
            self.active_games.pop(user_id, None)
            print(f"[{self.log_label}] {reason} game for {user_id}")

    async def _auto_timeout_game(self, user_id: int, timeout: int) -> None:
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(timeout)
            entry = self.active_games.get(user_id)
            if not entry:
                return
            game = entry.get("game")
            if game is None or getattr(game, "metrics_logged", False):
                return

            session_id = getattr(game, "metrics_session_id", None)
            metadata = self._collect_timeout_metadata(
                game,
                entry.get("metadata"),
            )
            metadata["timeout_after_seconds"] = timeout
            metadata["timeout_type"] = "auto"

            MetricsManager.record_game_timeout(
                session_id,
                metadata=metadata,
            )
            setattr(game, "metrics_logged", True)

            await self._finalize_session_message(
                entry,
                "Session timed out. Thanks for playing!",
                colour=discord.Colour.red(),
            )

            self._finalize_timeout_cleanup(
                user_id,
                entry,
                reason="Timed out",
            )
        except asyncio.CancelledError:
            raise
        finally:
            if self._timeout_tasks.get(user_id) is current_task:
                self._timeout_tasks.pop(user_id, None)

    async def _abandon_active_game(
        self,
        user_id: int,
        entry: dict[str, Any],
    ) -> None:
        game = entry.get("game")
        if game is not None and not getattr(game, "metrics_logged", False):
            metadata = self._collect_timeout_metadata(
                game,
                entry.get("metadata"),
            )
            metadata["timeout_type"] = "replaced"
            MetricsManager.record_game_timeout(
                getattr(game, "metrics_session_id", None),
                reason="abandoned",
                metadata=metadata,
            )
            setattr(game, "metrics_logged", True)

        await self._notify_abandoned_session(entry, user_id)
        print(f"[{self.log_label}] Abandoned game replaced for {user_id}")

    async def _notify_abandoned_session(
        self,
        entry: dict[str, Any],
        user_id: int,
    ) -> None:
        await self._finalize_session_message(
            entry,
            "New session detected, thanks for playing!",
            colour=discord.Colour.orange(),
        )

    @staticmethod
    def _stop_view(view: Optional[discord.ui.View]) -> None:
        if isinstance(view, discord.ui.View):
            for item in view.children:
                if hasattr(item, "disabled"):
                    item.disabled = True
            view.stop()

    async def _finalize_session_message(
        self,
        entry: dict[str, Any],
        status_message: str,
        *,
        colour: discord.Colour | None = None,
    ) -> None:
        view = entry.get("view")
        self._stop_view(view)
        message = entry.get("message") or getattr(view, "msg", None)
        if message is None:
            return

        payload = await self._render_cleanup_payload(entry, status_message, colour=colour)
        payload.setdefault("view", None)
        if "attachments" not in payload or payload.get("attachments") is None:
            payload["attachments"] = []

        try:
            await message.edit(**payload)
        except discord.NotFound:
            return
        except Exception as exc:  # pragma: no cover - best effort
            print(f"[{self.log_label}] Failed to apply cleanup message for {entry.get('game')}: {exc}")

    async def _render_cleanup_payload(
        self,
        entry: dict[str, Any],
        status_message: str,
        *,
        colour: discord.Colour | None = None,
    ) -> CleanupPayload:
        renderer = entry.get("cleanup_renderer")
        if renderer is not None:
            try:
                result = renderer(status_message, colour)
                if asyncio.iscoroutine(result):
                    result = await result
                if isinstance(result, dict):
                    embed_obj = result.get("embed")
                    if colour is not None and isinstance(embed_obj, discord.Embed):
                        embed_obj.colour = colour
                    return result
            except Exception as exc:  # pragma: no cover - best effort
                print(f"[{self.log_label}] Cleanup renderer failed: {exc}")

        embed = discord.Embed(
            description=status_message,
            colour=colour or discord.Colour.orange(),
        )
        return {"content": None, "embed": embed}
