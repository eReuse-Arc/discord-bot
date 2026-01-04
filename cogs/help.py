import discord
from discord.ext import commands
from discord import app_commands
from collections import defaultdict


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    
    @app_commands.command(name="help", description="Show the avaliable commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="📖 Bot Commands",
            description="Here are all of the commands:",
            color=discord.Color.green()
        )
        
        grouped_commands = defaultdict(list)

        for command in self.bot.tree.walk_commands():
            try:
                await command._check_can_run(interaction)
            except app_commands.CheckFailure:
                continue

            cog_name = command.binding.__class__.__name__ if command.binding else "General"
            grouped_commands[cog_name].append(command)

        for cog_name, command_list in grouped_commands.items():
            value = ""

            for command in command_list:
                value += f"**/{command.name}** - {command.description}\n"

            embed.add_field(
                name = cog_name,
                value=value,
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Help(bot))