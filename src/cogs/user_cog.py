###########################################################
# File: user_cog.py
#
# Description: Generic player-facing commands for Luigi's Casino
###########################################################

import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands
from economy.bank import Bank
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager
from utils.visibility import resolve_command_visibility
from casinogames.picturepoker.PicturePoker import PicturePoker
from utils.emoji_config import (
    get_cashout_emoji,
    get_cashout_component_emoji,
    get_coin_emoji,
    get_coin_component_emoji,
    get_star_emoji,
    get_star_component_emoji,
    picture_poker_emojis,
)

bank = Bank()
GAMES_EMOJI = "\N{GAME DIE}"


###########################################################
# Safe Send Utility
###########################################################
async def safe_send(
    interaction: discord.Interaction, *, ephemeral: bool = False, **kwargs
):
    # Safely send a message even if the interaction is already acknowledged
    try:
        if interaction.response.is_done():
            await interaction.followup.send(ephemeral=ephemeral, **kwargs)
        else:
            await interaction.response.send_message(ephemeral=ephemeral, **kwargs)
    except Exception as e:
        print(f"[ERROR] safe_send failed: {e}")


class UserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _picture_poker_reference() -> tuple[list[str], list[str]]:
        symbol_labels = {
            "cloud": "Lakitu's Cloud",
            "mushroom": "Super Mushroom",
            "flower": "Fire Flower",
            "luigi": "Luigi",
            "mario": "Mario",
            "star": "Star",
        }
        symbol_emojis = dict(picture_poker_emojis())

        ordered_symbols = sorted(
            PicturePoker.SYMBOL_ORDER.items(), key=lambda item: item[1]
        )
        symbol_lines: list[str] = []
        for idx, (symbol, _) in enumerate(ordered_symbols):
            label = symbol_labels.get(symbol, symbol.title())
            emoji = symbol_emojis.get(symbol, symbol_emojis.get(symbol.lower(), ""))
            qualifier = ""
            if idx == 0:
                qualifier = " (best)"
            elif idx == len(ordered_symbols) - 1:
                qualifier = " (worst)"
            symbol_lines.append(f"{emoji} {label}{qualifier}")

        ordered_hands = sorted(
            PicturePoker.HAND_RANKS.items(), key=lambda item: item[1], reverse=True
        )
        payout_lines: list[str] = []
        for hand_key, _ in ordered_hands:
            display = PicturePoker.HAND_NAMES.get(
                hand_key, hand_key.replace("_", " ").title()
            )
            if hand_key == "junk":
                payout_lines.append(
                    f"• {display}: no payout (only ties if both are junk)"
                )
                continue
            multiplier = PicturePoker.MULTIPLIER.get(hand_key, 0)
            payout_lines.append(f"• {display}: x{multiplier} payout")

        return symbol_lines, payout_lines

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("UserCog loaded.")

    ###########################################################
    # PLAYER COMMANDS
    ###########################################################

    @discord.app_commands.command(
        name="casino_profile", description="View your casino profile for Luigi's Casino"
    )
    async def profile(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "profile")
        # defer to acknowledge the command
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_profile")

        uid = interaction.user.id
        username = interaction.user.name

        # ensure user exists or create a new one
        record = EconomyManager.ensure_user(uid, username)

        balance = record.get("balance", 0)
        games_played = record.get("games_played", 0)
        coins_won = record.get("coins_won", 0)
        coins_lost = record.get("coins_lost", 0)
        biggest_cashout = record.get("biggest_cashout", 0)
        daily_streak = record.get("daily_claim_streak", 0)
        career_stars = record.get("career_stars_total", 0)

        # build the profile embed
        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Casino Profile",
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        embed.add_field(
            name="Casino Balance",
            value=f"{get_coin_emoji()} {balance:,} coins",
            inline=True,
        )
        embed.add_field(
            name="Games Played",
            value=f"{GAMES_EMOJI} {games_played:,}",
            inline=True,
        )
        embed.add_field(
            name="Career Stars",
            value=f"{get_star_emoji()} {career_stars:,}",
            inline=True,
        )

        embed.add_field(
            name="Daily Streak", value=f"⏲️ {daily_streak} days", inline=True
        )
        embed.add_field(
            name="Coins Won",
            value=f"📈{coins_won:,}",
            inline=True,
        )
        embed.add_field(
            name="Coins Lost",
            value=f"📉 {coins_lost:,}",
            inline=True,
        )
        embed.add_field(
            name="Largest Cashout",
            value=f"{get_cashout_emoji()} {biggest_cashout:,}",
            inline=False,
        )

        # send followup
        await interaction.followup.send(embed=embed, ephemeral=visibility.ephemeral)

    @discord.app_commands.command(
        name="casino_balance", description="Check your casino balance for Luigi's Casino"
    )
    async def balance(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "balance")
        # always defer early acknowledges immediately
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_balance")

        user = interaction.user
        user_id = user.id
        username = user.name

        record = EconomyManager.ensure_user(user_id, username)
        balance = record.get("balance", 0)

        # follow up
        await interaction.followup.send(
            f"{user.name}, your current balance is **{balance} coins**.",
            ephemeral=visibility.ephemeral,
        )

    @discord.app_commands.command(
        name="casino_pokerkey",
        description="Show Picture Poker symbol priority and hand payouts",
    )
    async def poker_key(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "pokerkey")
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_pokerkey")

        symbol_lines, payout_lines = self._picture_poker_reference()

        embed = discord.Embed(
            title="Picture Poker Rank Reference",
            description=(
                "Ties are settled via Symbol Priority\n"
                "Payouts multiply your bet when you beat Luigi."
            ),
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Symbol Priority (best to worst)",
            value="\n".join(symbol_lines),
            inline=False,
        )
        embed.add_field(
            name="Hand Payouts",
            value="\n".join(payout_lines),
            inline=False,
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=visibility.ephemeral,
        )

    @discord.app_commands.command(
        name="casino_pity", description="Gambled your life-savings? Luigi's got you."
    )
    async def pity(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "pity")
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_pity")

        user = interaction.user
        user_id = user.id
        username = user.name

        record = EconomyManager.ensure_user(user_id, username)
        balance = record.get("balance", 0)

        if balance > 5:
            await interaction.followup.send(
                f"{user.display_name}, your balance is **{balance} coins** - keep spinning!",
                ephemeral=visibility.ephemeral,
            )
            return

        new_balance = EconomyManager.grant(user_id, 100, username)
        await interaction.followup.send(
            f"{user.display_name}, Luigi tossed you **100 coins**. New balance: **{new_balance}**.",
            ephemeral=visibility.ephemeral,
        )

    @discord.app_commands.command(
        name="casino_music", description="Queue up Luigi's Casino soundtrack"
    )
    async def casino_music(self, interaction: discord.Interaction):
        MetricsManager.record_command_event(interaction, "casino_music")
        visibility = resolve_command_visibility(interaction, "music")

        music_url = "https://youtu.be/AqY4RtNeJOI?si=qUD9RQdktk2K9WDO"
        thumbnail_url = "https://img.youtube.com/vi/AqY4RtNeJOI/hqdefault.jpg"

        embed = discord.Embed(
            title="Luigi's Casino Radio",
            url=music_url,
            description=(
                "Ante Up the atmosphere with our favorite casino lounge music.\n"
                "[Click Here to play on YouTube](https://youtu.be/AqY4RtNeJOI?si=qUD9RQdktk2K9WDO)"
            ),
            color=discord.Color.gold(),
        )
        embed.set_image(url=thumbnail_url)
        await safe_send(
            interaction,
            embed=embed,
            ephemeral=visibility.ephemeral,
        )

    @discord.app_commands.command(
        name="casino_daily", description="Claim your daily coin bonus for Luigi's Casino"
    )
    async def daily(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "daily")
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_daily")
        uid = interaction.user.id
        username = interaction.user.name
        claim_info = EconomyManager.record_daily_claim(uid, username)

        # if not available, show time remaining, moved some stuff to economy manager
        if not claim_info.get("available", False):
            remaining = int(claim_info.get("seconds_remaining", 0))
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await safe_send(
                interaction,
                content=(
                    f"You've already claimed your daily reward. "
                    f"Come back in {hours}h {minutes}m."
                ),
                ephemeral=visibility.ephemeral,
            )
            return

        reward = 150
        streak = claim_info.get("streak", 1)
        EconomyManager.grant(uid, reward, username)

        await safe_send(
            interaction,
            content=(
                f"Daily bonus claimed! You received **{reward} coins**.\n"
                f"Daily streak: {streak} day{'s' if streak != 1 else ''}."
            ),
            ephemeral=visibility.ephemeral,
        )

    @discord.app_commands.command(
        name="casino_leaderboard", description="Show top casino players by coin balance for Luigi's Casino"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "leaderboard")
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_leaderboard")

        collection = EconomyManager.COLLECTION

        def resolve_name(record: dict) -> str:
            uid = record.get("user_id")
            user = self.bot.get_user(uid)
            if user is not None:
                return user.display_name
            return record.get("username") or f"User {uid}"

        def resolve_avatar(record: dict) -> str:
            uid = record.get("user_id")
            user = self.bot.get_user(uid)
            if user is not None:
                return user.display_avatar.url
            return "https://cdn.discordapp.com/embed/avatars/0.png"

        def build_entries(records: list[dict], metric: str, formatter) -> list[dict]:
            entries: list[dict] = []
            for record in records:
                value = record.get(metric, 0) or 0
                entries.append(
                    {
                        "name": resolve_name(record),
                        "value": formatter(value),
                        "avatar": resolve_avatar(record),
                    }
                )
            return entries

        datasets = {
            "balance": {
                "label": "Top 10 players with the highest coin balance.",
                "entries": build_entries(
                    list(collection.find().sort("balance", -1).limit(10)),
                    "balance",
                    lambda v: f"{v:,} coins",
                ),
                "select_label": "Coin Balance",
                "emoji": get_coin_component_emoji(),
            },
            "games": {
                "label": "Top 10 players with the most games played.",
                "entries": build_entries(
                    list(collection.find().sort("games_played", -1).limit(10)),
                    "games_played",
                    lambda v: f"{v:,}",
                ),
                "select_label": "Games Played",
                "emoji": GAMES_EMOJI,
            },
            "cashout": {
                "label": "Top 10 players with the largest cashout.",
                "entries": build_entries(
                    list(collection.find().sort("biggest_cashout", -1).limit(10)),
                    "biggest_cashout",
                    lambda v: f"{v:,}",
                ),
                "select_label": "Largest Cashout",
                "emoji": get_cashout_component_emoji(),
            },
        }

        bot_avatar = (
            self.bot.user.display_avatar.url  # type: ignore[attr-defined]
            if getattr(self.bot, "user", None) is not None
            else None
        )

        view = LeaderboardView(
            datasets,
            initial_key="balance",
            requester=interaction.user,
            title="🏆 Luigi's Casino Leaderboard",
            thumbnail_url=bot_avatar,
        )
        embed = view.build_embed()
        await interaction.followup.send(
            embed=embed, view=view, ephemeral=visibility.ephemeral
        )

    @discord.app_commands.command(
        name="casino_server_leaderboard",
        description="Show top casino players in this server for Luigi's Casino",
    )
    async def server_leaderboard(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await safe_send(
                interaction,
                content="This command is only available inside a server.",
                ephemeral=True,
            )
            return

        visibility = resolve_command_visibility(interaction, "server_leaderboard")
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_server_leaderboard")

        collection = EconomyManager.COLLECTION

        member_cache: dict[int, discord.Member] = {}

        async def resolve_member(uid: int) -> discord.Member | None:
            cached = member_cache.get(uid)
            if cached is not None:
                return cached
            member = guild.get_member(uid)
            if member is not None:
                member_cache[uid] = member
                return member
            try:
                member = await guild.fetch_member(uid)
            except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                return None
            member_cache[uid] = member
            return member

        async def build_entries(metric: str, formatter) -> list[dict]:
            entries: list[dict] = []
            cursor = collection.find().sort(metric, -1).limit(200)
            for record in cursor:
                if len(entries) >= 10:
                    break
                uid = record.get("user_id")
                if not isinstance(uid, int):
                    continue
                member = await resolve_member(uid)
                if member is None:
                    continue
                value = record.get(metric, 0) or 0
                entries.append(
                    {
                        "name": member.display_name,
                        "value": formatter(value),
                        "avatar": member.display_avatar.url,
                    }
                )
            return entries

        balance_entries = await build_entries(
            "balance", lambda v: f"{v:,} coins"
        )
        games_entries = await build_entries(
            "games_played", lambda v: f"{v:,}"
        )
        cashout_entries = await build_entries(
            "biggest_cashout", lambda v: f"{v:,}"
        )

        datasets = {
            "balance": {
                "label": "Top 10 players in this server with the highest\n coin balance.",
                "entries": balance_entries,
                "select_label": "Coin Balance",
                "emoji": get_coin_component_emoji(),
            },
            "games": {
                "label": "Top 10 players in this server with the most\n games played.",
                "entries": games_entries,
                "select_label": "Games Played",
                "emoji": GAMES_EMOJI,
            },
            "cashout": {
                "label": "Top 10 players in this server with the\n largest cashout.",
                "entries": cashout_entries,
                "select_label": "Largest Cashout",
                "emoji": get_cashout_component_emoji(),
            },
        }

        view = LeaderboardView(
            datasets,
            initial_key="balance",
            requester=interaction.user,
            title=f"🏆 {guild.name} Leaderboard",
            thumbnail_url=guild.icon.url if guild.icon else None,
        )
        embed = view.build_embed()
        await interaction.followup.send(
            embed=embed, view=view, ephemeral=visibility.ephemeral
        )

    @discord.app_commands.command(
        name="casino_help", description="Show help information for the casino games for Luigi's Casino"
    )
    async def help_cmd(self, interaction: discord.Interaction):
        visibility = resolve_command_visibility(interaction, "help")
        MetricsManager.record_command_event(interaction, "casino_help")
        embed = discord.Embed(
            title="📜 Luigi's Casino Help",
            description="Quick reference for available commands",
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="General Commands",
            value="\n".join(
                [
                    "**/casino_profile** - View your casino profile",
                    "**/casino_daily** - Claim your daily coin bonus",
                    "**/casino_leaderboard** - View the top players",
                    "**/casino_balance** - Check your coin balance",
                    "**/casino_pity** - Luigi fuels your addiction",
                    "**/casino_music** - Stream the casino soundtrack, Youtube Link",
                    "**/casino_animations** - Toggle animated vs static layout",
                ]
            ),
            inline=False,
        )

        embed.add_field(
            name="Game Commands",
            value="\n".join(
                [
                    "**/casino_memorymatch** - Face Down Match Pairs",
                    "**/casino_pairagone** - Match Pairs Till Deck's Gone",
                    "**/casino_luckystars** - 50/50 Card Game",
                    "**/casino_picturepoker** - Luigi's Picture Poker",
                    "**/casino_blackjack** - Traditional Blackjack",
                    "**/casino_pokerkey** - Picture Poker ranks & payouts guide",
                ]
            ),
            inline=False,
        )

        symbol_lines, payout_lines = self._picture_poker_reference()
        embed.add_field(
            name="Picture Poker Quick Reference",
            value=(
                f"{' → '.join(line.split(' ', 1)[0] for line in symbol_lines)}"
            ),
            inline=False,
        )

        await safe_send(
            interaction,
            embed=embed,
            ephemeral=visibility.ephemeral,
        )

    @discord.app_commands.command(
        name="casino_animations",
        description="Toggle whether casino games play full animations or use a condensed static layout for Luigi's Casino",
    )
    @app_commands.describe(
        mode="Use 'on for the animations or 'off' for static updates"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="On", value="enabled"),
            app_commands.Choice(name="Off", value="disabled"),
        ]
    )
    async def casino_animations(
        self,
        interaction: discord.Interaction,
        mode: app_commands.Choice[str],
    ):
        visibility = resolve_command_visibility(interaction, "casino_animations")
        await interaction.response.defer(ephemeral=visibility.ephemeral)
        MetricsManager.record_command_event(interaction, "casino_animations")

        enable = mode.value == "enabled"
        user = interaction.user
        EconomyManager.set_animations_enabled(user.id, enable, user.name)

        state = "enabled" if enable else "disabled"
        detail = (
            "Games will show animations with compatibe UI"
            if enable
            else "Games will show static updates with condensed UI."
        )

        await interaction.followup.send(
            f"Animation preference **{state}**. {detail}",
            ephemeral=visibility.ephemeral,
        )


class LeaderboardCategorySelect(discord.ui.Select):
    def __init__(self, parent: "LeaderboardView"):
        options = [
            discord.SelectOption(
                label=data["select_label"],
                value=key,
                emoji=data.get("emoji"),
                default=(key == parent.current_key),
            )
            for key, data in parent.datasets.items()
        ]
        super().__init__(placeholder="Choose a leaderboard", options=options)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.requester_id:
            await interaction.response.send_message(
                "Not your leaderboard!", ephemeral=True
            )
            return
        selected = self.values[0]
        self.parent_view.current_key = selected
        for option in self.options:
            option.default = option.value == selected
        await interaction.response.edit_message(
            embed=self.parent_view.build_embed(),
            view=self.parent_view,
        )


class LeaderboardView(discord.ui.View):
    def __init__(
        self,
        datasets: dict[str, dict],
        initial_key: str,
        requester: discord.User,
        *,
        title: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
    ):
        super().__init__(timeout=480)
        self.datasets = datasets
        self.current_key = initial_key
        self.requester_id = requester.id
        self.custom_title = title
        self.thumbnail_url = thumbnail_url
        self.select_component = LeaderboardCategorySelect(self)
        self.add_item(self.select_component)

    def build_embed(self) -> discord.Embed:
        data = self.datasets[self.current_key]
        # base embed
        embed = discord.Embed(
            title=self.custom_title or "🏆 Luigi's Casino Leaderboard",
            description=data["label"],
            color=discord.Color.gold(),
        )
        if self.thumbnail_url:
            embed.set_thumbnail(url=self.thumbnail_url)
        entries = data.get("entries", [])
        if entries:
            lines = []
            for i, entry in enumerate(entries, start=1):
                lines.append(f"**#{i}** {entry['name']} - {entry['value']}")
            leaderboard_text = "\n".join(lines)
            embed.add_field(name="\u200b", value=leaderboard_text, inline=False)
        else:
            embed.add_field(
                name="No players yet",
                value="Play some games to appear here!",
                inline=False,
            )

        embed.set_footer(text="Use the selector below to change the leaderboard.")
        return embed

    async def on_timeout(self) -> None:
        self.clear_items()


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(UserCog(bot))
