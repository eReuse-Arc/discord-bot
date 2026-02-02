import discord
from discord.ext import commands
from discord import app_commands
from constants import EREUSE_WEBSITE_URL

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Say hello back to the user
    @app_commands.command(name="hello", description="Says Hello back to the sender")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user.mention}!")


    # DM the user a message
    @app_commands.command(name="dm", description= "Dms the user what they typed")
    @app_commands.describe(message="The message you want to recieve")
    async def dm(self, interaction: discord.Interaction, message: str):
        await interaction.user.send(f"You said {message}")
        await interaction.response.send_message("Check your DM's :P", ephemeral=True)

    @app_commands.command(name="github", description="Where the bots code is (Feel free to contribute 😁)")
    async def github(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"### The github is [eReuse Bot]({'https://github.com/eReuse-Arc/discord-bot'}), you are extremely welcome to help develop any new features or fix other issues! 😁\n"
            f"or to open any [issues]({'https://github.com/eReuse-Arc/discord-bot/issues'})"
        )

    @app_commands.command(name="website", description="View the Arc eReuse Website")
    async def website(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="View The eReuse Website",
                style=discord.ButtonStyle.url,
                url=EREUSE_WEBSITE_URL,
            )
        )

        await interaction.response.send_message(
            "Click the button to view the amazing eReuse Website!\n"
            "This is where you can find the links to donate and request devices.",
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(General(bot))