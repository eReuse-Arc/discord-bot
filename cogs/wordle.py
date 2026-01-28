import re
import json
from pathlib import Path
from datetime import timedelta, date as date_cls, datetime
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
from constants import *
from helpers.admin import admin_meta

WORDLE_PATH = Path(WORDLE_STATS_PATH)
SYD = ZoneInfo("Australia/Sydney")

RECAP_RE = re.compile(r"Your group is on a\s+(\d+)\s+day streak", re.I)
LINE_RE = re.compile(r"^\s*(?:👑\s*)?([1-6X])/6\s*:\s*(.+)\s*$")


RESULT_CHOICES = [
    Choice(name="Solved", value="solved"),
    Choice(name="Failed", value="failed"),
    Choice(name="Missed / Did not play", value="missed"),
]

TURNS_CHOICES = [
    Choice(name="1", value="1"),
    Choice(name="2", value="2"),
    Choice(name="3", value="3"),
    Choice(name="4", value="4"),
    Choice(name="5", value="5"),
    Choice(name="6", value="6"),
    Choice(name="X (failed)", value="X"),
    Choice(name="- (no turns / missed)", value="-"),
]


def _parse_iso_date(s: str) -> date_cls:
    try:
        return date_cls.fromisoformat(s.strip())
    except Exception:
        raise ValueError("date must be in YYYY-MM-DD format")


def _iso(d: date_cls) -> str:
    return d.isoformat()


def _now_ts() -> int:
    return int(datetime.now(tz=ZoneInfo("UTC")).timestamp())


class WordleTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def load_state(self):
        if WORDLE_PATH.exists():
            return json.loads(WORDLE_PATH.read_text(encoding="utf-8"))
        return {
            "group": {"current": 0, "best": 0, "last_date": None, "total_days_tracked": 0},
            "users": {}
        }

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

        u.setdefault("history", {})
        u.setdefault("history_seeded", False)

        return u

    def seed_history_if_needed(self, udata: dict):
        if udata.get("history_seeded"):
            return

        hist: dict = udata.setdefault("history", {})
        if hist:
            udata["history_seeded"] = True
            return

        last = udata.get("last_date")
        if not last:
            udata["history_seeded"] = True
            return

        total_solved = int(udata.get("total_solved") or 0)
        total_failed = int(udata.get("total_failed") or 0)
        total_played = int(udata.get("total_played") or 0)
        current_streak = int(udata.get("current_streak") or 0)
        best_streak = int(udata.get("best_streak") or 0)

        if total_played <= 0:
            total_played = total_solved + total_failed
        if total_played < total_solved + total_failed:
            total_played = total_solved + total_failed

        try:
            end_day = _parse_iso_date(last)
        except Exception:
            udata["history_seeded"] = True
            return


        L = max(total_played + 10, best_streak + current_streak + 10, total_solved + total_failed + 10)
        days = [end_day - timedelta(days=(L - 1 - i)) for i in range(L)]

        state = ["missed"] * L

        def can_place_solved_run(start_idx: int, length: int) -> bool:
            if start_idx < 0 or start_idx + length > L:
                return False
            if any(state[i] != "missed" for i in range(start_idx, start_idx + length)):
                return False

            left = start_idx - 1
            right = start_idx + length
            if left >= 0 and state[left] == "solved":
                return False
            if right < L and state[right] == "solved":
                return False
            return True

        def place_solved_run(start_idx: int, length: int):
            for i in range(start_idx, start_idx + length):
                state[i] = "solved"

        if current_streak > 0:
            place_solved_run(L - current_streak, current_streak)

        if best_streak > current_streak and best_streak > 0:
            latest_start = (L - current_streak) - (best_streak + 2)
            placed = False
            for s in range(max(0, latest_start - 50), max(0, latest_start) + 1):
                if can_place_solved_run(s, best_streak):
                    place_solved_run(s, best_streak)
                    placed = True
                    break

        placed_solved = sum(1 for x in state if x == "solved")
        remaining_solved = max(0, total_solved - placed_solved)

        if remaining_solved > 0:
            for i in range(L):
                if remaining_solved == 0:
                    break
                if state[i] != "missed":
                    continue
                left = i - 1
                right = i + 1
                if (left >= 0 and state[left] == "solved") or (right < L and state[right] == "solved"):
                    continue
                state[i] = "solved"
                remaining_solved -= 1

        remaining_failed = total_failed
        if remaining_failed > 0:
            for i in range(L):
                if remaining_failed == 0:
                    break
                if state[i] == "missed":
                    state[i] = "failed"
                    remaining_failed -= 1

        gc = udata.get("guess_counts") or {}
        guess_pool: list[int] = []
        for k in ["1", "2", "3", "4", "5", "6"]:
            guess_pool.extend([int(k)] * int(gc.get(k, 0)))

        guess_pool.sort()

        solved_indices = [i for i, st in enumerate(state) if st == "solved"]
        for idx in solved_indices:
            g = guess_pool.pop(0) if guess_pool else None
            hist[_iso(days[idx])] = {"state": "solved", "guesses": g, "source": "seed", "ts": _now_ts()}

        for i, st in enumerate(state):
            if st == "failed":
                hist[_iso(days[i])] = {"state": "failed", "guesses": None, "source": "seed", "ts": _now_ts()}
            elif st == "missed":
                hist[_iso(days[i])] = {"state": "missed", "guesses": None, "source": "seed", "ts": _now_ts()}

        udata["history"] = hist
        udata["history_seeded"] = True


    def set_history_entry(self, udata: dict, day_str: str, state: str, guesses: int | None, source: str):
        hist: dict = udata.setdefault("history", {})
        hist[day_str] = {
            "state": state,
            "guesses": guesses,
            "source": source,
            "ts": _now_ts(),
        }

    def rebuild_user_from_history(self, udata: dict):
        hist: dict = udata.get("history", {}) or {}
        if not hist:
            return

        days = []
        for ds in hist.keys():
            try:
                days.append(_parse_iso_date(ds))
            except Exception:
                continue
        days.sort()
        if not days:
            return

        total_played = 0
        total_solved = 0
        total_failed = 0
        guess_counts = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0}
        best_turn: int | None = None

        best_streak = 0
        current_run = 0
        prev_day: date_cls | None = None

        for d in days:
            ds = _iso(d)
            entry = hist.get(ds, {})
            st = entry.get("state")

            if st in ("solved", "failed"):
                total_played += 1
            if st == "solved":
                total_solved += 1
                g = entry.get("guesses")
                if isinstance(g, int) and 1 <= g <= 6:
                    guess_counts[str(g)] = int(guess_counts.get(str(g), 0)) + 1
                    if best_turn is None or g < best_turn:
                        best_turn = g
            elif st == "failed":
                total_failed += 1

            if st == "solved":
                if prev_day is not None and d == prev_day + timedelta(days=1):
                    current_run += 1
                else:
                    current_run = 1
                best_streak = max(best_streak, current_run)
            else:
                current_run = 0

            prev_day = d

        latest = days[-1]
        latest_state = (hist.get(_iso(latest), {}) or {}).get("state")
        if latest_state == "solved":
            cur = 0
            d = latest
            while True:
                e = hist.get(_iso(d), {})
                if e.get("state") != "solved":
                    break
                cur += 1
                d2 = d - timedelta(days=1)
                if _iso(d2) not in hist:
                    break
                d = d2
            current_streak = cur
        else:
            current_streak = 0

        udata["total_played"] = total_played
        udata["total_solved"] = total_solved
        udata["total_failed"] = total_failed
        udata["guess_counts"] = guess_counts
        udata["best_turn"] = best_turn
        udata["best_streak"] = best_streak
        udata["current_streak"] = current_streak
        udata["last_date"] = _iso(latest)

    async def eval_achievements_for(self, guild: discord.Guild, member_id: int):
        challenges = self.bot.get_cog("Challenges")
        if not challenges:
            return
        m = guild.get_member(member_id)
        if not m:
            return
        ctx = challenges.build_ctx(m)
        await challenges.achievement_engine.evaluate(ctx)


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
            self.seed_history_if_needed(udata)

            if udata.get("last_date") != wordle_day_str and int(uid_str) not in played:
                udata["current_streak"] = 0
                self.set_history_entry(udata, wordle_day_str, "missed", None, source="recap")

        for uid, (solved, guesses) in played.items():
            uid_str = str(uid)
            udata = self.ensure_schema(users, uid_str)
            self.seed_history_if_needed(udata)

            if not solved:
                self.set_history_entry(udata, wordle_day_str, "failed", None, source="recap")
            else:
                self.set_history_entry(udata, wordle_day_str, "solved", guesses, source="recap")

            self.rebuild_user_from_history(udata)

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

        # achievements
        challenges_cog = self.bot.get_cog("Challenges")
        if challenges_cog:
            for uid in summary["processed_users"]:
                member = message.guild.get_member(uid)
                if member:
                    ctx = challenges_cog.build_ctx(member)
                    await challenges_cog.achievement_engine.evaluate(ctx)

    @app_commands.command(name="wordle_grant_day", description="(Admin) Grant or edit a user's Wordle result for a specific day.")
    @app_commands.describe(
        member="User to grant/edit",
        date="Wordle day (YYYY-MM-DD)",
        result="Solved / Failed / Missed",
        turns="1-6 for solved, X for failed, - for missed"
    )
    @app_commands.choices(result=RESULT_CHOICES, turns=TURNS_CHOICES)
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["Wordle Stats Data", "Achievements"],
        notes="Manually grant/edit a user's Wordle day and rebuild their streaks/totals."
    )
    async def wordle_grant_day(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        date: str,
        result: Choice[str],
        turns: Choice[str],
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            d = _parse_iso_date(date)
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return

        day_str = _iso(d)
        state_val = result.value
        turns_val = turns.value

        guesses: int | None = None
        if state_val == "solved":
            if turns_val not in {"1", "2", "3", "4", "5", "6"}:
                await interaction.followup.send("❌ For **Solved**, turns must be **1-6**.", ephemeral=True)
                return
            guesses = int(turns_val)

        elif state_val == "failed":
            if turns_val != "X":
                await interaction.followup.send("❌ For **Failed**, turns must be **X**.", ephemeral=True)
                return
            guesses = None

        else:  # missed
            if turns_val != "-":
                await interaction.followup.send("❌ For **Missed**, turns must be **-**.", ephemeral=True)
                return
            guesses = None

        state = self.load_state()
        users = state.setdefault("users", {})

        udata = self.ensure_schema(users, str(member.id))
        self.seed_history_if_needed(udata)

        self.set_history_entry(udata, day_str, state_val, guesses, source="manual")

        self.rebuild_user_from_history(udata)

        self.save_state(state)

        try:
            await self.eval_achievements_for(interaction.guild, member.id)
        except Exception:
            pass

        pretty = {
            "solved": f"Solved in **{guesses}/6**",
            "failed": "Failed (**X/6**)",
            "missed": "Missed / Did not play",
        }[state_val]

        await interaction.followup.send(
            f"✅ Updated **{member.mention}** for **{day_str}** → {pretty}\n"
            f"Now: current streak **{udata.get('current_streak', 0)}**, best streak **{udata.get('best_streak', 0)}**\n"
            f"Totals: played **{udata.get('total_played', 0)}**, solved **{udata.get('total_solved', 0)}**, failed **{udata.get('total_failed', 0)}**\n"
            f"Best turn: **{udata.get('best_turn')}**",
            ephemeral=True
        )


    @app_commands.command(name="wordle_test", description="reprocess a Wordle recap message by ID")
    @app_commands.describe(message_id="Message ID of the Wordle bot recap post")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["Wordle Stats Data", "Achievements"],
        notes="Run the wordle check on a message from the wordle bot"
    )
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