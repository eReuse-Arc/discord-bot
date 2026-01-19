import discord
from discord.ext import commands, tasks
from discord import app_commands
from pathlib import Path
import json
import random
import time
from io import BytesIO
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFont
from constants import *
from helpers.admin import admin_meta
from helpers.stats import StatsStore
from helpers.achievement_engine import AchievementEngine

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

async def log_action(guild, message: str):
        channel = guild.get_channel(MODERATOR_ONLY_CHANNEL_ID)
        if channel:
            await channel.send(message, silent=True)

class ActiveSpawn:
    def __init__(self, item: dict, variant: str, message_id: int, expires_at: int, channel_id: int, image_name: str | None):
        self.item = item
        self.variant = variant
        self.message_id = message_id
        self.expires_at = expires_at
        self.channel_id = channel_id
        self.image_name = image_name

        self.hints_used = 0
        self.revealed = {
            "category_and_first_letter": False,
            "length_and_tag": False,
            "choices": False,
        }

        self.last_bucket: int | None = None

class DexView(discord.ui.View):
    def __init__(self, cog, owner: discord.User, entries: list[dict], title: str):
        super().__init__(timeout=120)
        self.cog = cog
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
                sub += f"\n**Tags:** {', '.join(tags[:4])}"
            source = e.get("source", "spawn")
            sub += f"\n**Obtained:** {self.cog.fmt_source(source)}"
            sub += f"\n**Odds (per spawn):** {self.cog.fmt_odds(e.get('odds_p', 0.0))}"

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


class TradeSearchModal(discord.ui.Modal):
    def __init__(self, view, who: str):
        super().__init__(title="Search your items")
        self.view = view
        self.who = who

        self.query = discord.ui.TextInput(
            label="Search",
            placeholder="e.g. thinkpad, dongle, pristine, epic… (leave empty to clear)",
            required=False,
            max_length=50
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        q = str(self.query.value or "").strip()

        if self.who == "a":
            self.view.a_filter = q
        else:
            self.view.b_filter = q

        self.view.reset_confirms()

        self.view.a_select.options = self.view.make_options_for(self.view.a)
        self.view.b_select.options = self.view.make_options_for(self.view.b)

        a_tag = f" (filter: {self.view.a_filter})" if self.view.a_filter else ""
        b_tag = f" (filter: {self.view.b_filter})" if self.view.b_filter else ""
        self.view.a_select.placeholder = f"Select item to offer ({self.view.a.display_name}){a_tag}"
        self.view.b_select.placeholder = f"Select item to offer ({self.view.b.display_name}){b_tag}"

        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)

class TradeView(discord.ui.View):
    def __init__(self, cog, a: discord.Member, b: discord.Member, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.a = a
        self.b = b

        self.a_filter: str = ""
        self.b_filter: str = ""

        self.a_pick: tuple[str, str] | None = None
        self.b_pick: tuple[str, str] | None = None

        self.a_confirm = False
        self.b_confirm = False

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🔁 Trade")
        embed.description = (
            f"{self.a.mention} 🔁 {self.b.mention}\n\n"
            "Pick one item each, then both press **Confirm**."
        )

        def fmt_pick(user: discord.Member, pick: tuple[str, str] | None):
            if not pick:
                return "*(nothing selected)*"
            item_id, variant = pick
            c = self.cog.by_id.get(item_id)
            if not c:
                return "*(unknown item)*"
            vemoji = VARIANT_EMOJI.get(variant, "")
            return f"{vemoji} **{c['name']}** [{variant}]"

        embed.add_field(name=f"{self.a.display_name} offers", value=fmt_pick(self.a, self.a_pick), inline=True)
        embed.add_field(name=f"{self.b.display_name} offers", value=fmt_pick(self.b, self.b_pick), inline=True)

        embed.add_field(
            name="Status",
            value=f"{'✅' if self.a_confirm else '⬜'} {self.a.display_name} confirmed\n"
                  f"{'✅' if self.b_confirm else '⬜'} {self.b.display_name} confirmed",
            inline=False
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in (self.a.id, self.b.id)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    def reset_confirms(self):
        self.a_confirm = False
        self.b_confirm = False

    def make_options_for(self, user: discord.Member) -> list[discord.SelectOption]:
        own = self.cog.load_ownership().get(str(user.id), [])
        owned_keys = {(x["id"], x.get("variant", "Normal")) for x in own}

        f = (self.a_filter if user.id == self.a.id else self.b_filter).lower().strip()

        options: list[discord.SelectOption] = []
        for (item_id, variant) in sorted(owned_keys, key=lambda t: (t[0], t[1])):
            c = self.cog.by_id.get(item_id)
            if not c:
                continue

            label = self.cog.format_owned_label(c, variant)
            hay = " ".join([
                c.get("name", ""),
                variant,
                c.get("rarity", ""),
                c.get("category", ""),
                " ".join(c.get("tags") or []),
            ]).lower()

            if f and f not in hay:
                continue

            value = f"{item_id}|{variant}"
            options.append(discord.SelectOption(label=label[:100], value=value[:100]))
            if len(options) >= 25:
                break

        if not options:
            options.append(discord.SelectOption(label="(No matches)", value="none", default=True))

        return options


    async def try_finalise(self, interaction: discord.Interaction):
        if not (self.a_confirm and self.b_confirm):
            return

        if not self.a_pick or not self.b_pick:
            return await interaction.response.send_message("Both sides must select an item first.", ephemeral=True)

        a_item_id, a_variant = self.a_pick
        b_item_id, b_variant = self.b_pick

        if not self.cog.has_item(self.a.id, a_item_id, a_variant):
            return await interaction.response.send_message(f"{self.a.mention} no longer owns their selected item.", ephemeral=True)
        if not self.cog.has_item(self.b.id, b_item_id, b_variant):
            return await interaction.response.send_message(f"{self.b.mention} no longer owns their selected item.", ephemeral=True)

        if self.cog.has_item(self.b.id, a_item_id, a_variant):
            return await interaction.response.send_message(f"{self.b.mention} already owns that exact variant.", ephemeral=True)
        if self.cog.has_item(self.a.id, b_item_id, b_variant):
            return await interaction.response.send_message(f"{self.a.mention} already owns that exact variant.", ephemeral=True)

        self.cog.stats_store.bump(str(self.a.id), SALVAGE_TRADES, 1)
        self.cog.stats_store.bump(str(self.b.id), SALVAGE_TRADES, 1)
        await self.cog.eval_achievements_for(self.a)
        await self.cog.eval_achievements_for(self.b)

        self.cog.remove_item(self.a.id, a_item_id, a_variant)
        self.cog.remove_item(self.b.id, b_item_id, b_variant)

        self.cog.grant_item_and_track(self.b.id, a_item_id, a_variant, source=f"trade:{self.a.id}")
        self.cog.grant_item_and_track(self.a.id, b_item_id, b_variant, source=f"trade:{self.b.id}")

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(title="✅ Trade completed!")
        a_name = self.cog.by_id[a_item_id]["name"]
        b_name = self.cog.by_id[b_item_id]["name"]
        embed.description = (
            f"{self.a.mention} traded **{a_name}** [{a_variant}] → {self.b.mention}\n"
            f"{self.b.mention} traded **{b_name}** [{b_variant}] → {self.a.mention}"
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def start(self, interaction: discord.Interaction):
        self.a_select.options = self.make_options_for(self.a)
        self.b_select.options = self.make_options_for(self.b)

        self.a_select.placeholder = f"Select item to offer ({self.a.display_name})"
        self.b_select.placeholder = f"Select item to offer ({self.b.display_name})"

        await interaction.response.send_message(embed=self.build_embed(), view=self)
    
    @discord.ui.button(label="Search my items", style=discord.ButtonStyle.primary)
    async def search_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.a.id:
            return await interaction.response.send_modal(TradeSearchModal(self, "a"))
        if interaction.user.id == self.b.id:
            return await interaction.response.send_modal(TradeSearchModal(self, "b"))
        return await interaction.response.send_message("Not part of this trade.", ephemeral=True)


    @discord.ui.select(placeholder="Select item to offer (User A)", min_values=1, max_values=1)
    async def a_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.a.id:
            return await interaction.response.send_message(f"Only **{self.a.display_name}** can change this selection.", ephemeral=True)

        if select.values[0] == "none":
            self.a_pick = None
        else:
            self.a_pick = self.cog.parse_owned_value(select.values[0])
        self.reset_confirms()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.select(placeholder="Select item to offer (User B)", min_values=1, max_values=1)
    async def b_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user.id != self.b.id:
            return await interaction.response.send_message(f"Only **{self.b.display_name}** can change this selection.", ephemeral=True)


        if select.values[0] == "none":
            self.b_pick = None
        else:
            self.b_pick = self.cog.parse_owned_value(select.values[0])
        self.reset_confirms()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.a.id:
            self.a_confirm = True
        elif interaction.user.id == self.b.id:
            self.b_confirm = True
        else:
            return await interaction.response.send_message("Not part of this trade.", ephemeral=True)

        await self.try_finalise(interaction)
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(title="❌ Trade cancelled.")
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class BattleSearchModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Search your items")
        self.view = view
        self.query = discord.ui.TextInput(
            label="Search",
            placeholder="e.g. thinkpad, pristine, legendary… (leave empty to clear)",
            required=False,
            max_length=50
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        q = str(self.query.value or "").strip()
        self.view.set_filter_for(interaction.user.id, q)
        self.view.reset_confirms()
        self.view.refresh_select_options()
        await interaction.response.edit_message(embed=self.view.build_embed(), view=self.view)


class BattleView(discord.ui.View):
    def __init__(self, cog, a: discord.Member, b: discord.Member, timeout: int = 240):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.a = a
        self.b = b

        self.a_locked = False
        self.b_locked = False

        self.a_filter: str = ""
        self.b_filter: str = ""

        self.a_slots: list[tuple[str, str] | None] = [None, None, None]
        self.b_slots: list[tuple[str, str] | None] = [None, None, None]

        self.stage: str = "PICK_A"  # PICK_A -> PICK_B -> DONE

        self.slot1.row = 0
        self.slot2.row = 1
        self.slot3.row = 2

        self.search_items.row = 3
        self.lock_in.row = 3
        self.cancel.row = 3

    # -------------------------
    # interaction safety helpers
    # -------------------------
    async def ephemeral(self, interaction: discord.Interaction, content: str):
        if not interaction.response.is_done():
            await interaction.response.send_message(content, ephemeral=True)
        else:
            await interaction.followup.send(content, ephemeral=True)

    async def edit_main(self, interaction: discord.Interaction, **kwargs):
        if not interaction.response.is_done():
            await interaction.response.edit_message(**kwargs)
        else:
            await interaction.message.edit(**kwargs)

    def reset_confirms(self):
        pass

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in (self.a.id, self.b.id)

    def current_picker(self) -> discord.Member:
        if self.stage == "PICK_A":
            return self.a
        if self.stage == "PICK_B":
            return self.b
        return self.a

    def set_filter_for(self, user_id: int, q: str):
        if user_id == self.a.id:
            self.a_filter = q
        elif user_id == self.b.id:
            self.b_filter = q

    def filter_for(self, user: discord.Member) -> str:
        return (self.a_filter if user.id == self.a.id else self.b_filter).lower().strip()

    def picks_for(self, user: discord.Member) -> list[tuple[str, str] | None]:
        return self.a_slots if user.id == self.a.id else self.b_slots

    def make_options_for(self, user: discord.Member) -> list[discord.SelectOption]:
        own = self.cog.load_ownership().get(str(user.id), [])
        owned_keys = {(x["id"], x.get("variant", "Normal")) for x in own}

        f = self.filter_for(user)

        opts: list[discord.SelectOption] = []
        for (item_id, variant) in sorted(owned_keys, key=lambda t: (t[0], t[1])):
            c = self.cog.by_id.get(item_id)
            if not c:
                continue

            label = self.cog.format_owned_label(c, variant)

            hay = " ".join([
                c.get("name", ""),
                variant,
                c.get("rarity", ""),
                c.get("category", ""),
                " ".join(c.get("tags") or []),
            ]).lower()

            if f and f not in hay:
                continue

            value = f"{item_id}|{variant}"
            opts.append(discord.SelectOption(label=label[:100], value=value[:100]))
            if len(opts) >= 25:
                break

        if not opts:
            opts.append(discord.SelectOption(label="(No matches)", value="none", default=True))
        return opts

    def refresh_select_options(self):
        picker = self.current_picker()
        opts = self.make_options_for(picker)

        self.slot1.options = opts
        self.slot2.options = opts
        self.slot3.options = opts

        tag = self.filter_for(picker)
        tag_txt = f" (filter: {tag})" if tag else ""

        self.slot1.placeholder = f"Slot 1 ({picker.display_name}){tag_txt}"
        self.slot2.placeholder = f"Slot 2 ({picker.display_name}){tag_txt}"
        self.slot3.placeholder = f"Slot 3 ({picker.display_name}){tag_txt}"

    def fmt_slot(self, pick: tuple[str, str] | None) -> str:
        if not pick:
            return "*(empty)*"
        item_id, variant = pick
        c = self.cog.by_id.get(item_id)
        if not c:
            return "*(unknown)*"
        vemoji = VARIANT_EMOJI.get(variant, "")
        p, den = self.cog.battle_power(item_id, variant)
        pow_txt = f"1 in {den:,}" if den else "Unknown"
        return f"{vemoji} **{c['name']}** [{variant}] - **{pow_txt}**"

    def build_embed(self) -> discord.Embed:
        e = discord.Embed(title="⚔️ Battle (Best of 3)")

        if self.stage == "PICK_A":
            e.description = f"{self.a.mention} vs {self.b.mention}\n**{self.a.display_name}**: pick 3 items, then press **Lock In**."
        elif self.stage == "PICK_B":
            e.description = f"{self.a.mention} vs {self.b.mention}\n**{self.b.display_name}**: pick 3 items, then press **Lock In**."
        else:
            e.description = f"{self.a.mention} vs {self.b.mention}"

        if not (self.a_locked and self.b_locked):
            def slot_progress(user: discord.Member) -> str:
                slots = self.a_slots if user.id == self.a.id else self.b_slots
                filled = sum(1 for s in slots if s is not None)
                locked = "🔒 Locked" if ((user.id == self.a.id and self.a_locked) or (user.id == self.b.id and self.b_locked)) else "✏️ Picking"
                return f"{filled}/3 selected - {locked}"

            e.add_field(name=f"{self.a.display_name}", value=slot_progress(self.a), inline=True)
            e.add_field(name=f"{self.b.display_name}", value=slot_progress(self.b), inline=True)
            e.add_field(name="Picks", value="🔐 Picks are hidden until both players press **Lock In**.", inline=False)
        else:
            e.add_field(
                name=f"{self.a.display_name} picks",
                value="\n".join([f"**{i+1}.** {self.fmt_slot(self.a_slots[i])}" for i in range(3)]),
                inline=True
            )
            e.add_field(
                name=f"{self.b.display_name} picks",
                value="\n".join([f"**{i+1}.** {self.fmt_slot(self.b_slots[i])}" for i in range(3)]),
                inline=True
            )

        e.add_field(
            name="Status",
            value=f"{'✅' if self.a_locked else '⬜'} {self.a.display_name} locked\n"
                  f"{'✅' if self.b_locked else '⬜'} {self.b.display_name} locked",
            inline=False
        )
        return e

    def build_private_picks_text(self, user: discord.Member) -> str:
        slots = self.a_slots if user.id == self.a.id else self.b_slots
        lines = []
        for i in range(3):
            pick = slots[i]
            if not pick:
                lines.append(f"**{i+1}.** *(empty)*")
            else:
                item_id, variant = pick
                c = self.cog.by_id.get(item_id, {})
                name = c.get("name", "Unkown")
                rarity = c.get("rarity", "Common")
                vemoji = VARIANT_EMOJI.get(variant, "")
                lines.append(f"**{i+1}.** {vemoji} **{name}** [{variant}] - {rarity}")
        return "\n".join(lines)

    def enter_confirm_phase(self):
        for item in [self.slot1, self.slot2, self.slot3, self.search_items, self.lock_in]:
            try:
                self.remove_item(item)
            except Exception:
                pass

    async def set_slot(self, interaction: discord.Interaction, idx: int, value: str):
        if self.stage not in ("PICK_A", "PICK_B"):
            return await self.ephemeral(interaction, "Battle already locked / finished.")

        picker = self.current_picker()
        if interaction.user.id != picker.id:
            return await self.ephemeral(interaction, f"Only **{picker.display_name}** can pick right now.")

        if picker.id == self.a.id and self.a_locked:
            return await self.ephemeral(interaction, "You already locked in.")
        if picker.id == self.b.id and self.b_locked:
            return await self.ephemeral(interaction, "You already locked in.")

        pick = None if value == "none" else self.cog.parse_owned_value(value)

        if pick is not None:
            slots = self.picks_for(picker)
            already = {p for j, p in enumerate(slots) if p is not None and j != idx}
            if pick in already:
                return await self.ephemeral(interaction, "❌ You can't use the same salvage more than once in a battle.")

        slots = self.picks_for(picker)
        slots[idx] = pick

        await self.edit_main(interaction, embed=self.build_embed(), view=self)

    async def try_finalise(self, interaction: discord.Interaction):
        if self.stage == "DONE":
            return

        if not (self.a_locked and self.b_locked):
            return await self.ephemeral(interaction, "Both players must **Lock in** first.")

        for pick in self.a_slots:
            item_id, variant = pick
            if not self.cog.has_item(self.a.id, item_id, variant):
                return await self.ephemeral(interaction, f"{self.a.mention} no longer owns one of their picks.")

        for pick in self.b_slots:
            item_id, variant = pick
            if not self.cog.has_item(self.b.id, item_id, variant):
                return await self.ephemeral(interaction, f"{self.b.mention} no longer owns one of their picks.")

        rounds = []
        a_wins = b_wins = draws = 0

        for i in range(3):
            a_id, a_v = self.a_slots[i]
            b_id, b_v = self.b_slots[i]

            cmp = self.cog.compare_power(a_id, a_v, b_id, b_v)
            if cmp > 0:
                a_wins += 1
                outcome = "A"
            elif cmp < 0:
                b_wins += 1
                outcome = "B"
            else:
                draws += 1
                outcome = "D"

            rounds.append((i, a_id, a_v, b_id, b_v, outcome))

        if a_wins > b_wins:
            match = "A"
        elif b_wins > a_wins:
            match = "B"
        else:
            match = "D"

        uid_a = str(self.a.id)
        uid_b = str(self.b.id)

        self.cog.stats_store.bump(uid_a, SALVAGE_BATTLES_TOTAL, 1)
        self.cog.stats_store.bump(uid_b, SALVAGE_BATTLES_TOTAL, 1)

        self.cog.stats_store.bump(uid_a, SALVAGE_BATTLE_ROUNDS_WON, a_wins)
        self.cog.stats_store.bump(uid_a, SALVAGE_BATTLE_ROUNDS_LOST, b_wins)
        self.cog.stats_store.bump(uid_b, SALVAGE_BATTLE_ROUNDS_WON, b_wins)
        self.cog.stats_store.bump(uid_b, SALVAGE_BATTLE_ROUNDS_LOST, a_wins)

        if draws:
            self.cog.stats_store.bump(uid_a, SALVAGE_BATTLE_ROUND_DRAWS, draws)
            self.cog.stats_store.bump(uid_b, SALVAGE_BATTLE_ROUND_DRAWS, draws)

        if match == "A":
            self.cog.stats_store.bump(uid_a, SALVAGE_BATTLE_MATCH_WINS, 1)
            self.cog.stats_store.bump(uid_b, SALVAGE_BATTLE_MATCH_LOSSES, 1)
        elif match == "B":
            self.cog.stats_store.bump(uid_b, SALVAGE_BATTLE_MATCH_WINS, 1)
            self.cog.stats_store.bump(uid_a, SALVAGE_BATTLE_MATCH_LOSSES, 1)
        else:
            self.cog.stats_store.bump(uid_a, SALVAGE_BATTLE_MATCH_DRAWS, 1)
            self.cog.stats_store.bump(uid_b, SALVAGE_BATTLE_MATCH_DRAWS, 1)

        for child in self.children:
            child.disabled = True

        res = discord.Embed(title="🏁 Battle Result")
        res.description = f"{self.a.mention} vs {self.b.mention}"

        lines = []
        for i, a_id, a_v, b_id, b_v, outcome in rounds:
            a_item = self.cog.by_id.get(a_id, {})
            b_item = self.cog.by_id.get(b_id, {})
            a_name = a_item.get("name", "Unknown")
            b_name = b_item.get("name", "Unknown")

            a_p, a_den = self.cog.battle_power(a_id, a_v)
            b_p, b_den = self.cog.battle_power(b_id, b_v)
            a_pow = f"1 in {a_den:,}" if a_den else "Unknown"
            b_pow = f"1 in {b_den:,}" if b_den else "Unknown"

            if outcome == "A":
                mark = f"✅ {self.a.display_name} wins"
            elif outcome == "B":
                mark = f"✅ {self.b.display_name} wins"
            else:
                mark = "🤝 Draw"

            lines.append(f"**Round {i+1}:** {a_name} [{a_v}] ({a_pow}) 🆚 {b_name} [{b_v}] ({b_pow}) → {mark}")

        res.add_field(name="Rounds", value="\n".join(lines), inline=False)

        if match == "A":
            res.add_field(name="Match", value=f"🏆 **{self.a.display_name} wins** ({a_wins}–{b_wins}, draws {draws})", inline=False)
        elif match == "B":
            res.add_field(name="Match", value=f"🏆 **{self.b.display_name} wins** ({b_wins}–{a_wins}, draws {draws})", inline=False)
        else:
            res.add_field(name="Match", value=f"🤝 **Draw match** ({a_wins}–{b_wins}, draws {draws})", inline=False)

        file = None
        try:
            file = self.cog.build_battle_collage(rounds)
            if file:
                res.set_image(url=f"attachment://{file.filename}")
        except Exception:
            file = None

        if file:
            await self.edit_main(interaction, embed=res, view=None, attachments=[file])
        else:
            await self.edit_main(interaction, embed=res, view=None, attachments=[])

        ch = self.cog.bot.get_cog("Challenges")
        if ch:
            await self.cog.achievement_engine.evaluate(ch.build_ctx(self.a))
            await self.cog.achievement_engine.evaluate(ch.build_ctx(self.b))

        self.stage = "DONE"


    @discord.ui.select(placeholder="Slot 1", min_values=1, max_values=1)
    async def slot1(self, interaction: discord.Interaction, select: discord.ui.Select):
        await self.set_slot(interaction, 0, select.values[0])

    @discord.ui.select(placeholder="Slot 2", min_values=1, max_values=1)
    async def slot2(self, interaction: discord.Interaction, select: discord.ui.Select):
        await self.set_slot(interaction, 1, select.values[0])

    @discord.ui.select(placeholder="Slot 3", min_values=1, max_values=1)
    async def slot3(self, interaction: discord.Interaction, select: discord.ui.Select):
        await self.set_slot(interaction, 2, select.values[0])

    @discord.ui.button(label="Search my items", style=discord.ButtonStyle.primary)
    async def search_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        picker = self.current_picker()
        if interaction.user.id != picker.id:
            return await self.ephemeral(interaction, f"Only **{picker.display_name}** can search right now.")
        await interaction.response.send_modal(BattleSearchModal(self))

    @discord.ui.button(label="My Picks", style=discord.ButtonStyle.primary)
    async def my_picks(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.a.id, self.b.id):
            return await self.ephemeral(interaction, "Not part of this battle.")
        text = self.build_private_picks_text(interaction.user)
        embed = discord.Embed(title="🗒️ Your Picks (Private)", description=text)
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Lock in", style=discord.ButtonStyle.secondary)
    async def lock_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.stage == "DONE":
            return await self.ephemeral(interaction, "Battle already finished.")

        if interaction.user.id == self.a.id:
            if self.stage != "PICK_A":
                return await self.ephemeral(interaction, "It's not your turn to pick.")
            if not all(self.a_slots):
                return await self.ephemeral(interaction, "Fill all 3 slots before locking in.")

            self.a_locked = True
            self.stage = "PICK_B"
            self.refresh_select_options()

            return await self.edit_main(interaction, embed=self.build_embed(), view=self)

        if interaction.user.id == self.b.id:
            if self.stage != "PICK_B":
                return await self.ephemeral(interaction, "It's not your turn to pick.")
            if not all(self.b_slots):
                return await self.ephemeral(interaction, "Fill all 3 slots before locking in.")

            self.b_locked = True

            self.enter_confirm_phase()

            await self.edit_main(interaction, embed=self.build_embed(), view=self)

            await self.try_finalise(interaction)
            return

        return await self.ephemeral(interaction, "Not part of this battle.")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await self.edit_main(interaction, embed=discord.Embed(title="❌ Battle cancelled."), view=self)
        self.stop()



class Salvage(commands.Cog):
    def __init__(self, bot: commands.Bot, stats_store: StatsStore, achievemnet_engine: AchievementEngine):
        self.bot = bot
        self.stats_store = stats_store
        self.achievement_engine = achievemnet_engine
        self.collectibles = self.load_collectibles()
        self.by_id = {c["id"]: c for c in self.collectibles}
        self.active_spawn: ActiveSpawn | None = None
        self.next_spawn_time = 0
        self.last_hint_time = 0
        self.spawn_updater.start()

    def cog_unload(self):
        self.spawn_updater.cancel()
        return super().cog_unload()

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


    def grant_item_and_track(self, user_id: int, item_id: str, variant: str, source: str):
        item = self.by_id.get(item_id)
        if not item:
            return

        self.grant_item(user_id, item_id, variant, source=source)

        p_exact, _bucket, _den, _p_rarity, _p_variant = self.odds_for_item_variant_per_spawn(item, variant)
        denom = int(round(1.0 / p_exact)) if p_exact > 0 else 0

        uid = str(user_id)

        self.stats_store.bump(uid, SALVAGE_TOTAL, 1)

        if source == "spawn":
            self.stats_store.bump(uid, SALVAGE_SPAWN_CAUGHT, 1)
        elif source.startswith("gift:"):
            self.stats_store.bump(uid, SALVAGE_GIFTS_RECEIVED, 1)
        elif source.startswith("trade:"):
            pass

        rarity = item.get("rarity", "Common")
        if rarity == "Epic":
            self.stats_store.bump(uid, SALVAGE_EPIC_TOTAL, 1)
        if rarity == "Legendary":
            self.stats_store.bump(uid, SALVAGE_LEGENDARY_TOTAL, 1)

        if denom >= 50_000:
            self.stats_store.bump(uid, SALVAGE_RARE_50K_TOTAL, 1)
        if denom >= 1_000_000:
            self.stats_store.bump(uid, SALVAGE_RARE_1M_TOTAL, 1)

        self.stats_store.set_bump(uid, SALVAGE_UNIQUE_VARIANTS, variant)
        self.stats_store.set_bump(uid, SALVAGE_UNIQUE_RARITIES, rarity)


    def format_owned_label(self, collectible: dict, variant: str) -> str:
        vemoji = VARIANT_EMOJI.get(variant, "")
        rarity = collectible.get("rarity", "Common")
        remoji = RARITY_EMOJI.get(rarity, "⚪")
        return f"{remoji}{vemoji} {collectible['name']} [{variant}]"

    def parse_owned_value(self, value: str) -> tuple[str, str]:
        item_id, variant = value.split("|", 1)
        return item_id, variant

    def game_channel_only(self, interaction: discord.Interaction) -> bool:
        return interaction.channel_id == SALVAGE_CHANNEL_ID

    async def send_wrong_channel(self, interaction: discord.Interaction):
        ch = self.bot.get_channel(SALVAGE_CHANNEL_ID)
        mention = ch.mention if isinstance(ch, discord.TextChannel) else f"<#{SALVAGE_CHANNEL_ID}>"
        await interaction.response.send_message(f"Use this in {mention}.", ephemeral=True)

    def weight_map(self, weights_list: list[tuple[str, int]]) -> dict[str, int]:
        return {k: int(v) for k, v in weights_list}

    def available_rarity_weights(self) -> list[tuple[str, int]]:
        available = {c.get("rarity", "Common") for c in self.collectibles}
        return [(r, w) for (r, w) in RARITY_WEIGHTS if r in available]

    def pick_rarity(self) -> str:
        pool = self.available_rarity_weights()
        if not pool:
            return "Common"
        rarities = [r for r, _w in pool]
        weights = [w for _r, w in pool]
        return random.choices(rarities, weights=weights, k=1)[0]

    def pick_collectible_weighted_by_rarity(self) -> dict:
        rarity = self.pick_rarity()
        bucket = [c for c in self.collectibles if c.get("rarity", "Common") == rarity]
        return random.choice(bucket) if bucket else random.choice(self.collectibles)

    def bucket_size_for_rarity(self, rarity: str) -> int:
        return sum(1 for c in self.collectibles if c.get("rarity", "Common") == rarity)

    def odds_for_item_variant_per_spawn(self, item: dict, variant: str) -> tuple[float, int, int, float, float]:
        r = item.get("rarity", "Common")
        r_pool = self.available_rarity_weights()
        r_map = self.weight_map(r_pool)
        r_total = sum(w for _rr, w in r_pool) or 1
        r_w = r_map.get(r, 0)
        p_rarity = (r_w / r_total) if r_w > 0 else 0.0

        bucket_size = self.bucket_size_for_rarity(r) or 1
        p_item_given_rarity = 1.0 / bucket_size

        v_map = self.weight_map(VARIANT_WEIGHTS)
        v_total = sum(v_map.values()) or 1
        v_w = v_map.get(variant, 0)
        p_variant = (v_w / v_total) if v_w > 0 else 0.0

        p_exact = p_rarity * p_item_given_rarity * p_variant
        denom_exact = int(round(1.0 / p_exact)) if p_exact > 0 else 0
        return p_exact, bucket_size, denom_exact, p_rarity, p_variant

    def fmt_odds(self, p: float) -> str:
        if p <= 0:
            return "Unknown"
        denom = int(round(1.0 / p))
        pct = p * 100.0

        if denom >= 10_000:
            return f"1 in {denom:,} ({pct:.6f}%)"
        return f"1 in {denom:,} ({pct:.3f}%)"

    def fmt_source(self, source: str) -> str:
        if source == "spawn":
            return "Spawn"
        if source.startswith("gift:"):
            uid = source.split(":", 1)[1]
            return f"Gift from <@{uid}>"
        if source.startswith("trade:"):
            uid = source.split(":", 1)[1]
            return f"Trade with <@{uid}>"
        return source

    async def eval_achievements_for(self, member: discord.Member):
        challenges = self.bot.get_cog("Challenges")
        if not challenges:
            return
        ctx = challenges.build_ctx(member)
        await self.achievement_engine.evaluate(ctx)

    @staticmethod
    def safe_open_image(path: str, size=(256,256)) -> Image.Image:
        try:
            img = Image.open(path).convert("RGBA")
        except:
            img = Image.new("RGBA", size, (40,40,40,255))
        img = ImageOps.contain(img, size)
        canvas = Image.new("RGBA", size, (0,0,0,0))
        canvas.paste(img, ((size[0]-img.size[0])//2, (size[1]-img.size[1])//2), img)
        return canvas

    @staticmethod
    def gray_out(img: Image.Image) -> Image.Image:
        g = ImageOps.grayscale(img).convert("RGBA")
        g = ImageEnhance.Brightness(g).enhance(0.75)
        alpha = g.split()[-1].point(lambda a: int(a * 0.55))
        g.putalpha(alpha)
        return g

    def add_red_x(self, img: Image.Image) -> Image.Image:
        overlay = img.copy()
        d = ImageDraw.Draw(overlay)

        w, h = overlay.size
        margin = int(min(w,h) * 0.12)
        thickness = max(8, int(min(w, h) * 0.06))

        red = (220, 50, 60, 255)

        d.line((margin, margin, w - margin, h - margin), fill=red, width=thickness)
        d.line((w - margin, margin, margin, h - margin), fill=red, width=thickness)
        return overlay

    def build_battle_collage(self, rounds) -> discord.File | None:
        cell = (220, 220)
        pad = 20
        rows = 3
        w = pad + cell[0] + pad + 80 + pad + cell[0] + pad
        h = pad + rows * (cell[1] + pad)

        canvas = Image.new("RGBA", (w, h), (20, 20, 24, 255))
        draw = ImageDraw.Draw(canvas)

        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()

        for i, a_id, a_v, b_id, b_v, outcome in rounds[:3]:
            a_item = self.by_id.get(a_id, {})
            b_item = self.by_id.get(b_id, {})
            a_img_path = a_item.get("image", "")
            b_img_path = b_item.get("image", "")

            left = self.safe_open_image(a_img_path, size=cell)
            right = self.safe_open_image(b_img_path, size=cell)

            if outcome == "A":
                right = self.add_red_x(self.gray_out(right))
            elif outcome == "B":
                left = self.add_red_x(self.gray_out(left))

            y = pad + i * (cell[1] + pad)
            x_left = pad
            x_mid = x_left + cell[0] + pad
            x_right = x_mid + 80 + pad

            canvas.paste(left, (x_left, y), left)
            canvas.paste(right, (x_right, y), right)

            vs = "VS"
            bbox = draw.textbbox((0,0), vs, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((x_mid + (80 - tw)//2, y + (cell[1] - th)//2), vs, font=font, fill=(230,230,240,255))

        out = BytesIO()
        canvas.save(out, format="PNG")
        out.seek(0)
        return discord.File(fp=out, filename="battle.png")

    def build_escaped_spawn_image(self, item: dict) -> discord.File | None:
        img_path = item.get("image", "")
        if not img_path:
            return None

        try:
            base = self.safe_open_image(img_path, size=(256, 256))
            base = self.add_red_x(self.gray_out(base))

            out = BytesIO()
            base.save(out, format="PNG")
            out.seek(0)
            return discord.File(fp=out, filename="escaped.png")
        except Exception:
            return None


    def battle_power(self, item_id: str, variant: str) -> tuple[float, int]:
        item = self.by_id.get(item_id)
        if not item:
            return (0.0, 0)

        p_exact, _bucket, denom_exact, _p_rarity, _p_variant = self.odds_for_item_variant_per_spawn(item, variant)
        return (p_exact, denom_exact)

    def compare_power(self, a_item_id: str, a_variant: str, b_item_id: str, b_variant: str) -> int:
        a_p, a_d = self.battle_power(a_item_id, a_variant)
        b_p, b_d = self.battle_power(b_item_id, b_variant)

        if a_p <= 0 or b_p <= 0:
            if a_d == b_d:
                return 0
            return 1 if a_d > b_d else -1

        eps = 1e-15
        if abs(a_p - b_p) <= eps:
            return 0
        return 1 if a_p < b_p else -1



    async def spawn(self, trigger_message: discord.Message | None = None):
        if not self.collectibles:
            return

        channel = self.bot.get_channel(SALVAGE_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return

        item = self.pick_collectible_weighted_by_rarity()
        variant = self.pick_variant()

        remaining = SPAWN_EXPIRE_SECONDS
        embed = self.build_spawn_embed(item, variant, remaining, escaped=False)

        img_path = Path(item.get("image", ""))
        file = None
        image_name = None
        if img_path.exists():
            image_name = img_path.name
            file = discord.File(str(img_path), filename=image_name)
            embed.set_image(url=f"attachment://{image_name}")

        ping_content = None
        role = None
        guild = channel.guild
        if guild and SALVAGE_PING_ROLE_NAME:
            role = discord.utils.get(guild.roles, name=SALVAGE_PING_ROLE_NAME)

        if role is not None:
            ping_content = f"Opt-In Mentions: {role.mention}"

        msg = await channel.send(content=ping_content, embed=embed, file=file, silent=True)

        if trigger_message is not None:
            try:
                if trigger_message.channel.id == channel.id:
                    await trigger_message.reply("♻️ You triggered a salvage spawn above!")
                else:
                    await trigger_message.reply(f"♻️ You triggered a salvage spawn in {channel.mention}!")
            except (discord.Forbidden, discord.HTTPException):
                pass

        self.active_spawn = ActiveSpawn(
            item=item,
            variant=variant,
            message_id=msg.id,
            expires_at=now() + SPAWN_EXPIRE_SECONDS,
            channel_id=channel.id,
            image_name=image_name
        )

        self.next_spawn_time = now() + random.randint(SPAWN_COOLDOWN_MIN, SPAWN_COOLDOWN_MAX)



    def build_spawn_embed(self, item: dict, variant: str, remaining: int, escaped: bool = False) -> discord.Embed:
        vemoji = VARIANT_EMOJI.get(variant, "")
        rarity = item.get("rarity", "Common")

        if escaped:
            embed = discord.Embed(
                title=f"💨 The salvage escaped! {vemoji}",
                description="Too slow… better luck next time.",
                color=discord.Color.red(),
            )
            embed.add_field(name="Rarity", value=rarity_style(rarity), inline=True)
            embed.add_field(name="Variant", value=f"{vemoji} **{variant}**" if variant != "Normal" else "**Normal**", inline=True)
            embed.add_field(name="Status", value="❌ **Escaped**", inline=False)
            return embed

        embed = discord.Embed(
            title=f"♻️ A salvage find appeared! {vemoji}",
            description="Type `/catch` and pick the correct name (autocomplete helps).\nYou can use `/hint` up to 3 times as a group.",
            color=discord.Color.green(),
        )
        embed.add_field(name="Rarity", value=rarity_style(rarity), inline=True)
        embed.add_field(name="Variant", value=f"{vemoji} **{variant}**" if variant != "Normal" else "**Normal**", inline=True)
        embed.add_field(name="Status", value=f"Escapes in **{max(0, remaining)}s**", inline=False)

        p_exact, bucket_size, denom_exact, p_rarity, p_variant = self.odds_for_item_variant_per_spawn(item, variant)
        embed.add_field(name="Odds (this exact item)", value=self.fmt_odds(p_exact), inline=False)
        embed.add_field(
            name="Odds breakdown (per spawn)",
            value=(
                f"Rarity: {self.fmt_odds(p_rarity)}\n"
                f"Variant: {self.fmt_odds(p_variant)}\n"
                f"Items in rarity bucket: **{bucket_size}**"
            ),
            inline=False
        )
        return embed


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.active_spawn:
            return

        if now() < self.next_spawn_time:
            return

        if random.random() < SPAWN_CHANCE:
            await self.spawn(trigger_message=message)
    

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


    @tasks.loop(seconds=5)
    async def spawn_updater(self):
        if not self.active_spawn:
            return

        s = self.active_spawn
        remaining = s.expires_at - now()

        if remaining <= 0:
            channel = self.bot.get_channel(s.channel_id)
            if not isinstance(channel, discord.TextChannel):
                self.active_spawn = None
                return

            try:
                msg = await channel.fetch_message(s.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                self.active_spawn = None
                return

            escaped_embed = self.build_spawn_embed(s.item, s.variant, 0, escaped=True)

            escaped_file = self.build_escaped_spawn_image(s.item)
            if escaped_file:
                escaped_embed.set_image(url="attachment://escaped.png")
                await msg.edit(embed=escaped_embed, attachments=[escaped_file])
            else:
                await msg.edit(embed=escaped_embed)

            self.active_spawn = None
            return

        bucket = remaining // 5
        if s.last_bucket == bucket:
            return
        s.last_bucket = bucket

        channel = self.bot.get_channel(s.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            msg = await channel.fetch_message(s.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            self.active_spawn = None
            return

        new_embed = self.build_spawn_embed(s.item, s.variant, remaining, escaped=False)

        if s.image_name:
            new_embed.set_image(url=f"attachment://{s.image_name}")

        await msg.edit(embed=new_embed)


    @spawn_updater.before_loop
    async def before_spawn_updater(self):
        await self.bot.wait_until_ready()


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

        self.grant_item_and_track(interaction.user.id, item_id, variant, source="spawn")
        await self.eval_achievements_for(interaction.user)

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
        rec_map: dict[tuple[str, str], dict] = {}
        for x in own:
            key = (x["id"], x.get("variant", "Normal"))
            if key not in rec_map or int(x.get("obtained_at", 0)) < int(rec_map[key].get("obtained_at", 0)):
                rec_map[key] = x

        owned_keys = set(rec_map.keys())

        by_id = {c["id"]: c for c in self.collectibles}
        entries = []

        for (item_id, variant) in owned_keys:
            c = by_id.get(item_id)
            if not c:
                continue

            rec = rec_map[(item_id, variant)]
            source = rec.get("source", "spawn")

            p_exact, bucket_size, denom_exact, p_rarity, p_variant = self.odds_for_item_variant_per_spawn(c, variant)

            entries.append({
                "name": c["name"],
                "rarity": c.get("rarity", "Common"),
                "category": c.get("category", "Unknown"),
                "variant": variant,
                "tags": c.get("tags") or [],
                "source": source,
                "odds_p": p_exact
            })

        entries.sort(key=lambda e: (e["odds_p"] if e["odds_p"] > 0 else 1.0, e["name"].lower(), e["variant"]))

        total_possible = len(self.collectibles) * len({v for v,_w in VARIANT_WEIGHTS})
        completion = f"{len(owned_keys)}/{total_possible}"

        title = f"♻️ SalvageDex - {completion}"
        view = DexView(cog=self, owner=interaction.user, entries=entries, title=title)
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
        self.stats_store.bump(str(interaction.user.id), SALVAGE_GIFTS_SENT, 1)
        self.grant_item_and_track(member.id, item_id, variant, source=f"gift:{interaction.user.id}")
        await self.eval_achievements_for(interaction.user)
        await self.eval_achievements_for(member)

        vemoji = VARIANT_EMOJI.get(variant, "")
        embed = discord.Embed(
            title="🎁 Gifted!",
            description=f"{interaction.user.mention} gifted {member.mention} {vemoji} **{cand['name']}** [{variant}]"
        )
        embed.add_field(name="Rarity", value=rarity_style(cand.get("rarity","Common")), inline=True)
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="trade", description="Start a trade with another member.")
    async def trade_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if not self.game_channel_only(interaction):
            return await self.send_wrong_channel(interaction)

        if member.bot:
            return await interaction.response.send_message("You can't trade with bots.", ephemeral=True)

        if member.id == interaction.user.id:
            return await interaction.response.send_message("You can't trade with yourself.", ephemeral=True)

        self.by_id = {c["id"]: c for c in self.collectibles}

        a_own = self.load_ownership().get(str(interaction.user.id), [])
        b_own = self.load_ownership().get(str(member.id), [])
        if not a_own:
            return await interaction.response.send_message("You don't own anything to trade yet.", ephemeral=True)
        if not b_own:
            return await interaction.response.send_message(f"{member.mention} doesn't own anything to trade yet.", ephemeral=True)

        view = TradeView(self, interaction.user, member)
        await view.start(interaction)


    @app_commands.command(name="battle", description="Battle someone using 3 salvages each (best of 3).")
    async def battle_cmd(self, interaction: discord.Interaction, member: discord.Member):
        if not self.game_channel_only(interaction):
            return await self.send_wrong_channel(interaction)

        if member.bot:
            return await interaction.response.send_message("You can't battle bots.", ephemeral=True)

        if member.id == interaction.user.id:
            return await interaction.response.send_message("You can't battle yourself.", ephemeral=True)

        self.by_id = {c["id"]: c for c in self.collectibles}

        a_own = self.load_ownership().get(str(interaction.user.id), [])
        b_own = self.load_ownership().get(str(member.id), [])

        a_unique = {(x["id"], x.get("variant","Normal")) for x in a_own}
        b_unique = {(x["id"], x.get("variant","Normal")) for x in b_own}

        if len(a_unique) < 3:
            return await interaction.response.send_message("You need at least **3** unique salvages to battle.", ephemeral=True)
        if len(b_unique) < 3:
            return await interaction.response.send_message(f"{member.mention} needs at least **3** unique salvages to battle.", ephemeral=True)

        view = BattleView(self, interaction.user, member)
        view.refresh_select_options()
        await interaction.response.send_message(embed=view.build_embed(), view=view)



    @app_commands.command(name="salvage_test_spawn", description="(Admin) Force a salvage spawn now.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.check(lambda itx: False) # Disabled
    @admin_meta(permissions= "Administrator",
            affects= ["Collectibles", "Ownerships"],
            notes= "To test if salvage spawning works, forcefully spawn one")
    async def salvage_test_spawn(self, interaction: discord.Interaction):
        if interaction.channel_id != SALVAGE_CHANNEL_ID:
            return await self.send_wrong_channel(interaction)

        self.active_spawn = None
        self.last_hint_time = 0
        self.next_spawn_time = 0

        await log_action(
            guild=interaction.guild,
            message=f"🐣 {interaction.user.mention} spawned a Salvage"
        )

        await interaction.response.send_message("✅ Forcing a spawn in the salvage channel.", ephemeral=True)
        await self.spawn()
    
    @salvage_test_spawn.error
    async def salvage_test_spawn_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "⚠️ This command is currently disabled.", 
                ephemeral=True
            )
        else:
            print(f"An unexpected error occurred: {error}")

async def setup(bot, stats_store, achievement_engine):
    await bot.add_cog(Salvage(bot, stats_store, achievement_engine))