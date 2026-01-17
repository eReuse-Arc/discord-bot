import discord
from discord import app_commands
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import traceback
from constants import *
from helpers.stats import StatsStore
from pathlib import Path
from helpers.achievement_engine import AchievementEngine
import os
import json
from typing import Any, Dict
import cogs.challenges
import cogs.voice

load_dotenv()

def _safe_json_load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except:
        return {}


def _safe_json_save(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


stats_store = StatsStore(Path(USER_STATS_PATH))

achievement_engine = AchievementEngine(
    load_fn=lambda: _safe_json_load(Path(ACHEIVEMENTS_PATH)),
    save_fn=lambda d: _safe_json_save(Path(ACHEIVEMENTS_PATH), d)
)


class eReuseBot(commands.Bot):
    async def setup_hook(self) -> None:
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    if filename.endswith("challenges.py"):
                        await cogs.challenges.setup(bot, stats_store, achievement_engine)
                    elif filename.endswith("voice.py"):
                        await cogs.voice.setup(bot, stats_store, achievement_engine)
                    else:
                        await bot.load_extension(f"cogs.{filename[:-3]}")
                except Exception as e:
                    print(f"[ERROR] failed to load {filename}: {e}")

        try:
            guild = discord.Object(id=1446585420283646054)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        except Exception as e:
            print(f"[ERROR] tree.sync failed: {e}")


        guild = discord.Object(id=1446585420283646054)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)

        print("Commands Synced")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = eReuseBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is up and running :D")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.guild is None:
        return

    stats_store.bump(str(message.author.id), "messages", 1)

    if message.attachments:
        stats_store.bump(str(message.author.id), "files", len(message.attachments))

    if "ereuse" in message.content.lower():
        emoji = discord.utils.get(message.guild.emojis, name="eReuse")
        if emoji:
            try:
                await message.add_reaction(emoji)
                stats_store.bump(str(message.author.id), "ereuse_reacts", 1)
            except Exception as e:
                print(f"Failed to react: {e}")

    if "67" in message.content:
        try:
            stats_store.bump(str(message.author.id), SIX_SEVEN, 1)
        except Exception as e:
            pass

    try:
        member = message.guild.get_member(message.author.id)
        challenges_cog = bot.get_cog("Challenges")
        if member and challenges_cog:
            ctx = challenges_cog.build_ctx(member)
            await achievement_engine.evaluate(ctx)
    except Exception as e:
        print(f"[WARN] achievment eval failed: {e}")

    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return

    if reaction.message.guild is None:
        return

    stats_store.bump(str(user.id), REACTIONS_GIVEN, 1)

    if reaction.message.author.id == bot.user.id and reaction.emoji == "💚":
        stats_store.set_value(str(user.id), FOOTER_READER, True)

    if reaction.message.channel.id == ANNOUNCEMENT_CHANNEL_ID:
        already_reacted = False
        for r in reaction.message.reactions:
            if r == reaction:
                continue

            users = [u async for u in r.users()]
            if user in users:
                already_reacted = True
                break

        if not already_reacted:
            stats_store.bump(str(user.id), ANNOUNCEMENT_REACTS, 1)

    unique_users = {u.id for r in reaction.message.reactions async for u in r.users() if not u.bot}
    total_reactions = sum(r.count for r in reaction.message.reactions)
    message_owner = reaction.message.guild.get_member(reaction.message.author.id)

    challenges_cog = bot.get_cog("Challenges")

    if message_owner:
        stats_store.set_bump(str(user.id), REACTED_USERS, str(message_owner.id))

        stats = stats_store.get(message_owner.id)
        curr_unique = stats.get(MAX_UNIQUE_REACTORS, 0)
        curr_reacts = stats.get(MAX_REACTIONS_ON_MESSAGE, 0)
        updated = False

        if len(unique_users) > curr_unique:
            stats_store.set_value(str(message_owner.id), MAX_UNIQUE_REACTORS, len(unique_users))
            updated = True

        if total_reactions > curr_reacts:
            stats_store.set_value(str(message_owner.id), MAX_REACTIONS_ON_MESSAGE, total_reactions)
            updated = True

        if updated and challenges_cog:
            ctx = challenges_cog.build_ctx(message_owner)
            await achievement_engine.evaluate(ctx)

    member = reaction.message.guild.get_member(user.id)
    if member and challenges_cog:
        ctx = challenges_cog.build_ctx(member)
        await achievement_engine.evaluate(ctx)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    traceback.print_exception(type(error), error, error.__traceback__)

    msg = f"❌ Error: `{error}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

def main():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        raise RuntimeError("Missing Discord_Token Environment Variable")
    bot.run(token, log_handler=handler, log_level=logging.DEBUG)


if __name__ == "__main__":
    main()