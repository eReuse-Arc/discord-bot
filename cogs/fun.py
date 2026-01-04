import discord
from discord.ext import commands
from discord import app_commands


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dance", description="Dances for you")
    async def dance(self, interaction: discord.Interaction):
        await interaction.response.send_message("[just for you](https://tenor.com/view/funny-animal-dancing-cat-cat-kitty-cute-gif-1879301708244436198)")


async def setup(bot):
    await bot.add_cog(Fun(bot))