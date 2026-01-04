import discord
from discord.ext import commands
from discord import app_commands


class Leaderboards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name="inviteleaderboard", description="Shows the invite leaderboard")
    async def inviteLeaderboard(self, interaction: discord.Interaction):
        guild = interaction.guild
        invites = await guild.invites()

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

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboards(bot))
