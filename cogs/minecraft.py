import discord
from discord.ext import commands
from discord import app_commands
from helpers.roleChecks import *
from pathlib import Path
import json
from dotenv import load_dotenv
import os
from constants import VOLUNTEER_ROLE, SENIOR_VOLUNTEER_ROLE, OFFICER_ROLE, MINECRAFT_LINKS_PATH, RATE_LIMIT_SECONDS, MODERATOR_ONLY_CHANNEL_ID
from mcrcon import MCRcon
import time
import re

load_dotenv()

RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = int(os.getenv("RCON_PORT"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD")

LINKS_FILE = Path(MINECRAFT_LINKS_PATH)

ROLE_MAP = {
    VOLUNTEER_ROLE: "volunteer",
    SENIOR_VOLUNTEER_ROLE: "seniorvolunteer",
    OFFICER_ROLE: "officer"
}

BEDROCK_GEYSER_RE = re.compile(
    r"""^
    \.?                          # optional leading dot (Geyser)
    (?! )                        # no leading space
    (?!.*\s{2,})                 # no consecutive spaces
    [A-Za-z0-9_\- ]{3,20}        # allowed characters
    (?<! )                       # no trailing space
    $
    """,
    re.VERBOSE
)
JAVA_REGEX = re.compile(r"^[A-Za-z0-9_]{3,16}$")

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_action(self, guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

    def save_links(self, data):
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def load_links(self):
        if not LINKS_FILE.exists():
            return {}
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_lp_group(self, member: discord.Member):
        for role in member.roles:
            if role.name in ROLE_MAP:
                return ROLE_MAP[role.name]

        return None

    def run_rcon(self, cmd: str):
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            mcr.command(cmd)

    def is_valid_java(self, name: str) -> bool:
        return bool(JAVA_REGEX.fullmatch(name))

    def is_valid_bedrock(self, name: str) -> bool:
        return bool(BEDROCK_GEYSER_RE.fullmatch(name))

    def safe_username(self, name: str, platform: str) -> bool:
        if not isinstance(name, str):
            return False

        if any(c in name for c in ("\n", "\r", "\t", "\0")):
            return False

        if platform == "java":
            return self.is_valid_java(name)
        else:
            return self.is_valid_bedrock(name)

    @app_commands.command(name="link", description="Link your minecraft account")
    @app_commands.describe(platform= "Java or Bedrock", minecraft_name="Your minecraft username for java or bedrock")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock")
    ])
    async def link(self, interaction: discord.Interaction, platform: app_commands.Choice[str], minecraft_name: str):
        await interaction.response.defer()

        if not self.safe_username(minecraft_name, platform.value):
            await interaction.followup.send("❌ username is unsafe", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        now = time.time()
        data = self.load_links()

        user_entry = data.get(user_id, {
            "java": None,
            "bedrock": None,
            "last_action": 0
        })

        if now - user_entry["last_action"] < RATE_LIMIT_SECONDS:
            await interaction.followup.send("⌛ Please wait before using this command again", ephemeral=True)
            return

        if platform.value == "bedrock" and not minecraft_name.startswith("."):
            minecraft_name = "." + minecraft_name

        if user_entry[platform.value] is not None:
            await interaction.followup.send(f"❌ You already have a {platform.name} account linked: {user_entry[platform.value]}", ephemeral=True)
            return

        lp_group = self.get_lp_group(interaction.user)
        if not lp_group:
            await interaction.followup.send(f"❌ You do not have a valid discord role to link a minecraft account. Needs at least: ***{VOLUNTEER_ROLE}***", ephemeral=True)
            return

        self.run_rcon(f"whitelist add {minecraft_name}")
        self.run_rcon(f"lp user {minecraft_name} parent set {lp_group}")

        user_entry[platform.value] = minecraft_name
        user_entry["last_action"] = now
        data[user_id] = user_entry
        self.save_links(data)

        await self.log_action(interaction.guild, f"🌲 {interaction.user.mention} linked {platform.value} account `{minecraft_name}`")

        await interaction.followup.send(f"✅ **{platform.name} account linked:** `{minecraft_name}`")


    @app_commands.command(name="unlink", description="unlink your minecraft account")
    @app_commands.describe(platform= "Java or Bedrock")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock")
    ])
    async def unlink(self, interaction: discord.Interaction, platform: app_commands.Choice[str]):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        now = time.time()
        data = self.load_links()

        user_entry = data.get(user_id, {})

        if not user_entry or not user_entry.get(platform.value):
            await interaction.followup.send(f"❌ No {platform.name} account linked.", ephemeral=True)
            return

        mc_name = user_entry[platform.value]

        self.run_rcon(f"whitelist remove {mc_name}")
        self.run_rcon(f"lp user {mc_name} clear")

        user_entry[platform.value] = None
        user_entry["last_action"] = now
        data[user_id] = user_entry
        self.save_links(data)

        await self.log_action(interaction.guild, f"🌲 {interaction.user.mention} unlinked {platform.value} account `{mc_name}`")

        await interaction.followup.send(f"🗑️ **{platform.name} account linked:** `{mc_name}`")

    @app_commands.command(name="status", description="Link your minecraft account")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        data = self.load_links()

        user_entry = data.get(user_id, {})

        if not user_entry:
            await interaction.followup.send(f"❌ You have no linked accounts", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔗 Minecraft Link Status",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Java",
            value= user_entry.get("java", "❌ Not Linked"),
            inline= False
        )
        embed.add_field(
            name="Bedrock",
            value= user_entry.get("bedrock", "❌ Not Linked"),
            inline= False
        )

        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Minecraft(bot))