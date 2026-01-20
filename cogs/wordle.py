import re
import json
from pathlib import Path
from datetime import timedelta
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
from discord import app_commands
from constants import *
from helpers.admin import admin_meta

WORDLE_PATH = Path(WORDLE_STATS_PATH)

SYD = ZoneInfo("Australia/Sydney")

RECAP_RE = re.compile(r"Your group is on a\s+(\d+)\s+day streak", re.I)
LINE_RE = re.compile(r"^\s*(?:👑\s*)?([1-6X])/6\s*:\s*(.+)\s*$")


class WordleTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def load_state(self):
        if WORDLE_PATH.exists():
            return json.loads(WORDLE_PATH.read_text(encoding="utf-8"))
        return {"group": {"current": 0, "best": 0, "last_date": None, "total_days_tracked": 0}, "users": {}}

    def save_state(self, state):
        WORDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        WORDLE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    
    def ensure_schema(self, users: dict, uid_str: str) -> dict:
        u = users.setdefault(str(uid_str), {})

        u.setdefault("current_streak", u.get("current_streak", 0))
        u.setdefault("best_streak", u.get("best_streak", 0))
        u.setdefault("last_date", u.get("last_date"))
        u.setdefault("total_played", 0)
        u.setdefault("total_solved", 0)
        u.setdefault("total_failed", 0)
        u.setdefault("best_turn", None)
        u.setdefault("guess_counts", {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0})

        return u


    async def process_wordle_recap_message(self, message: discord.Message) -> dict:
        m = RECAP_RE.search(message.content)
        if not m:
            return {"ok": False, "reason": "Message doesn't look like a recap (streak line not found)."}

        group_streak = int(m.group(1))

        created_syd = message.created_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(SYD)
        wordle_day = created_syd.date() - timedelta(days=1)
        wordle_day_str = wordle_day.isoformat()
        prev_day_str = (created_syd.date() - timedelta(days=2)).isoformat()

        state = self.load_state()

        g = state.setdefault("group", {})
        g.setdefault("current", 0)
        g.setdefault("best", 0)
        g.setdefault("last_date", None)
        g.setdefault("total_days_tracked", 0)

        g["current"] = group_streak
        g["best"] = max(int(g.get("best") or 0), group_streak)
        if g.get("last_date") != wordle_day_str:
            g["total_days_tracked"] = int(g.get("total_days_tracked") or 0) + 1
        g["last_date"] = wordle_day_str

        token_to_id = {}
        for u in message.mentions:
            token_to_id[f"<@{u.id}>"] = u.id
            token_to_id[f"<@!{u.id}>"] = u.id

        played: dict[int, tuple[bool, int | None]] = {}

        for line in message.content.splitlines():
            lm = LINE_RE.match(line)
            if not lm:
                continue

            score = lm.group(1)
            rest = lm.group(2)

            solved = (score != "X")
            guesses = None if score == "X" else int(score)

            for token, uid in token_to_id.items():
                if token in rest:
                    played[uid] = (solved, guesses)

        users = state.setdefault("users", {})

        # Safe iteration (users can grow)
        for uid_str in list(users.keys()):
            udata = self.ensure_schema(users, uid_str)
            if udata.get("last_date") != wordle_day_str and int(uid_str) not in played:
                udata["current_streak"] = 0

        for uid, (solved, guesses) in played.items():
            uid_str = str(uid)
            udata = self.ensure_schema(users, uid_str)

            udata["total_played"] = int(udata["total_played"]) + 1

            if not solved:
                udata["total_failed"] = int(udata["total_failed"]) + 1
                udata["current_streak"] = 0
            else:
                udata["total_solved"] = int(udata["total_solved"]) + 1

                if udata.get("last_date") == prev_day_str and int(udata.get("current_streak") or 0) > 0:
                    udata["current_streak"] = int(udata["current_streak"]) + 1
                else:
                    udata["current_streak"] = 1

                if guesses is not None:
                    if udata["best_turn"] is None or guesses < int(udata["best_turn"]):
                        udata["best_turn"] = guesses

                    gc = udata["guess_counts"]
                    gc[str(guesses)] = int(gc.get(str(guesses), 0)) + 1

            udata["best_streak"] = max(int(udata["best_streak"]), int(udata["current_streak"]))
            udata["last_date"] = wordle_day_str

        self.save_state(state)

        return {
            "ok": True,
            "group_streak": group_streak,
            "wordle_day": wordle_day_str,
            "processed_users": list(played.keys()),
            "processed_count": len(played),
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        if message.channel.id != WORDLE_CHANNEL_ID:
            return
        
        if message.author.id != WORDLE_BOT_ID:
            return
        
        summary = await self.process_wordle_recap_message(message)
        if not summary.get("ok"):
            return


        challenges_cog = self.bot.get_cog("Challenges")
        if challenges_cog:
            for uid in summary["processed_users"]:
                member = message.guild.get_member(uid)
                if member:
                    ctx = challenges_cog.build_ctx(member)
                    await challenges_cog.achievement_engine.evaluate(ctx)



    @app_commands.command(name="wordle_test", description="reprocess a Wordle recap message by ID")
    @app_commands.describe(message_id="Message ID of the Wordle bot recap post")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= ["Wordle Stats Data", "Achievements"],
            notes= "Run the wordle check on a message from the world bot")
    async def wordle_test(self, interaction: discord.Interaction, message_id: str):
        await interaction.response.defer(ephemeral=True)

        channel = interaction.guild.get_channel(WORDLE_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send("❌ WORDLE_CHANNEL_ID not found in this server.", ephemeral=True)
            return

        try:
            mid = int(message_id)
        except ValueError:
            await interaction.followup.send("❌ message_id must be a number.", ephemeral=True)
            return

        try:
            msg = await channel.fetch_message(mid)
        except discord.NotFound:
            await interaction.followup.send("❌ Message not found in the Wordle channel.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.followup.send("❌ I don’t have permission to fetch messages in that channel.", ephemeral=True)
            return

        if msg.author.id != WORDLE_BOT_ID:
            await interaction.followup.send("❌ That message is not from the Wordle bot.", ephemeral=True)
            return

        summary = await self.process_wordle_recap_message(msg)
        if not summary.get("ok"):
            await interaction.followup.send(f"❌ Not processed: {summary.get('reason')}", ephemeral=True)
            return

        challenges_cog = interaction.client.get_cog("Challenges")
        if challenges_cog:
            for uid in summary["processed_users"]:
                member = interaction.guild.get_member(uid)
                if member:
                    ctx = challenges_cog.build_ctx(member)
                    await challenges_cog.achievement_engine.evaluate(ctx)

        await interaction.followup.send(
            f"✅ Processed recap for **{summary['wordle_day']}**.\n"
            f"Group streak: **{summary['group_streak']}**\n"
            f"Users updated: **{summary['processed_count']}**",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(WordleTracker(bot))