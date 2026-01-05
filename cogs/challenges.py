import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from pathlib import Path
from constants import WEEKLY_CHALLENGE_ROLE, CHALLENGE_PATH, CHALLENGE_CHANNEL_ID, CHALLENGE_POINTS_PATH, MODERATOR_ONLY_CHANNEL_ID, ACHEIVEMENTS_PATH
from helpers.embedHelper import add_spacer
from helpers.achievments import ACHIEVEMENTS

DATA_FILE = Path(CHALLENGE_PATH)
POINTS_FILE = Path(CHALLENGE_POINTS_PATH)
ACHIEVEMENTS_FILE = Path(ACHEIVEMENTS_PATH)

class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    async def log_action(self, guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

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

        achievement_data = self.load_achievements()
        earned = set(achievement_data.get(user_id, []))

        for key, ach in ACHIEVEMENTS.items():
            if key in earned:
                continue

            if ach["check"](weeks, streak):
                earned.add(key)
                await interaction.channel.send(
                    f"### 🏅 {user.mention} Unlocked an Achievement\n"
                    f"**{ach['name']}**\n"
                    f"{ach['description']}"
                )

        achievement_data[user_id] = sorted(earned)
        self.save_achievements(achievement_data)

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

        if user_id in data:
            del data[user_id]


        self.save_achievements(data)

        await self.log_action(
            guild=interaction.guild,
            message=f"⚒️ {interaction.user.mention} reset all of {user.mention}'s achievements"
        )

        await interaction.followup.send(
            f"🗑️ Reset {user.mention} achievements!\n",
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

        if not earned:
            await interaction.followup.send("You haven't unlocked any achievements **YET**!")
            return

        text = f"## {interaction.user.mention}'s Achievments\n"
        text += "\n".join(
            f"🏅 **{ACHIEVEMENTS[k]['name']} - {ACHIEVEMENTS[k]['description']}**" for k in earned
        )

        await interaction.followup.send(text)

    @app_commands.command(name="viewachievements", description="View all avaliable achievements")
    async def view_achievements(self, interaction: discord.Interaction):
        await interaction.response.defer()

        text = f"## 🏆 All Avaliable Achievements\n"
        text += "\n".join(
            f"🏅 **{ach['name']} - {ach['description']}**" for ach in ACHIEVEMENTS.values()
        )

        await interaction.followup.send(text)

async def setup(bot):
    await bot.add_cog(Challenges(bot))