import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from helpers.roleChecks import *
from pathlib import Path
import json
import time
from typing import Optional

from constants import VOLUNTEER_VOTES_PATH, REQUESTED_ITEMS_PATH
from helpers.admin import admin_meta

VOTES_FILE = Path(VOLUNTEER_VOTES_PATH)
REQUESTED_ITEMS_FILE = Path(REQUESTED_ITEMS_PATH)

def now() -> int:
    return int(time.time())

def load_json(path: Path, default = {}):
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default

def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class RequestItemModal(discord.ui.Modal):
    def __init__(self, cog: "Workshops"):
        super().__init__(title="Request an Item")
        self.cog = cog

        self.request_item = discord.ui.TextInput(
            label="Item and Amount",
            placeholder="e.g. DDR5 RAM sticks (x2)",
            max_length=80,
            required=True
        )

        self.reason = discord.ui.TextInput(
            label="Reason for item",
            placeholder="Describe what the item will be used for",
            style=discord.TextStyle.paragraph,
            max_length=300,
            required=True
        )

        self.add_item(self.request_item)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        request = self.cog.create_item_request(
            guild_id = interaction.guild_id,
            requester_id = interaction.user.id,
            requester_tag = str(interaction.user),
            item = str(self.request_item.value).strip(),
            reason = str(self.reason.value).strip(),
            channel_id = interaction.channel_id
        )

        await self.cog.post_item_request(interaction.guild, request)

        await interaction.response.send_message(
            f"✅ Item request submitted! Your request ID is **#{request['id']}**",
            ephemeral=True
        )

class RequestItemView(discord.ui.View):
    def __init__(self, owner_id: int, requests: list[dict], title: str):
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.requests = requests
        self.title = title
        self.page = 0
        self.per_page = 2

    def page_count(self) -> int:
        if not self.requests:
            return 1
        return (len(self.requests) + self.per_page - 1) // self.per_page

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title)
        embed.set_footer(text=f"Page {self.page + 1} / {self.page_count()}")

        if not self.requests:
            embed.description = "Nothing here yet."
            return embed

        start = self.page * self.per_page
        chunk = self.requests[start:(start + self.per_page)]

        for r in chunk:
            status = r.get("status", "open")
            status_emoji = "🔴" if status == "open" else "✅"
            rid = r.get("id", "?")
            summary = r.get("summary", "No summary")
            reporter = r.get("reporter_tag", "unknown")
            created_at = r.get("created_at", 0)

            value = (
                f"**Status:** {status_emoji} {status}\n"
                f"**Reporter:** {reporter}\n"
                f"**Created:** <t:{int(created_at)}:R>\n"
            )

            if status != "open":
                closed_at = r.get("closed_rejected_at")
                closed_by = r.get("closed_rejected_by_tag", "unknown")
                if closed_at:
                    value += f"**Closed:** <t:{int(closed_at)}:R> by **{closed_by}**\n"
                note = (r.get("closed_rejected_note") or "").strip()
                if note:
                    value += f"**Note:** {note[:250]}\n"

            embed.add_field(name=f"#{rid} - {summary[:90]}", value=value, inline=False)

        return embed


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


    # Request item helpers

    def load_item_requests(self) -> dict:
        return load_json(REQUESTED_ITEMS_FILE, {"next_id": 1, "requests": []})

    def save_item_requests(self, data: dict) -> None:
        save_json(REQUESTED_ITEMS_FILE, data)

    def create_item_request(self, guild_id: Optional[int], requester_id: int, requester_tag: str, item: str, reason: str, channel_id: Optional[int]) -> dict:
        data = self.load_item_requests()
        rid = int(data.get("next_id", 1))
        data["next_id"] = rid + 1

        request = {
            "id": rid,
            "guild_id": guild_id,
            "status": "open",
            "item": item,
            "reason": reason,
            "requester_id": requester_id,
            "requester_tag": requester_tag,
            "created_at": now(),
            "created_in_channel_id": channel_id,

            "closed_rejected_at": None,
            "closed_rejected_by_id": None,
            "closed_rejected_by_tag": None,
            "closed_rejected_note": None
        }

        data["requests"].append(request)
        self.save_item_requests(data)
        return request

    async def post_item_request(self, guild: discord.Guild, request: dict):
        if not guild:
            return

        embed = discord.Embed(title=f"💻 New Item Request #{request['id']}")
        embed.add_field(name="Item", value=request["item"][:1024], inline=False)
        embed.add_field(name="Requester", value=f"<@{request['requester_id']}> ({request['requester_tag']})")

        reason = request["reason"]
        embed.add_field(name="Reason", value=reason, inline=False)

        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed, silent=True)


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


    # Requesting items to purchase for workshops

    @app_commands.command(name="requestitem", description="Request items to purchase for workshops")
    async def request_item(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RequestItemModal(self))

    @app_commands.command(name="requesteditems", description="View items requested to be purchased")
    @app_commands.describe(mine="Only show your requests", status="The status of the request")
    @app_commands.choices(status=[
        Choice(name="Open", value="open"),
        Choice(name="Closed", value="closed"),
        Choice(name="All", value="all")
    ])
    async def requested_items(self, interaction: discord.Interaction, mine: bool = False, status: Choice[str] = None):
        if status and status.value not in ("open", "closed", "all"):
            await interaction.response.send_message("Status must be: `Open`, `Closed`, or `All`.", ephemeral=True)
            return

        state = status.value if status else "all"

        data = self.load_item_requests()
        requests = data.get("requests", [])

        if mine:
            requests = [r for r in requests if int(r.get("requester_id", 0)) == interaction.user.id]
        
        if state != "all":
            requests = [r for r in requests if (r.get("status", "open")) == state]
        
        requests.sort(key=lambda r: int(r.get("created_at", 0)), reverse=True)

        title = "🖥️ Requested Items"
        if mine:
            title += " (yours)"
        title += f" - {state}"

        view = RequestItemView(self, owner_id=interaction.user.id, requests=requests, title=title)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Workshops(bot))