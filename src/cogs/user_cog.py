###########################################################
# File: user_cog.py
#
# Description: Generic player-facing commands for Luigi's Casino
###########################################################

import discord
from discord import app_commands
from discord.ext import commands
from economy.bank import Bank
from economy.EconomyManager import EconomyManager
from metrics.metrics_manager import MetricsManager
from utils.visibility import resolve_command_visibility

bank = Bank()


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
        MetricsManager.record_command_event(interaction, "casino_profile")
        visibility = resolve_command_visibility(interaction, "profile")
        # defer to acknowledge the command
        await interaction.response.defer(ephemeral=visibility.ephemeral)

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
            name="casino_balance", value=f"💰 {balance:,} coins", inline=True
        )
        embed.add_field(name="Games Played", value=f"🎲 {games_played:,}", inline=True)
        embed.add_field(name="Career Stars", value=f"🌟 {career_stars:,}", inline=True)

        embed.add_field(
            name="Daily Streak", value=f"⏲️ {daily_streak} days", inline=True
        )
        embed.add_field(name="Coins Won", value=f"📈 {coins_won:,}", inline=True)
        embed.add_field(name="Coins Lost", value=f"📉 {coins_lost:,}", inline=True)
        embed.add_field(
            name="Largest Cashout", value=f"💸 {biggest_cashout:,}", inline=False
        )

        # send followup
        await interaction.followup.send(embed=embed, ephemeral=visibility.ephemeral)

    @discord.app_commands.command(
        name="casino_balance", description="Check your casino balance for Luigi's Casino"
    )
    async def balance(self, interaction: discord.Interaction):
        MetricsManager.record_command_event(interaction, "casino_balance")
        visibility = resolve_command_visibility(interaction, "balance")
        # always defer early acknowledges immediately
        await interaction.response.defer(ephemeral=visibility.ephemeral)

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
        name="casino_pity", description="Gambled your life-savings? Luigi's got you."
    )
    async def pity(self, interaction: discord.Interaction):
        MetricsManager.record_command_event(interaction, "casino_pity")
        visibility = resolve_command_visibility(interaction, "pity")
        await interaction.response.defer(ephemeral=visibility.ephemeral)

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
        name="casino_daily", description="Claim your daily coin bonus for Luigi's Casino"
    )
    async def daily(self, interaction: discord.Interaction):
        MetricsManager.record_command_event(interaction, "casino_daily")
        visibility = resolve_command_visibility(interaction, "daily")
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
        MetricsManager.record_command_event(interaction, "casino_leaderboard")
        visibility = resolve_command_visibility(interaction, "leaderboard")
        await interaction.response.defer(ephemeral=visibility.ephemeral)

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
                "emoji": "💰 ",
            },
            "games": {
                "label": "Top 10 players with the most games played.",
                "entries": build_entries(
                    list(collection.find().sort("games_played", -1).limit(10)),
                    "games_played",
                    lambda v: f"{v:,}",
                ),
                "select_label": "Games Played",
                "emoji": "🎲",
            },
            "cashout": {
                "label": "Top 10 players with the largest cashout.",
                "entries": build_entries(
                    list(collection.find().sort("biggest_cashout", -1).limit(10)),
                    "biggest_cashout",
                    lambda v: f"{v:,}",
                ),
                "select_label": "Largest Cashout",
                "emoji": "💰",
            },
        }

        view = LeaderboardView(
            datasets, initial_key="balance", requester=interaction.user
        )
        embed = view.build_embed()
        await interaction.followup.send(
            embed=embed, view=view, ephemeral=visibility.ephemeral
        )

    @discord.app_commands.command(
        name="casino_help", description="Show help information for the casino games for Luigi's Casino"
    )
    async def help_cmd(self, interaction: discord.Interaction):
        MetricsManager.record_command_event(interaction, "casino_help")
        visibility = resolve_command_visibility(interaction, "help")
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
                ]
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
        MetricsManager.record_command_event(interaction, "casino_animations")
        visibility = resolve_command_visibility(interaction, "casino_animations")
        await interaction.response.defer(ephemeral=visibility.ephemeral)

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
        self, datasets: dict[str, dict], initial_key: str, requester: discord.User
    ):
        super().__init__(timeout=120)
        self.datasets = datasets
        self.current_key = initial_key
        self.requester_id = requester.id
        self.select_component = LeaderboardCategorySelect(self)
        self.add_item(self.select_component)

    def build_embed(self) -> discord.Embed:
        data = self.datasets[self.current_key]
        # base embed
        embed = discord.Embed(
            title="🏆 Luigi's Casino Leaderboard",
            description=data["label"],
            color=discord.Color.gold(),
        )
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
