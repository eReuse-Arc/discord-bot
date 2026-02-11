import discord
from discord import app_commands
from discord.ext import commands

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Dict, List, Tuple, Any
from constants import PUT_THROUGH_PATH


Scope = Literal["all", "weekly", "bingo", "stamp", "votw"]
Show = Literal["pending", "all"]


def now_unix() -> int:
    import time
    return int(time.time())


def _load_json(path: Path, default):
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _atomic_save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _safe_int(x) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


@dataclass
class TaskItem:
    owner_uid: str
    scope: Literal["weekly", "bingo", "stamp", "votw"]
    task_id: str
    title: str
    sort_key: int
    meta: dict



class BaseAdminView(discord.ui.View):
    def __init__(self, actor_id: int, timeout: int = 300):
        super().__init__(timeout=timeout)
        self.actor_id = actor_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "❌ Only the admin who opened this menu can use it.",
                ephemeral=True
            )
            return False
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


class ProcessInboxView(BaseAdminView):
    def __init__(self, cog: "Processing", actor_id: int):
        super().__init__(actor_id=actor_id, timeout=300)
        self.cog = cog
        self.page = 0
        self.page_size = 20
        self._rows: List[dict] = []


    async def _refresh_rows(self, guild: discord.Guild):
        self._rows = await self.cog.build_inbox_rows(guild)

        self._rows.sort(key=lambda r: (r["pending_total"], r["recent_sort"]), reverse=True)

        max_page = max(0, (len(self._rows) - 1) // self.page_size)
        self.page = max(0, min(self.page, max_page))

    def _page_slice(self) -> List[dict]:
        start = self.page * self.page_size
        end = start + self.page_size
        return self._rows[start:end]

    async def _make_embed(self, guild: discord.Guild) -> discord.Embed:
        total_users = len(self._rows)
        pending_users = sum(1 for r in self._rows if r["pending_total"] > 0)
        pending_total = sum(r["pending_total"] for r in self._rows)

        e = discord.Embed(
            title="🧾 Processing Inbox",
            description=(
                "Select a user to batch mark tasks as **put through**.\n"
                "Default view shows **pending only**."
            ),
            color=discord.Color.green()
        )
        e.add_field(
            name="Summary",
            value=(
                f"👥 Users with pending: **{pending_users} / {total_users}**\n"
                f"⏳ Total pending items: **{pending_total}**"
            ),
            inline=False
        )

        rows = self._page_slice()
        if not rows:
            e.add_field(name="No pending items", value="Nothing to process 🎉", inline=False)
        else:
            lines = []
            for r in rows:
                member = guild.get_member(int(r["uid"])) if _safe_int(r["uid"]) else None
                name = member.mention if member else f"<@{r['uid']}>"
                lines.append(
                    f"{name} - "
                    f"**{r['pending_total']}** pending "
                    f"(W:{r['pending_weekly']} B:{r['pending_bingo']} S:{r['pending_stamp']} V:{r['pending_votw']})"
                )
            e.add_field(name="This page", value="\n".join(lines), inline=False)

        max_page = max(1, (len(self._rows) - 1) // self.page_size + 1)
        e.set_footer(text=f"Page {self.page + 1}/{max_page} • /processuser also available")
        return e

    def _rebuild_children(self, guild: discord.Guild):
        self.clear_items()

        rows = self._page_slice()
        options = []
        for r in rows[:25]:
            uid = r["uid"]
            member = guild.get_member(int(uid)) if _safe_int(uid) else None
            label = (member.display_name if member else uid)[:100]
            desc = f"{r['pending_total']} pending (W:{r['pending_weekly']} B:{r['pending_bingo']} S:{r['pending_stamp']} V:{r['pending_votw']})"
            options.append(discord.SelectOption(label=label, value=uid, description=desc[:100]))

        select = discord.ui.Select(
            placeholder="Pick a user to process…",
            min_values=1,
            max_values=1,
            options=options or [discord.SelectOption(label="No users on this page", value="none")]
        )

        async def _on_select(interaction: discord.Interaction):
            if select.values[0] == "none":
                return await interaction.response.send_message("Nothing to open.", ephemeral=True)
            uid = select.values[0]
            member = guild.get_member(int(uid)) if _safe_int(uid) else None
            if member is None:
                return await interaction.response.send_message("User not found in guild.", ephemeral=True)

            view = ProcessUserView(self.cog, actor_id=self.actor_id, target=member, scope="all", show="pending")
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)

        select.callback = _on_select
        self.add_item(select)

        self.add_item(self.PrevButton())
        self.add_item(self.NextButton())
        self.add_item(self.RefreshButton())

    class PrevButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="⬅️ Prev", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessInboxView" = self.view
            view.page -= 1
            await view.render(interaction)

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="➡️ Next", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessInboxView" = self.view
            view.page += 1
            await view.render(interaction)

    class RefreshButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="🔄 Refresh", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessInboxView" = self.view
            await view.render(interaction)

    async def render(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            return await interaction.response.send_message("Run this in a server.", ephemeral=True)

        await self._refresh_rows(guild)
        self._rebuild_children(guild)
        embed = await self._make_embed(guild)

        max_page = max(0, (len(self._rows) - 1) // self.page_size)
        self.page = max(0, min(self.page, max_page))

        await interaction.response.edit_message(embed=embed, view=self)


class ProcessUserView(BaseAdminView):
    def __init__(self, cog: "Processing", actor_id: int, target: discord.Member, scope: Scope, show: Show):
        super().__init__(actor_id=actor_id, timeout=300)
        self.cog = cog
        self.target = target
        self.scope: Scope = scope
        self.show: Show = show

        self.page = 0
        self.page_size = 20
        self.items: List[TaskItem] = []
        self._selected_task_ids: List[str] = []

        self.add_item(self.BackButton())
        self.add_item(self.ToggleShowButton())
        self.add_item(self.ScopeSelect())
        self.add_item(self.MarkSelectedButton())
        self.add_item(self.MarkAllShownButton())
        self.add_item(self.UndoSelectedButton())
        self.add_item(self.PrevButton())
        self.add_item(self.NextButton())
        self.add_item(self.RefreshButton())


    async def refresh(self):
        self.items = await self.cog.build_tasks_for_user(self.target.guild, self.target.id, scope=self.scope, show=self.show)

        self.items.sort(key=lambda t: t.sort_key, reverse=True)

        max_page = max(0, (len(self.items) - 1) // self.page_size)
        self.page = max(0, min(self.page, max_page))

        self._rebuild_task_select()

    def _page_slice(self) -> List[TaskItem]:
        start = self.page * self.page_size
        end = start + self.page_size
        return self.items[start:end]

    def _rebuild_task_select(self):
        to_remove = []
        for child in self.children:
            if isinstance(child, discord.ui.Select) and (child.custom_id or "").startswith("task_select:"):
                to_remove.append(child)
        for c in to_remove:
            self.remove_item(c)

        page_items = self._page_slice()
        options = []
        for t in page_items[:25]:
            options.append(
                discord.SelectOption(
                    label=(t.title[:100] or t.task_id[:100]),
                    value=t.task_id,
                    description=f"{t.scope} • {t.task_id}"[:100]
                )
            )

        if not options:
            options = [discord.SelectOption(label="No items on this page", value="none")]

        select = discord.ui.Select(
            placeholder="Select tasks (multi-select) …",
            min_values=1,
            max_values=min(25, len(options)),
            options=options,
            custom_id=f"task_select:{self.target.id}:{self.page}"
        )

        async def _on_select(interaction: discord.Interaction):
            if select.values and select.values[0] == "none":
                self._selected_task_ids = []
            else:
                self._selected_task_ids = list(select.values)
            await interaction.response.send_message(
                f"Selected **{len(self._selected_task_ids)}** task(s).",
                ephemeral=True
            )

        select.callback = _on_select
        self.add_item(select)

    async def make_embed(self) -> discord.Embed:
        pending_total, counts = await self.cog.count_user_pending(self.target.guild, self.target.id)
        e = discord.Embed(
            title=f"🧾 Processing - {self.target.display_name}",
            description=(
                f"Status view: **{self.show}** • Scope: **{self.scope}**\n"
                f"Pending totals: W:{counts['weekly']} B:{counts['bingo']} S:{counts['stamp']} V:{counts['votw']} "
                f"(**{pending_total}** total)\n\n"
                "Tip: Use **Mark all shown processed** to batch submit."
            ),
            color=discord.Color.green()
        )

        page_items = self._page_slice()
        if not page_items:
            e.add_field(name="No items", value="Nothing matches this filter.", inline=False)
        else:
            lines = []
            for t in page_items:
                status = await self.cog.get_task_status_for_display(self.target.id, t)
                icon = "✅" if status == "processed" else "⏳"
                lines.append(f"{icon} **{t.title}** - `{t.task_id}`")
            e.add_field(name="This page", value="\n".join(lines), inline=False)

        max_page = max(1, (len(self.items) - 1) // self.page_size + 1)
        e.set_footer(text=f"Page {self.page + 1}/{max_page} • Selected: {len(self._selected_task_ids)}")
        return e


    class BackButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="⬅️ Inbox", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            inbox = ProcessInboxView(view.cog, actor_id=view.actor_id)
            await inbox._refresh_rows(interaction.guild)
            inbox._rebuild_children(interaction.guild)
            await interaction.response.edit_message(embed=await inbox._make_embed(interaction.guild), view=inbox)

    class ToggleShowButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="Toggle pending/all", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            view.show = "all" if view.show == "pending" else "pending"
            view.page = 0
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)

    class ScopeSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="All", value="all"),
                discord.SelectOption(label="Weekly", value="weekly"),
                discord.SelectOption(label="Bingo", value="bingo"),
                discord.SelectOption(label="Stamp", value="stamp"),
                discord.SelectOption(label="VOTW", value="votw"),
            ]
            super().__init__(placeholder="Filter scope…", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            view.scope = self.values[0]
            view.page = 0
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)

    class MarkSelectedButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="✅ Mark selected processed", style=discord.ButtonStyle.success)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            if not view._selected_task_ids:
                return await interaction.response.send_message("Select tasks first.", ephemeral=True)

            changed = await view.cog.mark_tasks_processed(
                guild=interaction.guild,
                owner_uid=str(view.target.id),
                task_ids=view._selected_task_ids,
                processed_by=str(interaction.user.id)
            )
            view._selected_task_ids = []
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)
            await interaction.followup.send(f"✅ Marked **{changed}** task(s) processed.", ephemeral=True)

    class MarkAllShownButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="✅ Mark all shown processed", style=discord.ButtonStyle.success)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            page_items = view._page_slice()
            if not page_items:
                return await interaction.response.send_message("No items on this page.", ephemeral=True)

            task_ids = [t.task_id for t in page_items]
            changed = await view.cog.mark_tasks_processed(
                guild=interaction.guild,
                owner_uid=str(view.target.id),
                task_ids=task_ids,
                processed_by=str(interaction.user.id)
            )
            view._selected_task_ids = []
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)
            await interaction.followup.send(f"✅ Marked **{changed}** task(s) processed.", ephemeral=True)

    class UndoSelectedButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="↩️ Mark selected pending", style=discord.ButtonStyle.danger)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            if not view._selected_task_ids:
                return await interaction.response.send_message("Select tasks first.", ephemeral=True)

            changed = await view.cog.mark_tasks_pending(
                guild=interaction.guild,
                owner_uid=str(view.target.id),
                task_ids=view._selected_task_ids
            )
            view._selected_task_ids = []
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)
            await interaction.followup.send(f"↩️ Marked **{changed}** task(s) pending.", ephemeral=True)

    class PrevButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="⬅️ Prev", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            view.page -= 1
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)

    class NextButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="➡️ Next", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            view.page += 1
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)

    class RefreshButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="🔄 Refresh", style=discord.ButtonStyle.secondary)

        async def callback(self, interaction: discord.Interaction):
            view: "ProcessUserView" = self.view
            await view.refresh()
            await interaction.response.edit_message(embed=await view.make_embed(), view=view)



class Processing(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ledger_path = Path(PUT_THROUGH_PATH)
        self._lock = asyncio.Lock()


    def _load_ledger(self) -> dict:
        return _load_json(self.ledger_path, {"version": 1, "users": {}, "global": {"tasks": {}}})

    def _save_ledger(self, data: dict) -> None:
        _atomic_save_json(self.ledger_path, data)

    def _get_user_task_entry(self, data: dict, uid: str) -> dict:
        users = data.setdefault("users", {})
        u = users.setdefault(uid, {})
        tasks = u.setdefault("tasks", {})
        return tasks

    def _get_global_tasks(self, data: dict) -> dict:
        g = data.setdefault("global", {})
        return g.setdefault("tasks", {})

    async def get_task_status_for_display(self, owner_uid: int | str, task: TaskItem) -> str:
        uid = str(owner_uid)
        async with self._lock:
            data = self._load_ledger()
            if task.scope == "votw":
                gt = self._get_global_tasks(data)
                return (gt.get(task.task_id, {}) or {}).get("status", "pending")
            ut = self._get_user_task_entry(data, uid)
            return (ut.get(task.task_id, {}) or {}).get("status", "pending")


    def _challenges(self) -> Optional[commands.Cog]:
        return self.bot.get_cog("Challenges")

    async def build_tasks_for_user(self, guild: discord.Guild, user_id: int, scope: Scope, show: Show) -> List[TaskItem]:
        challenges = self._challenges()
        if challenges is None:
            return []

        uid = str(user_id)

        points_data = challenges.load_points()
        bingo_progress = challenges.load_bingo_progress()
        stamp_cards = challenges.load_stamp_cards()
        votw_winners = challenges.load_volunteer_winners()

        items: List[TaskItem] = []

        if scope in ("all", "weekly"):
            weeks = points_data.get(uid, [])
            for w in weeks:
                wi = _safe_int(w)
                if wi is None:
                    continue
                items.append(TaskItem(
                    owner_uid=uid,
                    scope="weekly",
                    task_id=f"weekly:week={wi}",
                    title=f"Weekly Challenge - Week {wi}",
                    sort_key=wi,
                    meta={"week": wi}
                ))

        if scope in ("all", "bingo"):
            user_cards = (bingo_progress.get(uid) or {})
            if isinstance(user_cards, dict):
                for card_key, cd in user_cards.items():
                    if not isinstance(cd, dict):
                        continue
                    completed = cd.get("completed", [])
                    if not isinstance(completed, list):
                        continue
                    try:
                        is_bingo = challenges.has_bingo(set(map(str, completed)))
                    except Exception:
                        is_bingo = False
                    if not is_bingo:
                        continue

                    card_num = _safe_int(card_key) or 0
                    items.append(TaskItem(
                        owner_uid=uid,
                        scope="bingo",
                        task_id=f"bingo:card={card_key}",
                        title=f"Bingo Completed - Card {card_key}",
                        sort_key=1000000 + card_num,  # keep bingo above weekly if desired
                        meta={"card": card_key}
                    ))

        if scope in ("all", "stamp"):
            entry = stamp_cards.get(uid, {}) if isinstance(stamp_cards, dict) else {}
            cards = entry.get("cards", {}) if isinstance(entry, dict) else {}
            if isinstance(cards, dict):
                for card_key, ts in cards.items():
                    sk = 0
                    if isinstance(ts, str):
                        dt = _parse_iso(ts)
                        if dt:
                            sk = int(dt.timestamp())
                    if sk == 0:
                        sk = 2000000 + (_safe_int(card_key) or 0)

                    items.append(TaskItem(
                        owner_uid=uid,
                        scope="stamp",
                        task_id=f"stamp:card={card_key}",
                        title=f"Stamp Card Completed - Card {card_key}",
                        sort_key=sk,
                        meta={"card": card_key, "timestamp": ts}
                    ))

        if scope in ("all", "votw"):
            if isinstance(votw_winners, dict):
                for wk, winner_uid in votw_winners.items():
                    if str(winner_uid) != uid:
                        continue
                    wki = _safe_int(wk) or 0
                    items.append(TaskItem(
                        owner_uid=uid,
                        scope="votw",
                        task_id=f"votw:week={wk}",
                        title=f"Volunteer of the Week - Week {wk}",
                        sort_key=3000000 + wki,
                        meta={"week": wk}
                    ))

        if show == "pending":
            pending_items: List[TaskItem] = []
            for t in items:
                st = await self.get_task_status_for_display(uid, t)
                if st != "processed":
                    pending_items.append(t)
            items = pending_items

        return items

    async def build_inbox_rows(self, guild: discord.Guild) -> List[dict]:
        challenges = self._challenges()
        if challenges is None:
            return []

        points_data = challenges.load_points()
        bingo_progress = challenges.load_bingo_progress()
        stamp_cards = challenges.load_stamp_cards()
        votw_winners = challenges.load_volunteer_winners()

        uids: set[str] = set()
        if isinstance(points_data, dict):
            uids.update(points_data.keys())
        if isinstance(bingo_progress, dict):
            uids.update(bingo_progress.keys())
        if isinstance(stamp_cards, dict):
            uids.update(stamp_cards.keys())
        if isinstance(votw_winners, dict):
            for _wk, winner_uid in votw_winners.items():
                uids.add(str(winner_uid))

        rows: List[dict] = []
        for uid in uids:
            pending_total, counts = await self.count_user_pending(guild, int(uid) if _safe_int(uid) else uid)
            if pending_total <= 0:
                continue

            recent_sort = max(counts.get("_recent_sort", 0), 0)

            rows.append({
                "uid": uid,
                "pending_total": pending_total,
                "pending_weekly": counts["weekly"],
                "pending_bingo": counts["bingo"],
                "pending_stamp": counts["stamp"],
                "pending_votw": counts["votw"],
                "recent_sort": recent_sort
            })

        return rows

    async def count_user_pending(self, guild: discord.Guild, user_id: int | str) -> Tuple[int, dict]:
        challenges = self._challenges()
        if challenges is None:
            return 0, {"weekly": 0, "bingo": 0, "stamp": 0, "votw": 0, "_recent_sort": 0}

        uid = str(user_id)

        weekly = await self.build_tasks_for_user(guild, int(uid) if _safe_int(uid) else 0, scope="weekly", show="pending")
        bingo = await self.build_tasks_for_user(guild, int(uid) if _safe_int(uid) else 0, scope="bingo", show="pending")
        stamp = await self.build_tasks_for_user(guild, int(uid) if _safe_int(uid) else 0, scope="stamp", show="pending")
        votw = await self.build_tasks_for_user(guild, int(uid) if _safe_int(uid) else 0, scope="votw", show="pending")

        counts = {
            "weekly": len(weekly),
            "bingo": len(bingo),
            "stamp": len(stamp),
            "votw": len(votw),
            "_recent_sort": 0
        }

        max_sk = 0
        for lst in (weekly, bingo, stamp, votw):
            for t in lst:
                max_sk = max(max_sk, t.sort_key)
        counts["_recent_sort"] = max_sk

        return sum((counts["weekly"], counts["bingo"], counts["stamp"], counts["votw"])), counts


    async def mark_tasks_processed(self, guild: discord.Guild, owner_uid: str, task_ids: List[str], processed_by: str) -> int:
        if not task_ids:
            return 0

        async with self._lock:
            data = self._load_ledger()
            utasks = self._get_user_task_entry(data, owner_uid)
            gtasks = self._get_global_tasks(data)

            changed = 0
            for tid in task_ids:
                if tid.startswith("votw:"):
                    cur = gtasks.get(tid, {}) or {}
                    if cur.get("status") != "processed":
                        changed += 1
                    gtasks[tid] = {
                        **cur,
                        "status": "processed",
                        "processed_at": now_unix(),
                        "processed_by": processed_by
                    }
                else:
                    cur = utasks.get(tid, {}) or {}
                    if cur.get("status") != "processed":
                        changed += 1
                    utasks[tid] = {
                        **cur,
                        "status": "processed",
                        "processed_at": now_unix(),
                        "processed_by": processed_by
                    }

            self._save_ledger(data)
            return changed

    async def mark_tasks_pending(self, guild: discord.Guild, owner_uid: str, task_ids: List[str]) -> int:
        if not task_ids:
            return 0

        async with self._lock:
            data = self._load_ledger()
            utasks = self._get_user_task_entry(data, owner_uid)
            gtasks = self._get_global_tasks(data)

            changed = 0
            for tid in task_ids:
                if tid.startswith("votw:"):
                    cur = gtasks.get(tid, {}) or {}
                    if cur.get("status") == "processed":
                        changed += 1
                    cur["status"] = "pending"
                    gtasks[tid] = cur
                else:
                    cur = utasks.get(tid, {}) or {}
                    if cur.get("status") == "processed":
                        changed += 1
                    cur["status"] = "pending"
                    utasks[tid] = cur

            self._save_ledger(data)
            return changed


    @app_commands.command(name="processinbox", description="Admin: view pending tasks grouped by user (put-through inbox).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def process_inbox(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            return await interaction.followup.send("Run this in a server.", ephemeral=True)

        view = ProcessInboxView(self, actor_id=interaction.user.id)
        await view._refresh_rows(interaction.guild)
        view._rebuild_children(interaction.guild)
        embed = await view._make_embed(interaction.guild)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="processuser", description="Admin: process a specific user's tasks.")
    @app_commands.describe(scope="Filter category", show="pending or all")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def process_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        scope: Scope = "all",
        show: Show = "pending"
    ):
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            return await interaction.followup.send("Run this in a server.", ephemeral=True)

        view = ProcessUserView(self, actor_id=interaction.user.id, target=user, scope=scope, show=show)
        await view.refresh()
        await interaction.followup.send(embed=await view.make_embed(), view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Processing(bot))
