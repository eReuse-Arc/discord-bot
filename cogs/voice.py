import discord
from discord.ext import commands
from discord import app_commands
from constants import *
from datetime import datetime


class VoiceTracking(commands.Cog):
    def __init__(self, bot, stats_store, achievement_engine):
        self.bot = bot
        self.stats_store = stats_store
        self.achievement_engine = achievement_engine

        # Active
        self.sessions = {}

    def count_humans(self, channel: discord.VoiceChannel) -> int:
        return sum(1 for m in channel.members if not m.bot and not m.voice.deaf and not m.voice.afk)

    def start_session(self, member: discord.Member):
        user_id = str(member.id)
        if user_id in self.sessions:
            return

        self.sessions[user_id] = {
            "channel_id" : member.voice.channel.id,
            "start": datetime.now(datetime.timezone.utc),
            "max_people": self.count_humans(member.voice.channel)
        }

    def end_session(self, member: discord.Member):
        user_id = str(member.id)
        session = self.session.pop(user_id, None)
        if not session:
            return

        now = datetime.now(datetime.timezone.utc)
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
            ctx = cog.build_ctx(member)
            self.achievement_engine.evaluate(ctx)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        if member.bot:
            return

        # left voice
        if before.channel and not after.channel:
            self.end_session(member)

        # joined
        if after.channel:
            humans = self.count_humans(after.channel)

            if humans >= 2:
                for m in after.channel.members:
                    if m.bot or m.voice.deaf:
                        continue
                    self.start_session(m)
            else:
                self.end_session(member)

        # Changed
        if before.channel and after.channel and before.channel != after.channel:
            self.end_session(member)

async def setup(bot, stats_store, achievement_engine):
    await bot.add_cog(VoiceTracking(bot, stats_store, achievement_engine))