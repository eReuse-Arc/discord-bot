from __future__ import annotations
import json
from datetime import datetime, date, timedelta, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from helpers.admin import admin_meta
from helpers.leetcode_api import (
    fetch_all_problems,
    pick_random_free_problem,
    recent_accepted_submissions,
    LeetCodeProblem,
)
from constants import LEETCODE_DATA_PATH, LEETCODE_CHANNEL_ID, LEETCODE_PING_ROLE_NAME

SYDNEY = ZoneInfo("Australia/Sydney")

LEETCODE_DATA_FILE = Path(LEETCODE_DATA_PATH)
LEETCODE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

RECENT_SLUGS_MAX = 21
RECENT_SUB_LIMIT = 40

DIFFICULTY_WEIGHTS = (0.55, 0.40, 0.05)


def sydney_today() -> date:
    return datetime.now(SYDNEY).date()


def date_str(d: date) -> str:
    return d.isoformat()


def parse_lc_username(raw: str) -> str:
    return raw.strip()


def unix_to_sydney_date(ts: int) -> date:
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo("UTC")).astimezone(SYDNEY)
    return dt.date()


def load_json(path: Path, default):
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def save_json(path: Path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_state() -> dict:
    default = {
        "daily": {
            "date": None,
            "question_id": None,
            "title": None,
            "title_slug": None,
            "difficulty": None,
            "url": None,
            "posted_message_id": None,
        },
        "daily_history": {},
        "solves": {},
        "stats": {},
        "links": {},
        "recent_slugs": [],
        "summaries": {},
    }

    state = load_json(LEETCODE_DATA_FILE, default)

    for k, v in default.items():
        if k not in state:
            state[k] = v

    if "daily" not in state or not isinstance(state["daily"], dict):
        state["daily"] = default["daily"]
    for k, v in default["daily"].items():
        if k not in state["daily"]:
            state["daily"][k] = v

    if "daily_history" not in state or not isinstance(state["daily_history"], dict):
        state["daily_history"] = {}

    if "summaries" not in state or not isinstance(state["summaries"], dict):
        state["summaries"] = {}

    return state


def diff_emoji(difficulty: str) -> str:
    return {"Easy": "🟩", "Medium": "🟨", "Hard": "🟥"}.get(difficulty, "⬜")


def make_daily_embed(problem: LeetCodeProblem) -> discord.Embed:
    e = discord.Embed(
        title="eReuse | LeetCode Daily",
        description=(
            f"**{problem.title}**\n"
            f"{diff_emoji(problem.difficulty)} **{problem.difficulty}** - ID `{problem.question_id}`"
        ),
        url=problem.url,
        timestamp=datetime.now(SYDNEY),
    )
    e.add_field(name="Link", value=problem.url, inline=False)
    e.add_field(
        name="How to submit",
        value=(
            "1) Link your account: `/leetcode link <username>`\n"
            "2) After you get **Accepted**, submit: `/leetcode submit` or press **Submit**"
        ),
        inline=False,
    )
    e.set_footer(text="Verification uses your recent accepted submissions (no login).")
    return e


class SubmitModal(discord.ui.Modal, title="Submit LeetCode"):
    # label MUST be 1..45 chars (Discord hard limit)
    note = discord.ui.TextInput(
        label="Submission link / note (optional)",
        placeholder="Optional. We'll verify via recent ACs.",
        required=False,
        max_length=200,
    )

    def __init__(self, cog: "LeetCode"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.handle_submit(interaction)


class DailySubmitView(discord.ui.View):
    def __init__(self, cog: "LeetCode"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Submit",
        style=discord.ButtonStyle.primary,
        custom_id="leetcode:submit_daily",
    )
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SubmitModal(self.cog))


class LeetCode(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._all_problems_cache: dict | None = None
        self._session: aiohttp.ClientSession | None = None

        # Register persistent view so the Submit button works for the whole day + across restarts
        self.bot.add_view(DailySubmitView(self))

        self.daily_post.start()
        self.daily_summary_post.start()

    async def cog_load(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    def cog_unload(self):
        self.daily_post.cancel()
        self.daily_summary_post.cancel()
        if self._session and not self._session.closed:
            self.bot.loop.create_task(self._session.close())

    def state(self) -> dict:
        return ensure_state()

    def save_state(self, state: dict):
        save_json(LEETCODE_DATA_FILE, state)

    def channel_only(self, interaction: discord.Interaction) -> bool:
        return interaction.channel_id == int(LEETCODE_CHANNEL_ID)

    def get_leetcode_channel(self) -> discord.TextChannel | None:
        ch = self.bot.get_channel(int(LEETCODE_CHANNEL_ID))
        return ch if isinstance(ch, discord.TextChannel) else None

    def get_ping_role(self, guild: discord.Guild | None) -> discord.Role | None:
        if guild is None:
            return None
        target = (LEETCODE_PING_ROLE_NAME or "").strip().lower()
        if not target:
            return None
        for r in guild.roles:
            if r.name.lower() == target:
                return r
        return None

    async def ensure_problem_cache(self):
        if not self._session:
            self._session = aiohttp.ClientSession()
        if self._all_problems_cache is None:
            self._all_problems_cache = await fetch_all_problems(self._session)

    def write_daily_history(self, state: dict, d: str, problem: LeetCodeProblem, posted_message_id: int | None = None):
        state.setdefault("daily_history", {})
        state["daily_history"][d] = {
            "date": d,
            "question_id": problem.question_id,
            "title": problem.title,
            "title_slug": problem.title_slug,
            "difficulty": problem.difficulty,
            "url": problem.url,
            "posted_message_id": posted_message_id,
        }

    async def pick_today_problem(self, state: dict) -> LeetCodeProblem:
        await self.ensure_problem_cache()
        avoid = set(state.get("recent_slugs") or [])

        problem = pick_random_free_problem(
            self._all_problems_cache,
            avoid_slugs=avoid,
            weights=DIFFICULTY_WEIGHTS,
        )

        recent = list(state.get("recent_slugs") or [])
        recent.append(problem.title_slug)

        seen = set()
        recent2 = []
        for s in recent:
            if s in seen:
                continue
            seen.add(s)
            recent2.append(s)

        state["recent_slugs"] = recent2[-RECENT_SLUGS_MAX:]

        today = date_str(sydney_today())
        state["daily"] = {
            "date": today,
            "question_id": problem.question_id,
            "title": problem.title,
            "title_slug": problem.title_slug,
            "difficulty": problem.difficulty,
            "url": problem.url,
            "posted_message_id": None,
        }

        self.write_daily_history(state, today, problem, posted_message_id=None)

        return problem

    async def post_daily_to_channel(self, channel: discord.TextChannel, problem: LeetCodeProblem, state: dict):
        embed = make_daily_embed(problem)

        view = DailySubmitView(self)
        view.add_item(discord.ui.Button(label="Open Problem", url=problem.url))

        role = self.get_ping_role(channel.guild)
        content = f"{role.mention}" if role else None

        msg = await channel.send(
            content=content,
            embed=embed,
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True) if role else discord.AllowedMentions.none(),
            silent=True,
        )

        today = date_str(sydney_today())
        state["daily"]["posted_message_id"] = msg.id

        self.write_daily_history(state, today, problem, posted_message_id=msg.id)

    async def post_summary_for_yesterday(self):
        channel = self.get_leetcode_channel()
        if channel is None:
            return

        st = self.state()

        y = date_str(sydney_today() - timedelta(days=1))
        if (st.get("summaries") or {}).get(y):
            return

        solves_for_y = (st.get("solves") or {}).get(y) or {}
        if not solves_for_y:
            st.setdefault("summaries", {})
            st["summaries"][y] = True
            self.save_state(st)
            return

        hist = (st.get("daily_history") or {}).get(y) or {}
        title = hist.get("title")
        diff = hist.get("difficulty")
        url = hist.get("url")
        qid = hist.get("question_id")

        e = discord.Embed(
            title=f"📌 LeetCode Daily - Summary for {y}",
            timestamp=datetime.now(SYDNEY),
        )

        if title and diff and url and qid:
            e.description = (
                f"**Problem:** [{title}]({url})\n"
                f"{diff_emoji(str(diff))} **{diff}** - ID `{qid}`"
            )
        else:
            e.description = "Yesterday's results:"

        items = list(solves_for_y.items())

        def sort_key(kv):
            rec = kv[1] or {}
            return int(rec.get("matched_ts") or 0)

        items.sort(key=sort_key)

        lines = [f"<@{uid}>" for uid, _ in items]
        chunk = "\n".join(lines)
        if len(chunk) > 3900:
            chunk = chunk[:3900] + "\n…"

        e.add_field(name=f"Solvers ({len(items)})", value=chunk or "—", inline=False)
        await channel.send(embed=e, silent=True)

        st.setdefault("summaries", {})
        st["summaries"][y] = True
        self.save_state(st)

    @tasks.loop(time=dtime(hour=0, minute=0, tzinfo=SYDNEY))
    async def daily_post(self):
        channel = self.get_leetcode_channel()
        if channel is None:
            return

        st = self.state()
        today = date_str(sydney_today())
        if (st.get("daily") or {}).get("date") == today:
            return

        problem = await self.pick_today_problem(st)
        await self.post_daily_to_channel(channel, problem, st)
        self.save_state(st)

    @tasks.loop(time=dtime(hour=0, minute=1, tzinfo=SYDNEY))
    async def daily_summary_post(self):
        await self.post_summary_for_yesterday()

    @daily_post.before_loop
    async def before_daily_post(self):
        await self.bot.wait_until_ready()
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    @daily_summary_post.before_loop
    async def before_daily_summary_post(self):
        await self.bot.wait_until_ready()

    async def handle_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not self.channel_only(interaction):
            return await interaction.followup.send("❌ Use this in the LeetCode channel.", ephemeral=True)

        st = self.state()
        today = date_str(sydney_today())
        daily = st.get("daily") or {}
        slug = daily.get("title_slug")
        if not slug:
            return await interaction.followup.send(
                "❌ No daily problem set yet. An admin can run `/leetcode postnow`.",
                ephemeral=True,
            )

        uid = str(interaction.user.id)
        username = (st.get("links") or {}).get(uid)
        if not username:
            return await interaction.followup.send(
                "❌ Link your LeetCode username first: `/leetcode link <username>`",
                ephemeral=True,
            )

        solves_today = (st.get("solves") or {}).get(today) or {}
        if uid in solves_today:
            return await interaction.followup.send("✅ You already got today's solve recorded.", ephemeral=True)

        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()

        try:
            recents = await recent_accepted_submissions(self._session, username=username, limit=RECENT_SUB_LIMIT)
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Couldn't verify via LeetCode API. ({type(e).__name__})",
                ephemeral=True,
            )

        matched_ts = None
        for item in recents:
            item_slug = item.get("titleSlug")
            ts_raw = item.get("timestamp")
            if item_slug != slug or ts_raw is None:
                continue
            try:
                ts = int(ts_raw)
            except Exception:
                continue
            if date_str(unix_to_sydney_date(ts)) == today:
                matched_ts = ts
                break

        if matched_ts is None:
            url = daily.get("url") or f"https://leetcode.com/problems/{slug}/"
            return await interaction.followup.send(
                f"❌ Not verified yet.\n"
                f"- Make sure you **AC (Accepted)** today's problem: {url}\n"
                f"- And that your LeetCode username `{username}` is correct.\n"
                f"- If you just solved it, try again in ~30-60 seconds (sometimes it lags).",
                ephemeral=True,
            )

        st.setdefault("solves", {})
        st["solves"].setdefault(today, {})
        st["solves"][today][uid] = {"username": username, "matched_ts": matched_ts}

        st.setdefault("stats", {})
        stats = st["stats"].get(uid) or {
            "total": 0,
            "current_streak": 0,
            "best_streak": 0,
            "last_solved_date": None,
        }

        yesterday = date_str(sydney_today() - timedelta(days=1))
        if stats.get("last_solved_date") == yesterday:
            stats["current_streak"] = int(stats.get("current_streak") or 0) + 1
        else:
            stats["current_streak"] = 1

        stats["total"] = int(stats.get("total") or 0) + 1
        stats["best_streak"] = max(int(stats.get("best_streak") or 0), int(stats["current_streak"]))
        stats["last_solved_date"] = today

        st["stats"][uid] = stats

        st.setdefault("summaries", {})
        st["summaries"].pop(today, None)

        self.save_state(st)

        return await interaction.followup.send(
            f"✅ Verified! Recorded your solve for **{daily.get('title', slug)}**.\n"
            f"🔥 Streak: **{stats['current_streak']}** - 🏆 Best: **{stats['best_streak']}** - 📌 Total: **{stats['total']}**",
            ephemeral=True,
        )

    leetcode = app_commands.Group(name="leetcode", description="Daily LeetCode for eReuse")

    @leetcode.command(name="link", description="Link your LeetCode username for verification")
    async def link(self, interaction: discord.Interaction, username: str):
        username = parse_lc_username(username)
        if not username:
            return await interaction.response.send_message("❌ Invalid username.", ephemeral=True)

        st = self.state()
        st.setdefault("links", {})
        st["links"][str(interaction.user.id)] = username
        self.save_state(st)

        await interaction.response.send_message(f"✅ Linked LeetCode username: `{username}`", ephemeral=True)

    @leetcode.command(name="unlink", description="Remove your linked LeetCode username")
    async def unlink(self, interaction: discord.Interaction):
        st = self.state()
        links = st.get("links") or {}
        links.pop(str(interaction.user.id), None)
        st["links"] = links
        self.save_state(st)
        await interaction.response.send_message("✅ Unlinked your LeetCode username.", ephemeral=True)

    @leetcode.command(name="today", description="Show today's LeetCode problem")
    async def today(self, interaction: discord.Interaction):
        if not self.channel_only(interaction):
            return await interaction.response.send_message("❌ Use this in the LeetCode channel.", ephemeral=True)

        st = self.state()
        daily = st.get("daily") or {}
        if daily.get("date") != date_str(sydney_today()) or not daily.get("title_slug"):
            return await interaction.response.send_message(
                "❌ No daily problem posted yet. Try again later or ask an admin.",
                ephemeral=True,
            )

        e = discord.Embed(
            title=f"{daily.get('title')} ({daily.get('difficulty')})",
            url=daily.get("url"),
            description=f"ID `{daily.get('question_id')}` - Slug `{daily.get('title_slug')}`",
            timestamp=datetime.now(SYDNEY),
        )

        view = DailySubmitView(self)
        view.add_item(discord.ui.Button(label="Open Problem", url=daily.get("url")))
        await interaction.response.send_message(embed=e, view=view, ephemeral=True)

    @leetcode.command(name="submit", description="Submit today's solve (verified via recent accepted submissions)")
    async def submit(self, interaction: discord.Interaction):
        if not self.channel_only(interaction):
            return await interaction.response.send_message("❌ Use this in the LeetCode channel.", ephemeral=True)
        await interaction.response.send_modal(SubmitModal(self))

    @leetcode.command(name="leaderboard", description="Show LeetCode daily leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        if not self.channel_only(interaction):
            return await interaction.response.send_message("❌ Use this in the LeetCode channel.", ephemeral=True)

        st = self.state()
        stats = st.get("stats") or {}

        rows = []
        for uid, s in stats.items():
            rows.append(
                (
                    int(uid),
                    int(s.get("total") or 0),
                    int(s.get("current_streak") or 0),
                    int(s.get("best_streak") or 0),
                )
            )

        if not rows:
            return await interaction.response.send_message("No data yet - be the first to solve today 😈", ephemeral=True)

        rows.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

        lines = []
        for i, (uid, total, cur, best) in enumerate(rows[:10], start=1):
            member = interaction.guild.get_member(uid) if interaction.guild else None
            name = member.display_name if member else f"<@{uid}>"
            lines.append(f"**{i}.** {name} - 📌 **{total}** - 🔥 **{cur}** - 🏆 **{best}**")

        e = discord.Embed(
            title="eReuse | LeetCode Leaderboard",
            description="\n".join(lines),
            timestamp=datetime.now(SYDNEY),
        )
        e.set_footer(text="📌 total solves - 🔥 current streak - 🏆 best streak")
        await interaction.response.send_message(embed=e)

    @leetcode.command(name="postnow", description="Post today's problem now (admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["LeetCode Daily Post", "LeetCode Challenge Rotation"],
        notes="Posts the daily LeetCode to the channel. Avoid using multiple times in a day unless rerolling intentionally."
    )
    async def postnow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        channel = self.get_leetcode_channel()
        if channel is None:
            return await interaction.followup.send("❌ LeetCode channel not found / not a text channel.", ephemeral=True)

        st = self.state()
        today = date_str(sydney_today())
        if (st.get("daily") or {}).get("date") != today:
            problem = await self.pick_today_problem(st)
        else:
            daily = st.get("daily") or {}
            problem = LeetCodeProblem(
                question_id=str(daily.get("question_id")),
                title=str(daily.get("title")),
                title_slug=str(daily.get("title_slug")),
                difficulty=str(daily.get("difficulty")),
                url=str(daily.get("url")),
            )
            self.write_daily_history(
                st,
                today,
                problem,
                posted_message_id=int(daily.get("posted_message_id") or 0) or None,
            )

        await self.post_daily_to_channel(channel, problem, st)
        self.save_state(st)
        await interaction.followup.send(f"✅ Posted: **{problem.title}**", ephemeral=True)

    @leetcode.command(name="reroll", description="Pick a new problem for today and post it (admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["LeetCode Daily Post", "LeetCode Challenge Rotation"],
        notes="Rerolls today's LeetCode problem and posts a new one. This changes today's challenge for everyone."
    )
    async def reroll(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        channel = self.get_leetcode_channel()
        if channel is None:
            return await interaction.followup.send("❌ LeetCode channel not found / not a text channel.", ephemeral=True)

        st = self.state()

        st["daily"]["date"] = None
        problem = await self.pick_today_problem(st)
        await self.post_daily_to_channel(channel, problem, st)

        today = date_str(sydney_today())
        st.setdefault("summaries", {})
        st["summaries"].pop(today, None)

        self.save_state(st)

        await interaction.followup.send(f"✅ Rerolled + posted: **{problem.title}**", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LeetCode(bot))
