###########################################################
# File: admin_cog.py
#
# Description: Admin and utility commands for Luigi’s Casino
###########################################################

import discord
from discord.ext import commands
from economy.bank import Bank

bank = Bank()

# manager / developer role IDs
MANAGER_ROLES = {1140136411056590859, 1087723690285858836}


# create a decorator that checks for manager roles
def manager_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        return any(r.id in MANAGER_ROLES for r in getattr(interaction.user, "roles", []))
    return discord.app_commands.check(predicate)


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
    # ADMIN COMMANDS (ROLE LOCKED)
    ###########################################################

    @discord.app_commands.command(name="ping", description="Check if the bot is alive")
    @manager_only()
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Don't Ping Me.", ephemeral=True)

    @discord.app_commands.command(name="grant", description="Grant yourself coins (admin/dev only)")
    @manager_only()
    async def grant_cmd(self, interaction: discord.Interaction, amount: int):
        new_bal = bank.grant(interaction.user.id, amount)
        await interaction.response.send_message(
            f"Granted {amount} coins. Your new balance is {new_bal}.", ephemeral=True
        )

    ###########################################################
    # ERROR HANDLER
    ###########################################################

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "🚫 You don't have permission to use admin commands.", ephemeral=True
            )


###########################################################
# COG SETUP
###########################################################

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
