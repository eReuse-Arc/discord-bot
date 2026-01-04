import discord
from discord.ext import commands
from discord import app_commands
# from helpers.roleChecks import *

class Workshops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admintest", description="only admins can use")
    # @app_commands.check(isAdmin)
    async def adminTest(self, interaction: discord.Interaction):
        await interaction.response.send_message("You have admin permissions")


async def setup(bot):
    await bot.add_cog(Workshops(bot))