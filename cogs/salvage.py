import discord
from discord.ext import commands
from discord import app_commands
from pathlib import Path
import json
import random
import time
from constants import *
from helpers.admin import admin_meta

COLLECTIBLES_FILE = Path(COLLECTIBLES_PATH)
OWNERSHIP_FILE = Path(OWNERSHIP_PATH)

def now() -> int:
    return int(time.time())

def load_json(path: Path, default):
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except:
        return default

def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def rarity_style(rarity: str) -> str:
    return f"{RARITY_EMOJI.get(rarity,'⚪')} **{rarity}**"


class ActiveSpawn:
    def __init__(self, item: dict, variant: str, message_id: int, expires_at: int):
        self.item = item
        self.variant = variant
        self.message_id = message_id
        self.expires_at = expires_at
        self.hints_used = 0
        self.revealed = {
            "category_and_first_letter": False,
            "length_and_tag": False,
            "choices": False,
        }

class DexView(discord.ui.View):
    def __init__(self, owner: discord.User, entries: list[dict], title: str):
        super().__init__(timeout=120)
        self.owner = owner
        self.entries = entries
        self.title = title
        self.page = 0
        self.per_page = 3

    def page_count(self) -> int:
        if not self.entries:
            return 1
        return (len(self.entries) + self.per_page - 1) // self.per_page

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=self.title)
        embed.set_footer(text=f"Page {self.page+1}/{self.page_count()} - {self.owner.display_name}")
        start = self.page * self.per_page
        chunk = self.entries[start:start + self.per_page]

        if not chunk:
            embed.description = "Nothing here yet."
            return embed

        for e in chunk:
            variant = e.get("variant", "Normal")
            vemoji = VARIANT_EMOJI.get(variant, "")
            name_line = f"{vemoji} **{e['name']}**"
            sub = f"{rarity_style(e['rarity'])} - {e['category']}"
            tags = e.get("tags") or []
            if tags:
                sub += f"\n*Tags:* {', '.join(tags[:4])}"
            embed.add_field(name=name_line, value=sub, inline=False)

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return self.owner.id == interaction.user.id

    @discord.ui.button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page - 1) % self.page_count()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = (self.page + 1) % self.page_count()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(view=None)


class Salvage(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.collectibles = self.load_collectibles()
        self.active_spawn: ActiveSpawn | None = None
        self.next_spawn_time = 0
        self.last_hint_time = 0

    def load_collectibles(self) -> list[dict]:
        data = load_json(COLLECTIBLES_FILE, [])
        data.sort(key=lambda x: (RARITY_ORDER.index(x.get("rarity","Common")) if x.get("rarity") in RARITY_ORDER else 0, x.get("name","")))
        return data

    def load_ownership(self) -> dict[str, list[dict]]:
        return load_json(OWNERSHIP_FILE, {})

    def save_ownership(self, data: dict[str, list[dict]]) -> None:
        save_json(OWNERSHIP_FILE, data)
    
    def pick_variant(self) -> str:
        total = sum(w for _, w in VARIANT_WEIGHTS)
        r = random.randint(1, total)
        acc = 0
        for name, w in VARIANT_WEIGHTS:
            acc += w
            if r <= acc:
                return name
        return "Normal"

    def has_item(self, user_id: int, item_id: str, variant: str) -> bool:
        own = self.load_ownership()
        items = own.get(str(user_id), [])
        return any(x["id"] == item_id and x.get("variant","Normal") == variant for x in items)


    def grant_item(self, user_id: int, item_id: str, variant: str, source: str):
        own = self.load_ownership()
        items = own.get(str(user_id), [])
        items.append({"id": item_id, "variant": variant, "obtained_at": now(), "source": source})
        own[str(user_id)] = items
        self.save_ownership(own)

    def remove_item(self, user_id: int, item_id: str, variant: str) -> bool:
        own = self.load_ownership()
        items = own.get(str(user_id), [])
        before = len(items)
        items = [x for x in items if not (x["id"] == item_id and x.get("variant","Normal") == variant)]
        if len(items) == before:
            return False
        own[str(user_id)] = items
        self.save_ownership(own)
        return True

    def game_channel_only(self, interaction: discord.Interaction) -> bool:
        return interaction.channel_id == SALVAGE_CHANNEL_ID

    async def send_wrong_channel(self, interaction: discord.Interaction):
        ch = self.bot.get_channel(SALVAGE_CHANNEL_ID)
        mention = ch.mention if isinstance(ch, discord.TextChannel) else f"<#{SALVAGE_CHANNEL_ID}>"
        await interaction.response.send_message(f"Use this in {mention}.", ephemeral=True)
    
    async def spawn(self):
        channel = self.bot.get_channel(SALVAGE_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return

        item = random.choice(self.collectibles)
        variant = self.pick_variant()
        vemoji = VARIANT_EMOJI.get(variant, "")
        rarity = item.get("rarity", "Common")

        embed = discord.Embed(
            title=f"♻️ A salvage find appeared! {vemoji}",
            description="Type `/catch` and pick the correct name (autocomplete helps).",
        )
        embed.add_field(name="Rarity", value=rarity_style(rarity), inline=True)
        embed.add_field(name="Variant", value=f"{vemoji} **{variant}**" if variant != "Normal" else "**Normal**", inline=True)
        embed.add_field(name="Status", value=f"Escapes in **{SPAWN_EXPIRE_SECONDS}s**", inline=False)

        img_path = Path(item.get("image",""))
        file = None
        if img_path.exists():
            file = discord.File(str(img_path), filename=img_path.name)
            embed.set_image(url=f"attachment://{img_path.name}")

        msg = await channel.send(embed=embed, file=file)
        self.active_spawn = ActiveSpawn(item=item, variant=variant, message_id=msg.id, expires_at=now() + SPAWN_EXPIRE_SECONDS)

        self.next_spawn_time = now() + random.randint(SPAWN_COOLDOWN_MIN, SPAWN_COOLDOWN_MAX)
    

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.active_spawn and now() >= self.active_spawn.expires_at:
            self.active_spawn = None

        if self.active_spawn:
            return

        if now() < self.next_spawn_time:
            return

        if random.random() < SPAWN_CHANCE:
            await self.spawn()
    

    async def catch_autocomplete(self, interaction: discord.Interaction, current: str):
        if not self.active_spawn:
            return []

        needle = (current or "").lower().strip()


        choices = []
        for it in self.collectibles:
            name = it["name"]
            if needle and needle not in name.lower():
                continue
            choices.append(app_commands.Choice(name=name, value=name))
            if len(choices) >= 25:
                break

        return choices


    @app_commands.command(name="catch", description="Catch the current salvage spawn!")
    @app_commands.autocomplete(name=catch_autocomplete)
    async def catch_cmd(self, interaction: discord.Interaction, name: str):
        if not self.game_channel_only(interaction):
            return await self.send_wrong_channel(interaction)

        if not self.active_spawn or now() >= self.active_spawn.expires_at:
            self.active_spawn = None
            return await interaction.response.send_message("No active spawn right now.", ephemeral=True)

        correct_name = self.active_spawn.item["name"]
        if name.strip().lower() != correct_name.strip().lower():
            return await interaction.response.send_message("❌ Not quite.", ephemeral=True)

        item_id = self.active_spawn.item["id"]
        variant = self.active_spawn.variant

        if self.has_item(interaction.user.id, item_id, variant):
            return await interaction.response.send_message("You already own this exact variant, let someone else grab it.", ephemeral=True)

        self.grant_item(interaction.user.id, item_id, variant, source="spawn")

        vemoji = VARIANT_EMOJI.get(variant, "")
        rarity = self.active_spawn.item.get("rarity","Common")
        embed = discord.Embed(
            title="✅ Salvaged!",
            description=f"🏅 {interaction.user.mention} caught {vemoji} **{correct_name}**",
        )
        embed.add_field(name="Rarity", value=rarity_style(rarity), inline=True)
        embed.add_field(name="Variant", value=f"{vemoji} **{variant}**" if variant != "Normal" else "**Normal**", inline=True)

        await interaction.response.send_message(embed=embed)
        self.active_spawn = None
    
    @app_commands.command(name="hint", description="Reveal a hint for the current spawn (shared cooldown).")
    async def hint_cmd(self, interaction: discord.Interaction):
        if not self.game_channel_only(interaction):
            return await self.send_wrong_channel(interaction)

        if not self.active_spawn or now() >= self.active_spawn.expires_at:
            self.active_spawn = None
            return await interaction.response.send_message("No active spawn right now.", ephemeral=True)

        if now() - self.last_hint_time < HINT_COOLDOWN_SECONDS:
            remaining = HINT_COOLDOWN_SECONDS - (now() - self.last_hint_time)
            return await interaction.response.send_message(f"Hint cooldown: **{remaining}s**", ephemeral=True)

        if self.active_spawn.hints_used >= MAX_HINTS_PER_SPAWN:
            return await interaction.response.send_message("No more hints for this spawn.", ephemeral=True)

        self.last_hint_time = now()
        self.active_spawn.hints_used += 1

        item = self.active_spawn.item
        name = item["name"]
        category = item.get("category","Unknown")
        tags = item.get("tags") or []

        hint_text = ""
        if self.active_spawn.hints_used == 1:
            hint_text = f"**Category:** {category}\n**Starts with:** **{name[0]}**"
        elif self.active_spawn.hints_used == 2:
            tag = tags[0] if tags else "None"
            hint_text = f"**Length:** {len(name)}\n**Tag:** {tag}"
        else:
            pool = [c for c in self.collectibles if c["id"] != item["id"]]
            decoys = random.sample(pool, k=min(2, len(pool)))
            options = [item["name"]] + [d["name"] for d in decoys]
            random.shuffle(options)
            hint_text = "**It's one of:**\n" + "\n".join([f"- {opt}" for opt in options])

        embed = discord.Embed(title="💡 Hint", description=hint_text)
        await interaction.response.send_message(embed=embed)
    

    @app_commands.command(name="dex", description="View your SalvageDex (paginated).")
    async def dex_cmd(self, interaction: discord.Interaction):
        if not self.game_channel_only(interaction):
            return await self.send_wrong_channel(interaction)

        own = self.load_ownership().get(str(interaction.user.id), [])
        owned_keys = {(x["id"], x.get("variant","Normal")) for x in own}

        by_id = {c["id"]: c for c in self.collectibles}
        entries = []
        for (item_id, variant) in sorted(owned_keys, key=lambda t: (t[0], t[1])):
            c = by_id.get(item_id)
            if not c:
                continue
            entries.append({
                "name": c["name"],
                "rarity": c.get("rarity","Common"),
                "category": c.get("category","Unknown"),
                "variant": variant,
                "tags": c.get("tags") or []
            })

        total_possible = len(self.collectibles) * len({v for v,_w in VARIANT_WEIGHTS})
        completion = f"{len(owned_keys)}/{total_possible}"

        title = f"♻️ SalvageDex - {completion}"
        view = DexView(owner=interaction.user, entries=entries, title=title)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
    

    async def owned_autocomplete(self, interaction: discord.Interaction, current: str):
        own = self.load_ownership().get(str(interaction.user.id), [])
        if not own:
            return []
        by_id = {c["id"]: c for c in self.collectibles}
        needle = (current or "").lower().strip()

        seen = []
        for x in own:
            c = by_id.get(x["id"])
            if not c:
                continue
            variant = x.get("variant","Normal")
            label = f"{c['name']} [{variant}]"
            if needle and needle not in label.lower():
                continue
            seen.append(app_commands.Choice(name=label, value=label))
            if len(seen) >= 25:
                break
        return seen

    @app_commands.command(name="gift", description="Gift one of your items to someone.")
    @app_commands.autocomplete(item=owned_autocomplete)
    async def gift_cmd(self, interaction: discord.Interaction, member: discord.Member, item: str):
        if not self.game_channel_only(interaction):
            return await self.send_wrong_channel(interaction)

        if "[" not in item or not item.endswith("]"):
            return await interaction.response.send_message("Pick an item from autocomplete.", ephemeral=True)

        base_name = item.split("[", 1)[0].strip()
        variant = item.split("[", 1)[1].rstrip("]").strip()

        cand = next((c for c in self.collectibles if c["name"].lower() == base_name.lower()), None)
        if not cand:
            return await interaction.response.send_message("Could not resolve that item.", ephemeral=True)

        item_id = cand["id"]

        if member.id == interaction.user.id:
            return await interaction.response.send_message("You can't gift yourself 😭", ephemeral=True)

        if not self.has_item(interaction.user.id, item_id, variant):
            return await interaction.response.send_message("You don't own that item/variant.", ephemeral=True)

        if self.has_item(member.id, item_id, variant):
            return await interaction.response.send_message("They already own that exact variant.", ephemeral=True)

        self.remove_item(interaction.user.id, item_id, variant)
        self.grant_item(member.id, item_id, variant, source=f"gift:{interaction.user.id}")

        vemoji = VARIANT_EMOJI.get(variant, "")
        embed = discord.Embed(
            title="🎁 Gifted!",
            description=f"{interaction.user.mention} gifted {member.mention} {vemoji} **{cand['name']}** [{variant}]"
        )
        embed.add_field(name="Rarity", value=rarity_style(cand.get("rarity","Common")), inline=True)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="salvage_test_spawn", description="(Admin) Force a salvage spawn now.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @admin_meta(permissions= "Administrator",
            affects= ["Collectibles", "Ownerships"],
            notes= "To test if salvage spawning works, forcefully spawn one")
    async def salvage_test_spawn(self, interaction: discord.Interaction):
        if interaction.channel_id != SALVAGE_CHANNEL_ID:
            return await self.send_wrong_channel(interaction)

        self.active_spawn = None
        self.last_hint_time = 0
        self.next_spawn_time = 0

        await interaction.response.send_message("✅ Forcing a spawn in the salvage channel.", ephemeral=True)
        await self.spawn()

async def setup(bot: commands.Bot):
    await bot.add_cog(Salvage(bot))