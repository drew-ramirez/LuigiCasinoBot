###########################################################
# File: admin_cog.py
#
# Description: Admin and utility commands for Luigi’s Casino
###########################################################

import discord
from discord.ext import commands
from economy.bank import Bank

bank = Bank()


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    ###########################################################
    # EVENTS
    ###########################################################

    @commands.Cog.listener()
    async def on_ready(self):
        print("AdminCog loaded.")

    ###########################################################
    # ADMIN COMMANDS
    ###########################################################

    @discord.app_commands.command(name="ping", description="Check if the bot is alive")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Don't Ping Me.", ephemeral=True)


    @discord.app_commands.command(name="balance", description="Check your coin balance")
    async def balance_cmd(self, interaction: discord.Interaction):
        bal = bank.balance(interaction.user.id)
        await interaction.response.send_message(
            f"{interaction.user.mention}, your balance is {bal} coins.", ephemeral=True
        )

    @discord.app_commands.command(name="grant", description="Grant yourself coins (admin/dev only)")
    async def grant_cmd(self, interaction: discord.Interaction, amount: int):
        new_bal = bank.grant(interaction.user.id, amount)
        await interaction.response.send_message(
            f"Granted {amount} coins. Your new balance is {new_bal}.", ephemeral=True
        )


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
