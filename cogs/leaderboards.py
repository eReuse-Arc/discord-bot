from discord.ext import commands


class Leaderboards(commands.Cog):
    @commands.command(help="Shows the leaderboard")
    async def leaderboard(self, ctx):
        await ctx.send("Coming soon!")


async def setup(bot):
    await bot.add_cog(Leaderboards(bot))
