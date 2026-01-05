import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path
from constants import CHALLENGE_POINTS_PATH


POINTS_FILE = Path(CHALLENGE_POINTS_PATH)

class Leaderboards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def load_points(self):
        if not POINTS_FILE.exists():
            return {}
        with open(POINTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def calculate_streak(self, weeks: list[int]) -> int:
        if not weeks:
            return 0

        weeks = sorted(set(weeks), reverse=True)
        streak = 1

        for i in range(len(weeks) - 1):
            if weeks[i] - 1 == weeks[i+1]:
                streak += 1
            else:
                break

        return streak

    @app_commands.command(name="inviteleaderboard", description="Shows the invite leaderboard")
    async def invite_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)


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
                name= "",
                value= f"**{user.mention}** - {count} invites",
                inline=False
            )

        await interaction.followup.send(embed=embed, silent=True)


    @app_commands.command(name="challengeleaderboard", description="Shows the weekly challenge points leaderboard")
    async def challenge_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = self.load_points()
        guild = interaction.guild

        leaderboard = []

        for user_id, weeks in data.items():
            member = guild.get_member(int(user_id))

            if not member:
                continue

            weeks = sorted({int(w) for w in weeks})
            streak = self.calculate_streak(weeks)

            leaderboard.append((member, len(weeks), streak, sorted(weeks)))

        if not leaderboard:
            await interaction.followup.send(
                "❌ No challenges have been completed :("
            )
            return

        leaderboard.sort(key = lambda x: (x[1], x[2]), reverse=True)

        embed = discord.Embed(
            title="🏆 **Challenge Leaderboard**",
            description="Top Challenge Participants",
            color=discord.Color.green()
        )

        for position, (member, points, streak, weeks) in enumerate(leaderboard[:10], start=1):
            embed.add_field(
                name=f"#{position}",
                value=(
                    f"{member.mention}\n"
                    f"**Points:** {points}\n"
                    f"**Streak:** {streak} weeks\n"
                    f"**Weeks**: {', '.join(map(str, weeks))}"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leaderboards(bot))
