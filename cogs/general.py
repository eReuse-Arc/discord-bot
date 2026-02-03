import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from constants import EREUSE_WEBSITE_URL
from pathlib import Path
import json
import time
from typing import Optional
from constants import MODERATOR_ONLY_CHANNEL_ID, BUGS_PATH, BUGS_RESOLVED
from helpers.stats import StatsStore
from helpers.achievement_engine import AchievementEngine
from helpers.admin import admin_meta

BUGS_FILE = Path(BUGS_PATH)

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


class BugReportModal(discord.ui.Modal):
    def __init__(self, cog: "General"):
        super().__init__(title="Report a Bug")
        self.cog = cog

        self.summary = discord.ui.TextInput(
            label="Short Summary",
            placeholder="e.g. /trade command doesn't trade items",
            max_length=80,
            required=True
        )
        
        self.details = discord.ui.TextInput(
            label="What happened? Steps to reproduce + expected vs actual",
            placeholder=(
                "Steps:\n"
                "1) ...\n"
                "2) ...\n\n"
                "Expected:\n"
                "Actual:\n"
            ),
            style=discord.TextStyle.paragraph,
            max_length=1500,
            required=True
        )

        self.add_item(self.summary)
        self.add_item(self.details)
    
    async def on_submit(self, interaction: discord.Interaction):
        report = self.cog.create__bug_report(
            guild_id = interaction.guild_id,
            reporter_id = interaction.user.id,
            reporter_tag = str(interaction.user),
            summary = str(self.summary.value).strip(),
            details = str(self.details.value).strip(),
            channel_id = interaction.channel_id
        )
        
        await interaction.response.send_message(
            f"✅ Bug report submitted! Your report ID is **#{report['id']}**",
            ephemeral=True
        )


class BugView(discord.ui.View):
    def __init__(self, cog: "General", owner_id: int, bugs: list[dict], title: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id
        self.bugs = bugs
        self.title = title
        self.page = 0
        self.per_page = 2

    def page_count(self) -> int:
        if not self.bugs:
            return 1
        return (len(self.bugs) + self.per_page - 1) // self.per_page

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title)
        embed.set_footer(text=f"Page {self.page + 1} / {self.page_count()}")

        if not self.bugs:
            embed.description = "Nothing here yet."
            return embed

        start = self.page * self.per_page
        chunk = self.bugs[start:(start + self.per_page)]

        for b in chunk:
            status = b.get("status", "open")
            status_emoji = "🔴" if status == "open" else "✅"
            rid = b.get("id", "?")
            summary = b.get("summary", "No summary")
            reporter = b.get("reporter_tag", "unknown")
            created_at = b.get("created_at", 0)

            value = (
                f"**Status:** {status_emoji} {status}\n"
                f"**Reporter:** {reporter}\n"
                f"**Created:** <t:{int(created_at)}:R>\n"
            )

            if status != "open":
                fixed_at = b.get("fixed_at")
                fixed_by = b.get("fixed_by_tag", "unknown")
                if fixed_at:
                    value += f"**Fixed:** <t:{int(fixed_at)}:R> by **{fixed_by}**\n"
                note = (b.get("fix_note") or "").strip()
                if note:
                    value += f"**Note:** {note[:250]}\n"

            embed.add_field(name=f"#{rid} - {summary[:90]}", value=value, inline=False)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_id

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % self.page_count()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % self.page_count()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(view=None)


class General(commands.Cog):
    def __init__(self, bot, stats_store: StatsStore, achievement_engine: AchievementEngine):
        self.bot = bot
        self.stats_store = stats_store
        self.achievement_engine = achievement_engine

    def load_bugs(self) -> dict:
        return load_json(BUGS_FILE, {"next_id": 1, "bugs": []})

    def save_bugs(self, data: dict) -> None:
        save_json(BUGS_FILE, data)
    
    def create_bug_report(self, guild_id: Optional[int], reporter_id: int, reporter_tag: str, summary: str, details: str, channel_id: Optional[int]) -> dict:
        data = self.load_bugs()
        rid = int(data.get("next_id", 1))
        data["next_id"] = rid + 1
        
        report = {
            "id": rid,
            "guild_id": guild_id,
            "status": "open",
            "summary": summary,
            "details": details,
            "reporter_id": reporter_id,
            "reporter_tag": reporter_tag,
            "created_at": now(),
            "created_in_channel_id": channel_id,

            "fixed_at": None,
            "fixed_by_id": None,
            "fixed_by_tag": None,
            "fix_note": None
        }

        data["bugs"].append(report)
        self.save_bugs(data)
        return report
    
    async def log_action(self, guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

    async def post_bug(self, guild: discord.Guild, report: dict):
        if not guild:
            return
        
        embed = discord.Embed(title="🐛 New Bug Report #{'id}")
        embed.add_field(name="Summary", value=report["Summary"][:1024], inline=False)
        embed.add_field(name="Reporter", value=f"<@{report['reporter_id']}> ({report['reporter_tag']})")

        details = report["details"]
        if len(details) > 1500:
            details = details[:1500] + "..."
        embed.add_field(name="Details", value=details, inline=False)

        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed, silent=True)
    
    def find_bug(self, rid: int) -> Optional[dict]:
        data = self.load_bugs()
        for b in data.get("bugs", []):
            if int(b.get("id", -1)) == int(rid):
                return b
        return None
    
    def update_bug(self, updated_bug: dict) -> None:
        data = self.load_bugs()
        bugs = data.get("bugs", [])
        for i, b in enumerate(bugs):
            if int(b.get("id", -1)) == int(updated_bug.get("id", -2)):
                bugs[i] = updated_bug
                break
        data["bugs"] = bugs
        self.save_bugs(data)

    # Say hello back to the user
    @app_commands.command(name="hello", description="Says Hello back to the sender")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user.mention}!")


    # DM the user a message
    @app_commands.command(name="dm", description= "Dms the user what they typed")
    @app_commands.describe(message="The message you want to recieve")
    async def dm(self, interaction: discord.Interaction, message: str):
        await interaction.user.send(f"You said {message}")
        await interaction.response.send_message("Check your DM's :P", ephemeral=True)

    @app_commands.command(name="github", description="Where the bots code is (Feel free to contribute 😁)")
    async def github(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"### The github is [eReuse Bot]({'https://github.com/eReuse-Arc/discord-bot'}), you are extremely welcome to help develop any new features or fix other issues! 😁\n"
            f"or to open any [issues]({'https://github.com/eReuse-Arc/discord-bot/issues'})"
        )

    @app_commands.command(name="website", description="View the Arc eReuse Website")
    async def website(self, interaction: discord.Interaction):
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="View The eReuse Website",
                style=discord.ButtonStyle.url,
                url=EREUSE_WEBSITE_URL,
            )
        )

        await interaction.response.send_message(
            "Click the button to view the amazing eReuse Website!\n"
            "This is where you can find the links to donate and request devices.",
            view=view,
            ephemeral=True
        )


    @app_commands.command(name="bug", description="report a bug to the admins")
    async def bug_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BugReportModal(self))
    
    @app_commands.command(name="bugs", description="View bug reports")
    @app_commands.describe(mine="Only show your reports", status="The status of the bug")
    @app_commands.choices(status=[
        Choice(name="Open", value="open"),
        Choice(name="Fixed", value="fixed"),
        Choice(name="All", value="all")
    ])
    async def bugs_cmd(self, interaction: discord.Interaction, mine: bool = False, status: Choice[str] = None):
        
        if status and status not in ("open", "fixed", "all"):
            await interaction.response.send_message("Status must be: `Open`, `Fixed`, or `All`.")
            return

        state = status.value if status else "all"

        data = self.load_bugs()
        bugs = data.get("bugs", [])

        if mine:
            bugs = [b for b in bugs if int(b.get("reporter_id", 0)) == interaction.user.id]
        
        if state != "all":
            bugs = [b for b in bugs if (b.get("status", "open")) == state]
        
        bugs.sort(key=lambda b: int(b.get("created_at", 0)), reverse=True)

        title = "🐛 Bug Reports"
        if mine:
            title += " (yours)"
        title += f" - {status}"

        view = BugView(self, owner_id=interaction.user.id, bugs=bugs, title=title)
        await interaction.response.send_message(embed=view.build_embed, view=view, ephemeral=True)
    
    @app_commands.command(name="bugfix", description="Mark a bug as fixed and reward the reported")
    @app_commands.describe(id="The bug report id number", note="Optional resolution area")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["Bug Data", "Achievements"],
        notes="Once a bug has been fixed, mark it off here and give stats to the reported"
    )
    async def bug_fix(self, interaction: discord.Interaction, id: int, note: str = ""):
        data = self.load_bugs()
        bugs = data.get("bugs", [])
        target = None
        for b in bugs:
            if int(b.get("id", -1)) == int(id):
                target = b
                break
        
        if not target:
            await interaction.response.send_message(f"Could not find bug **#{id}**.")
            return
        
        if target.get("status") == "fixed":
            await interaction.response.send_message(f"Bug **#{id}** has already been marked as fixed.")
            return

        target["status"] = "fixed"
        target["fixed_at"] = now()
        target["fixed_by_id"] = interaction.user.id
        target["fixed_by_tag"] = str(interaction.user)
        target["fix_not"] = (note or "").strip()[:800] or None

        self.update_bug(target)

        reporter_id = int(target.get("reporter_id", 0))
        reporter_member = interaction.guild.get_member(reporter_id)

        msg = f"✅ Marked bug **#{id}** as fixed."
        if reporter_id:
            msg += f" Reporter: <@{reporter_id}>"
        self.log_action(interaction.guild, msg)

        if reporter_member:
            try:
                dm = discord.Embed(title=f"✅ Your bug report #{id} was fixed!")
                dm.add_field(name="Summary", value=target.get("summary", "")[:1024], inline=False)
                if target.get("fix_note"):
                    dm.add_field(name="Note", value=target["fix_note"][:1024], inline=False)
                await reporter_member.send(embed=dm)
            except Exception:
                pass


        try:
            self.stats_store.bump(str(reporter_id), BUGS_RESOLVED, 1)
        except Exception:
            pass

        if reporter_member:
            try:
                challenges = self.bot.get_cog("Challenges")
                ctx = challenges.build_ctx(reporter_member)

                await self.achievement_engine.evaluate(ctx)
            except Exception:
                pass



async def setup(bot, stats_store: StatsStore, achievement_engine: AchievementEngine):
    await bot.add_cog(General(bot, stats_store, achievement_engine))