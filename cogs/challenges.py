import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice
import json
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone
from constants import *
from helpers.embedHelper import add_spacer
from helpers.achievements import ACHIEVEMENTS
from helpers.bingo_render import render_bingo_card
from helpers.admin import admin_meta

DATA_FILE = Path(CHALLENGE_PATH)
CHALLENGE_SUGGESTIONS_FILE = Path(CHALLENGE_SUGGESTIONS_PATH)
POINTS_FILE = Path(CHALLENGE_POINTS_PATH)
ACHIEVEMENTS_FILE = Path(ACHEIVEMENTS_PATH)
VOLUNTEER_FILE = Path(VOLUNTEER_OF_THE_WEEK_PATH)
VOTES_FILE = Path(VOLUNTEER_VOTES_PATH)
BINGO_CARDS_FILE = Path(BINGO_CARDS_PATH)
BINGO_PROGRESS_FILE = Path(BINGO_PROGRESS_PATH)
BINGO_SUGGESTIONS_FILE = Path(BINGO_SUGGESTIONS_PATH)
LINKS_FILE = Path(MINECRAFT_LINKS_PATH)

class CreateBingoCardModal(discord.ui.Modal, title="Create Bingo Card!"):
    row1 = discord.ui.TextInput(label="Row 1 (A - E)", placeholder=("A | B | C | D | E"))
    row2 = discord.ui.TextInput(label="Row 2", placeholder=("..."))
    row3 = discord.ui.TextInput(label="Row 3", placeholder=("Include a FREE if wanted"))
    row4 = discord.ui.TextInput(label="Row 4")
    row5 = discord.ui.TextInput(label="Row 5")

    def __init__(self, cog, card_number):
        super().__init__()
        self.cog = cog
        self.card_number = card_number

    async def on_submit(self, interaction: discord.Interaction):
        rows = [self.row1, self.row2, self.row3, self.row4, self.row5]

        grid = []

        for r in rows:
            parts = [p.strip() for p in r.value.split("|")]
            if len(parts) != 5:
                await interaction.response.send_message(
                    "❌ Each row must contain **exactly 5 items** seperated by `|`",
                    ephemeral=True
                )
                return
            grid.append(parts)

        free_tiles = []

        for r, row in enumerate(grid):
            for c, text in enumerate(row):
                if text.upper() == "FREE":
                    coord = f"{chr(ord('A') + c)}{r + 1}"
                    free_tiles.append(coord)


        card_key = str(self.card_number)
        cards = self.cog.load_bingo_cards()
        cards[card_key] = {
            "grid": grid,
            "free_tiles": free_tiles
        }

        self.cog.save_bingo_cards(cards)

        await interaction.response.send_message(f"✅ **Bingo Card #{self.card_number} created!**")

class AchievementPages(discord.ui.View):
    def __init__(self, embeds: list[discord.Embed], viewer_id: int, target_id: int):
        super().__init__(timeout=120)
        self.embeds = embeds
        self.index =  0
        self.viewer_id = viewer_id
        self.target_id = target_id
        self.clicks = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("❌ Only the person who opened this menu can change pages, use `/achievements` to check your own!", ephemeral=True)
            return False

        self.clicks += 1

        if self.clicks < 20:
            return True

        challenges_cog = interaction.client.get_cog("Challenges")
        if challenges_cog:
            challenges_cog.stats_store.set_value(self.viewer_id, BUTTON_SMASHER, True)

            ctx = challenges_cog.build_ctx(interaction.user)
            await challenges_cog.achievement_engine.evaluate(ctx)

        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1 + len(self.embeds)) % len(self.embeds)

        challenges_cog = interaction.client.get_cog("Challenges")
        if self.index == len(self.embeds) - 1 and challenges_cog:
            challenges_cog.stats_store.set_value(self.viewer_id, YOU_FOUND_THIS, True)

            ctx = challenges_cog.build_ctx(interaction.user)
            await challenges_cog.achievement_engine.evaluate(ctx)

        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.embeds)

        challenges_cog = interaction.client.get_cog("Challenges")
        if self.index == 0 and challenges_cog:
            challenges_cog.stats_store.set_value(self.viewer_id, YOU_FOUND_THIS, True)

            ctx = challenges_cog.build_ctx(interaction.user)
            await challenges_cog.achievement_engine.evaluate(ctx)

        await interaction.response.edit_message(embed=self.embeds[self.index], view=self)

class Challenges(commands.Cog):
    def __init__(self, bot, stats_store, achievement_engine):
        self.bot = bot
        self.stats_store = stats_store
        self.achievement_engine = achievement_engine

    def load_challenges(self):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_challenges(self, data):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)


    def load_points(self):
        if not POINTS_FILE.exists():
            return {}
        with open(POINTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_points(self, points):
        with open(POINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(points, f, indent=2, sort_keys=True)

    def load_achievements(self):
        if not ACHIEVEMENTS_FILE.exists():
            return {}
        with open(ACHIEVEMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_achievements(self, achievements):
        with open(ACHIEVEMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(achievements, f, indent=2, sort_keys=True)

    def load_volunteer_winners(self):
        if not VOLUNTEER_FILE.exists():
            return {}
        with open(VOLUNTEER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_volunteer_winners(self, data):
        with open(VOLUNTEER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def load_volunteer_votes(self):
        if not VOTES_FILE.exists():
            return {}
        with open(VOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_bingo_progress(self):
        if not BINGO_PROGRESS_FILE.exists():
            return {}
        with open(BINGO_PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_bingo_progress(self, data):
        with open(BINGO_PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def load_bingo_cards(self):
        if not BINGO_CARDS_FILE.exists():
            return {}
        try:
            with open(BINGO_CARDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except(json.JSONDecodeError, OSError):
            return {}

    def save_bingo_cards(self, data):
        tmp = BINGO_CARDS_FILE.with_suffix(".tmp")

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        tmp.replace(BINGO_CARDS_FILE)

    def load_bingo_suggestions(self):
        if not BINGO_SUGGESTIONS_FILE.exists():
            return {}
        try:
            with open(BINGO_SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except(json.JSONDecodeError, OSError):
            return {}

    def save_bingo_suggestions(self, data):
        tmp = BINGO_SUGGESTIONS_FILE.with_suffix(".tmp")

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        tmp.replace(BINGO_SUGGESTIONS_FILE)


    def load_challenge_suggestions(self):
        if not CHALLENGE_SUGGESTIONS_FILE.exists():
            return {}
        try:
            with open(CHALLENGE_SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except(json.JSONDecodeError, OSError):
            return {}

    def save_challenge_suggestions(self, data):
        tmp = CHALLENGE_SUGGESTIONS_FILE.with_suffix(".tmp")

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        tmp.replace(CHALLENGE_SUGGESTIONS_FILE)

    def load_links(self):
        if not LINKS_FILE.exists():
            return {}
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
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

    def calculate_longest_streak(self, weeks: list[int]) -> int:
        if not weeks:
            return 0

        weeks = sorted(set(weeks), reverse=True)
        longest = current = 1

        for i in range(len(weeks) - 1):
            if weeks[i] - 1 == weeks[i+1]:
                current += 1
                longest = max(longest, current)
            else:
                current = 1

        return longest

    def get_rank(self, user_id: str, data: dict) -> int:
        leaderboard = sorted(
            data.items(),
            key = lambda x: len(x[1]),
            reverse=True
        )

        for i, (uid, _) in enumerate(leaderboard, start=1):
            if uid == user_id:
                return i

        return len(leaderboard) + 1

    def count_votes_given(self, user_id: str) -> int:
        user_id = str(user_id)
        votes = self.load_volunteer_votes()
        total = 0

        for week_votes in votes.values():
            (week_votes)
            total += len(week_votes.get(user_id, []))

        return total

    def count_votes_recieved(self, user_id) -> int:
        user_id = str(user_id)
        votes = self.load_volunteer_votes()

        total = 0

        for week_votes in votes.values():
            for nominees in week_votes.values():
                total += nominees.count(user_id)

        return total

    async def log_action(self, guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

    def _format_user_summary(self, member: discord.Member) -> dict:
        user_id = str(member.id)

        points_data = self.load_points()
        achievements_data = self.load_achievements()

        weeks = [int(w) for w in points_data.get(user_id, [])]
        earned = achievements_data.get(user_id, [])

        ctx = self.build_ctx(member)

        return {
            "member": member,
            "user_id": user_id,
            "weeks": weeks,
            "points": len(weeks),
            "earned": earned,
            "current_streak": ctx["current_streak"],
            "longest_streak": ctx["longest_streak"],
            "achievements": len(earned),
            "messages": ctx["messages"],
            "files": ctx["files"],
            "votes_given": self.count_votes_given(user_id),
            VOTW_VOTES_RECIEVED: ctx[VOTW_VOTES_RECIEVED],
            REACTIONS_GIVEN: ctx[REACTIONS_GIVEN],
            SIX_SEVEN: ctx[SIX_SEVEN],
            BINGOS_COMPLETE: ctx[BINGOS_COMPLETE],
            UNIQUE_COMMANDS: ctx[UNIQUE_COMMANDS],
            COMMANDS_USED: ctx[COMMANDS_USED],
            BINGO_SUGGESTIONS: ctx[BINGO_SUGGESTIONS],
            CHALLENGE_SUGGESTIONS: ctx[CHALLENGE_SUGGESTIONS],
            HIDDEN_ACHIEVEMENTS_COUNT: ctx[HIDDEN_ACHIEVEMENTS_COUNT],
            VOICE_MINUTES: ctx[VOICE_MINUTES],
            VOICE_SESSION_MAX: ctx[VOICE_SESSION_MAX],
            VOICE_3P_MINUTES: ctx[VOICE_3P_MINUTES],
            VOICE_5P_MINUTES: ctx[VOICE_5P_MINUTES]
        }

    def _cmp(self, a: int, b: int) -> tuple[str, str]:
        if a > b:
            return f"**{a} 🏆**", str(b)
        elif b > a:
            return str(a), f"**{b} 🏆**"
        else:
            return f"{a} 🤝", f"{b} 🤝"

    async def _build_achievement_embeds(self, member: discord.Member):
        achievement_data = self.load_achievements()
        earned = set(achievement_data.get(str(member.id), []))

        ctx = self.build_ctx(member)

        embeds = []
        chunk_size = 5
        items = list(ACHIEVEMENTS.items())

        for page in range(0, len(items), chunk_size):
            embed = discord.Embed(
                title=f"🏆 {member.display_name}'s Achievements",
                color=discord.Color.green()
            )

            for key, ach in items[page:min(page + chunk_size, len(items))]:
                unlocked = key in earned
                status = "✅  Unlocked" if unlocked else "🔒  Locked"
                is_hidden = ach.get("hidden", False)

                percent = await self.achievement_percentage(key, member.guild)
                rarity = (
                    "💎 Ultra Rare" if percent <= 5 else
                    "🔥 Rare" if percent <= 15 else
                    "⭐ Uncommon" if percent <= 40 else
                    "✅ Common"
                )

                if is_hidden and not unlocked:
                    embed.add_field(
                        name=f"❓ Hidden Achievement",
                        value=f"{status}\n💬  ???\n📊  {percent}% of members - {rarity}",
                        inline=False
                    )
                    continue

                value = (
                    f" \n"
                    f"{status}\n"
                    f"💬  {ach['description']}\n"
                    f"📊  {percent}% of members - {rarity}"
                )

                progress = self.achievement_progress(ach, ctx)
                if progress:
                    current, maximum, p = progress
                    bar = "▓" * (round(p) // 5) + "░" * (20 - round(p) // 5)
                    value += f"\n📈 {current} / {maximum}  ({p}%)\n`{bar}`\n \u200b\n"



                embed.add_field(
                    name=f"🏅 {ach['name']}",
                    value=value,
                    inline=False
                )
            embed.set_footer(text=f"Page {page // chunk_size + 1} / {((len(items) - 1) // chunk_size) + 1}")

            embeds.append(embed)
        return embeds

    async def rarest_achievement(self, earned: list[str], guild: discord.guild):
        if not earned:
            return None, None

        rarest_key = None
        rarest_percent = 100.0

        for key in earned:
            percent = await self.achievement_percentage(key, guild)
            if percent < rarest_percent:
                rarest_percent = percent
                rarest_key = key

        return rarest_key, rarest_percent

    async def grant_achievement_role(self, member: discord.Member, role_name: str):
        role = discord.utils.get(member.guild.roles, name=role_name)

        if not role:
            return

        if role in member.roles:
            return

        try:
            await member.add_roles(role, reason="Achievement Unlocked")
        except:
            pass

    async def remove_achievement_role(self, member: discord.Member, role_name: str):
        role = discord.utils.get(member.guild.roles, name=role_name)

        if not role:
            return

        if role not in member.roles:
            return

        try:
            await member.remove_roles(role, reason="Achievements Reset")
        except:
            pass

    async def achievement_percentage(self, achievement_key: str, guild: discord.Guild) -> float:
        data = self.load_achievements()

        if not data:
            return 0.0

        total_users = guild.member_count
        if total_users == 0:
            return 0.0

        earned_count = sum(1 for achievements in data.values() if achievement_key in achievements)

        return round((earned_count / total_users) * 100.0, 1)


    def achievement_progress(self, ach: dict, ctx):
        if "progress" not in ach or "max" not in ach:
            return None

        current = ach["progress"](ctx)
        maximum = ach["max"]

        percent = round((current / maximum) * 100.0, 1) if maximum > 0 else 0
        return current, maximum, percent

    def has_bingo(self, completed: set[str]) -> bool:
        rows = [{f"{c}{r}" for c in "ABCDE"} for r in range(1,6)]
        cols = [{f"{c}{r}" for r in range(1,6)} for c in "ABCDE"]
        diags = [
            {f"{'ABCDE'[i]}{i+1}" for i in range(5)},
            {f"{'ABCDE'[4-i]}{i+1}" for i in range(5)}
        ]

        return any(line <= completed for line in rows + cols + diags)

    def count_bingo_suggestions(self, user_id: str) -> int:
        data = self.load_bingo_suggestions()
        return len(data.get(str(user_id), []))

    def count_challenge_suggestions(self, user_id: str) -> int:
        data = self.load_challenge_suggestions()
        return len(data.get(str(user_id), []))

    def build_ctx(self, user: discord.Member):
        user_id = str(user.id)

        points_data = self.load_points()
        weeks = [int(w) for w in points_data.get(user_id, [])]

        current_streak = self.calculate_streak(weeks)
        longest_streak = self.calculate_longest_streak(weeks)

        stats_data = self.stats_store.get(user_id)

        volunteer_data = self.load_volunteer_winners()
        votw_wins = sum(1 for uid in volunteer_data.values() if uid == user_id)

        curious = self.is_curious_ready(user_id) if not stats_data.get(CURIOUS_WINDOW_OK, False) else True

        earned = self.load_achievements().get(user_id, [])
        hidden_count = self.count_hidden_achievements(earned)

        return {
            MEMBER: user,
            USER_ID: str(user.id),
            WEEKS: weeks,
            TOTAL_CHALLENGES: len(weeks),
            CURRENT_STREAK: current_streak,
            LONGEST_STREAK: longest_streak,

            MESSAGES: stats_data.get(MESSAGES, 0),
            FILES: stats_data.get(FILES, 0),
            EREUSE_REACTS: stats_data.get(EREUSE_REACTS, 0),
            REACTIONS_GIVEN: stats_data.get(REACTIONS_GIVEN, 0),
            COMMANDS_USED: stats_data.get(COMMANDS_USED, 0),
            UNIQUE_COMMANDS: len(stats_data.get(UNIQUE_COMMANDS, [])),
            COMMAND_USAGE: stats_data.get(COMMAND_USAGE, {}),
            ANNOUNCEMENT_REACTS: stats_data.get(ANNOUNCEMENT_REACTS, 0),
            BINGOS_COMPLETE: stats_data.get(BINGOS_COMPLETE, 0),
            BINGO_SUGGESTIONS: self.count_bingo_suggestions(user_id),
            CHALLENGE_SUGGESTIONS: self.count_challenge_suggestions(user_id),

            VOICE_MINUTES: stats_data.get(VOICE_MINUTES, 0),
            VOICE_SESSION_MAX: stats_data.get(VOICE_SESSION_MAX, 0),
            VOICE_3P_MINUTES: stats_data.get(VOICE_3P_MINUTES, 0),
            VOICE_5P_MINUTES: stats_data.get(VOICE_5P_MINUTES, 0),

            VOTW_WINS: votw_wins,
            VOTW_VOTES_CAST: self.count_votes_given(user.id),
            VOTW_VOTES_RECIEVED: self.count_votes_recieved(user.id),

            SIX_SEVEN: stats_data.get(SIX_SEVEN, 0),
            ADMIN_VICTIM: stats_data.get(ADMIN_VICTIM, False),
            HIDDEN_ACHIEVEMENTS_COUNT: hidden_count,

            MAX_UNIQUE_REACTORS: stats_data.get(MAX_UNIQUE_REACTORS, 0),
            MAX_REACTIONS_ON_MESSAGE: stats_data.get(MAX_REACTIONS_ON_MESSAGE, 0),
            UNIQUE_USERS_REACTED_TO: len(stats_data.get(REACTED_USERS, [])),

            CURIOUS_WINDOW_OK: curious,
            YOU_FOUND_THIS: stats_data.get(YOU_FOUND_THIS, False),
            BUTTON_SMASHER: stats_data.get(BUTTON_SMASHER, False),
            USE_IT_WRONG: stats_data.get(USE_IT_WRONG, False),
            FOOTER_READER: stats_data.get(FOOTER_READER, False),

            LINKED_MINECRAFT: self.has_account_linked(user_id)
        }


    def _now_iso(self):
        return datetime.now(timezone.utc).isoformat()


    def _parse_iso(self, ts: str | None):
        if not ts:
            return None

        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None

    def is_curious_ready(self, user_id: str) -> bool:
        stats = self.stats_store.get(str(user_id))
        t1 = self._parse_iso(stats.get(LAST_PROFILE_AT))
        t2 = self._parse_iso(stats.get(LAST_COMPARE_AT))
        t3 = self._parse_iso(stats.get(LAST_SERVERSTATS_AT))

        if not (t1 and t2 and t3):
            return False

        now = datetime.now(timezone.utc)
        if (now - t1).total_seconds() > CURIOUS_WINDOW_SECONDS: return False
        if (now - t2).total_seconds() > CURIOUS_WINDOW_SECONDS: return False
        if (now - t3).total_seconds() > CURIOUS_WINDOW_SECONDS: return False

        times = [t1, t2, t3]
        if (max(times) - min(times)).total_seconds() > CURIOUS_WINDOW_SECONDS:
            return False

        self.stats_store.set_value(user_id, CURIOUS_WINDOW_OK, True)

        return True

    def count_hidden_achievements(self, earned: list[str]) -> int:
        return sum(1 for key in earned if ACHIEVEMENTS.get(key, {}).get("hidden", False))

    def has_account_linked(self, user_id: str) -> bool:
        user_id = str(user_id)
        data = self.load_links()
        user_entry = data.get(user_id, {})

        if user_entry.get("java" , None) or user_entry.get("bedrock", None):
            return True
        return False

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command):
        user_id = str(interaction.user.id)
        self.stats_store.bump(user_id, COMMANDS_USED, 1)

        stats = self.stats_store.all()
        user = stats.setdefault(user_id, {})

        unique = set(user.get(UNIQUE_COMMANDS, []))
        unique.add(command.name)
        user[UNIQUE_COMMANDS] = list(unique)

        usage = stats.get(user_id).setdefault(COMMAND_USAGE, {})
        usage[command.name] = usage.get(command.name, 0) + 1

        self.stats_store.save(stats)

        ctx = self.build_ctx(interaction.user)
        await self.achievement_engine.evaluate(ctx)

    @app_commands.command(name="sendchallenges", description="Send a random challenge to all the weekly challengers through DM's")
    @app_commands.describe(week="Week Number (e.g. 5)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= ["Challenge User DM's", "Weekly Challenges"],
            notes= "All challengers recieve a DM from the bot DO NOT USE twice in one week, check if already used")
    async def send_challenges(self, interaction: discord.Interaction, week: int):
        await interaction.response.defer()

        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=WEEKLY_CHALLENGE_ROLE)

        if not role:
            await interaction.followup.send(f"❌ {WEEKLY_CHALLENGE_ROLE} does not exist")
            return

        challenges = self.load_challenges()
        all_challenges = [challenge for category in challenges.values() for challenge in category]

        if not all_challenges:
            await interaction.followup.send(f"❌ No challenges found in {CHALLENGE_PATH}")
            return

        proof_channel = guild.get_channel(CHALLENGE_CHANNEL_ID)

        if not proof_channel:
            await interaction.followup.send(f"❌ Proof channel with id {CHALLENGE_CHANNEL_ID} not found")
            return

        proof_link = (f"https://discord.com/channels/{guild.id}/{CHALLENGE_CHANNEL_ID}")

        sent = 0
        failed = 0
        failed_users = []

        for member in role.members:
            challenge = random.choice(all_challenges)

            embed = discord.Embed(
                title=f"🎯 **Weekly eReuse Challenge - Week {week}**",
                color=discord.Color.green()
            )

            add_spacer(embed)

            embed.add_field(
                name="📌 **CHALLENGE**",
                value=("- " + challenge),
                inline=False
            )

            add_spacer(embed)

            embed.add_field(
                name="📥 **HOW TO SUBMIT PROOF**",
                value=(
                    "1️⃣ Click the proof channel link below\n"
                    "2️⃣ Paste the template\n"
                    "3️⃣ Attach the image/video proof\n"
                    "4️⃣ Click send!"
                ),
                inline=False
            )

            add_spacer(embed)

            embed.add_field(
                name="📍 **PROOF CHANNEL!**",
                value=f"{proof_link}",
                inline=False
            )

            add_spacer(embed)

            embed.add_field(
                name="📃 **COPY & PASTE TEMPLATE**",
                value=(
                    "```"
                    f"## Challenge (Week {week}):\n"
                    f"- {challenge}\n\n"
                    "### Proof:\n"
                    "```"
                ),
                inline=False
            )

            embed.set_footer(text="Good Luck! 💚 eReuse")

            try:
                await member.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                failed += 1
                failed_users.append(member.mention)

        failed_list_text = "\n".join(failed_users) if failed_users else "None 🎊"

        await self.log_action(
            guild=guild,
            message=f"⚒️ {interaction.user.mention} sent challenges out to {role.mention} for week **{week}**"
        )

        await interaction.followup.send(
            f"✅ **Challenges Sent!**\n\n"
            f"✉️ **Sent: {sent}**\n"
            f"❌ **Failed (DM's Closed): {failed}**\n"
            f"👥 **Users Who Did Not Recieve a DM:**\n"
            f"{failed_list_text}",
            allowed_mentions=discord.AllowedMentions(users=False)
        )


    @app_commands.command(name="resendchallenge", description="resend a challenge to a specific user")
    @app_commands.describe(user="User to send the challenge to", week="Week Number")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator", affects= ["Challenge User DM's", "Weekly Challenges"], notes= "An individual recieves a DM from the bot DO NOT USE twice on a person, check if already used")
    async def resend_challenge(self, interaction: discord.Interaction, user: discord.Member, week: int):
        await interaction.response.defer()

        guild = interaction.guild

        challenges = self.load_challenges()
        all_challenges = [challenge for category in challenges.values() for challenge in category]

        if not all_challenges:
            await interaction.followup.send(f"❌ No challenges found in {CHALLENGE_PATH}")
            return

        proof_channel = guild.get_channel(CHALLENGE_CHANNEL_ID)

        if not proof_channel:
            await interaction.followup.send(f"❌ Proof channel with id {CHALLENGE_CHANNEL_ID} not found")
            return

        proof_link = (f"https://discord.com/channels/{guild.id}/{CHALLENGE_CHANNEL_ID}")

        challenge = random.choice(all_challenges)

        embed = discord.Embed(
            title=f"🎯 **Weekly eReuse Challenge - Week {week}**",
            color=discord.Color.green()
        )

        add_spacer(embed)

        embed.add_field(
            name="📌 **CHALLENGE**",
            value=("- " + challenge),
            inline=False
        )

        add_spacer(embed)

        embed.add_field(
            name="📥 **HOW TO SUBMIT PROOF**",
            value=(
                "1️⃣ Click the proof channel link below\n"
                "2️⃣ Paste the template\n"
                "3️⃣ Attach the image/video proof\n"
                "4️⃣ Click send!"
            ),
            inline=False
        )

        add_spacer(embed)

        embed.add_field(
            name="📍 **PROOF CHANNEL!**",
            value=f"{proof_link}",
            inline=False
        )

        add_spacer(embed)

        embed.add_field(
            name="📃 **COPY & PASTE TEMPLATE**",
            value=(
                "```"
                f"## Challenge (Week {week}):\n"
                f"- {challenge}\n\n"
                "### Proof:\n"
                "```"
            ),
            inline=False
        )

        embed.set_footer(text="Good Luck! 💚 eReuse")

        await self.log_action(
            guild=guild,
            message=f"⚒️ {interaction.user.mention} resent the challenge out to {user.mention} for week **{week}**"
        )

        try:
            await user.send(embed=embed)
            await interaction.followup.send("✅ **Challenges Sent!**")
        except discord.Forbidden:
            await interaction.followup.send("❌ **Failed (DM's Closed)**")


    @app_commands.command(name="remindchallenges", description="Sends a reminder to complete the weekly challenge for those who havent")
    @app_commands.describe(week="The week to remind them")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator", affects= [
                "Challenge User DM's",
                "Weekly Challenges"
            ], notes= "The bot sends a reminder message to all users whose challenge has not been marked complete")
    async def remind_challenges(self, interaction: discord.Interaction, week: int):
        await interaction.response.defer()

        guild = interaction.guild
        role = discord.utils.get(guild.roles, name=WEEKLY_CHALLENGE_ROLE)

        if not role:
            await interaction.followup.send(f"❌ {WEEKLY_CHALLENGE_ROLE} does not exist")
            return

        data = self.load_points()

        sent = 0
        skipped = 0
        failed = 0
        failed_users = []

        for member in role.members:
            user_id = str(member.id)
            completed = {int(w) for w in data.get(user_id, [])}

            streak = self.calculate_streak(completed)

            if week in completed:
                skipped += 1
                continue

            try:
                await member.send(
                    f"## ⏰ Weekly **eReuse** Challenge Reminder\n"
                    f"You haven't completed the challenge for **Week {week}** yet!\n"
                    f"🔥 Complete it soon to " +
                    (f"keep your streak of {streak} alive!" if streak > 0 else f"start a streak!")
                )
                sent += 1
            except discord.Forbidden:
                failed += 1
                failed_users.append(member.mention)

        failed_list_text = "\n".join(failed_users) if failed_users else "None 🎊"

        await self.log_action(
            guild=guild,
            message=f"⚒️ {interaction.user.mention} sent challenge reminders out to {role.mention} for week **{week}**"
        )

        await interaction.followup.send(
            f"✅ **Challenge Reminder Sent!**\n\n"
            f"✉️ **Sent: {sent}**\n"
            f"⏩ **Already Completed:** {skipped}\n"
            f"❌ **Failed (DM's Closed): {failed}**\n"
            f"👥 **Users Who Did Not Recieve a DM:**\n"
            f"{failed_list_text}",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @app_commands.command(name="completechallenge", description="Complete a challenge for a user")
    @app_commands.describe(user="Who completed the challenge", week="Week number to award")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Weekly Challenges"
            ],
            notes= "Marks off a users challenge as completed, react to their proof aswell")
    async def complete_challenge(self, interaction: discord.Interaction, user: discord.Member, week: int):
        await interaction.response.defer()

        data = self.load_points()
        user_id = str(user.id)

        weeks = set(data.get(user_id, []))

        if week in weeks:
            await interaction.followup.send(
                f"⚠️ {user.mention} has already recieved points for **Week {week}**\n"
                f"🏆 Total Points: **{len(weeks)}**",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions(users=False)
            )

            return

        weeks.add(week)
        data[user_id] = sorted(weeks)
        self.save_points(data)

        streak = self.calculate_streak(list(weeks))

        if streak in {3, 5, 7, 10}:
            channel = interaction.guild.get_channel(CHALLENGE_CHANNEL_ID)
            await channel.send(
                f"🎊 {user.mention} just hit a streak of {streak} weeks! {'🔥' * (streak // 2)}"
            )

        ctx = self.build_ctx(user)
        await self.achievement_engine.evaluate(ctx)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} marked {user.mention}'s challenge for week **{week}** as completed"
        )

        await interaction.followup.send(
                f"✅ {user.mention} has completed the challenge for **Week {week}!**\n"
                f"🏆 Total Points: **{len(weeks)}**\n"
                f"🔥 Current Streak: **{streak}** weeks"
            )

    @app_commands.command(name="removechallenge", description="Remove a completed challenge from a user")
    @app_commands.describe(user="Who to remove the challenge from", week="Week number to remove")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Weekly Challenges",
                "Achievements"
            ],
            notes= "Removes a users challenge that was marked as completed")
    async def remove_challenge(self, interaction: discord.Interaction, user: discord.Member, week: int):
        await interaction.response.defer(ephemeral=True)

        data = self.load_points()
        user_id = str(user.id)

        weeks = set(data.get(user_id, []))

        if week not in weeks:
            await interaction.followup.send(
                f"⚠️ {user.mention} does not have any points for **Week {week}**\n"
                f"🏆 Total Points: **{len(weeks)}**",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions(users=False)
            )

            return

        weeks.remove(week)
        data[user_id] = sorted(weeks)
        self.save_points(data)

        self.stats_store.set_value(user_id, ADMIN_VICTIM, True)

        ctx = self.build_ctx(user)
        await self.achievement_engine.evaluate(ctx)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} removed {user.mention}'s challenge for week **{week}**"
        )

        await interaction.followup.send(
                f"✅ Removed {user.mention} from completing the challenge for **Week {week}!**\n"
                f"🏆 Total Points: **{len(weeks)}**",
                allowed_mentions=discord.AllowedMentions(users=False)
            )


    @app_commands.command(name="resetchallengepoints", description="Reset the challenge points for a user")
    @app_commands.describe(user="Whose points to reset")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Weekly Challenges"
            ],
            notes= "Removes all the completed challenges from a user")
    async def reset_challenge_points(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        data = self.load_points()
        user_id = str(user.id)

        if user_id in data:
            del data[user_id]


        self.save_points(data)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} reset all of {user.mention}'s challenge points"
        )

        await interaction.followup.send(
            f"🗑️ Reset {user.mention} points!\n",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @app_commands.command(name="resetachievements", description="Reset the achievements for a user")
    @app_commands.describe(user="Whose achievements to reset")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Achievements"
            ],
            notes= "Removes all the achievements from a user")
    async def reset_achievements(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        data = self.load_achievements()
        user_id = str(user.id)

        earned = data.get(user_id, [])

        for key in earned:
            role_name = ACHIEVEMENTS.get(key, {}).get("role")

            if role_name:
                await self.remove_achievement_role(user, role_name)

        if user_id in data:
            del data[user_id]


        self.save_achievements(data)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} reset all of {user.mention}'s achievements"
        )

        await interaction.followup.send(
            f"🗑️ Reset {user.mention} achievements and removed roles!\n",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @app_commands.command(name="challengepoints", description="Check a users weekly challenge points")
    @app_commands.describe(user="Whose points to check")
    async def challenge_points(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()

        if user.bot:
            self.stats_store.set_value(str(interaction.user.id), USE_IT_WRONG, True)
            ctx = self.build_ctx(interaction.user)
            await self.achievement_engine.evaluate(ctx)

        data = self.load_points()
        user_id = str(user.id)

        weeks = data[user_id] if user_id in data else []
        points = len(weeks)
        streak = self.calculate_streak(weeks)


        await interaction.followup.send(
            f"🏆 {user.mention} has {points} points!\n"
            f"📅 Weeks completed: {', '.join(map(str, weeks))}"
            f"🔥 Streak: {streak} weeks",
            allowed_mentions=discord.AllowedMentions(users=False)
        )


    @app_commands.command(name="mystreak", description="View your challenge streaks")
    async def my_streak(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = self.load_points()
        user_id = str(interaction.user.id)
        weeks = [int(w) for w in data.get(user_id, [])]

        current = self.calculate_streak(weeks)
        longest = self.calculate_longest_streak(weeks)

        fire = lambda x : "🔥" * max(1, min(3, x // 2)) if x != 0 else ""

        await interaction.followup.send(
            f"### {interaction.user.mention}'s Challenge Streak\n"
            f"🔥 Current Streak: **{current}** weeks {fire(current)}\n"
            f"🏆 Longest Streak: **{longest}** weeks {fire(longest)}\n"
            f"📅 Weeks Completed: {', '.join(map(str, weeks)) if weeks else 'None'}"
        )



    @app_commands.command(name="serverstats", description="View eReuse challenge server stats")
    async def server_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()

        guild = interaction.guild

        points = self.load_points()
        achievements = self.load_achievements()
        volunteer_winners = self.load_volunteer_winners()


        total_point_participants = len(points)
        total_completed = sum(len(w) for w in points.values())

        current_streaks = {
            uid: self.calculate_streak(w)
            for uid, w in points.items()
        }

        longest_streaks = {
            uid: self.calculate_longest_streak(w)
            for uid, w in points.items()
        }

        active_streaks = sum(1 for s in current_streaks.values() if s > 0)
        longest_current = max(current_streaks.values(), default=0)
        longest_ever =max(longest_streaks.values(), default=0)
        avg_challenges = round(total_completed / total_point_participants, 2) if total_point_participants else 0


        total_achievement_particiants = len(achievements)
        total_achievements = sum(len(v) for v in achievements.values())
        avg_achievements = round(total_achievements / total_achievement_particiants, 2) if total_achievement_particiants else 0

        achievements_counts = {}
        for user_achs in achievements.values():
            for key in user_achs:
                achievements_counts[key] = achievements_counts.get(key, 0) + 1

        most_common_ach = max(achievements_counts, key=achievements_counts.get, default=None)
        rarest_ach = min(achievements_counts, key=achievements_counts.get, default=None)
        common_percent = await self.achievement_percentage(most_common_ach, guild) if most_common_ach else 0.0
        rarest_percent = await self.achievement_percentage(rarest_ach, guild) if rarest_ach else 0.0

        stats = self.stats_store.all()

        total_messages = sum(v.get(MESSAGES, 0) for v in stats.values())
        total_reacts = sum(v.get(REACTIONS_GIVEN, 0) for v in stats.values())
        total_ann_reacts = sum(v.get(ANNOUNCEMENT_REACTS, 0) for v in stats.values())
        total_bingos = sum(v.get(BINGOS_COMPLETE, 0) for v in stats.values())

        top_messages = max(stats.items(), key=lambda x: x[1].get(MESSAGES, 0), default=(None, {}))[0]
        top_reacts = max(stats.items(), key=lambda x: x[1].get(REACTIONS_GIVEN, 0), default=(None, {}))[0]
        top_bingo = max(stats.items(), key=lambda x: x[1].get(BINGOS_COMPLETE, 0), default=(None, {}))
        top_bingo = top_bingo[0] if top_bingo[1].get(BINGOS_COMPLETE, 0) > 0 else None

        command_counts = {}

        for user_data in stats.values():
            usage = user_data.get(COMMAND_USAGE, {})
            for cmd, count in usage.items():
                command_counts[cmd] = command_counts.get(cmd, 0) + count

        most_commmon_command = max(command_counts, key=command_counts.get, default=None)
        most_commmon_count = command_counts.get(most_commmon_command, 0)

        def mention(uid):
            member = guild.get_member(int(uid)) if uid else None
            return member.mention if member else "-"

        emoji = discord.utils.get(interaction.guild.emojis, name="eReuse") or "📊"

        embed = discord.Embed(
            title=f"{emoji} **eReuse** Server Stats",
            description="📈 Live Community Overview",
            color=discord.Color.green()
        )

        embed.add_field(
            name="🌍 Community Activity",
            value=(
                f"💬  Messages Sent: **{total_messages}**\n"
                f"👍  Reactions Given: **{total_reacts}**\n"
                f"📢  Announcement Reactions: **{total_ann_reacts}**\n"
                f"🎟️  Total Bingos Complete: **{total_bingos}**\n"
                f"🏆  VOTW Awarded: **{len(volunteer_winners)}**\n"
            ),
            inline=False
        )

        add_spacer(embed)

        embed.add_field(
            name = "🏆 Challenges",
            value= (
                f"👥  Participants: **{total_point_participants}**\n"
                f"✅  Completed: **{total_completed}**\n"
                f"📊  Avg Per User: **{avg_challenges}**\n"
                f"🔥  Active Streaks: **{active_streaks}**\n"
                f"💥  Longest Current Streak: **{longest_current}**\n"
                f"🎖️  Longest Streak Ever: **{longest_ever}**"
            ),
            inline=False
        )

        add_spacer(embed)

        embed.add_field(
            name="🏅 Achievements",
            value= (
                f"👥  Total Participants: **{total_achievement_particiants}**\n"
                f"🎯  Total Unlocked: **{total_achievements}**\n"
                f"📊  Avg Per User: **{avg_achievements}**\n"
                f"✅  Most Common Achievement: **{ACHIEVEMENTS[most_common_ach]['name'] if most_common_ach else 'None'}** ({common_percent}%)\n"
                f"💎  Rarest Achievement: **{ACHIEVEMENTS[rarest_ach]['name'] if rarest_ach else 'None'}** ({rarest_percent}%)"
            ),
            inline=False
        )

        add_spacer(embed)

        embed.add_field(
            name="📊 Command Usage",
            value=(
                f"🏆 Most Used Command: **/{most_commmon_command}** ({most_commmon_count} uses)\n"
                f"⚙️ Total Commands Used: **{sum(command_counts.values())}**"
            )
        )

        add_spacer(embed)

        embed.add_field(
            name="👑 Top Contributors",
            value= (
                f"💬  Most Messages: {mention(top_messages)}\n"
                f"👍  Most Reactions: {mention(top_reacts)}\n"
                f"🎫  Most Bingos: {mention(top_bingo)}"
            ),
            inline=False
        )

        embed.set_footer(text="💚 eReuse")

        self.stats_store.set_value(str(interaction.user.id), LAST_SERVERSTATS_AT, self._now_iso())
        ctx = self.build_ctx(interaction.user)
        await self.achievement_engine.evaluate(ctx)

        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=False))


    @app_commands.command(name="achievements", description="View your achievements")
    @app_commands.describe(user="User to view (optional)")
    async def achievements(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()

        if user and user.id == interaction.user.id:
            self.stats_store.set_value(str(interaction.user.id), USE_IT_WRONG, True)
            ctx = self.build_ctx(interaction.user)
            await self.achievement_engine.evaluate(ctx)

        target = user or interaction.user

        embeds = await self._build_achievement_embeds(target)

        if not embeds:
            await interaction.followup.send("☹️ No Achievements Found.")
            return

        view = AchievementPages(embeds=embeds, viewer_id=interaction.user.id, target_id=target.id)

        await interaction.followup.send(embed=embeds[0], view=view)


    @app_commands.command(name="volunteeroftheweek", description="grant a volunteer the volunteer of the week")
    @app_commands.describe(user="Volunteer of the Week", week="week number")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Achievements",
                "Volunteer of The Week"
            ],
            notes= "Sets a user as volunteer of the week")
    async def volunteer_of_the_week(self, interaction: discord.Interaction, user: discord.Member, week: int):
        await interaction.response.defer()

        winners = self.load_volunteer_winners()
        week_key = str(week)

        previous = winners.get(week_key)
        if previous:
            await interaction.followup(f"⚠️ Winner for week {week} already exists!", ephemeral=True)
            return

        winners[week_key] = str(user.id)
        self.save_volunteer_winners(winners)

        ctx = self.build_ctx(user)
        await self.achievement_engine.evaluate(ctx)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} made {user.mention} the **Volunteer of the Week** for week {week}"
        )

        await interaction.followup.send(
            f"🏆 {user.mention} is **Volunteer of the Week (Week {week})** 💚"
        )

    @app_commands.command(name="removevotw", description="removes the volunteer of a week")
    @app_commands.describe(week="week number")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Achievements",
                "Volunteer of The Week"
            ],
            notes= "Removes a user as volunteer of the week")
    async def remove_volunteer_of_the_week(self, interaction: discord.Interaction, week: int):
        await interaction.response.defer()

        winners = self.load_volunteer_winners()
        week_key = str(week)

        if week_key in winners:
            del winners[week_key]

        self.save_volunteer_winners(winners)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} removed the **Volunteer of the Week** for week {week}"
        )

        await interaction.followup.send(
            f"❌ **Volunteer of the Week** has been removed from week {week}"
        )

    @app_commands.command(name="votw", description="Shows the volunteers of the week")
    async def volunteer_of_the_week_list(self, interaction: discord.Interaction):
        await interaction.response.defer()

        winners = self.load_volunteer_winners()

        if not winners:
            await interaction.followup.send("No **Volunteers of the Week** just yet 💤")
            return

        lines = ["## 🏆 **Volunteer of the Week* Winners\n"]

        for week in sorted(winners.keys(), key=int):
            user_id = winners[week]
            member = interaction.guild.get_member(int(user_id))
            name = member.mention if member else f"<@{user_id}>"

            lines.append(f"**Week {week}**  -  {name}")

        await interaction.followup.send("\n".join(lines), allowed_mentions=discord.AllowedMentions(users=False))


    @app_commands.command(name="profile", description="View a public eReuse profile")
    @app_commands.describe(user="User to view (optional)")
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()

        if user and user.id == interaction.user.id:
            self.stats_store.set_value(str(interaction.user.id), USE_IT_WRONG, True)
            ctx = self.build_ctx(interaction.user)
            await self.achievement_engine.evaluate(ctx)

        member = user or interaction.user

        s = self._format_user_summary(member)

        rare_key, rare_percent = await self.rarest_achievement(s["earned"], interaction.guild)

        embed = discord.Embed(
            title=f"📊 {member.display_name}'s eReuse Profile",
            color=discord.Color.green()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="🏆 Achievements",
            value=f"{s['achievements']} / {len(ACHIEVEMENTS)}",
            inline=True
        )

        if rare_key:
            embed.add_field(
                name="💎 Rarest Achievement",
                value=f"{ACHIEVEMENTS[rare_key]['name']} ({rare_percent}%)",
                inline=True
            )

        embed.add_field(
            name="🔥 Streaks",
            value=(
                f"Current: **{s['current_streak']}** weeks\n"
                f"Longest: **{s['longest_streak']}** weeks"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 Activity",
            value=(
                f"🗳️ Votes Given: **{s['votes_given']}**\n"
                f"📜 Votes Recieved: **{s['votes_received']}**\n"
                f"💬 Messages Sent: **{s['messages']}**\n"
                f"📎 Files Sent: **{s['files']}**\n"
                f"👍 Messages Reacted: **{s[REACTIONS_GIVEN]}**"
            ),
            inline=False
        )

        if s["earned"]:
            latest = s["earned"][-3:]
            embed.add_field(
                name="🏅 Recent Achievements",
                value="\n".join(f"- {ACHIEVEMENTS[k]['name']}" for k in latest),
                inline=False
            )

        if s[HIDDEN_ACHIEVEMENTS_COUNT] > 0:
            embed.add_field(
                name="🕵️ Hidden Achievements",
                value=f"**{s[HIDDEN_ACHIEVEMENTS_COUNT]}** discovered",
                inline=True
            )

        embed.add_field(
            name="🧠 Bot Usage",
            value=(
                f"⚙️ Commands Used: **{s[COMMANDS_USED]}**\n"
                f"🧩 Unique Commands: **{s[UNIQUE_COMMANDS]}**"
            ),
            inline=False
        )

        self.stats_store.set_value(str(interaction.user.id), LAST_PROFILE_AT, self._now_iso())
        ctx = self.build_ctx(interaction.user)
        await self.achievement_engine.evaluate(ctx)


        await interaction.followup.send(embed=embed)


    @app_commands.command(name="compare", description="Compare two eReuse profiles")
    @app_commands.describe(user1 = "First User", user2 = "Second User")
    async def compare_profiles(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        await interaction.response.defer()

        if user1.bot or user2.bot or user1.id == user2.id:
            self.stats_store.set_value(str(interaction.user.id), USE_IT_WRONG, True)
            ctx = self.build_ctx(interaction.user)
            await self.achievement_engine.evaluate(ctx)

        a = self._format_user_summary(user1)
        b = self._format_user_summary(user2)

        embed = discord.Embed(
            title="⚔️ Profile Comparison",
            description=f"{user1.mention} vs {user2.mention}",
            color=discord.Color.green()
        )

        embed.set_author(
            name=user1.display_name,
            icon_url=user1.display_avatar.url
        )

        embed.set_thumbnail(url=user2.display_avatar.url)

        pts_a, pts_b = self._cmp(a["points"], b["points"])
        streak_a, streak_b = self._cmp(a["current_streak"], b["current_streak"])
        ach_a, ach_b = self._cmp(a["achievements"], b["achievements"])
        vg_a, vg_b = self._cmp(a["votes_given"], b["votes_given"])
        vr_a, vr_b = self._cmp(a["votes_received"], b["votes_received"])
        msg_a, msg_b = self._cmp(a["messages"], b["messages"])
        file_a, file_b = self._cmp(a["files"], b["files"])
        react_a, react_b = self._cmp(a[REACTIONS_GIVEN], b[REACTIONS_GIVEN])
        bingo_sug_a, bingo_sug_b = self._cmp(a[BINGO_SUGGESTIONS], b[BINGO_SUGGESTIONS])
        challenge_sug_a, challenge_sug_b = self._cmp(a[CHALLENGE_SUGGESTIONS], b[CHALLENGE_SUGGESTIONS])
        command_a, command_b = self._cmp(a[COMMANDS_USED], b[COMMANDS_USED])
        u_command_a, u_command_b = self._cmp(a[UNIQUE_COMMANDS], b[UNIQUE_COMMANDS])
        hidden_a, hidden_b = self._cmp(a[HIDDEN_ACHIEVEMENTS_COUNT], b[HIDDEN_ACHIEVEMENTS_COUNT])

        embed.add_field(
            name=f"👤 {user1.display_name}",
            value=(
                f"🏆 Points: **{pts_a}**\n"
                f"🔥 Streak: **{streak_a}** (Longest: {a['longest_streak']})\n"
                f"🏅 Achievements: **{ach_a}**\n"
                f"🗳️ Votes Given: **{vg_a}**\n"
                f"📥 Votes Received: **{vr_a}**\n"
                f"💬 Messages: **{msg_a}**\n"
                f"📎 Files: **{file_a}**\n"
                f"👍 Reactions Given: **{react_a}**\n"
                f"🎟️ Bingo Suggestions: **{bingo_sug_a}**\n"
                f"🧩 Challenge Suggestions: **{challenge_sug_a}**\n"
                f"⚙️ Bot Commands Used: **{command_a}**\n"
                f"🤖 Unique Commands: **{u_command_a}**\n"
                f"❓ Hidden Achievements: **{hidden_a}**"
            ),
            inline=True
        )

        embed.add_field(
            name=f"👤 {user2.display_name}",
            value=(
                f"🏆 Points: **{pts_b}**\n"
                f"🔥 Streak: **{streak_b}** (Longest: {b['longest_streak']})\n"
                f"🏅 Achievements: **{ach_b}**\n"
                f"🗳️ Votes Given: **{vg_b}**\n"
                f"📥 Votes Received: **{vr_b}**\n"
                f"💬 Messages: **{msg_b}**\n"
                f"📎 Files: **{file_b}**\n"
                f"👍 Reactions Given: **{react_b}**\n"
                f"🎟️ Bingo Suggestions: **{bingo_sug_b}**\n"
                f"🧩 Challenge Suggestions: **{challenge_sug_b}**\n"
                f"⚙️ Bot Commands Used: **{command_b}**\n"
                f"🤖 Unique Commands: **{u_command_b}**\n"
                f"❓ Hidden Achievements: **{hidden_b}**"
            ),
            inline=True
        )

        self.stats_store.set_value(str(interaction.user.id), LAST_COMPARE_AT, self._now_iso())
        ctx = self.build_ctx(interaction.user)
        await self.achievement_engine.evaluate(ctx)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="completebingo", description="Mark a users bingo tile complete")
    @app_commands.describe(user="Who to mark progress for", card_number="Bingo card number", row="Row number (1-5)", col="Column Letter (A-E)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Achievements",
                "Bingo Progress",
            ],
            notes= "Completes an individual tile for a users bingo")
    async def complete_bingo(self, interaction: discord.Interaction, user: discord.Member, card_number: int, row: int, col: str):
        await interaction.response.defer()

        col = col.upper()

        if row not in range(1, 6) or col not in "ABCDE":
            await interaction.followup.send(f"⚠️ Invalid Row or Column", ephemeral=True)
            return

        user_id = str(user.id)
        card_key = str(card_number)
        tile = f"{col}{row}"

        progress = self.load_bingo_progress()
        user_data = progress.setdefault(user_id, {})
        card_data = user_data.setdefault(card_key, {"completed": []})

        cards = self.load_bingo_cards()

        if card_key not in cards:
            await interaction.followup.send(f"⚠️ Card {card_key} does not exist", ephemeral=True)
            return


        cards_def = cards[card_key]
        free_tiles = cards_def.get("free_tiles", [])

        for ftile in free_tiles:
            if ftile not in card_data["completed"]:
                card_data["completed"].append(ftile)

        if tile in card_data["completed"]:
            await interaction.followup.send(f"⚠️ Tile already completed", ephemeral=True)
            return

        card_data["completed"].append(tile)
        self.save_bingo_progress(progress)

        if self.has_bingo(set(card_data["completed"])):
            self.stats_store.bump(str(user.id), BINGOS_COMPLETE, 1)
            channel = interaction.guild.get_channel(BINGO_CHANNEL_ID)
            if channel:
                await channel.send(f"## Congrats to {user.mention} for completing the bingo card {card_number} 🥳🎉", silent=True)

        ctx = self.build_ctx(user)
        await self.achievement_engine.evaluate(ctx)

        await self.log_action(message= f"⚒️ {interaction.user.mention} marked {user.mention}'s bingo tile {tile} for card **{card_number}** complete", guild=interaction.guild)

        await interaction.followup.send(
            f"✅ Marked {user.mention}'s bingo tile {tile} for card **{card_number}** completed",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @app_commands.command(name="removebingo", description="Remove a users completed bingo tile")
    @app_commands.describe(user="Who to remove the bingo tile from", card_number="Bingo card number", row="Row Number (1-5)", col="Column Letter (A-E)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Stats Tracking",
                "Achievements",
                "Bingo Progress",
            ],
            notes= "Removes an individual tiles completion for a users bingo")
    async def remove_bingo(self, interaction: discord.Interaction, user: discord.Member, card_number: int, row: int, col: str):
        await interaction.response.defer(ephemeral=True)

        col = col.upper()

        if row not in range(1, 6) or col not in "ABCDE":
            await interaction.followup.send(f"⚠️ Invalid Row or Column", ephemeral=True)
            return

        user_id = str(user.id)
        card_key = str(card_number)
        tile = f"{col}{row}"

        progress = self.load_bingo_progress()
        user_data = progress.setdefault(user_id, {})
        card_data = user_data.setdefault(card_key, {"completed": []})

        if not card_data or tile not in card_data.get("completed", []):
            await interaction.followup.send(
                f"⚠️ {user.mention} does not have completed the bingo card tile **{tile}** for card **{card_key}**",
                allowed_mentions=discord.AllowedMentions(users=False)
            )
            return

        was_bingo = self.has_bingo(set(card_data["completed"]))
        card_data["completed"].remove(tile)

        if not card_data["completed"]:
            user_data.pop(card_key)
        else:
            user_data[card_key] = card_data

        if not user_data:
            progress.pop(user_id)
        else:
            progress[user_id] = user_data

        self.save_bingo_progress(progress)

        is_bingo = self.has_bingo(set(card_data.get("completed", [])))

        if was_bingo and not is_bingo:
            self.stats_store.bump(user_id, BINGOS_COMPLETE, -1)

        self.stats_store.set_value(user_id, ADMIN_VICTIM, True)

        ctx = self.build_ctx(user)
        await self.achievement_engine.evaluate(ctx)

        await self.log_action(
            guild=interaction.guild,
            message=f"🗑️ {interaction.user.mention} removed {user.mention}'s the bingo card tile **{tile}** for card **{card_key}**"
        )

        await interaction.followup.send(
            f"✅ Removed bingo card **{card_key}** from {user.mention}.",
            allowed_mentions=discord.AllowedMentions(users=False)
        )

    @app_commands.command(name="mybingo", description="View your completed bingo cards")
    async def my_bingo(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        progress = self.load_bingo_progress()
        user_id = str(interaction.user.id)
        cards = progress.get(user_id, {})

        completed = []

        for card_key, data in cards.items():
            if self.has_bingo(set(data.get("completed", []))):
                completed.append(card_key)

        if not completed:
            await interaction.followup.send("☹️ You haven't completed any bingo cards yet.")
            return

        await interaction.followup.send(
            "## 🎟️ Your completed bingo cards\n" +
            "\n".join(f"- Card **{c}**" for c in completed)
        )

    @app_commands.command(name="createbingocard", description="Create a new bingo card")
    @app_commands.describe(card_number="The number associated with the card")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Bingo Cards",
            ],
            notes= "Creates a brand new bingo card for a specific week, only test with negative weeks (-1, -2, ...)")
    async def create_bingo_card(self, interaction: discord.Interaction, card_number: int):
        await interaction.response.send_modal(CreateBingoCardModal(self, card_number))

    @app_commands.command(name="viewbingocard", description="View a bingo card")
    @app_commands.describe(card_number="The bingo cards number")
    async def view_bingo_card(self, interaction: discord.Interaction, card_number: int):
        await interaction.response.defer()

        cards = self.load_bingo_cards()
        key = str(card_number)

        if key not in cards:
            await interaction.followup.send(
                f"❌ Bingo card #{card_number} does not exist",
                ephemeral=True
            )
            return

        grid = cards[key]["grid"]

        image_path = render_bingo_card(key, grid, [], None)

        await interaction.followup.send(
            file=discord.File(image_path)
        )

    @app_commands.command(name="bingo", description="View someones bingo card")
    @app_commands.describe(card_number="Bingo Card Number", user = "Whose bingo card")
    async def view_bingo(self, interaction: discord.Interaction, card_number: int, user: discord.Member | None = None):
        await interaction.response.defer()

        if user and user.id == interaction.id:
            self.stats_store.set_value(str(interaction.user.id), USE_IT_WRONG, True)
            ctx = self.build_ctx(interaction.user)
            await self.achievement_engine.evaluate(ctx)

        user = user or interaction.user

        cards = self.load_bingo_cards()
        card_key = str(card_number)

        if card_key not in cards:
            await interaction.followup.send(
                f"❌ Bingo card #{card_number} does not exist",
                ephemeral=True
            )
            return

        progress = self.load_bingo_progress()
        completed = progress.get(str(user.id), {}).get(card_key, {}).get("completed", [])

        image_path = render_bingo_card(card_key, cards[card_key]["grid"], completed, user)
        await interaction.followup.send(
            file=discord.File(image_path)
        )


    @app_commands.command(name="suggestbingo", description="Suggest a bingo tile idea")
    @app_commands.describe(text="The suggestion")
    async def suggest_bingo(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=True)

        data = self.load_bingo_suggestions()
        user_id = str(interaction.user.id)

        data.setdefault(user_id, []).append({
            "text": text,
            "timestamp": interaction.created_at.isoformat()
        })

        self.save_bingo_suggestions(data)

        await self.log_action(
            interaction.guild,
            f"🧩 {interaction.user.mention} suggested a bingo tile: `{text}`"
        )

        await interaction.followup.send("✅ Bingo Suggestion Submitted! 💚")


    @app_commands.command(name="suggestchallenge", description="Suggest a weekly challenge idea")
    @app_commands.describe(text="The suggestion")
    async def suggest_challenge(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=True)

        data = self.load_challenge_suggestions()
        user_id = str(interaction.user.id)

        data.setdefault(user_id, []).append({
            "text": text,
            "timestamp": interaction.created_at.isoformat()
        })

        self.save_challenge_suggestions(data)

        await self.log_action(
            interaction.guild,
            f"🧩 {interaction.user.mention} suggested a weekly challenge: `{text}`"
        )

        await interaction.followup.send("✅ Weekly Challenge Suggestion Submitted! 💚")


    @app_commands.command(name="createchallenge", description="Create a new weekly challenge")
    @app_commands.describe(category="The Category of the challenge (General/Fun/Tech)", text="The challenge itself")
    @app_commands.choices(category=[
        Choice(name="General", value="General"),
        Choice(name="Fun", value="Fun"),
        Choice(name="Tect", value="Tech")
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
                "Weekly Challenges",
            ],
            notes= "Check out `/viewchallenges` for existing challenges and\n`/viewsuggestions challenge` for suggestions")
    async def create_challenge(self, interaction: discord.Interaction, category: Choice[str], text: str):
        await interaction.response.defer(ephemeral=True)

        challenges = self.load_challenges()
        category = category.capitalize()

        challenges.setdefault(category, []).append(text)

        self.save_challenges(challenges)

        await self.log_action(
            interaction.guild,
            f"⚒️ {interaction.user.mention} added a challenge to **{category}**: `{text}`"
        )

        await interaction.followup.send(
            f"✅ Challenge added to **{category}**"
        )


    @app_commands.command(name="viewchallenges", description="View all of the weekly challenges")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
            ],
            notes= "Use this as a basis for other ideas for challenges")
    async def view_challenges(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        challenges = self.load_challenges()
        embeds = []

        chunk_size = 5

        for category, items in challenges.items():
            for i in range(0, len(items), chunk_size):

                embed = discord.Embed(
                    title="🧩 Weekly Challenges",
                    description=f"**Catergory:** {category}",
                    color=discord.Color.green()
                )

                chunk = items[i:i + chunk_size]

                for challenge in chunk:
                    embed.add_field(
                        name = f"- {challenge}",
                        value="\n",
                        inline=False
                    )

                embeds.append(embed)

        if not embeds:
           await interaction.followup.send("🥲 No Commands Avaliable", ephemeral=True)
           return

        total_pages = len(embeds)
        for i, embed in enumerate(embeds, start=1):
            embed.set_footer(
                    text = f"Page {i} / {total_pages}"
                )

        view = AchievementPages(embeds=embeds, viewer_id=interaction.user.id, target_id=interaction.user.id)

        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)


    @app_commands.command(name="viewsuggestions", description="View submitted suggestions")
    @app_commands.describe(kind="Type of suggestion to view")
    @app_commands.choices(kind=[
        Choice(name="Bingo", value="bingo"),
        Choice(name="Challenge", value="challenge")
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [
            ],
            notes= "Use this to view the bingo and weekly challenge suggestions")
    async def view_suggestions(self, interaction: discord.Interaction, kind: Choice[str]):
        await interaction.response.defer(ephemeral=True)

        if kind.value == "bingo":
            data = self.load_bingo_suggestions()
            title = "🧩 Bingo Suggestions"
        else:
            data = self.load_challenge_suggestions()
            title = "💡 Challenge Suggestions"

        embeds = []
        chunk_size = 5

        if not data:
            await interaction.followup.send(f"🥲 No {kind.value} suggestions yet.", ephemeral=True)
            return

        all_suggestions = []
        for uid, items in data.items():
            for entry in items:
                all_suggestions.append((uid, entry))

        for i in range(0, len(all_suggestions), chunk_size):
            embed = discord.Embed(
                title=title,
                color=discord.Color.green()
            )

            chunk = items[i:i + chunk_size]

            for uid, entry in chunk:
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else f"User {uid}"

                embed.add_field(
                    name = f"👥 {name}",
                    value=f"📝 {entry['text']}",
                    inline=False
                )

            embeds.append(embed)

        if not embeds:
           await interaction.followup.send("🥲 No Suggestions Avaliable", ephemeral=True)
           return

        total_pages = len(embeds)
        for i, embed in enumerate(embeds, start=1):
            embed.set_footer(
                    text = f"Page {i} / {total_pages}"
                )

        view = AchievementPages(embeds=embeds, viewer_id=interaction.user.id, target_id=interaction.user.id)

        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)

async def setup(bot, stats_store, achievement_engine):
    await bot.add_cog(Challenges(bot, stats_store, achievement_engine))