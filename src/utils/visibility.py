###################################################################
# File: visibility.py
#
# Description: Helpers for determining whether a command should
#              respond publicly or ephemerally based on guild config.
######################################################################

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import discord

from config import CasinoConfigManager, VisibilityDecision
from config.settings import fallback_allowed_channels


@dataclass
class CommandVisibility:
    is_public: bool
    home_channel_id: Optional[int]
    decision: VisibilityDecision

    @property
    def ephemeral(self) -> bool:
        return not self.is_public


def resolve_command_visibility(
    interaction: discord.Interaction,
    command_key: Optional[str],
) -> CommandVisibility:
    guild = interaction.guild
    channel_id = getattr(interaction, "channel_id", None)

    if guild is None:
        return CommandVisibility(
            is_public=False,
            home_channel_id=None,
            decision=VisibilityDecision(
                is_public=False,
                home_channel_id=None,
                config=CasinoConfigManager.get_config(
                    guild_id=0,
                    fallback_channels=fallback_allowed_channels(),
                ),
            ),
        )

    decision = CasinoConfigManager.resolve_visibility(
        guild_id=guild.id,
        channel_id=channel_id,
        command_key=command_key,
        fallback_channels=fallback_allowed_channels(),
    )

    return CommandVisibility(
        is_public=decision.is_public,
        home_channel_id=decision.home_channel_id,
        decision=decision,
    )
