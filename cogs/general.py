import discord
from discord.ext import commands

class General(commands.Cog):
    # Say hello back to the user
    @commands.command(help="Says Hello back to the sender")
    async def hello(self, ctx):
        await ctx.send(f"Hello {ctx.author.mention}!")


    # DM the user a message
    @commands.command(help= "Dms the user what they typed")
    async def dm(self, ctx, *, msg):
        await ctx.author.send(f"You said {msg}")

    # Creates a basic embed poll
    @commands.command(help ="Creates a basic poll")
    async def poll(self, ctx, *, question):
        embed = discord.Embed(title="Poll", description=question)
        poll_message = await ctx.send(embed=embed)
        await poll_message.add_reaction("👍")
        await poll_message.add_reaction("👎")

async def setup(bot):
    await bot.add_cog(General(bot))