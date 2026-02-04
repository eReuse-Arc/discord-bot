from __future__ import annotations
from helpers.achievements import ACHIEVEMENTS
import discord
import asyncio
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

    async def _revoke_role_if_needed(self, member: discord.Member, role_name: str | None):
        if not role_name:
            return

        role = discord.utils.get(member.guild.roles, name=role_name)
        if not role or role not in member.roles:
            return

        try:
            await member.remove_roles(role, reason="Achievement Revoked")
        except:
            pass

    def _normalize_user_earned(self, raw) -> dict[str, int]:
        if isinstance(raw, dict):
            out: dict[str, int] = {}
            for k, v in raw.items():
                try:
                    out[str(k)] = int(v)
                except Exception:
                    out[str(k)] = 0
            return out

        if isinstance(raw, list):
            return {str(k): 0 for k in raw}

        return {}

    def _now_ts(self) -> int:
        import time
        return int(time.time())


    async def evaluate(self, ctx):
        data = self.load()
        user_id = str(ctx[USER_ID])
        member: discord.Member = ctx[MEMBER]

        earned_map = self._normalize_user_earned(data.get(user_id))
        earned_keys = set(earned_map.keys())
        newly_unlocked: list[tuple[str, dict]] = []

        for key, ach in ACHIEVEMENTS.items():
            if key in earned_keys:
                continue

            try:
                ok = ach["check"](ctx)
            except Exception:
                continue

            if ok:
                newly_unlocked.append((key, ach))

        if not newly_unlocked:
            return

        now = self._now_ts()

        for key, _ach in newly_unlocked:
            if earned_map.get(key, 0) == 0:
                earned_map[key] = now

        data[user_id] = dict(sorted(earned_map.items(), key=lambda kv: kv[0]))
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



    async def revoke_for_member(self, member: discord.Member, achievement_key: str) -> bool:
        if achievement_key not in ACHIEVEMENTS:
            return False

        ach = ACHIEVEMENTS.get(achievement_key, {})
        role_name = ach.get("role")

        data = self.load()
        user_id = str(member.id)

        earned_map = self._normalize_user_earned(data.get(user_id))
        changed = False

        if achievement_key in earned_map:
            earned_map.pop(achievement_key, None)
            changed = True

            if earned_map:
                data[user_id] = dict(sorted(earned_map.items(), key=lambda kv: kv[0]))
            else:
                data.pop(user_id, None)

            self.save(data)

        await self._revoke_role_if_needed(member, role_name)

        return changed or (role_name is not None)

    
    async def revoke_for_members(self, members: list[discord.Member], achievement_key: str, *, sleep_every: int = 10, sleep_seconds = 0.6) -> tuple[int, int]:
        revoked = 0
        attempted = 0

        for idx, m in enumerate(members, start=1):
            attempted += 1
            try:
                did = await self.revoke_for_member(m, achievement_key)
                if did:
                    revoked += 1
            except:
                pass

            if idx % sleep_every == 0:
                await asyncio.sleep(sleep_seconds)
        
        return revoked, attempted