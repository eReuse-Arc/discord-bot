import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from pathlib import Path
from constants import WEEKLY_CHALLENGE_ROLE, CHALLENGE_PATH, CHALLENGE_CHANNEL_ID, CHALLENGE_POINTS_PATH
from helpers.embedHelper import add_spacer

DATA_FILE = Path(CHALLENGE_PATH)
POINTS_FILE = Path(CHALLENGE_POINTS_PATH)

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

        await interaction.followup.send(
            f"✅ **Challenges Sent!**\n\n"
            f"✉️ **Sent: {sent}**\n"
            f"❌ **Failed (DM's Closed): {failed}**\n"
            f"👥 **Users Who Did Not Recieve a DM:**\n"
            f"{failed_list_text}"
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

        sent = 0
        failed = 0
        failed_users = []

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
            await user.send(embed=embed)
            await interaction.followup.send("✅ **Challenges Sent!**")
        except discord.Forbidden:
            await interaction.followup.send("❌ **Failed (DM's Closed)**")

async def setup(bot):
    await bot.add_cog(Challenges(bot))