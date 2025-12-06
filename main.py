import discord
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
bot.remove_command("help")

@bot.event
async def setup_hook():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

@bot.event
async def on_ready():
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


@bot.command(help="Shows all the commands that exist")
async def help(ctx):
    embed = discord.Embed(
        title="Bot Commands",
        description="Here are all of the commands categories",
        color=discord.Color.green()
    )

    for cog_name, cog in bot.cogs.items():
        command_list = cog.get_commands()

        if not command_list:
            continue

        command_text = ""

        for command in command_list:
            if command.hidden:
                continue

            description = command.help or ""
            command_text += f"**{ctx.prefix}{command.name}** {command.signature}    - {description}\n"

        embed.add_field(
            name=cog_name,
            value=command_text,
            inline=False
        )
    await ctx.send(embed=embed)


bot.run(token, log_handler=handler, log_level=logging.DEBUG)