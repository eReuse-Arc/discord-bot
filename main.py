import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()

token = os.getenv('DISCORD_TOKEN')


handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_ready():
    guild = discord.Object(id=1446585420283646054)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"{bot.user.name} is up and running :D")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "ereuse" in message.content.lower():
        emoji = discord.utils.get(message.guild.emojis, name="eReuse")
        if emoji:
            try:
                await message.add_reaction(emoji)
            except Exception as e:
                print(f"Failed to react: {e}")

    await bot.process_commands(message)

@bot.tree.error
async def onAppCommandError(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure) or isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Sorry, you don't have permission to use this command", ephemeral=True)


bot.run(token, log_handler=handler, log_level=logging.DEBUG)