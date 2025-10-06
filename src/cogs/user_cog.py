###########################################################
# File: user_cog.py
#
# Description: Generic player-facing commands for Luigi’s Casino
###########################################################

import discord
import datetime
from discord.ext import commands
from economy.bank import Bank
from economy.EconomyManager import EconomyManager

bank = Bank()


class UserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # track when users last claimed their daily reward
        # TODO: prob gonna have to do this in DB later 
        self.last_daily_claim = {}

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("UserCog loaded.")

    ###########################################################
    # PLAYER COMMANDS
    ###########################################################

    @discord.app_commands.command(name="profile", description="View your casino profile")
    async def profile(self, interaction: discord.Interaction):
        uid = interaction.user.id
        username = interaction.user.name

        # ensure user exists or create a new one
        record = EconomyManager.ensure_user(uid, username)
        bal = record.get("balance", 0)

        # placeholder values — you can later hook in star tracking or per-game stats
        stars = record.get("stars", 0)
        games_played = record.get("games_played", 0)
        last_game = record.get("last_game", "—")

        msg = (
            f"🎩 **{interaction.user.display_name}'s Casino Profile**\n"
            f"💰 Coins: {bal}\n"
            f"⭐ Stars: {stars}\n"
            f"🎮 Games Played: {games_played}\n"
        )
        await interaction.response.send_message(msg, ephemeral=True)


    @discord.app_commands.command(name="balance", description="Check your casino balance.")
    async def balance(self, interaction: discord.Interaction):
        user = interaction.user
        user_id = user.id
        username = user.name

        record = EconomyManager.ensure_user(user_id, username)
        balance = record.get("balance", 0)

        await interaction.response.send_message(
            f"{user.mention}, your current balance is **{balance} coins**.",
            ephemeral=True
        )


    @discord.app_commands.command(name="daily", description="Claim your daily coin bonus")
    async def daily(self, interaction: discord.Interaction):
        uid = interaction.user.id
        username = interaction.user.name
        now = datetime.datetime.utcnow()
        last_claim = self.last_daily_claim.get(uid)

        # check if already claimed in the last 24 hours
        if last_claim and (now - last_claim).total_seconds() < 86400:
            remaining = 86400 - (now - last_claim).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await interaction.response.send_message(
                f"🕒 You’ve already claimed your daily reward. Come back in {hours}h {minutes}m.",
                ephemeral=True,
            )
            return

        # grant reward
        reward = 50
        EconomyManager.grant(uid, reward, username)
        self.last_daily_claim[uid] = now

        await interaction.response.send_message(
            f"💰 You claimed your daily bonus of **{reward} coins!**\n"
            f"See you again tomorrow, {interaction.user.display_name}.",
            ephemeral=True,
        )

    @discord.app_commands.command(name="leaderboard", description="Show top casino players by coin balance")
    async def leaderboard(self, interaction: discord.Interaction):
        # pull leaderboard data from Mongo instead of in-memory
        users = list(EconomyManager.COLLECTION.find().sort("balance", -1).limit(10))

        if not users:
            await interaction.response.send_message(
                "No leaderboard data available yet.", ephemeral=True
            )
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
            embed.add_field(name=f"#{i} {name}", value=f"💰 {coins} coins", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(name="help", description="Show help information for the casino games")
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
        await interaction.response.send_message(msg, ephemeral=True)


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(UserCog(bot))
