import discord
from discord.ext import commands
from discord import app_commands
from pathlib import Path
import json
import time
import secrets
from typing import Dict, Any, Optional
from constants import VERIFY_PATH, VERIFY_ROLE, VERIFY_SITE_BASE, STATE_TTL_SECONDS, MODERATOR_ONLY_CHANNEL_ID
from helpers.admin import admin_meta

def _now() -> int:
    return int(time.time())

class VerifyStore:
    def __init__(self, path: str = VERIFY_PATH):
        self.path = Path(str)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"verified": {}, "pending": {}}
        
        try:
            raw = self.path.read_text(encoding="utf-8").strip()
            if not raw:
                return {"verified": {}, "pending": {}}

            data = json.loads(raw)
            if not isinstance(data, dict):
                return {"verified": {}, "pending": {}}
            
            data.setdefault("verified", {})
            data.setdefault("pending", {})
            return data
        except:
            return {"verified": {}, "pending": {}}
    
    def save(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    
    def is_verified(self, user_id: int) -> bool:
        data = self.load()
        return str(user_id) in data.get("verified")

    def mark_verified(self, user_id: int, identifier: Optional[str] = None) -> None:
        data = self.load()
        uid = str(user_id)

        data["verified"][uid] = {
            "verified_at": _now(),
            "identifier": identifier
        }

        data["pending"].pop(uid, None)
        self.save(data)
    
    def revoke_verified(self, user_id: int) -> None:
        data = self.load()
        uid = str(user_id)
        data["verified"].pop(uid, None)
        data["pending"].pop(uid, None)
        self.save(data)
    
    def create_state(self, user_id: int) -> str:
        data = self.load()
        now = _now()

        for uid, entry in list(data["pending"].items()):
            if int(entry.get("expires_at", 0)) <= now:
                data["pending"].pop(uid, None)
        
        state = secrets.token_urlsafe(32)
        uid = str(user_id)
        data["pending"][uid] = {
            "state": state,
            "created_at": now,
            "expires_at": now + STATE_TTL_SECONDS
        }

        self.save(data)
        return state

    def get_state(self, user_id: int) -> Optional[str]:
        data = self.load()
        uid = str(user_id)
        entry = data["pending"].get(uid)

        if not entry:
            return None
        if int(entry.get("expires_at", 0)) <= _now():
            data["pending"].pop(uid, None)
            self.save(data)
            return None

        return entry.get("state")

    def clear_state(self, user_id: int) -> None:
        data = self.load()
        uid = str(user_id)
        if uid in data["pending"]:
            data["pending"].pop(uid, None)
            self.save(data)



class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = VerifyStore(VERIFY_PATH)
    
    def get_verify_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        return discord.utils.get(guild.roles, name=VERIFY_ROLE)

    async def log_action(self, guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

    async def grant_role(self, member: discord.Member, role: discord.Role) -> bool:
        if role in member.roles:
            return True
        
        try:
            await member.add_roles(role, reason="UNSW, verification completed")
        except discord.Forbidden:
            return False
    
    @app_commands.command(name="verify", description="Verify you're a UNSW student to get access")
    async def verify(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if not role:
            await interaction.response.send_message(f"I couldn't find the role `{VERIFY_ROLE}`. Ask an admin for help", ephemeral=True)
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(f"Run this command inside the server", ephemeral=True)
            return

        if role in member.roles or self.store.is_verified(member.id):
            ok = await self.grant_role(member, role)
            if not ok:
                await interaction.response.send_message(f"✅ You're verified but I couldnt grant the role. Ask an admin", ephemeral=True)
                return

            if not self.store.is_verified(member.id):
                self.store.mark_verified(member.id)
            
            await interaction.response.send_message(f"✅ You're already verified", ephemeral=True)
            return
        
        state = self.store.create_state(member.id)
        url = f"{VERIFY_SITE_BASE}/verify?state={state}"

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Verify with UNSW (Microsoft)",
                style=discord.ButtonStyle.link,
                url=url
            )
        )

        await interaction.response.send_message(
            "Click the button to verify using your UNSW Microsoft login.\n"
            "After you finish in the browser, run `/verifyfinish`.\n\n"
            "Note: The login link expires for security, but once verified your access stays permanently",
            view=view,
            ephemeral=True
        )
    
    @app_commands.command(name="verifyfinish", description="Finish verification after signing in")
    async def verify_finish(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if not role:
            await interaction.response.send_message(f"I couldn't find the role `{VERIFY_ROLE}`. Ask an admin for help", ephemeral=True)
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(f"Run this command inside the server", ephemeral=True)
            return
        
        if role in member.roles or self.store.is_verified(member.id):
            ok = await self.grant_role(member, role)
            if ok and not self.store.is_verified(member.id):
                self.store.mark_verified(member.id)
            await interaction.response.send_message(f"✅ You're verified!", ephemeral=True)
            return

        state = self.store.get_state(member.id)
        if not state:
            await interaction.response.send_message(
                "No active verification session found. Run `/verify` to start again.",
                ephemeral=True
            )
            return

        ## This is where we do the verify

        await interaction.response.send_message("I found your verification session.", ephemeral=True)


    @app_commands.command(name="verifyrevoke", description="Revoke a members Verified Status")
    @app_commands.describe(user="Who to revoke the verify from")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= ["User Verification"],
            notes= "Remove a verified users verification status")
    async def verify_revoke(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if role and role in user.roles:
            try:
                await user.remove_roles(role, reason="Verification Revoked")
            except discord.Forbidden:
                await interaction.response.send_message("I Couldn't remove the role", ephemeral=True)
                return
        
        self.store.revoke_verified(user.id)

        await self.log_action(interaction.guild, f"🛠️ {interaction.user.mention} revoked verification for {user.mention}")
        await interaction.response.send_message(f"Revoked verification for {user.mention}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))