import discord
from discord.ext import commands, tasks
from discord import app_commands
from helpers.roleChecks import *
from pathlib import Path
import json
from dotenv import load_dotenv
import os
from constants import VOLUNTEER_ROLE, SENIOR_VOLUNTEER_ROLE, OFFICER_ROLE, MINECRAFT_LINKS_PATH, RATE_LIMIT_SECONDS, MODERATOR_ONLY_CHANNEL_ID, MINECRAFT_SERVER_STATUS_MESSAGE_ID, MINECRAFT_SERVER_CHANNEL_ID
from mcrcon import MCRcon
import socket
import time
import re
from helpers.achievements import get_user_achievements, AchievementView, achievement_percentage, rarity_style
from mcstatus import JavaServer
import aiohttp
import asyncio
from helpers.admin import admin_meta


load_dotenv()

RCON_HOST = os.getenv("RCON_HOST")
RCON_PORT = int(os.getenv("RCON_PORT"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD")

LINKS_FILE = Path(MINECRAFT_LINKS_PATH)

ROLE_PRIORITY = [
    (OFFICER_ROLE, "officer"),
    (SENIOR_VOLUNTEER_ROLE, "seniorvolunteer"),
    (VOLUNTEER_ROLE, "volunteer"),
]

BEDROCK_GEYSER_RE = re.compile(
    r"""
    ^
    (?!\s)                           # no leading space
    (?!.*\s{2,})                     # no consecutive spaces
    [A-Za-z0-9_\-\ ]{3,20}           # ✅ escaped space
    (?<!\s)                          # no trailing space
    $
    """,
    re.VERBOSE
)
JAVA_REGEX = re.compile(r"^[A-Za-z0-9_]{3,16}$")

OFFLINE_STRIKES_REQUIRED = 3

class MinecraftServerOffline(Exception):
    pass

def is_server_online() -> tuple[bool, int | None]:
    try:
        server = JavaServer.lookup("java.ereuse.minecraft.party:25565")
        status = server.status()
        return True, status.players.online
    except Exception:
        return False, None

class Minecraft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_state = None
        self.last_players = None
        self.offline_strikes = 0
        self.status_loop.start()

    async def log_action(self, guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

    def save_links(self, data):
        if "blacklist" not in data:
            data["blacklist"] = {"discord": [], "java": [], "bedrock_gamertag": [], "floodgate_uuid": []}

        
        with open(LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def load_links(self):
        if not LINKS_FILE.exists():
            return {"blacklist": {"discord": [], "java": [], "bedrock_gamertag": [], "floodgate_uuid": []}}
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "blacklist" not in data or not isinstance(data["blacklist"], dict):
            data["blacklist"] = {"discord": [], "java": [], "bedrock_gamertag": [], "floodgate_uuid": []}

        bl = data["blacklist"]
        bl.setdefault("discord", [])
        bl.setdefault("java", [])
        bl.setdefault("bedrock_gamertag", [])
        bl.setdefault("floodgate_uuid", [])

        for k, v in list(data.items()):
            if k == "blacklist":
                continue
            if not isinstance(v, dict):
                continue

            v.setdefault("java", None)
            v.setdefault("bedrock", None)
            v.setdefault("last_action", 0)
            v.setdefault("lp_group", None)
            v.setdefault("suffix", None)
            v.setdefault("last_resync", 0)

            if isinstance(v.get("bedrock"), str):
                old_gt = v["bedrock"]
                v["bedrock"] = {"gamertag": old_gt, "floodgate_uuid": None}

        return data

    def get_lp_group(self, member: discord.Member) -> str | None:
        role_names = {r.name for r in member.roles}
        for role_name, lp_group in ROLE_PRIORITY:
            if role_name in role_names:
                return lp_group
        return None

    def run_rcon(self, cmd: str):
        try:
            with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT, timeout=3) as mcr:
                response = mcr.command(cmd)

                print(f"[RCON] {cmd}")
                print(f"[RCON-RESPONSE] {response}")

                return response

        except socket.timeout:
            raise MinecraftServerOffline("Minecraft Server Offline (timeout)")
        except ConnectionRefusedError:
            raise MinecraftServerOffline("Minecraft Server Offline (connection refused)")
        except socket.gaierror:
            raise MinecraftServerOffline("Minecraft Server Offline (invalid host)")
        except Exception as e:
            raise MinecraftServerOffline("Minecraft Server Offline or RCON unavaliable")

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

    def get_linked_usernames(self, user_id: int) -> list[str]:
        data = self.load_links()
        entry = self.get_user_entry(data, user_id)

        out = []

        if entry.get("java", None):
            out.append(entry.get("java"))

        bed = entry.get("bedrock")
        if isinstance(bed, dict) and bed.get("gamertag"):
            out.append(bed["gamertag"])
        elif isinstance(bed, str) and bed:
            out.append(bed)

        return out

    async def apply_suffix(self, interaction: discord.Interaction, achievement: str):
        await interaction.response.defer(ephemeral=True)

        percent = await achievement_percentage(achievement, interaction.guild)
        _, colour = rarity_style(percent)

        suffix = f" &7{colour}[{achievement}]&7"

        minecraft_names = self.get_linked_usernames(interaction.user.id)
        if not minecraft_names:
            await interaction.followup.send(f"❌ No Minecraft accounts linked.", ephemeral=True)
            return

        for name in minecraft_names:
            self.run_rcon(f'lp user {name} meta setsuffix 1000 "{suffix}"')
            await interaction.followup.send(f"✅ Suffix set to **{achievement}** for ***{name}***")
        
        data = self.load_links()
        user = self.get_user_entry(data, interaction.user.id)
        user["suffix"] = suffix
        data[str(interaction.user.id)] = user
        self.save_links(data)

    async def get_bedrock_profile(self, gamertag: str):
        url = f"https://mcprofile.io/api/v1/bedrock/gamertag/{gamertag}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    def _java_norm(self, name: str) -> str:
        return (name or "").strip().lower()

    def is_discord_blacklisted(self, data: dict, user_id: int) -> bool:
        return str(user_id) in set(data["blacklist"]["discord"])

    def is_java_blacklisted(self, data: dict, java_name: str) -> bool:
        return self._java_norm(java_name) in set(map(self._java_norm, data["blacklist"]["java"]))

    def is_bedrock_name_blacklisted(self, data:dict, gamertag: str) -> bool:
        return gamertag in set(data["blacklist"]["bedrock_gamertag"])

    def is_floodgate_uuid_blacklisted(self, data:dict, uuid: str) -> bool:
        uuid = (uuid or "").strip()
        return uuid in set(x.strip().lower() for x in data["blacklist"]["floodgate_uuid"])

    def get_user_entry(self, data:dict, discord_id: int) -> dict:
        return data.get(str(discord_id), {"java": None, "bedrock": None, "last_action": 0})

    def apply_lp_state(self, mc_id: str, group: str | None, suffix: str | None):
        if group:
            self.run_rcon(f"lp user {mc_id} parent set {group}")
        
        if suffix:
            self.run_rcon(f'lp user {mc_id} meta setsuffix 1000 "{suffix}"')


    @tasks.loop(seconds=30)
    async def status_loop(self):
        online, players = await asyncio.to_thread(is_server_online)

        if online:
            self.offline_strikes = 0
            effective_online = True
        else:
            self.offline_strikes += 1
            effective_online = self.offline_strikes < OFFLINE_STRIKES_REQUIRED

        if effective_online == self.last_state and players == self.last_players:
            return

        self.last_state = effective_online
        self.last_players = players

        channel = self.bot.get_channel(MINECRAFT_SERVER_CHANNEL_ID)
        message = await channel.fetch_message(MINECRAFT_SERVER_STATUS_MESSAGE_ID)

        if online:
            content = (
                "🟢 **Minecraft Server: ONLINE**\n"
                f"👥 Players Online: **{players}**\n"
                "🌏 Java & Bedrock Supported"
            )
        else:
            content = (
                "🔴 **Minecraft Server: OFFLINE**\n"
                "⌛ Please check back later."
            )

        await message.edit(content=content)

    @status_loop.before_loop
    async def before_status_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="link", description="Link your minecraft account")
    @app_commands.describe(platform="Java or Bedrock", minecraft_name="Your minecraft username for java or bedrock")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock")
    ])
    async def link(self, interaction: discord.Interaction, platform: app_commands.Choice[str], minecraft_name: str):
        await interaction.response.defer(ephemeral=True)

        if not self.safe_username(minecraft_name, platform.value):
            await interaction.followup.send("❌ username is unsafe", ephemeral=True)
            return

        now = time.time()
        data = self.load_links()

        if self.is_discord_blacklisted(data, interaction.user.id):
            await interaction.followup.send("⛔ You are blacklisted and cannot link Minecraft accounts.", ephemeral=True)
            return

        user_entry = self.get_user_entry(data, interaction.user.id)

        if now - user_entry["last_action"] < RATE_LIMIT_SECONDS:
            await interaction.followup.send("⌛ Please wait before using this command again", ephemeral=True)
            return

        if platform.value == "java" and user_entry.get("java") is not None:
            await interaction.followup.send(f"❌ You already have a Java account linked: {user_entry['java']}", ephemeral=True)
            return

        if platform.value == "bedrock":
            bed = user_entry.get("bedrock")
            if bed is not None:
                existing = bed.get("gamertag") if isinstance(bed, dict) else bed
                await interaction.followup.send(f"❌ You already have a Bedrock account linked: {existing}", ephemeral=True)
                return

        lp_group = self.get_lp_group(interaction.user)
        if not lp_group:
            await interaction.followup.send(
                f"❌ You do not have a valid discord role to link a minecraft account. Needs at least: ***{VOLUNTEER_ROLE}***",
                ephemeral=True
            )
            return

        if platform.value == "java":
            if self.is_java_blacklisted(data, minecraft_name):
                await interaction.followup.send("⛔ That Java account is blacklisted and cannot be linked.", ephemeral=True)
                return

            self.run_rcon(f"whitelist add {minecraft_name}")
            self.run_rcon(f"lp user {minecraft_name} parent set {lp_group}")
            user_entry["lp_group"] = lp_group
            user_entry["java"] = minecraft_name
        else:
            if self.is_bedrock_name_blacklisted(data, minecraft_name):
                await interaction.followup.send("⛔ That Bedrock gamertag is blacklisted and cannot be linked.", ephemeral=True)
                return

            profile = await self.get_bedrock_profile(minecraft_name)
            if not profile:
                await interaction.followup.send(f"❌ Cannot find Bedrock account with name {minecraft_name}", ephemeral=True)
                return

            floodgate_uuid = profile.get("floodgateuid")
            if not floodgate_uuid:
                await interaction.followup.send("❌ Floodgate UUID unavailable", ephemeral=True)
                return

            if self.is_floodgate_uuid_blacklisted(data, floodgate_uuid):
                await interaction.followup.send("⛔ That Bedrock account is blacklisted and cannot be linked.", ephemeral=True)
                return

            self.run_rcon(f"fwhitelist add {floodgate_uuid}")
            self.run_rcon(f"lp user {floodgate_uuid} parent set {lp_group}")
            user_entry["lp_group"] = lp_group

            user_entry["bedrock"] = {"gamertag": minecraft_name, "floodgate_uuid": floodgate_uuid}

        user_entry["last_action"] = now
        data[str(interaction.user.id)] = user_entry
        self.save_links(data)

        challenges_cog = interaction.client.get_cog("Challenges")
        if challenges_cog:
            ctx = await challenges_cog.build_ctx(interaction.user)
            await challenges_cog.achievement_engine.evaluate(ctx)

        await self.log_action(interaction.guild, f"🌲 {interaction.user.mention} linked {platform.value} account `{minecraft_name}`")
        await interaction.followup.send(f"✅ **{platform.name} account linked:** `{minecraft_name}`", ephemeral=True)



    @app_commands.command(name="unlink", description="unlink your minecraft account")
    @app_commands.describe(platform="Java or Bedrock")
    @app_commands.choices(platform=[
        app_commands.Choice(name="Java", value="java"),
        app_commands.Choice(name="Bedrock", value="bedrock")
    ])
    async def unlink(self, interaction: discord.Interaction, platform: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)

        now = time.time()
        data = self.load_links()
        user_entry = self.get_user_entry(data, interaction.user.id)

        if platform.value == "java":
            mc_name = user_entry.get("java")
            if not mc_name:
                await interaction.followup.send("❌ No Java account linked.", ephemeral=True)
                return

            self.run_rcon(f"whitelist remove {mc_name}")
            self.run_rcon(f"lp user {mc_name} clear")
            user_entry["java"] = None

        else:
            bed = user_entry.get("bedrock")
            if not bed:
                await interaction.followup.send("❌ No Bedrock account linked.", ephemeral=True)
                return

            if isinstance(bed, str):
                bed = {"gamertag": bed, "floodgate_uuid": None}

            gamertag = bed.get("gamertag")
            floodgate_uuid = bed.get("floodgate_uuid")

            if not floodgate_uuid and gamertag:
                profile = await self.get_bedrock_profile(gamertag)
                if profile:
                    floodgate_uuid = profile.get("floodgateuid")
                    bed["floodgate_uuid"] = floodgate_uuid

            if not floodgate_uuid:
                await interaction.followup.send("❌ Floodgate UUID unavailable; cannot unwhitelist.", ephemeral=True)
                return

            self.run_rcon(f"fwhitelist remove {floodgate_uuid}")
            self.run_rcon(f"lp user {floodgate_uuid} clear")
            user_entry["bedrock"] = None

        user_entry["last_action"] = now
        data[str(interaction.user.id)] = user_entry
        self.save_links(data)

        await self.log_action(interaction.guild, f"🌲 {interaction.user.mention} unlinked {platform.value} account")
        await interaction.followup.send(f"🗑️ **{platform.name} account unlinked.**", ephemeral=True)


    @app_commands.command(name="status", description="View your linked minecraft accounts")
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
            value= user_entry.get("java") or "❌ Not Linked",
            inline= False
        )

        bedrock_entry = user_entry.get("bedrock")
        bedrock = "❌ Not Linked"
        if isinstance(bedrock_entry, str):
            bedrock = bedrock_entry
        elif isinstance(bedrock_entry, dict):
            bedrock = bedrock_entry.get("gamertag", "❌ Not Linked")

        embed.add_field(
            name="Bedrock",
            value= bedrock,
            inline= False
        )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="suffix", description="Choose an achievement suffix to display in Minecraft")
    async def suffix(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("❌ Run this in a server.", ephemeral=True)
            return

        achievements = await get_user_achievements(interaction.user.id, guild)

        if not achievements:
            await interaction.followup.send(
                "☹️ You don't have any achievements yet, so there's nothing to set as a suffix.\n"
                "Try earning one first, then run `/suffix` again.",
                ephemeral=True
            )
            return

        view = AchievementView(achievements=achievements, viewer_id=interaction.user.id)

        await interaction.followup.send(
            "Pick an achievement to use as your Minecraft suffix:",
            view=view,
            ephemeral=True
        )



    @app_commands.command(name="finddiscord", description="Find the Discord user who owns a Minecraft username")
    @app_commands.describe(minecraft_name="Java username or Bedrock gamertag")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [],
            notes= "Useful for blacklisting a user who broke the rules, for bedrock don't include the leading .")
    async def find_discord(self, interaction: discord.Interaction, minecraft_name: str):
        await interaction.response.defer(ephemeral=True)

        data = self.load_links()
        target_java = self._java_norm(minecraft_name)
        target_bed = minecraft_name.strip()

        found = None
        found_platform = None

        for uid, entry in data.items():
            if uid == "blacklist":
                continue
            if not isinstance(entry, dict):
                continue

            j = entry.get("java")
            if j and self._java_norm(j) == target_java:
                found = int(uid)
                found_platform = "java"
                break

            bed = entry.get("bedrock")
            if isinstance(bed, dict):
                gt = (bed.get("gamertag") or "").strip()
                if gt and gt == target_bed:
                    found = int(uid)
                    found_platform = "bedrock"
                    break
            elif isinstance(bed, str):
                if bed.strip() == target_bed:
                    found = int(uid)
                    found_platform = "bedrock"
                    break

        if not found:
            await interaction.followup.send("❌ No Discord user found for that Minecraft name.", ephemeral=True)
            return

        member = interaction.guild.get_member(found)
        if member:
            await interaction.followup.send(f"✅ `{minecraft_name}` is linked to {member.mention} (**{found_platform}**).", ephemeral=True)
        else:
            await interaction.followup.send(f"✅ `{minecraft_name}` is linked to Discord user ID `{found}` (**{found_platform}**).", ephemeral=True)


    @app_commands.command(name="findminecraft", description="Find the Minecraft accounts linked to a Discord user")
    @app_commands.describe(member="Discord user")
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= [],
            notes= "Useful for finding out what someones minecraft is")
    async def find_minecraft(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)

        data = self.load_links()
        entry = self.get_user_entry(data, member.id)

        java = entry.get("java")
        bed = entry.get("bedrock")

        bed_gt = None
        bed_uuid = None
        if isinstance(bed, dict):
            bed_gt = bed.get("gamertag")
            bed_uuid = bed.get("floodgate_uuid")
        elif isinstance(bed, str):
            bed_gt = bed

        embed = discord.Embed(title="🔎 Linked Minecraft Accounts", color=discord.Color.gold())
        embed.add_field(name="Discord", value=member.mention, inline=False)
        embed.add_field(name="Java", value=java or "❌ Not linked", inline=False)

        if bed_gt:
            if bed_uuid:
                embed.add_field(name="Bedrock", value=f"{bed_gt}\n`{bed_uuid}`", inline=False)
            else:
                embed.add_field(name="Bedrock", value=f"{bed_gt}\n`(no floodgate uuid stored yet)`", inline=False)
        else:
            embed.add_field(name="Bedrock", value="❌ Not linked", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)


    @app_commands.command(name="mcblacklist", description="Blacklist a Discord user (blocks linking + blacklists their accounts)")
    @app_commands.describe(action="add/remove/check", member="Discord user", reason="Optional reason")
    @app_commands.choices(action=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="check", value="check"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= ["Minecraft Accounts"],
            notes= "If someone has been breaking rules or against eReuse policy remove them from the minecraft")
    async def mc_blacklist(self, interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member, reason: str = ""):
        await interaction.response.defer(ephemeral=True)

        data = self.load_links()
        bl = data["blacklist"]
        uid = str(member.id)

        if action.value == "check":
            is_bl = uid in bl["discord"]
            await interaction.followup.send(
                f"{'⛔' if is_bl else '✅'} {member.mention} blacklist status: **{is_bl}**",
                ephemeral=True
            )
            return

        if action.value == "remove":
            if uid in bl["discord"]:
                bl["discord"] = [x for x in bl["discord"] if x != uid]
                self.save_links(data)
                await self.log_action(interaction.guild, f"🟩 {interaction.user.mention} removed blacklist for {member.mention}. {reason}".strip())
                await interaction.followup.send(f"✅ Removed blacklist for {member.mention}.", ephemeral=True)
            else:
                await interaction.followup.send("ℹ️ User is not blacklisted.", ephemeral=True)
            return


        if uid not in bl["discord"]:
            bl["discord"].append(uid)

        entry = self.get_user_entry(data, member.id)

        java = entry.get("java")
        if java:
            jn = self._java_norm(java)
            if jn and jn not in set(map(self._java_norm, bl["java"])):
                bl["java"].append(java)

        bed = entry.get("bedrock")
        bed_gt = None
        bed_uuid = None

        if isinstance(bed, dict):
            bed_gt = bed.get("gamertag")
            bed_uuid = bed.get("floodgate_uuid")
        elif isinstance(bed, str):
            bed_gt = bed

        if bed_gt:
            if bed_gt.strip() not in set(x.strip() for x in bl["bedrock_gamertag"]):
                bl["bedrock_gamertag"].append(bed_gt)

        if bed_gt and not bed_uuid:
            profile = await self.get_bedrock_profile(bed_gt)
            if profile:
                bed_uuid = profile.get("floodgateuid")
                entry["bedrock"] = {"gamertag": bed_gt, "floodgate_uuid": bed_uuid}

        if bed_uuid:
            u = bed_uuid.strip().lower()
            if u and u not in set(x.strip().lower() for x in bl["floodgate_uuid"]):
                bl["floodgate_uuid"].append(bed_uuid)


        try:
            if java:
                self.run_rcon(f"whitelist remove {java}")
                self.run_rcon(f"lp user {java} clear")
                entry["java"] = None

            if bed_uuid:
                self.run_rcon(f"fwhitelist remove {bed_uuid}")
                self.run_rcon(f"lp user {bed_uuid} clear")
                entry["bedrock"] = None
        except Exception:
            pass

        data[str(member.id)] = entry
        self.save_links(data)

        await self.log_action(
            interaction.guild,
            f"🟥 {interaction.user.mention} blacklisted {member.mention}. Reason: {reason}".strip()
        )

        await interaction.followup.send(
            f"⛔ Blacklisted {member.mention}. They can no longer link accounts, and their linked accounts were added to the blacklist.",
            ephemeral=True
        )


    @app_commands.command(name="resync", description="Resync your minecraft permissions and suffix")
    async def resync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        now = time.time()
        data = self.load_links()
        user_entry = self.get_user_entry(data, interaction.user.id)

        if now - user_entry["last_resync"] < RATE_LIMIT_SECONDS:
            await interaction.followup.send("⌛ Please wait before using this command again", ephemeral=True)
            return

        lp_group = self.get_lp_group(interaction.user)
        if not lp_group:
            await interaction.followup.send(
                f"❌ You do not have a valid discord role to link a minecraft account. Needs at least: ***{VOLUNTEER_ROLE}***",
                ephemeral=True
            )
            return

        suffix = user_entry.get("suffix", None)

        applied = []

        java = user_entry.get("java", None)
        if java:
            self.apply_lp_state(java, lp_group, suffix)
            applied.append(f"Java: `{java}`")
        
        bed = user_entry.get("bedrock", None)
        if isinstance(bed, dict):
            uuid = bed.get("floodgate_uuid", None)
            if uuid:
                self.apply_lp_state(uuid, lp_group, suffix)
                applied.append(f"Bedrock: `{bed.get('gamertag')}`")
        
        if not applied:
            await interaction.followup.send("❌ No linked minecraft accounts to resync.", ephemeral=True)
        
        user_entry["lp_group"] = lp_group
        user_entry["last_resync"] = now
        data[str(interaction.user.id)] = user_entry
        self.save_links(data)

        await self.log_action(interaction.guild, f"🔁 {interaction.user.mention} resynced Minecraft permissions")

        msg = "✅ **Minecraft Permissions Resynced:**\n" + "\n".join(applied)
        if suffix:
            msg += f"\n **Suffix Reapplied**: {suffix}"
        
        await interaction.followup.send(msg, ephemeral=True)



async def setup(bot):
    await bot.add_cog(Minecraft(bot))