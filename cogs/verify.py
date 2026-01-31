import discord
from discord.ext import commands
from discord import app_commands
from pathlib import Path
from typing import Dict, Any, Optional
import os
import json
import time
import secrets
import hashlib
import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from constants import VERIFY_PATH, VERIFY_ROLE, MODERATOR_ONLY_CHANNEL_ID
from helpers.admin import admin_meta


ALLOWED_SUFFIXES = ("@student.unsw.edu.au", "@ad.unsw.edu.au", "@unsw.edu.au")

OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "600"))
OTP_MIN_RESEND_SECONDS = int(os.getenv("OTP_MIN_RESEND_SECONDS", "60"))
OTP_MAX_TRIES = int(os.getenv("OTP_MAX_TRIES", "5"))

SMTP_HOST = os.getenv("VERIFY_SMTP_HOST", "")
SMTP_PORT = int(os.getenv("VERIFY_SMTP_PORT", "587"))
SMTP_USER = os.getenv("VERIFY_SMTP_USER", "")
SMTP_PASS = os.getenv("VERIFY_SMTP_PASS", "")
VERIFY_FROM = os.getenv("VERIFY_FROM", "")


def _now() -> int:
    return int(time.time())


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _looks_like_unsw_email(email: str) -> bool:
    e = email.strip().lower()
    return any(e.endswith(suf) for suf in ALLOWED_SUFFIXES)


def _gen_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_email_smtp(host: str, port: int, user: str, pw: str,
                     from_addr: str, to_addr: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ctx)
        smtp.login(user, pw)
        smtp.send_message(msg)


async def _send_otp_email(to_email: str, code: str) -> None:
    body = (
        "Your eReuse Discord verification code is:\n\n"
        f"{code}\n\n"
        f"This code expires in {OTP_TTL_SECONDS // 60} minutes.\n"
        "If you did not request this, ignore this email."
    )
    await asyncio.to_thread(
        _send_email_smtp,
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
        VERIFY_FROM, to_email,
        "eReuse Discord Verification Code",
        body
    )


class VerifyStore:
    def __init__(self, path: str):
        self.path = Path(path)
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
        return str(user_id) in data.get("verified", {})

    def mark_verified(self, user_id: int) -> None:
        data = self.load()
        uid = str(user_id)
        data["verified"][uid] = {"verified_at": _now()}
        data["pending"].pop(uid, None)
        self.save(data)

    def revoke_verified(self, user_id: int) -> None:
        data = self.load()
        uid = str(user_id)
        data["verified"].pop(uid, None)
        data["pending"].pop(uid, None)
        self.save(data)

    def set_pending_otp(self, user_id: int, otp_hash: str, otp_salt: str) -> None:
        data = self.load()
        uid = str(user_id)
        now = _now()
        data.setdefault("pending", {})
        data["pending"][uid] = {
            "otp_hash": otp_hash,
            "otp_salt": otp_salt,
            "otp_expires_at": now + OTP_TTL_SECONDS,
            "otp_last_sent_at": now,
            "otp_tries": 0
        }
        self.save(data)

    def get_pending(self, user_id: int) -> Optional[Dict[str, Any]]:
        data = self.load()
        return data.get("pending", {}).get(str(user_id))

    def bump_tries(self, user_id: int) -> int:
        data = self.load()
        uid = str(user_id)
        entry = data.get("pending", {}).get(uid)
        if not entry:
            return 0
        entry["otp_tries"] = int(entry.get("otp_tries", 0)) + 1
        data["pending"][uid] = entry
        self.save(data)
        return int(entry["otp_tries"])

    def clear_pending(self, user_id: int) -> None:
        data = self.load()
        uid = str(user_id)
        if uid in data.get("pending", {}):
            data["pending"].pop(uid, None)
            self.save(data)


class VerifyEmailModal(discord.ui.Modal, title="UNSW Verification"):
    email = discord.ui.TextInput(
        label="Your UNSW email",
        placeholder="z1234567@ad.unsw.edu.au",
        required=True,
        max_length=100
    )

    preferred_name = discord.ui.TextInput(
        label="Preferred name",
        placeholder="name",
        required=True,
        max_length=32
    )

    def __init__(self, cog: "Verify", member: discord.Member):
        super().__init__()
        self.cog = cog
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.start_otp_flow(
            interaction=interaction,
            member=self.member,
            email=str(self.email.value).strip(),
            preferred_name=str(self.preferred_name.value).strip()
        )


class ForceVerifyConfirm(discord.ui.View):
    def __init__(self, cog: "Verify", actor_id: int, target: discord.Member):
        super().__init__(timeout=30)
        self.cog = cog
        self.actor_id = actor_id
        self.target = target

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "❌ Only the admin who ran the command can use these buttons.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="✅ Yes, force verify", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message("Run this in a server.", ephemeral=True)
            return

        role = self.cog.get_verify_role(interaction.guild)
        if not role:
            await interaction.response.send_message(
                f"I couldn't find the role `{VERIFY_ROLE}`. Ask an admin for help.",
                ephemeral=True
            )
            return

        ok = await self.cog.grant_role(self.target, role)
        if not ok:
            await interaction.response.send_message(
                "I couldn't grant the role (permissions/hierarchy).",
                ephemeral=True
            )
            return

        self.cog.store.mark_verified(self.target.id)

        await self.cog.log_action(
            interaction.guild,
            f"🛠️ {interaction.user.mention} FORCE-VERIFIED {self.target.mention}"
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"✅ Forced verification complete for {self.target.mention}.",
            view=self
        )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="Cancelled.",
            view=self
        )


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = VerifyStore(VERIFY_PATH)

    def get_verify_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        return discord.utils.get(guild.roles, name=VERIFY_ROLE)

    async def log_action(self, guild: discord.Guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

    async def grant_role(self, member: discord.Member, role: discord.Role) -> bool:
        if role in member.roles:
            return True
        try:
            await member.add_roles(role, reason="UNSW verification completed (OTP)")
            return True
        except discord.Forbidden:
            return False

    async def maybe_set_nickname(self, member: discord.Member, preferred_name: str) -> None:
        if not preferred_name:
            return
        try:
            await member.edit(nick=preferred_name[:32], reason="Set nickname from user preferred name (OTP verify)")
        except discord.Forbidden:
            pass

    async def start_otp_flow(self, interaction: discord.Interaction, member: discord.Member, email: str, preferred_name: str):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        # SMTP configured?
        if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, VERIFY_FROM]):
            await interaction.response.send_message(
                "Verification email is not configured. Tell an admin.",
                ephemeral=True
            )
            return

        if not _looks_like_unsw_email(email):
            await interaction.response.send_message(
                "That doesn't look like a UNSW email. Please use an address ending in:\n"
                "`@student.unsw.edu.au`, `@ad.unsw.edu.au`, or `@unsw.edu.au`.",
                ephemeral=True
            )
            return

        pending = self.store.get_pending(member.id) or {}
        last_sent = int(pending.get("otp_last_sent_at", 0))
        now = _now()
        if last_sent and now - last_sent < OTP_MIN_RESEND_SECONDS:
            remaining = OTP_MIN_RESEND_SECONDS - (now - last_sent)
            await interaction.response.send_message(
                f"I already sent you a code recently — please check your inbox/spam.\n"
                f"You can request another in **{remaining}s**.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Sending you a verification code now… (check inbox + spam)",
            ephemeral=True
        )

        code = _gen_code()
        salt = secrets.token_urlsafe(16)
        otp_hash = _sha256(salt + code)
        self.store.set_pending_otp(member.id, otp_hash=otp_hash, otp_salt=salt)

        try:
            await _send_otp_email(email, code)
        except Exception:
            self.store.clear_pending(member.id)
            await interaction.edit_original_response(
                content="I couldn't send the email code right now. Please try again later."
            )
            return

        await self.maybe_set_nickname(member, preferred_name)

        await interaction.edit_original_response(
            content="✅ Code sent! Now run `/verifyfinish code:123456` (replace with your code)."
        )


    @app_commands.command(name="verify", description="Verify you're a UNSW student to get access (email code).")
    async def verify(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if not role:
            await interaction.response.send_message(
                f"I couldn't find the role `{VERIFY_ROLE}`. Ask an admin for help.",
                ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        if role in member.roles or self.store.is_verified(member.id):
            ok = await self.grant_role(member, role)
            if not ok:
                await interaction.response.send_message(
                    "✅ You're verified but I couldn't grant the role. Ask an admin (permissions/hierarchy).",
                    ephemeral=True
                )
                return

            if not self.store.is_verified(member.id):
                self.store.mark_verified(member.id)

            await interaction.response.send_message("✅ You're already verified.", ephemeral=True)
            return

        await interaction.response.send_modal(VerifyEmailModal(self, member))

    @app_commands.command(name="verifyfinish", description="Finish verification using the code emailed to you.")
    @app_commands.describe(code="6-digit code from your UNSW email")
    async def verify_finish(self, interaction: discord.Interaction, code: str):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if not role:
            await interaction.response.send_message(
                f"I couldn't find the role `{VERIFY_ROLE}`. Ask an admin for help.",
                ephemeral=True
            )
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        if role in member.roles or self.store.is_verified(member.id):
            ok = await self.grant_role(member, role)
            if ok and not self.store.is_verified(member.id):
                self.store.mark_verified(member.id)
            await interaction.response.send_message("✅ You're verified!", ephemeral=True)
            return

        entry = self.store.get_pending(member.id)
        if not entry:
            await interaction.response.send_message("No code found. Run `/verify` again.", ephemeral=True)
            return

        if _now() > int(entry.get("otp_expires_at", 0)):
            self.store.clear_pending(member.id)
            await interaction.response.send_message("That code expired. Run `/verify` again.", ephemeral=True)
            return

        tries = int(entry.get("otp_tries", 0))
        if tries >= OTP_MAX_TRIES:
            self.store.clear_pending(member.id)
            await interaction.response.send_message("Too many attempts. Run `/verify` again.", ephemeral=True)
            return

        salt = str(entry.get("otp_salt", ""))
        expected = str(entry.get("otp_hash", ""))

        if _sha256(salt + code.strip()) != expected:
            self.store.bump_tries(member.id)
            await interaction.response.send_message("Incorrect code. Try again.", ephemeral=True)
            return

        ok = await self.grant_role(member, role)
        if not ok:
            await interaction.response.send_message(
                "✅ Code correct, but I couldn't grant the role. Tell an admin (permissions/hierarchy).",
                ephemeral=True
            )
            return

        self.store.mark_verified(member.id)
        await self.log_action(interaction.guild, f"✅ {member.mention} verified via email OTP.")
        await interaction.response.send_message("✅ You are verified!", ephemeral=True)

    @app_commands.command(name="verifyrevoke", description="Revoke a member's verified status.")
    @app_commands.describe(user="Who to revoke verification from")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["User Verification"],
        notes="Remove a verified user's verification status"
    )
    async def verify_revoke(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if role and role in user.roles:
            try:
                await user.remove_roles(role, reason="Verification revoked")
            except discord.Forbidden:
                await interaction.response.send_message("I couldn't remove the role (permissions/hierarchy).", ephemeral=True)
                return

        self.store.revoke_verified(user.id)
        await self.log_action(interaction.guild, f"🛠️ {interaction.user.mention} revoked verification for {user.mention}")
        await interaction.response.send_message(f"Revoked verification for {user.mention}", ephemeral=True)


    @app_commands.command(name="verifyforce", description="Force-verify a member")
    @app_commands.describe(user="Member to force-verify")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(
        permissions="Administrator",
        affects=["User Verification"],
        notes="Force-grants Verified role and marks user as verified in storage."
    )
    async def verify_force(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        role = self.get_verify_role(interaction.guild)
        if not role:
            await interaction.response.send_message(
                f"I couldn't find the role `{VERIFY_ROLE}`. Ask an admin for help.",
                ephemeral=True
            )
            return

        if role in user.roles or self.store.is_verified(user.id):
            ok = await self.grant_role(user, role)
            if ok and not self.store.is_verified(user.id):
                self.store.mark_verified(user.id)
            await interaction.response.send_message(
                f"✅ {user.mention} is already verified (role/store ensured).",
                ephemeral=True
            )
            return

        view = ForceVerifyConfirm(cog=self, actor_id=interaction.user.id, target=user)
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to **force verify** {user.mention}?\n"
            f"This will grant `{VERIFY_ROLE}` and permanently mark them as verified.",
            view=view,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))