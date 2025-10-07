###########################################################
# File: user_cog.py
#
# Description: Generic player-facing commands for Luigi’s Casino
###########################################################

import discord
from discord.ext import commands
from economy.bank import Bank
from economy.EconomyManager import EconomyManager

bank = Bank()

###########################################################
# Safe Send Utility
###########################################################
async def safe_send(interaction: discord.Interaction, **kwargs):
    # Safely send a message even if the interaction is already acknowledged
    try:
        if interaction.response.is_done():
            await interaction.followup.send(**kwargs)
        else:
            await interaction.response.send_message(**kwargs)
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
        name="profile", description="View your casino profile"
    )
    async def profile(self, interaction: discord.Interaction):
        uid = interaction.user.id
        username = interaction.user.name

        # ensure user exists or create a new one
        record = EconomyManager.ensure_user(uid, username)
        bal = record.get("balance", 0)

        # placeholder values  
        stars = record.get("stars", 0)
        games_played = record.get("games_played", 0)
        last_game = record.get("last_game", "—")

        msg = (
            f"🎩 **{interaction.user.display_name}'s Casino Profile**\n"
            f"💰 Coins: {bal}\n"
            f"⭐ Stars: {stars}\n"
            f"🎮 Games Played: {games_played}\n"
        )
        await safe_send(interaction, content=msg, ephemeral=True)

    @discord.app_commands.command(
        name="balance", description="Check your casino balance."
    )
    async def balance(self, interaction: discord.Interaction):
        user = interaction.user
        user_id = user.id
        username = user.name

        record = EconomyManager.ensure_user(user_id, username)
        balance = record.get("balance", 0)

        await safe_send(
            interaction,
            content=f"{user.mention}, your current balance is **{balance} coins**.",
            ephemeral=True,
        )

    @discord.app_commands.command(
        name="daily", description="Claim your daily coin bonus"
    )
    async def daily(self, interaction: discord.Interaction):
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
                ephemeral=True,
            )
            return

        reward = 100
        streak = claim_info.get("streak", 1)
        EconomyManager.grant(uid, reward, username)

        await safe_send(
            interaction,
            content=(
                f"💰 Daily bonus claimed! You received **{reward} coins**.\n"
                f"Daily streak: {streak} day{'s' if streak != 1 else ''}."
            ),
            ephemeral=True,
        )

    @discord.app_commands.command(
    name="leaderboard", description="Show top casino players by coin balance"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        collection = EconomyManager.COLLECTION

        def resolve_name(record: dict) -> str:
            uid = record.get('user_id')
            user = self.bot.get_user(uid)
            if user is not None:
                return user.display_name
            return record.get('username') or f'User {uid}'

        def build_entries(records: list[dict], metric: str, formatter) -> list[dict]:
            entries: list[dict] = []
            for record in records:
                value = record.get(metric, 0) or 0
                entries.append({
                    'name': resolve_name(record),
                    'value': formatter(value),
                })
            return entries

        datasets = {
            "balance": {
                "label": "Top 10 players with the highest coin balance.",
                "entries": build_entries(
                    list(collection.find().sort("balance", -1).limit(10)),
                    "balance",
                    lambda v: f"💰 Balance: {v:,} coins",
                ),
                "select_label": "Coin Balance",
                "emoji": "💰",
            },
            "games": {
                "label": "Top 10 players with the most games played.",
                "entries": build_entries(
                    list(collection.find().sort("games_played", -1).limit(10)),
                    "games_played",
                    lambda v: f"🎲 Games Played: {v:,}",
                ),
                "select_label": "Games Played",
                "emoji": "🎲",
            },
            "cashout": {
                "label": "Top 10 players with the largest cashout.",
                "entries": build_entries(
                    list(collection.find().sort("biggest_cashout", -1).limit(10)),
                    "biggest_cashout",
                    lambda v: f"💸 Largest Cashout: {v:,}",
                ),
                "select_label": "Largest Cashout",
                "emoji": "💸",
            },
        }

        view = LeaderboardView(datasets, initial_key="balance", requester=interaction.user)
        embed = view.build_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)




    @discord.app_commands.command(
        name="help", description="Show help information for the casino games"
    )
    async def help_cmd(self, interaction: discord.Interaction):
        msg = (
            "```markdown\n"
            "# 🎰 Luigi’s Casino Help Menu\n\n"
            "## 📜 General Commands\n"
            "/profile - view your casino profile\n"
            "/daily - claim a daily coin reward (every 24 hours)\n"
            "/leaderboard - view the top casino players\n"
            "/balance - check your current coin balance\n\n"
            "## 🎮 Game Commands\n"
            "/memory_start - play Memory Match (match pairs to earn coins)\n"
            "/pair_start - play Pair-a-Gone (clear the board by matching adjacent pairs)\n"
            "/lucky_start - play Lucky Stars (pick cards, test your luck)\n"
            "/poker_start - play Picture Poker (beat Luigi’s hand)\n"
            "```"
        )
        await safe_send(interaction, content=msg, ephemeral=True)


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
            await interaction.response.send_message("Not your leaderboard!", ephemeral=True)
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
    def __init__(self, datasets: dict[str, dict], initial_key: str, requester: discord.User):
        super().__init__(timeout=120)
        self.datasets = datasets
        self.current_key = initial_key
        self.requester_id = requester.id
        self.select_component = LeaderboardCategorySelect(self)
        self.add_item(self.select_component)

    def build_embed(self) -> discord.Embed:
        data = self.datasets[self.current_key]
        embed = discord.Embed(
            title="🏆 Luigi's Casino Leaderboard",
            description=data["label"],
            color=discord.Color.gold(),
        )
        entries = data.get("entries", [])
        if entries:
            for i, entry in enumerate(entries, start=1):
                embed.add_field(
                    name=f"#{i} {entry['name']}",
                    value=entry["value"],
                    inline=False,
                )
        else:
            embed.add_field(
                name="No players yet",
                value="Play some games to appear here!",
                inline=False,
            )
        embed.set_footer(text="Use the selector below to change the leaderboard")
        return embed

    async def on_timeout(self) -> None:
        self.clear_items()



###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(UserCog(bot))
