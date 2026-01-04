import discord
from discord.ext import commands
from discord import app_commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Say hello back to the user
    @app_commands.command(name="helllo", description="Says Hello back to the sender")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user.mention}!")


    # DM the user a message
    @app_commands.command(name="dm", description= "Dms the user what they typed")
    @app_commands.describe(message="The message you want to recieve")
    async def dm(self, interaction: discord.Interaction, message: str):
        await interaction.user.send(f"You said {message}")
        await interaction.response.send_message("Check your DM's :P", ephemeral=True)
async def setup(bot):
    await bot.add_cog(General(bot))