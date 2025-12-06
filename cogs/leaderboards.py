import discord
from discord.ext import commands


class Leaderboards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(help="Shows the invite leaderboard")
    async def inviteleaderboard(self, ctx):
        invites = await ctx.guild.invites()

        invite_counts = {}

        for invite in invites:
            if invite.inviter:
                invite_counts[invite.inviter] = invite_counts.get(invite.inviter, 0) + invite.uses

        sorted_invites = sorted(invite_counts.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title="Invite Leaderboard 🏆",
            color=discord.Color.green()
        )

        for user, count in sorted_invites[:10]:
            embed.add_field(
                name= f"**{user.display_name}** - {count} invites",
                value= "",
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboards(bot))
