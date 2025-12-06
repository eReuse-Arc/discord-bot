from discord.ext import commands


class Fun(commands.Cog):
    @commands.command(help="Dances")
    async def dance(self, ctx):
        await ctx.reply("[just for you](https://tenor.com/view/funny-animal-dancing-cat-cat-kitty-cute-gif-1879301708244436198)")


async def setup(bot):
    await bot.add_cog(Fun(bot))