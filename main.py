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

VOLUNTEER_ROLE = "Volunteer"

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

# Say hello back to the user
@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")


# DM the user a message
@bot.command()
async def dm(ctx, *, msg):
    await ctx.author.send(f"You said {msg}")

@bot.command()
async def poll(ctx, *, question):
    embed = discord.Embed(title="Poll", description=question)
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("👍")
    await poll_message.add_reaction("👎")


# Give the user the volunteering role
@bot.command()
async def volunteer(ctx):
    role = discord.utils.get(ctx.guild.roles, name=VOLUNTEER_ROLE)

    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} has been given the {VOLUNTEER_ROLE} role :D")
    else:
        await ctx.send(f"The role {VOLUNTEER_ROLE} does not exist")

# Remove the volunteering role from the user
@bot.command()
async def quit(ctx):
    role = discord.utils.get(ctx.guild.roles, name=VOLUNTEER_ROLE)

    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f"{ctx.author.mention} has been given up on the {VOLUNTEER_ROLE} role :(")
    else:
        await ctx.send(f"The role {VOLUNTEER_ROLE} does not exist")


@bot.command()
@commands.has_role(VOLUNTEER_ROLE)
async def dance(ctx):
    await ctx.reply("[just for you](https://tenor.com/view/funny-animal-dancing-cat-cat-kitty-cute-gif-1879301708244436198)")

@dance.error
async def dance_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("Only volunteers can make me dance :P")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)