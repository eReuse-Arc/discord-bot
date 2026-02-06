import discord
from discord.ext import commands
from discord import app_commands
from constants import *
from datetime import datetime, timezone


class VoiceTracking(commands.Cog):
    def __init__(self, bot, stats_store, achievement_engine):
        self.bot = bot
        self.stats_store = stats_store
        self.achievement_engine = achievement_engine

        # Active
        self.sessions = {}

    def count_humans(self, channel: discord.VoiceChannel) -> int:
        return sum(1 for m in channel.members if not m.bot and not m.voice.deaf)

    def start_session(self, member: discord.Member):
        user_id = str(member.id)
        if user_id in self.sessions:
            return

        self.sessions[user_id] = {
            "channel_id" : member.voice.channel.id,
            "start": datetime.now(timezone.utc),
            "max_people": self.count_humans(member.voice.channel)
        }


    async def end_session(self, member: discord.Member):
        user_id = str(member.id)
        session = self.sessions.pop(user_id, None)
        if not session:
            return

        now = datetime.now(timezone.utc)
        duration = int((now - session["start"]).total_seconds() // 60)


        if duration <= 0:
            return

        self.stats_store.bump(user_id, VOICE_MINUTES, duration)

        stats = self.stats_store.get(user_id)
        longest = stats.get(VOICE_SESSION_MAX, 0)
        if duration > longest:
            self.stats_store.set_value(user_id, VOICE_SESSION_MAX, duration)

        if session["max_people"] >= 3:
            self.stats_store.bump(user_id, VOICE_3P_MINUTES, duration)
        if session["max_people"] >= 5:
            self.stats_store.bump(user_id, VOICE_5P_MINUTES, duration)

        cog = self.bot.get_cog("Challenges")
        if cog:
            ctx = await cog.build_ctx(member)
            await self.achievement_engine.evaluate(ctx)



    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        # left voice
        if before.channel and not after.channel:
            await self.end_session(member)

            humans = self.count_humans(after.channel)
            if humans < 2:
                for m in before.channel.members:
                    if m.bot or m.voice.deaf:
                        continue
                    await self.end_session(m)

        # joined
        if after.channel:
            humans = self.count_humans(after.channel)

            if humans >= 2:
                for m in after.channel.members:
                    if m.bot or m.voice.deaf:
                        continue
                    self.start_session(m)

                    self.sessions[str(m.id)]["max_people"] = max(self.sessions[str(m.id)]["max_people"], humans)


async def setup(bot, stats_store, achievement_engine):
    await bot.add_cog(VoiceTracking(bot, stats_store, achievement_engine))