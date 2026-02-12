import discord
from discord.ext import commands
from discord import app_commands, ui
from helpers.roleChecks import *
from pathlib import Path
import json
from datetime import datetime
from helpers.scraper import fetch_arc_event_data, fetch_image_bytes
from constants import SYDNEY_TZ
from constants import VOLUNTEER_VOTES_PATH
from helpers.admin import admin_meta

VOTES_FILE = Path(VOLUNTEER_VOTES_PATH)


def fmt_12h(dt: datetime) -> str:
    return dt.strftime("%I:%M%p").lstrip("0")



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
    
    @app_commands.command(name="createevent", description="Create a Discord Scheduled Event from an Arc event page.")
    @app_commands.describe(link="Arc event link")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["Events"],
        notes="Can be used to create a discord event from an Arc Event page"
    )
    async def createevent(self, interaction: discord.Interaction, link: str):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            return await interaction.followup.send("This command can only be used in a server.", ephemeral=True)

        try:
            data = await fetch_arc_event_data(link)

            event_name = data.title
            if data.week_label:
                event_name = f"{event_name} | {data.week_label}"


            desc = data.description.strip()
            extras = []
            if data.register_url:
                extras.append(f"Register: {data.register_url}")
            if data.location_url:
                extras.append(f"Map: {data.location_url}")
            extras.append(f"Arc page: {data.page_url}")
            full_desc = (desc + "\n\n" + "\n".join(extras)).strip()[:1000]

            image_bytes = await fetch_image_bytes(data.hero_image_url) if data.hero_image_url else None

            created = await interaction.guild.create_scheduled_event(
                name=event_name,
                description=full_desc,
                start_time=data.start_dt,
                end_time=data.end_dt,
                entity_type=discord.EntityType.external,
                location=data.location[:100],
                privacy_level=discord.PrivacyLevel.guild_only,
                image=image_bytes,
            )

            start_local = data.start_dt.astimezone(SYDNEY_TZ)
            end_local = data.end_dt.astimezone(SYDNEY_TZ)

            pretty = f"{start_local.strftime('%a %d %b %Y')}, {fmt_12h(start_local)}-{fmt_12h(end_local)}"


            lines = [
                f"✅ Created event: **{created.name}**",
                f"📅 {data.date_str}",
                f"🕒 {pretty} (Sydney)",
                f"📍 {data.location}",
            ]
            if data.location_url:
                lines.append(f"🗺️ {data.location_url}")
            lines.append(f"🔗 {created.url}")


            channel = interaction.guild.get_channel(WORKSHOP_CHANNEL_ID)

            embed = discord.Embed(
                title=created.name,
                description=data.description[:600] + ("…" if len(data.description) > 600 else ""),
            )

            embed.add_field(name="Date", value=data.date_str, inline=True)
            embed.add_field(
                name="Time",
                value=f"{fmt_12h(start_local)}-{fmt_12h(end_local)}",
                inline=True
            )
            embed.add_field(name="Location", value=data.location, inline=False)

            if data.hero_image_url:
                embed.set_image(url=data.hero_image_url)

            view = ui.View()
            view.add_item(ui.Button(label="View event", url=created.url))
            if data.register_url:
                view.add_item(ui.Button(label="Register", url=data.register_url))
            if data.location_url:
                view.add_item(ui.Button(label="Map", url=data.location_url))

            if channel:
                await channel.send(embed=embed, view=view)

            await interaction.followup.send("\n".join(lines), ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create event: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Workshops(bot))