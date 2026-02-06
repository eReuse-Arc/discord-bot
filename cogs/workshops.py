import discord
from discord.ext import commands
from discord import app_commands
from helpers.roleChecks import *
from pathlib import Path
import json
from constants import VOLUNTEER_VOTES_PATH
from helpers.admin import admin_meta

VOTES_FILE = Path(VOLUNTEER_VOTES_PATH)

class Workshops(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def load_volunteer_votes(self):
        if not VOTES_FILE.exists():
            return {}
        with open(VOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_volunteer_votes(self, points):
        with open(VOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(points, f, indent=2, sort_keys=True)

    @app_commands.command(name="admintest", description="only admins can use")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
            ],
            notes= "Only gives a check for testing")
    async def adminTest(self, interaction: discord.Interaction):
        await interaction.response.send_message("You have admin permissions")

    @app_commands.command(name="votevolunteer", description="Vote for someone who you think deservers Volunteer of the Week")
    @app_commands.describe(user="Who you are voting for", week="What week you are voting in")
    async def vote_volunteer(self, interaction: discord.Interaction, user: discord.Member, week: int):
        await interaction.response.defer(ephemeral=True)

        voter_id = str(interaction.user.id)
        nominee_id = str(user.id)
        week_key = str(week)

        if voter_id == nominee_id:
            await interaction.followup.send(f"⚠️ You cannot vote for yourself")
            return

        votes = self.load_volunteer_votes()
        week_votes = votes.setdefault(week_key, {})
        user_votes = week_votes.setdefault(voter_id, [])

        if nominee_id in user_votes:
            await interaction.followup.send(f"⚠️ You already voted for {user.mention} this week")
            return

        user_votes.append(nominee_id)
        self.save_volunteer_votes(votes)

        challenges_cog = interaction.client.get_cog("Challenges")
        if challenges_cog:
            ctx = await challenges_cog.build_ctx(interaction.user)
            await challenges_cog.achievement_engine.evaluate(ctx)

        await interaction.followup.send(f"✅ You have voted for {user.mention} for **Volunteer of the Week** (Week {week}) 💚")


    @app_commands.command(name="votestats", description="Check the votes for volunteer of the week")
    @app_commands.describe(week="week number")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
            ],
            notes= "Can be used to help decide the VOTW, ensure the same person doesn't get it every week though")
    async def vote_stats(self, interaction: discord.Interaction, week: int):
        await interaction.response.defer()

        votes = self.load_volunteer_votes()
        week_key = str(week)

        if week_key not in votes:
            await interaction.followup.send(f"No votes recorded for week {week_key}")
            return

        counts = {}

        for _, nominees in votes[week_key].items():
            for uid in nominees:
                counts[uid] = counts.get(uid, 0) + 1

        if not counts:
            await interaction.followup.send(f"No votes recorded for week {week_key}")
            return

        lines = [f"## 📄 Volunteer Voting   -  Week {week}"]

        for uid, total in sorted(counts.items(), key = lambda x: x[1], reverse=True):
            member = interaction.guild.get_member(int(uid))
            name = member.mention if member else f"<@{uid}>"
            lines.append(f"**{name}**  -  {total} vote(s)")

        await interaction.followup.send("\n".join(lines), allowed_mentions=discord.AllowedMentions(users=False))


    @app_commands.command(name="myvotes", description="checks your votes for a specific week")
    @app_commands.describe(week="The week of voting to check")
    async def my_votes(self, interaction: discord.Interaction, week: int):
        await interaction.response.defer(ephemeral=True)

        voter_id = str(interaction.user.id)
        week_key = str(week)
        votes = self.load_volunteer_votes()


        if (week_key not in votes) or (voter_id not in votes[week_key]):
            await interaction.followup.send(f"❌ You have not submitted any votes for week {week}")
            return

        nominees = votes[week_key][voter_id]

        lines = [f"## 📄 Your Volunteer Votes  - Week {week}"]

        for uid in nominees:
            member = interaction.guild.get_member(int(uid))
            lines.append(member.mention if member else f"<@{uid}>")

        await interaction.followup.send("\n".join(lines), allowed_mentions=discord.AllowedMentions(users=False))

async def setup(bot):
    await bot.add_cog(Workshops(bot))