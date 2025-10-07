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
        # always defer FIRST prevents 'already acknowledged'
        await interaction.response.defer(ephemeral=True)

        users = list(EconomyManager.COLLECTION.find().sort("balance", -1).limit(10))

        if not users:
            await interaction.followup.send("No leaderboard data available yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 Luigi’s Casino Leaderboard",
            description="Top 10 players with the highest coin balance.",
            color=discord.Color.gold(),
        )

        for i, record in enumerate(users, start=1):
            uid = record.get("user_id")
            coins = record.get("balance", 0)
            user = self.bot.get_user(uid)
            name = user.display_name if user else record.get("username", f"User {uid}")
            coins_won = record.get("coins_won", 0)
            games_played = record.get("games_played", 0)
            biggest_cashout = record.get("biggest_cashout", 0)
            embed.add_field(
                name=f"#{i} {name}",
                value=(
                    f"💰 Balance: {coins:,} coins\n"
                    f"🎯 Games Played: {games_played:,}\n"
                    f"🏆 Coins Won: {coins_won:,}\n"
                    f"💸 Biggest Cashout: {biggest_cashout:,}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


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


###########################################################
# COG SETUP
###########################################################
async def setup(bot):
    await bot.add_cog(UserCog(bot))
