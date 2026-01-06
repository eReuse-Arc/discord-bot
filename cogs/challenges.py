import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from pathlib import Path
from constants import WEEKLY_CHALLENGE_ROLE, CHALLENGE_PATH, CHALLENGE_CHANNEL_ID, CHALLENGE_POINTS_PATH, MODERATOR_ONLY_CHANNEL_ID, ACHEIVEMENTS_PATH, VOLUNTEER_OF_THE_WEEK_PATH, VOLUNTEER_VOTES_PATH
from helpers.embedHelper import add_spacer
from helpers.achievements import ACHIEVEMENTS

DATA_FILE = Path(CHALLENGE_PATH)
POINTS_FILE = Path(CHALLENGE_POINTS_PATH)
ACHIEVEMENTS_FILE = Path(ACHEIVEMENTS_PATH)
VOLUNTEER_FILE = Path(VOLUNTEER_OF_THE_WEEK_PATH)
VOTES_FILE = Path(VOLUNTEER_VOTES_PATH)


class Challenges(commands.Cog):
    def __init__(self, bot, stats_store, achievement_engine):
        self.bot = bot
        self.stats_store = stats_store
        self.achievement_engine = achievement_engine

    def load_challenges(self):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

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

    def count_votes_recieved(self, user_id: str) -> int:
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

    def build_ctx(self, user: discord.Member):
        user_id = str(user.id)

        points_data = self.load_points()
        weeks = [int(w) for w in points_data.get(user_id, [])]

        current_streak = self.calculate_streak(weeks)
        longest_streak = self.calculate_longest_streak(weeks)

        stats_data = self.stats_store.get(user_id)

        volunteer_data = self.load_volunteer_winners()
        votw_wins = sum(1 for uid in volunteer_data.values() if uid == user_id)

        return {
            "member": user,
            "user_id": str(user.id),
            "weeks": weeks,
            "total_challenges": len(weeks),
            "current_streak": current_streak,
            "longest_streak": longest_streak,

            "messages": stats_data.get("messages", 0),
            "files": stats_data.get("files", 0),
            "ereuse_reacts": stats_data.get("ereuse_reacts", 0),

            "votw_wins": votw_wins,
            "votw_votes_cast": self.count_votes_given(user.id)
        }

    @app_commands.command(name="sendchallenges", description="Send a random challenge to all the weekly challengers through DM's")
    @app_commands.describe(week="Week Number (e.g. 5)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
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

    @app_commands.command(name="me", description="View your eResue stats")
    async def me(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = self.load_points()
        user_id = str(interaction.user.id)
        weeks = [int(w) for w in data.get(user_id, [])]

        fire = lambda x : "🔥" * max(1, min(3, x // 2)) if x != 0 else ""

        points = len(weeks)
        streak = self.calculate_streak(weeks)
        longest = self.calculate_longest_streak(weeks)
        rank = self.get_rank(user_id, data)

        emoji = discord.utils.get(interaction.guild.emojis, name="eReuse")
        emoji = "📊" if not emoji else emoji

        await interaction.followup.send(
            f"## {emoji} {interaction.user.mention}'s **eReuse** Stats\n"
            f"🏆 Points: **{points}**\n"
            f"🔥 Current Streak: **{streak}** {fire(streak)}\n"
            f"🎖️ Longest Streak: **{longest}** {fire(longest)}\n"
            f"📈 Rank: **#{rank}**\n"
            f"📅 Weeks Completed: {', '.join(map(str, weeks)) if weeks else 'None'}"
        )



    @app_commands.command(name="serverstats", description="View eReuse challenge server stats")
    async def server_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()

        data = self.load_points()

        total_participants = len(data)
        total_completed = sum(len(w) for w in data.values())
        active_streaks = sum(1 for w in data.values() if self.calculate_streak(w) > 0)
        longest_streak = max((self.calculate_streak(w) for w in data.values()), default=0)
        longest_ever =max((self.calculate_longest_streak(w) for w in data.values()), default=0)

        emoji = discord.utils.get(interaction.guild.emojis, name="eReuse")
        emoji = "📊" if not emoji else emoji

        embed = discord.Embed(
            title=f"{emoji} **eReuse** Server Stats",
            color=discord.Color.green()
        )

        embed.add_field(name="👥 Participants", value=total_participants, inline=True)
        embed.add_field(name="🏆 Challenges Completed", value=total_completed, inline=True)
        embed.add_field(name="🔥 Active Streaks", value=active_streaks, inline=True)
        embed.add_field(name="💥 Longest Current Streak", value=longest_streak, inline=True)
        embed.add_field(name="🎖️ Longest Streak Ever", value=longest_ever, inline=True)

        await interaction.followup.send(embed=embed)


    @app_commands.command(name="achievements", description="View your achievements")
    async def achievements(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        achievement_data = self.load_achievements()
        earned = achievement_data.get(user_id, [])

        points_data = self.load_points()
        weeks = [int(w) for w in points_data.get(user_id, [])]

        ctx = self.build_ctx(interaction.user)

        embed = discord.Embed(
            title=f"🏆 {interaction.user.display_name}'s Achievements",
            color=discord.Color.green()
        )

        for key, ach in ACHIEVEMENTS.items():
            unlocked = key in earned
            status = "✅  Unlocked" if unlocked else "🔒  Locked"

            percent = await self.achievement_percentage(key, interaction.guild)
            rarity = (
                "💎 Ultra Rare" if percent <= 5 else
                "🔥 Rare" if percent <= 15 else
                "⭐ Uncommon" if percent <= 40 else
                "✅ Common"
            )

            value = (
                f" \n"
                f"{status}\n"
                f"💬  {ach['description']}\n"
                f"📊  {percent}% of members - {rarity}"
            )

            progress = self.achievement_progress(ach, ctx)
            if progress:
                current, maximum, p = progress
                bar = "▓" * (round(p) // 10) + "░" * (10 - round(p) // 10)
                value += f"\n📈 {current} / {maximum}  ({p}%)\n`{bar}`\n \u200b\n"



            embed.add_field(
                name=f"🏅 {ach['name']}",
                value=value,
                inline=False
            )

        await interaction.followup.send(embed=embed)


    @app_commands.command(name="viewachievements", description="View all avaliable achievements")
    async def view_achievements(self, interaction: discord.Interaction):
        await interaction.response.defer()

        guild = interaction.guild

        text = f"## 🏆 All Avaliable Achievements\n"

        for key, ach in ACHIEVEMENTS.items():
            percent = await self.achievement_percentage(key, guild)

            rarity = (
                "💎 Ultra Rare" if percent <= 5 else
                "🔥 Rare" if percent <= 15 else
                "⭐ Uncommon" if percent <= 40 else
                "✅ Common"
            )

            text += (
                f"🏅 **{ach['name']}**\n"
                f"💬 {ach['description']}\n"
                f"📊 **Unlocked by {percent}% of members**  -  {rarity}\n\n"
            )

        await interaction.followup.send(text)


    @app_commands.command(name="volunteeroftheweek", description="grant a volunteer the volunteer of the week")
    @app_commands.describe(user="Volunteer of the Week", week="week number")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
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

        member = user or interaction.user
        user_id = str(member.id)

        points_data = self.load_points()
        achievments_data = self.load_achievements()

        weeks = [int(w) for w in points_data.get(user_id, [])]
        earned = achievments_data.get(user_id, [])

        ctx = self.build_ctx(member)

        votes_given = self.count_votes_given(user_id)
        votes_recieved = self.count_votes_recieved(user_id)

        rare_key, rare_percent = await self.rarest_achievement(earned, interaction.guild)

        embed = discord.Embed(
            title=f"📊 {member.display_name}'s eReuse Profile",
            color=discord.Color.green()
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="🏆 Achievements",
            value=f"{len(earned)} / {len(ACHIEVEMENTS)}",
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
                f"Current: {ctx['current_streak']} weeks\n"
                f"Longest: {ctx['longest_streak']} weeks"
            ),
            inline=False
        )

        embed.add_field(
            name="📈 Activity",
            value=(
                f"🗳️ Votes Given: {votes_given}\n"
                f"📜 Votes Recieved: {votes_recieved}\n"
                f"💬 Messages Sent: {ctx['messages']}\n"
                f"📎 Files Sent: {ctx['files']}"
            ),
            inline=False
        )

        if earned:
            latest = earned[-3:]
            embed.add_field(
                name="🏅 Recent Achievements",
                value="\n".join(f"- {ACHIEVEMENTS[k]['name']}" for k in latest),
                inline=False
            )

        await interaction.followup.send(embed=embed)

async def setup(bot, stats_store, achievement_engine):
    await bot.add_cog(Challenges(bot, stats_store, achievement_engine))