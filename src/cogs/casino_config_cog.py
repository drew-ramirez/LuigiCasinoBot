###########################################################
# File: casino_config_cog.py
#
# Description: Admin-facing configuration commands for Luigi's Casino.
###########################################################

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import CasinoConfigManager
from config.settings import fallback_allowed_channels


from casinogames.registry import GAMES

GAME_COMMAND_CHOICES = [
    app_commands.Choice(name=game.command_label, value=key)
    for key, game in GAMES.items()
]


async def manager_role_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    guild = interaction.guild
    if guild is None:
        return []

    config = CasinoConfigManager.get_config(
        guild.id,
        fallback_channels=fallback_allowed_channels(),
    )
    query = (current or "").lower()

    choices: list[app_commands.Choice[str]] = []
    for role_id in sorted(config.manager_role_ids):
        role = guild.get_role(role_id)
        if role is None:
            continue
        if query and query not in role.name.lower():
            continue
        choices.append(app_commands.Choice(name=role.name, value=str(role.id)))
        if len(choices) >= 25:
            break

    return choices

async def ensure_manager(interaction: discord.Interaction) -> bool:
    guild = interaction.guild
    user = interaction.user
    if guild is None or not isinstance(user, discord.Member):
        raise app_commands.CheckFailure("This command can only be used inside a server.")

    client = interaction.client
    if isinstance(client, commands.Bot):
        if await client.is_owner(user):
            return True

    if guild.owner_id == user.id:
        return True

    if CasinoConfigManager.user_has_manager_access(user):
        return True

    raise app_commands.CheckFailure(
        "You need Manage Server permission or a configured casino manager role to use this command."
    )

manager_check = app_commands.check(ensure_manager)


def _format_channel_mention(guild: discord.Guild, channel_id: int) -> str:
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.abc.GuildChannel):
        return channel.mention
    return f"<#{channel_id}>"


def _floor_channels(guild, allowed):
    visible = [_format_channel_mention(guild, cid) for cid in sorted(allowed)
               if guild.get_channel(cid) is not None]
    if visible:
        return "\n".join(visible)
    if allowed:
        return "Use `/casino floor add` to assign channels in this server."
    return "None (commands run privately outside mapped channels)"


def _game_channels(guild, channel_map):
    lines = []
    for key, channel_id in sorted(channel_map.items()):
        channel = guild.get_channel(channel_id)
        if channel is not None:
            lines.append(f"`{key}` \N{RIGHTWARDS ARROW} {channel.mention}")
    return "\n".join(lines) or "Not configured"


def _manager_roles(guild, role_ids):
    visible = [guild.get_role(rid).mention for rid in sorted(role_ids)
               if guild.get_role(rid) is not None]
    if visible:
        return "\n".join(visible)
    return "Roles configured elsewhere (deleted or missing)." if role_ids else "None"


class CasinoConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    casino = app_commands.Group(
        name="casino",
        description="Configure Luigi's Casino behaviour for this server.",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )


    async def _build_config_embed(
        self, interaction: discord.Interaction
    ) -> discord.Embed:
        guild = interaction.guild
        assert guild is not None

        config = CasinoConfigManager.get_config(
            guild.id,
            fallback_channels=fallback_allowed_channels(),
        )

        embed = discord.Embed(
            title="Luigi's Casino Configuration",
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Casino Floor Channels (general/non-game visibility)",
            value=_floor_channels(guild, config.allowed_channels), inline=False,
        )
        embed.add_field(
            name="Game Channel Map", value=_game_channels(guild, config.channel_map),
            inline=False,
        )
        embed.add_field(
            name="Casino Manager Roles", value=_manager_roles(guild, config.manager_role_ids),
            inline=False,
        )

        if config.category_id:
            category = guild.get_channel(config.category_id)
            if isinstance(category, discord.CategoryChannel):
                category_value = category.mention
            else:
                category_value = f"<#{config.category_id}>"
        else:
            category_value = "Not set"

        embed.add_field(
            name="Casino Category",
            value=category_value,
            inline=False,
        )

        embed.add_field(
            name="Admin Commands",
            value="\n".join(
                [
                    "`/casino config` - show this help menu",
                    "`/casino set <game> <#channel>` - map a game to a public channel",
                    "`/casino unset <game>` - clear a game's public channel",
                    "`/casino floor add <#channel>` - add a general casino floor channel",
                    "`/casino floor remove <#channel>` - remove a floor channel",
                    "`/casino category [#category]` - [WIP] assign auto-setup category",
                    "`/casino role add <@role>` - add a casino manager role NOTE: If you have many roles, type the role name in the box",
                    "`/casino role remove <@role>` - remove a casino manager role",
                ]
            ),
            inline=False,
        )
        embed.set_footer(
            text="Casino configuration for this server."
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed

    @casino.command(name="config", description="Show the current casino configuration.")
    @manager_check
    async def show(self, interaction: discord.Interaction):
        embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @casino.command(
        name="set",
        description="Map a casino game to a specific channel for public sessions.",
    )
    @app_commands.describe(
        game="Game command to configure.",
        channel="Channel where the game should run publicly.",
    )
    @app_commands.choices(game=GAME_COMMAND_CHOICES)
    @manager_check
    async def set_channel(
        self,
        interaction: discord.Interaction,
        game: app_commands.Choice[str],
        channel: discord.TextChannel,
    ):
        guild = interaction.guild
        assert guild is not None

        CasinoConfigManager.set_channel_map(
            guild.id, command_key=game.value, channel_id=channel.id
        )
        #embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(
            f"Mapped `{game.value}` to {channel.mention}.",
            #embed=embed,
            ephemeral=True,
        )

    @casino.command(
        name="unset",
        description="Remove a mapped public channel for a casino game.",
    )
    @app_commands.describe(game="Game command to clear.")
    @app_commands.choices(game=GAME_COMMAND_CHOICES)
    @manager_check
    async def clear_channel(
        self,
        interaction: discord.Interaction,
        game: app_commands.Choice[str],
    ):
        guild = interaction.guild
        assert guild is not None

        CasinoConfigManager.set_channel_map(
            guild.id, command_key=game.value, channel_id=None
        )
        #embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(
            f"Cleared mapping for `{game.value}`.",
            #embed=embed,
            ephemeral=True,
    )

    floor = app_commands.Group(
        name="floor",
        description="Manage casino floor channels.",
        parent=casino,
        guild_only=True,
    )

    role = app_commands.Group(
        name="role",
        description="Manage casino manager roles.",
        parent=casino,
        guild_only=True,
    )

    @floor.command(name="add", description="Add a channel to the casino floor.")
    @manager_check
    async def add_floor(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild
        assert guild is not None

        CasinoConfigManager.add_allowed_channel(guild.id, channel.id)
        #embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(
            f"Added {channel.mention} to the casino floor.",
            #embed=embed,
            ephemeral=True,
        )

    @floor.command(
        name="remove", description="Remove a channel from the casino floor."
    )
    @manager_check
    async def remove_floor(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        guild = interaction.guild
        assert guild is not None

        CasinoConfigManager.remove_allowed_channel(guild.id, channel.id)
        #embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(
            f"Removed {channel.mention} from the casino floor.",
            #embed=embed,
            ephemeral=True,
        )

    @role.command(name="add", description="Add a casino manager role. NOTE: If you have many roles, type the role name in the box")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_role(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        guild = interaction.guild
        assert guild is not None

        CasinoConfigManager.add_manager_role(guild.id, role.id)
        #embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(
            f"Added {role.mention} as a casino manager.",
            #embed=embed,
            ephemeral=True,
        )

    @role.command(name="remove", description="Remove a casino manager role.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_role(
        self, interaction: discord.Interaction, role: str
    ):
        guild = interaction.guild
        assert guild is not None

        try:
            role_id = int(role)
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "Select a valid casino manager role from the suggestions.",
                ephemeral=True,
            )
            return

        config = CasinoConfigManager.get_config(
            guild.id,
            fallback_channels=fallback_allowed_channels(),
        )
        if role_id not in config.manager_role_ids:
            await interaction.response.send_message(
                "That role is not currently configured as a casino manager.",
                ephemeral=True,
            )
            return

        target_role = guild.get_role(role_id)
        if target_role is None:
            await interaction.response.send_message(
                "That role no longer exists in this server.",
                ephemeral=True,
            )
            CasinoConfigManager.remove_manager_role(guild.id, role_id)
            return

        CasinoConfigManager.remove_manager_role(guild.id, role_id)
        #embed = await self._build_config_embed(interaction)
        await interaction.response.send_message(
            f"Removed {target_role.mention} from casino managers.",
            #embed=embed,
            ephemeral=True,
        )

    @remove_role.autocomplete("role")
    async def _remove_role_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        return await manager_role_autocomplete(interaction, current)


    @casino.command(
        name="category",
        description="Remember a category to auto-create casino channels later.",
    )
    @manager_check
    async def set_category(
        self,
        interaction: discord.Interaction,
        category: Optional[discord.CategoryChannel] = None,
    ):
        guild = interaction.guild
        assert guild is not None

        category_id = category.id if category else None
        CasinoConfigManager.set_category(guild.id, category_id)
        #embed = await self._build_config_embed(interaction)
        if category:
            message = f"Set casino category to {category.mention}."
        else:
            message = "Cleared the saved casino category."
        await interaction.response.send_message(
            message,
            #embed=embed,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(CasinoConfigCog(bot))
