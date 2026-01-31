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
import json
from typing import Any, Dict
import cogs.challenges
import cogs.voice
import cogs.salvage
from cogs.verify import VerifyStore

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

verify_store = VerifyStore(VERIFY_PATH)
ALLOWED_UNVERIFIED = {"verify", "verifyfinish", "help"}

def _has_role(member: discord.Member, role_name: str) -> bool:
    return any(r.name == role_name for r in member.roles)

class VerifiedOnlyTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True
        
        cmd = interaction.command
        root_name = ""
        if cmd:
            root_name = cmd.root_parent.name if cmd.root_parent else cmd.name
        
        if root_name in ALLOWED_UNVERIFIED:
            return True
        
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        
        return _has_role(member, VERIFY_ROLE) or verify_store.is_verified(member.id)

class eReuseBot(commands.Bot):
    async def setup_hook(self) -> None:
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    if filename.endswith("challenges.py"):
                        await cogs.challenges.setup(bot, stats_store, achievement_engine)
                    elif filename.endswith("voice.py"):
                        await cogs.voice.setup(bot, stats_store, achievement_engine)
                    elif filename.endswith("salvage.py"):
                        await cogs.salvage.setup(bot, stats_store, achievement_engine)
                    else:
                        await bot.load_extension(f"cogs.{filename[:-3]}")
                except Exception as e:
                    print(f"[ERROR] failed to load {filename}: {e}")

        try:
            guild = discord.Object(id=1446585420283646054)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print("Commands Synced")
        except Exception as e:
            print(f"[ERROR] tree.sync failed: {e}")
                 

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = eReuseBot(command_prefix="!", intents=intents, tree_cls=VerifiedOnlyTree)

@bot.event
async def on_ready():
    print(f"{bot.user.name} is up and running :D")

@bot.event
async def on_message(message: discord.Message):
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


    emoji_ids = CUSTOM_EMOJI_REGEX.findall(message.content)
    if emoji_ids:
        user_id = str(message.author.id)
        guild_emoji_ids = {str(e.id) for e in message.guild.emojis}

        used_this_message = set()

        for eid in emoji_ids:
            if eid in guild_emoji_ids:
                stats_store.bump(user_id, SERVER_EMOJIS_USED, 1)
                used_this_message.add(eid)
            
        if used_this_message:
            for eid in used_this_message:
                stats_store.set_bump(user_id, UNIQUE_SERVER_EMOJIS, eid)
            
            stats = stats_store.get(user_id)
            if not stats.get(EMOJI_ARCHIVIST, False):
                unique_count = len(stats.get(UNIQUE_SERVER_EMOJIS, []))
                total_emojis = len(message.guild.emojis)

                if total_emojis > 0 and unique_count >= total_emojis:
                    stats_store.set_value(user_id, EMOJI_ARCHIVIST, True)


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
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return

    if payload.guild_id is None:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    channel = guild.get_channel(payload.channel_id)
    if channel is None:
        return
    
    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.Forbidden, discord.NotFound):
        return
    
    user = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
    if user.bot:
        return

    stats_store.bump(str(user.id), REACTIONS_GIVEN, 1)

    if message.author.id == bot.user.id and str(payload.emoji) == "💚":
        stats_store.set_value(str(user.id), FOOTER_READER, True)

    if channel.id == ANNOUNCEMENT_CHANNEL_ID:
        already_reacted = False
        for r in message.reactions:
            if str(r.emoji) == str(payload.emoji):
                continue

            users = [u async for u in r.users()]
            if user in users:
                already_reacted = True
                break

        if not already_reacted:
            stats_store.bump(str(user.id), ANNOUNCEMENT_REACTS, 1)

    unique_users = {u.id for r in message.reactions async for u in r.users() if not u.bot}
    total_reactions = sum(r.count for r in message.reactions)
    message_owner = guild.get_member(message.author.id)

    challenges_cog = bot.get_cog("Challenges")

    if message_owner:
        stats_store.set_bump(str(user.id), REACTED_USERS, str(message_owner.id))

        stats = stats_store.get(str(message_owner.id))
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

    if user and challenges_cog:
        ctx = challenges_cog.build_ctx(user)
        await achievement_engine.evaluate(ctx)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    traceback.print_exception(type(error), error, error.__traceback__)

    if interaction.guild is not None:
        cmd = interaction.command
        root_name = cmd.root_parent.name if cmd and cmd.root_parent else (cmd.name if cmd else "")
        member = interaction.user

        if root_name not in ALLOWED_UNVERIFIED and isinstance(member, discord.Member):
            if not _has_role(member, VERIFY_ROLE) and not verify_store.is_verified(member.id):
                msg = (
                    "🔒 You must verify before using bot commands.\n"
                    "Use **`/verify`** to start, then **`/verifyfinish`** with your code.\n"
                    "Need help? Use **`/help`** or ask in the verification forum."
                )
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                return

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