import discord
from discord.ext import commands
from constants import VOLUNTEER_ROLE

class Workshops(commands.Cog):
    # Give the user the volunteering role
    @commands.command(help="Gives the user the volunteer role")
    async def volunteer(self, ctx):
        role = discord.utils.get(ctx.guild.roles, name=VOLUNTEER_ROLE)

        if role:
            await ctx.author.add_roles(role)
            await ctx.send(f"{ctx.author.mention} has been given the {VOLUNTEER_ROLE} role :D")
        else:
            await ctx.send(f"The role {VOLUNTEER_ROLE} does not exist")

    # Remove the volunteering role from the user
    @commands.command(help= "Removes the volunteer role from the user")
    async def quit(self, ctx):
        role = discord.utils.get(ctx.guild.roles, name=VOLUNTEER_ROLE)

        if role:
            await ctx.author.remove_roles(role)
            await ctx.send(f"{ctx.author.mention} has been given up on the {VOLUNTEER_ROLE} role :(")
        else:
            await ctx.send(f"The role {VOLUNTEER_ROLE} does not exist")


async def setup(bot):
    await bot.add_cog(Workshops(bot))