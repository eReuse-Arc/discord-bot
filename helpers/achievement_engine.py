from __future__ import annotations
from helpers.achievements import ACHIEVEMENTS
import discord
from constants import ACHIEVEMENT_UNLOCKS_CHANNEL_ID, USER_ID, MEMBER


class AchievementEngine:
    def __init__(self, load_fn, save_fn):
        self.load = load_fn
        self.save = save_fn
        self.channel_id = ACHIEVEMENT_UNLOCKS_CHANNEL_ID

    async def _grant_role_if_needed(self, member: discord.Member, role_name: str | None):
        if not role_name:
            return

        role = discord.utils.get(member.guild.roles, name=role_name)

        if not role or role in member.roles:
            return
        try:
            await member.add_roles(role, reason="Achievement Unlocked")
        except:
            pass

    async def evaluate(self, ctx):
        data = self.load()
        user_id = str(ctx[USER_ID])
        member: discord.Member = ctx[MEMBER]

        earned = set(data.get(user_id, []))
        newly_unlocked = []

        for key, ach in ACHIEVEMENTS.items():
            if key in earned:
                continue

            try:
                ok = ach["check"](ctx)
            except:
                continue

            if ok:
                earned.add(key)
                newly_unlocked.append((key, ach))

        if not newly_unlocked:
            return

        data[user_id] = sorted(earned)
        self.save(data)

        for key, ach in newly_unlocked:
            await self._grant_role_if_needed(member, ach.get("role"))

            is_hidden = ach.get("hidden", False)

            channel = member.guild.get_channel(self.channel_id)
            if channel:
                await channel.send(
                    (f"## ❓ Hidden Achievement Unlocked!\n" if is_hidden else "") +
                    f"🏅 **{member.mention} unlocked:** {ach['name']}\n" +
                    f"{ach['description']}"
                )

