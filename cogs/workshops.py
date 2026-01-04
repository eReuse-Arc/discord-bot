import discord
from discord.ext import commands
from discord import app_commands
from helpers.roleChecks import *

class Workshops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admintest", description="only admins can use")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def adminTest(self, interaction: discord.Interaction):
        await interaction.response.send_message("You have admin permissions")


async def setup(bot):
    await bot.add_cog(Workshops(bot))