from constants import *
import json
from pathlib import Path
import discord

ACH_FILE = Path(ACHEIVEMENTS_PATH)

def rarity_style(percent: float) -> tuple[str, str]:
    if percent <= 5:
        return "💎", "&d"
    if percent <= 15:
        return "🔥", "&6"
    if percent <= 40:
        return "⭐", "&e"
    return "✅", "&a"

async def achievement_percentage(achievement_key: str, guild: discord.Guild) -> float:
        data = json.loads(ACH_FILE.read_text())

        if not data:
            return 0.0

        total_users = guild.member_count
        if total_users == 0:
            return 0.0

        earned_count = sum(1 for achievements in data.values() if achievement_key in achievements)

        return round((earned_count / total_users) * 100.0, 1)

async def get_user_achievements(user_id: int, guild) -> list[str]:
    if not ACH_FILE.exists():
        return []

    try:
        data = json.loads(ACH_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    raw = data.get(str(user_id), {})

    if isinstance(raw, dict):
        keys = [str(k) for k in raw.keys()]
    elif isinstance(raw, list):
        keys = [str(k) for k in raw]
    else:
        keys = []

    achievements: list[str] = []
    for ach_key in keys:
        percent = await achievement_percentage(ach_key, guild)
        emoji, _ = rarity_style(percent)
        achievements.append(f"{emoji} {ach_key}")

    return achievements


class AchievementSearchModal(discord.ui.Modal):
    def __init__(self, parent_view: "AchievementView"):
        super().__init__(title="Search your achievements")
        self.parent_view = parent_view
        self.query = discord.ui.TextInput(
            label="Search",
            placeholder="e.g. reactor, wordle, (leave empty to clear)",
            required=False,
            max_length=50
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        q = str(self.query.value or "").strip()
        self.parent_view.set_filter_for(interaction.user.id, q)
        self.parent_view.refresh_select_options()
        await interaction.response.edit_message(view=self.parent_view)


class AchievementSelect(discord.ui.Select):
    def __init__(self, parent_view: "AchievementView"):
        self.parent_view = parent_view
        self.viewer_id = parent_view.viewer_id

        super().__init__(
            placeholder="Choose an achievement to display",
            options=[discord.SelectOption(label="Loading…", value="__loading__")],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message(
                "❌ This is not your achievements to select from.",
                ephemeral=True
            )
            return

        chosen = self.values[0]

        if chosen in {"__loading__", "__no_matches__"}:
            await interaction.response.send_message(
                "⚠️ Use **Search** or **Clear** first.",
                ephemeral=True
            )
            return

        cog = interaction.client.get_cog("Minecraft")
        await cog.apply_suffix(interaction, chosen)



class AchievementView(discord.ui.View):
    def __init__(self, achievements: list[str], viewer_id: int):
        super().__init__(timeout=120)
        self.viewer_id = viewer_id

        self._all: list[str] = list(achievements) 
        self._filter_by_user: dict[int, str] = {}

        self.select = AchievementSelect(self)
        self.add_item(self.select)

        self.refresh_select_options()

    def set_filter_for(self, user_id: int, query: str):
        self._filter_by_user[user_id] = (query or "").strip()

    def _get_filter_for(self, user_id: int) -> str:
        return (self._filter_by_user.get(user_id) or "").strip()

    def _filtered(self) -> list[str]:
        q = self._get_filter_for(self.viewer_id).lower()
        items = self._all

        if q:
            items = [a for a in items if q in a.lower()]

        return items[:25]

    def refresh_select_options(self):
        items = self._filtered()
        q = self._get_filter_for(self.viewer_id)

        if not items:
            self.select.options = [
                discord.SelectOption(
                    label="No matches (clear search)",
                    value="__no_matches__",
                    description="Use Clear to reset filter"
                )
            ]
            self.select.placeholder = "No matching achievements"
            self.select.disabled = True
            return

        self.select.disabled = False
        self.select.placeholder = f"Filtered: {q}" if q else "Choose an achievement to display"

        opts: list[discord.SelectOption] = []
        for a in items:
            opts.append(discord.SelectOption(label=a[:100], value=a))
        self.select.options = opts

    @discord.ui.button(label="🔎 Search", style=discord.ButtonStyle.secondary)
    async def search_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("❌ This menu isn't yours.", ephemeral=True)
            return
        await interaction.response.send_modal(AchievementSearchModal(self))

    @discord.ui.button(label="🧹 Clear", style=discord.ButtonStyle.secondary)
    async def clear_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if interaction.user.id != self.viewer_id:
            await interaction.response.send_message("❌ This menu isn't yours.", ephemeral=True)
            return
        self.set_filter_for(interaction.user.id, "")
        self.refresh_select_options()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

ACHIEVEMENTS = {
    MINECRAFTER:  {
        "name": "MineCrafter 🌲",
        "description": "Link your minecraft account to the **eReuse** minecraft server using `/link`",
        "role": MINECRAFTER,
        "check": lambda ctx: ctx[LINKED_MINECRAFT] == True,
        "progress": lambda ctx: min(int(ctx[LINKED_MINECRAFT]), 1),
        "max": 1
    },
    FIRST_CHALLENGE_ROLE: {
        "name": "First Challenger ♻️",
        "description": "Complete your first challenge",
        "role": FIRST_CHALLENGE_ROLE,
        "check": lambda ctx: ctx["total_challenges"] >= 1,
        "progress": lambda ctx: min(ctx["total_challenges"], 1),
        "max": 1
    },
    THREE_STREAK_ROLE: {
        "name": "On A Roll 🔥",
        "description": "Reach a 3-week streak",
        "role": THREE_STREAK_ROLE,
        "check": lambda ctx: ctx["current_streak"] >= 3,
        "progress": lambda ctx: min(ctx["current_streak"], 3),
        "max": 3
    },
    FIVE_STREAK_ROLE: {
        "name": "Consistency King 👑",
        "description": "Reach a 5-week streak",
        "role": FIVE_STREAK_ROLE,
        "check": lambda ctx: ctx["current_streak"] >= 5,
        "progress": lambda ctx: min(ctx["current_streak"], 5),
        "max": 5
    },
    TEN_CHALLENGES_ROLE: {
        "name": "eReuse Legend 🍀",
        "description": "Complete 10 Challenges",
        "role": TEN_CHALLENGES_ROLE,
        "check": lambda ctx: ctx["total_challenges"] >= 10,
        "progress": lambda ctx: min(ctx["total_challenges"], 10),
        "max": 10
    },
    BOT_REACTIONS_ROLE: {
        "name": "eReuse Ambassador 🕴️",
        "description": "Have the eReuse bot react to your messages 25 times",
        "role": BOT_REACTIONS_ROLE,
        "check": lambda ctx: ctx["ereuse_reacts"] >= 25,
        "progress": lambda ctx: min(ctx["ereuse_reacts"], 25),
        "max": 25
    },
    TEN_FILES: {
        "name": "Photographer 📷",
        "description": "Upload 10 images or files",
        "role": TEN_FILES,
        "check": lambda ctx: ctx["files"] >= 10,
        "progress": lambda ctx: min(ctx["files"], 10),
        "max": 10
    },
    INVITE_1_ROLE: {
        "name": "First Recruit 📨",
        "description": "Get your first invite",
        "role": INVITE_1_ROLE,
        "check": lambda ctx: ctx.get(INVITES_COUNT, 0) >= 1,
        "progress": lambda ctx: min(ctx.get(INVITES_COUNT, 0), 1),
        "max": 1
    },
    INVITE_3_ROLE: {
        "name": "Bring-a-Friend 🤝",
        "description": "Reach 3 invites",
        "role": INVITE_3_ROLE,
        "check": lambda ctx: ctx.get(INVITES_COUNT, 0) >= 3,
        "progress": lambda ctx: min(ctx.get(INVITES_COUNT, 0), 3),
        "max": 3
    },
    INVITE_10_ROLE: {
        "name": "Community Builder 🏗️",
        "description": "Reach 10 invites",
        "role": INVITE_10_ROLE,
        "check": lambda ctx: ctx.get(INVITES_COUNT, 0) >= 10,
        "progress": lambda ctx: min(ctx.get(INVITES_COUNT, 0), 10),
        "max": 10
    },
    INVITE_20_ROLE: {
        "name": "Squad Assembler 🪖",
        "description": "Reach 20 invites",
        "role": INVITE_20_ROLE,
        "check": lambda ctx: ctx.get(INVITES_COUNT, 0) >= 20,
        "progress": lambda ctx: min(ctx.get(INVITES_COUNT, 0), 20),
        "max": 20
    },
    HUNDRED_MESSAGES_ROLE: {
        "name": "Chatterbox 🔉",
        "description": "Send 100 messages",
        "role": HUNDRED_MESSAGES_ROLE,
        "check": lambda ctx: ctx["messages"] >= 100,
        "progress": lambda ctx: min(ctx["messages"], 100),
        "max": 100
    },
    FIVE_HUNDRED_MESSAGES_ROLE: {
        "name": "Yapper 🔊",
        "description": "Send 500 messages",
        "role": FIVE_HUNDRED_MESSAGES_ROLE,
        "check": lambda ctx: ctx["messages"] >= 500,
        "progress": lambda ctx: min(ctx["messages"], 500),
        "max": 500
    },
    FIVE_THOUSAND_MESSAGES_ROLE: {
        "name": "Can't Stop Talking 🗣️",
        "description": "Send 5000 messages",
        "role": FIVE_THOUSAND_MESSAGES_ROLE,
        "check": lambda ctx: ctx["messages"] >= 5000,
        "progress": lambda ctx: min(ctx["messages"], 5000),
        "max": 5000
    },
    JOINED_CALL: {
        "name": "Joined Call 🎧",
        "description": "Spend 5 hours in voice call with others",
        "role": JOINED_CALL,
        "check": lambda ctx: ctx[VOICE_MINUTES] >= 5 * 60,
        "progress": lambda ctx: round(min(ctx[VOICE_MINUTES], 5 * 60) / 60, 1),
        "max": 5
    },
    MARATHON_CALLER: {
        "name": "Marathon Caller ☎️",
        "description": "Spend 20 hours in voice call with others",
        "role": MARATHON_CALLER,
        "check": lambda ctx: ctx[VOICE_MINUTES] >= 20 * 60,
        "progress": lambda ctx: round(min(ctx[VOICE_MINUTES], 20 * 60) / 60, 1),
        "max": 20
    },
    STILL_TALKING: {
        "name": "Still Talking 🙊",
        "description": "Spend 40 hours in voice call with others",
        "role": STILL_TALKING,
        "check": lambda ctx: ctx[VOICE_MINUTES] >= 40 * 60,
        "progress": lambda ctx: round(min(ctx[VOICE_MINUTES], 40 * 60) / 60, 1),
        "max": 40
    },
    GROUP_CHAT: {
        "name": "Group Chat 👥",
        "description": "Spend 5 hours in call with 3+ people",
        "role": GROUP_CHAT,
        "check": lambda ctx: ctx[VOICE_3P_MINUTES] >= 5 * 60,
        "progress": lambda ctx: round(min(ctx[VOICE_3P_MINUTES], 5 * 60) / 60, 1),
        "max": 5
    },
    THE_STACK: {
        "name": "The Stack 👯",
        "description": "Spend 5 hours in call with 5+ people",
        "role": THE_STACK,
        "check": lambda ctx: ctx[VOICE_5P_MINUTES] >= 5 * 60,
        "progress": lambda ctx: round(min(ctx[VOICE_5P_MINUTES], 5 * 60) / 60, 1),
        "max": 5
    },
    VOLUNTEER_OF_WEEK: {
        "name": "Volunteer of The Week 🐐",
        "description": "Be a volunteer of one of the weeks",
        "role": VOLUNTEER_OF_WEEK,
        "check": lambda ctx: ctx["votw_wins"] >= 1,
        "progress": lambda ctx: min(ctx["votw_wins"], 1),
        "max": 1
    },
    FIRST_VOTER: {
        "name": "First Vote 🗳️",
        "description": "Vote for someone to be the Volunteer of the Week",
        "role": FIRST_VOTER,
        "check": lambda ctx: ctx["votw_votes_cast"] >= 1,
        "progress": lambda ctx: min(ctx["votw_votes_cast"], 1),
        "max": 1
    },
    FIVE_VOTER: {
        "name": "Civic Duty 📜",
        "description": "Vote five times for someone to be the Volunteer of the Week",
        "role": FIVE_VOTER,
        "check": lambda ctx: ctx["votw_votes_cast"] >= 5,
        "progress": lambda ctx: min(ctx["votw_votes_cast"], 5),
        "max": 5
    },
    TWELVE_VOTER: {
        "name": "Democracy Enjoyer 🗄️",
        "description": "Vote twelve times for someone to be the Volunteer of the Week",
        "role": TWELVE_VOTER,
        "check": lambda ctx: ctx["votw_votes_cast"] >= 12,
        "progress": lambda ctx: min(ctx["votw_votes_cast"], 12),
        "max": 12
    },
    TWENTY_FIVE_VOTER: {
        "name": "Community Pillar 🗿",
        "description": "Vote twenty five times for someone to be the Volunteer of the Week",
        "role": TWENTY_FIVE_VOTER,
        "check": lambda ctx: ctx["votw_votes_cast"] >= 25,
        "progress": lambda ctx: min(ctx["votw_votes_cast"], 25),
        "max": 25
    },
    TEN_REACTS: {
        "name": "Reactor 👍",
        "description": "React ten different times",
        "role": TEN_REACTS,
        "check": lambda ctx: ctx[REACTIONS_GIVEN] >= 10,
        "progress": lambda ctx: min(ctx[REACTIONS_GIVEN], 10),
        "max": 10
    },
    HUNDRED_REACTS: {
        "name": "React Goblin 👺",
        "description": "React one hundred different times",
        "role": HUNDRED_REACTS,
        "check": lambda ctx: ctx[REACTIONS_GIVEN] >= 100,
        "progress": lambda ctx: min(ctx[REACTIONS_GIVEN], 100),
        "max": 100
    },
    THREE_ANNOUNCEMENT_REACTS: {
        "name": "Actually Paying Attention 🤓",
        "description": "React to three different announcements",
        "role": THREE_ANNOUNCEMENT_REACTS,
        "check": lambda ctx: ctx[ANNOUNCEMENT_REACTS] >= 3,
        "progress": lambda ctx: min(ctx[ANNOUNCEMENT_REACTS], 3),
        "max": 3
    },
    THIRTY_ANNOUNCMENT_REACTS: {
        "name": "Town Crier 🗣️",
        "description": "React to thirty different announcements",
        "role": THIRTY_ANNOUNCMENT_REACTS,
        "check": lambda ctx: ctx[ANNOUNCEMENT_REACTS] >= 30,
        "progress": lambda ctx: min(ctx[ANNOUNCEMENT_REACTS], 30),
        "max": 30
    },
    SERVER_EMOJI_TEN: {
        "name": "Emoji Enjoyer 😄",
        "description": "Use 10 eReuse server emojis",
        "role": SERVER_EMOJI_TEN,
        "check": lambda ctx: ctx[SERVER_EMOJIS_USED] >= 10,
        "progress": lambda ctx: min(ctx[SERVER_EMOJIS_USED], 10),
        "max": 10
    },
    SERVER_EMOJI_HUNDRED: {
        "name": "Emoji Overlord 👑",
        "description": "Use 100 eReuse server emojis",
        "role": SERVER_EMOJI_HUNDRED,
        "check": lambda ctx: ctx[SERVER_EMOJIS_USED] >= 100,
        "progress": lambda ctx: min(ctx[SERVER_EMOJIS_USED], 100),
        "max": 100
    },
    SERVER_EMOJI_UNIQIE_FIVE: {
        "name": "Emoji Explorer 🧭",
        "description": "Use 5 unique eReuse server emojis",
        "role": SERVER_EMOJI_UNIQIE_FIVE,
        "check": lambda ctx: ctx[UNIQUE_SERVER_EMOJIS] >= 5,
        "progress": lambda ctx: min(ctx[UNIQUE_SERVER_EMOJIS], 5),
        "max": 5
    },
    SERVER_EMOJI_UNIQIE_TWENTY: {
        "name": "Emoji Connoisseur ♻️",
        "description": "Use 20 unique eReuse server emojis",
        "role": SERVER_EMOJI_UNIQIE_TWENTY,
        "check": lambda ctx: ctx[UNIQUE_SERVER_EMOJIS] >= 20,
        "progress": lambda ctx: min(ctx[UNIQUE_SERVER_EMOJIS], 20),
        "max": 20
    },
    ONE_BINGO: {
        "name": "Bingo Beginner 🎟️",
        "description": "Complete one bingo card",
        "role": ONE_BINGO,
        "check": lambda ctx: ctx[BINGOS_COMPLETE] >= 1,
        "progress": lambda ctx: min(ctx[BINGOS_COMPLETE], 1),
        "max": 1
    },
    THREE_BINGO: {
        "name": "Card Collector 🗂️",
        "description": "Complete three bingo cards",
        "role": THREE_BINGO,
        "check": lambda ctx: ctx[BINGOS_COMPLETE] >= 3,
        "progress": lambda ctx: min(ctx[BINGOS_COMPLETE], 3),
        "max": 3
    },
    SIX_BINGO: {
        "name": "eReuse Bingo Goat 🐐",
        "description": "Complete six bingo cards",
        "role": SIX_BINGO,
        "check": lambda ctx: ctx[BINGOS_COMPLETE] >= 6,
        "progress": lambda ctx: min(ctx[BINGOS_COMPLETE], 6),
        "max": 6
    },
    SIX_SEVEN_ACH: {
        "name": "Brainrot 💩",
        "description": "Say an unspecified number an unspecified number of times",
        "role": SIX_SEVEN_ACH,
        "check": lambda ctx: ctx[SIX_SEVEN] >= 67,
        "progress": lambda ctx: min(ctx[SIX_SEVEN], 67),
        "max": 67
    },
    BINGO_IDEA_ONE: {
        "name": "Bingo Brainstormer 🧠",
        "description": "Suggest one bingo tile",
        "role": BINGO_IDEA_ONE,
        "check": lambda ctx: ctx[BINGO_SUGGESTIONS] >= 1,
        "progress": lambda ctx: min(ctx[BINGO_SUGGESTIONS], 1),
        "max": 1
    },
    BINGO_IDEA_FIVE: {
        "name": "Grid Architect 🔨",
        "description": "Suggest five bingo tiles",
        "role": BINGO_IDEA_FIVE,
        "check": lambda ctx: ctx[BINGO_SUGGESTIONS] >= 5,
        "progress": lambda ctx: min(ctx[BINGO_SUGGESTIONS], 5),
        "max": 5
    },
    BINGO_IDEA_FIFTEEN: {
        "name": "Bingo's All Knowing 🤓",
        "description": "Suggest fifteen bingo tiles",
        "role": BINGO_IDEA_FIFTEEN,
        "check": lambda ctx: ctx[BINGO_SUGGESTIONS] >= 15,
        "progress": lambda ctx: min(ctx[BINGO_SUGGESTIONS], 15),
        "max": 15
    },
    CHALLENGE_IDEA_ONE: {
        "name": "Idea Haver 💡",
        "description": "Suggest one weekly challenge",
        "role": CHALLENGE_IDEA_ONE,
        "check": lambda ctx: ctx[CHALLENGE_SUGGESTIONS] >= 1,
        "progress": lambda ctx: min(ctx[CHALLENGE_SUGGESTIONS], 1),
        "max": 1
    },
    CHALLENGE_IDEA_TEN: {
        "name": "Community Think Tank 🤔",
        "description": "Suggest ten weekly challenge",
        "role": CHALLENGE_IDEA_TEN,
        "check": lambda ctx: ctx[CHALLENGE_SUGGESTIONS] >= 10,
        "progress": lambda ctx: min(ctx[CHALLENGE_SUGGESTIONS], 10),
        "max": 10
    },
    BOT_COMMAND_TEN: {
        "name": "Copper Age ⚡",
        "description": "Use the **eReuse** Bot 10 times",
        "role": BOT_COMMAND_TEN,
        "check": lambda ctx: ctx[COMMANDS_USED] >= 10,
        "progress": lambda ctx: min(ctx[COMMANDS_USED], 10),
        "max": 10
    },
    BOT_COMMAND_HUNDRED: {
        "name": "Power User 🔌",
        "description": "Use the **eReuse** Bot 100 times",
        "role": BOT_COMMAND_HUNDRED,
        "check": lambda ctx: ctx[COMMANDS_USED] >= 100,
        "progress": lambda ctx: min(ctx[COMMANDS_USED], 100),
        "max": 100
    },
    BOT_COMMAND_FIVE_HUNDRED: {
        "name": "Automation Overlord 🤖",
        "description": "Use the **eReuse** Bot 500 times",
        "role": BOT_COMMAND_FIVE_HUNDRED,
        "check": lambda ctx: ctx[COMMANDS_USED] >= 500,
        "progress": lambda ctx: min(ctx[COMMANDS_USED], 500),
        "max": 500
    },
    UNIQUE_COMMANDS_FIVE: {
        "name": "Explorer 🤠",
        "description": "Use five unique commands on the **eReuse** Bot",
        "role": UNIQUE_COMMANDS_FIVE,
        "check": lambda ctx: ctx[UNIQUE_COMMANDS] >= 5,
        "progress": lambda ctx: min(ctx[UNIQUE_COMMANDS], 5),
        "max": 5
    },
    UNIQUE_COMMANDS_TEN: {
        "name": "Command Engineer 👷",
        "description": "Use ten unique commands on the **eReuse** Bot",
        "role": UNIQUE_COMMANDS_TEN,
        "check": lambda ctx: ctx[UNIQUE_COMMANDS] >= 10,
        "progress": lambda ctx: min(ctx[UNIQUE_COMMANDS], 10),
        "max": 10
    },
    UNIQUE_COMMANDS_TWENTY: {
        "name": "Command Master 🥷",
        "description": "Use twenty unique commands on the **eReuse** Bot",
        "role": UNIQUE_COMMANDS_TWENTY,
        "check": lambda ctx: ctx[UNIQUE_COMMANDS] >= 20,
        "progress": lambda ctx: min(ctx[UNIQUE_COMMANDS], 20),
        "max": 20
    },
    UNIQUE_REACTS_TEN: {
        "name": "Conversation Starter 🗣️",
        "description": "Recieve a reaction from ten unique people on a single post",
        "role": UNIQUE_REACTS_TEN,
        "check": lambda ctx: ctx[MAX_UNIQUE_REACTORS] >= 10,
        "progress": lambda ctx: min(ctx[MAX_UNIQUE_REACTORS], 10),
        "max": 10
    },
    TOTAL_REACTS_FIFTEEN: {
        "name": "Crowd Favourite 🌟",
        "description": "Recieve fifteen reactions on a single post",
        "role": TOTAL_REACTS_FIFTEEN,
        "check": lambda ctx: ctx[MAX_REACTIONS_ON_MESSAGE] >= 15,
        "progress": lambda ctx: min(ctx[MAX_REACTIONS_ON_MESSAGE], 15),
        "max": 15
    },
    REACT_USERS_TWENTY: {
        "name": "Connector 🔗",
        "description": "React to 20 unique users",
        "role": REACT_USERS_TWENTY,
        "check": lambda ctx: ctx[UNIQUE_USERS_REACTED_TO] >= 20,
        "progress": lambda ctx: min(ctx[UNIQUE_USERS_REACTED_TO], 20),
        "max": 20
    },
    FIVE_VOTW_VOTES_RECIVED: {
        "name": "Recognised 🎖️",
        "description": "Recieve five volunteer of the week votes",
        "role": FIVE_VOTW_VOTES_RECIVED,
        "check": lambda ctx: ctx[VOTW_VOTES_RECIEVED] >= 5,
        "progress": lambda ctx: min(ctx[VOTW_VOTES_RECIEVED], 5),
        "max": 5
    },
    ADMIN_VICTIM_ROLE: {
        "name": "Admin Victim 💥",
        "description": "Have an admin take away one of your bingo tiles or weekly challenges",
        "role": ADMIN_VICTIM_ROLE,
        "check": lambda ctx: ctx[ADMIN_VICTIM] == True,
        "progress": lambda ctx: min(int(ctx[ADMIN_VICTIM]), 1),
        "max": 1
    },
    WORDLE_FIRST_SOLVE: {
        "name": "First Wordler 🟩",
        "description": "Solve your first Wordle",
        "role": WORDLE_FIRST_SOLVE,
        "check": lambda ctx: ctx[WORDLE_TOTAL_SOLVED] >= 1,
        "progress": lambda ctx: min(ctx[WORDLE_TOTAL_SOLVED], 1),
        "max": 1
    },
    WORDLE_TWENTY_FIVE_SOLVES: {
        "name": "Puzzle Addict 🧩",
        "description": "Solve 25 Wordles",
        "role": WORDLE_TWENTY_FIVE_SOLVES,
        "check": lambda ctx: ctx[WORDLE_TOTAL_SOLVED] >= 25,
        "progress": lambda ctx: min(ctx[WORDLE_TOTAL_SOLVED], 25),
        "max": 25
    },
    WORDLE_HUNDRED_SOLVES: {
        "name": "Daily Ritual ☕",
        "description": "Solve 100 Wordles",
        "role": WORDLE_HUNDRED_SOLVES,
        "check": lambda ctx: ctx[WORDLE_TOTAL_SOLVED] >= 100,
        "progress": lambda ctx: min(ctx[WORDLE_TOTAL_SOLVED], 100),
        "max": 100
    },
    WORDLE_STREAK_SEVEN: {
        "name": "Week Without Shame 🗓️",
        "description": "Reach a 7-day Wordle streak",
        "role": WORDLE_STREAK_SEVEN,
        "check": lambda ctx: ctx[WORDLE_BEST_STREAK] >= 7,
        "progress": lambda ctx: min(ctx[WORDLE_BEST_STREAK], 7),
        "max": 7
    },
    WORDLE_STREAK_THIRTY: {
        "name": "Wordle Machine 🤖",
        "description": "Reach a 30-day Wordle streak",
        "role": WORDLE_STREAK_THIRTY,
        "check": lambda ctx: ctx[WORDLE_BEST_STREAK] >= 30,
        "progress": lambda ctx: min(ctx[WORDLE_BEST_STREAK], 30),
        "max": 30
    },
    WORDLE_BEST_THREE: {
        "name": "Big Brain 🧠",
        "description": "Solve a Wordle in 3 guesses or less",
        "role": WORDLE_BEST_THREE,
        "check": lambda ctx: (ctx[WORDLE_BEST_TURN] is not None) and (ctx[WORDLE_BEST_TURN] <= 3),
        "progress": lambda ctx: 1 if ((ctx[WORDLE_BEST_TURN] is not None) and (ctx[WORDLE_BEST_TURN] <= 3)) else 0,
        "max": 1
    },
    MAKE_TEN_FIRST_SOLVE_ROLE: {
        "name": "First Tenner 🧮",
        "description": "Solve your first Make Ten",
        "role": MAKE_TEN_FIRST_SOLVE_ROLE,
        "check": lambda ctx: ctx[MAKE_TEN_TOTAL_SOLVED] >= 1,
        "progress": lambda ctx: min(ctx[MAKE_TEN_TOTAL_SOLVED], 1),
        "max": 1
    },

    MAKE_TEN_TWENTY_FIVE_SOLVES_ROLE: {
        "name": "Arithmetic Addict 🔢",
        "description": "Solve 25 Make Ten puzzles",
        "role": MAKE_TEN_TWENTY_FIVE_SOLVES_ROLE,
        "check": lambda ctx: ctx[MAKE_TEN_TOTAL_SOLVED] >= 25,
        "progress": lambda ctx: min(ctx[MAKE_TEN_TOTAL_SOLVED], 25),
        "max": 25
    },

    MAKE_TEN_HUNDRED_SOLVES_ROLE: {
        "name": "Ten Toes Down 💯",
        "description": "Solve 100 Make Ten puzzles",
        "role": MAKE_TEN_HUNDRED_SOLVES_ROLE,
        "check": lambda ctx: ctx[MAKE_TEN_TOTAL_SOLVED] >= 100,
        "progress": lambda ctx: min(ctx[MAKE_TEN_TOTAL_SOLVED], 100),
        "max": 100
    },

    MAKE_TEN_STREAK_SEVEN_ROLE: {
        "name": "Week Of Tens 🗓️",
        "description": "Reach a 7-day Make Ten streak",
        "role": MAKE_TEN_STREAK_SEVEN_ROLE,
        "check": lambda ctx: ctx[MAKE_TEN_BEST_STREAK] >= 7,
        "progress": lambda ctx: min(ctx[MAKE_TEN_BEST_STREAK], 7),
        "max": 7
    },

    MAKE_TEN_STREAK_THIRTY_ROLE: {
        "name": "Human Calculator 🤖",
        "description": "Reach a 30-day Make Ten streak",
        "role": MAKE_TEN_STREAK_THIRTY_ROLE,
        "check": lambda ctx: ctx[MAKE_TEN_BEST_STREAK] >= 30,
        "progress": lambda ctx: min(ctx[MAKE_TEN_BEST_STREAK], 30),
        "max": 30
    },

    MAKE_TEN_EARLY_BIRD_ROLE: {
        "name": "Early Bird 🐦",
        "description": "Solve within 15 minutes of the daily post (5 times)",
        "role": MAKE_TEN_EARLY_BIRD_ROLE,
        "check": lambda ctx: ctx.get(MAKE_TEN_EARLY_BIRD_SOLVES, 0) >= 5,
        "progress": lambda ctx: min(ctx.get(MAKE_TEN_EARLY_BIRD_SOLVES, 0), 5),
        "max": 5
    },
    MAKE_TEN_SPEEDRUNNER_ROLE: {
        "name": "Speedrunner ⚡",
        "description": "Get a fastest solve time of 90 seconds or less",
        "role": MAKE_TEN_SPEEDRUNNER_ROLE,
        "check": lambda ctx: (ctx.get(MAKE_TEN_TOTAL_SOLVED, 0) >= 1)
                  and (ctx.get(MAKE_TEN_FASTEST_SOLVE_SECONDS) is not None)
                  and (ctx[MAKE_TEN_FASTEST_SOLVE_SECONDS] <= 90),
        "progress": lambda ctx: 1 if ((ctx.get(MAKE_TEN_FASTEST_SOLVE_SECONDS) is not None) and (ctx[MAKE_TEN_FASTEST_SOLVE_SECONDS] <= 90)) else 0,
        "max": 1
    },
    SALVAGE_1_ROLE: {
        "name": "First Time Salvager ⛏️",
        "description": "Catch 1 salvage",
        "role": SALVAGE_1_ROLE,
        "check": lambda ctx: ctx[SALVAGE_SPAWN_CAUGHT] >= 1,
        "progress": lambda ctx: min(ctx[SALVAGE_SPAWN_CAUGHT], 1),
        "max": 1,
    },
    SALVAGE_50_ROLE: {
        "name": "Workshop Regular 🔧",
        "description": "Catch 50 salvages",
        "role": SALVAGE_50_ROLE,
        "check": lambda ctx: ctx[SALVAGE_SPAWN_CAUGHT] >= 50,
        "progress": lambda ctx: min(ctx[SALVAGE_SPAWN_CAUGHT], 50),
        "max": 50,
    },
    SALVAGE_200_ROLE: {
        "name": "Salvage Fein 🤑",
        "description": "Catch 200 salvages",
        "role": SALVAGE_200_ROLE,
        "check": lambda ctx: ctx[SALVAGE_SPAWN_CAUGHT] >= 200,
        "progress": lambda ctx: min(ctx[SALVAGE_SPAWN_CAUGHT], 200),
        "max": 200,
    },
    SALVAGE_GIFT_10_ROLE: {
        "name": "Generous Gifter 🎁",
        "description": "Send 10 salvage gifts",
        "role": SALVAGE_GIFT_10_ROLE,
        "check": lambda ctx: ctx[SALVAGE_GIFTS_SENT] >= 10,
        "progress": lambda ctx: min(ctx[SALVAGE_GIFTS_SENT], 10),
        "max": 10,
    },
    SALVAGE_TRADE_10_ROLE: {
        "name": "Market Trader 💱",
        "description": "Complete 10 salvage trades",
        "role": SALVAGE_TRADE_10_ROLE,
        "check": lambda ctx: ctx[SALVAGE_TRADES] >= 10,
        "progress": lambda ctx: min(ctx[SALVAGE_TRADES], 10),
        "max": 10,
    },
    SALVAGE_EPIC_ROLE: {
        "name": "Certified Salvager ♻️",
        "description": "Obtain an Epic salvage item",
        "role": SALVAGE_EPIC_ROLE,
        "check": lambda ctx: ctx[SALVAGE_EPIC_TOTAL] >= 1,
        "progress": lambda ctx: min(ctx[SALVAGE_EPIC_TOTAL], 1),
        "max": 1,
    },
    SALVAGE_LEGEND_ROLE: {
        "name": "Mythic Refurbisher 🛠️",
        "description": "Obtain a Legendary salvage item",
        "role": SALVAGE_LEGEND_ROLE,
        "check": lambda ctx: ctx[SALVAGE_LEGENDARY_TOTAL] >= 1,
        "progress": lambda ctx: min(ctx[SALVAGE_LEGENDARY_TOTAL], 1),
        "max": 1,
    },
    SALVAGE_ALL_RARITIES_ROLE: {
        "name": "Rarity Completionist 💎",
        "description": "Unlock every rarity at least once",
        "role": SALVAGE_ALL_RARITIES_ROLE,
        "check": lambda ctx: ctx["salvage_all_rarities"],
        "progress": lambda ctx: min(ctx["salvage_unique_rarities_count"], len(RARITY_ORDER)),
        "max": len(RARITY_ORDER),
    },
    SALVAGE_RARE_50K_ROLE: {
        "name": "Lottery Find 🎟️",
        "description": "Obtain an item with odds of 1 in 50,000 or rarer",
        "role": SALVAGE_RARE_50K_ROLE,
        "check": lambda ctx: ctx[SALVAGE_RARE_50K_TOTAL] >= 1,
        "progress": lambda ctx: min(ctx[SALVAGE_RARE_50K_TOTAL], 1),
        "max": 1,
    },
    SALVAGE_RARE_1M_ROLE: {
        "name": "Once-In-A-Million Pull 🌟",
        "description": "Obtain an item with odds of 1 in 1,000,000 or rarer",
        "role": SALVAGE_RARE_1M_ROLE,
        "check": lambda ctx: ctx[SALVAGE_RARE_1M_TOTAL] >= 1,
        "progress": lambda ctx: min(ctx[SALVAGE_RARE_1M_TOTAL], 1),
        "max": 1,
    },
    SALVAGE_ALT_VARIANT_ROLE: {
        "name": "Not Stock ✨",
        "description": "Obtain a salvage with a non-Normal variant",
        "role": SALVAGE_ALT_VARIANT_ROLE,
        "check": lambda ctx: ctx[SALVAGE_ALT_VARIANT],
        "progress": lambda ctx: 1 if ctx[SALVAGE_ALT_VARIANT] else 0,
        "max": 1,
    },
    SALVAGE_3_VARIANTS_ROLE: {
        "name": "Variant Dabbler 🎨",
        "description": "Unlock 3 different variants",
        "role": SALVAGE_3_VARIANTS_ROLE,
        "check": lambda ctx: ctx[SALVAGE_UNIQUE_VARIANTS_COUNT] >= 3,
        "progress": lambda ctx: min(ctx[SALVAGE_UNIQUE_VARIANTS_COUNT], 3),
        "max": 3,
    },
    SALVAGE_ALL_VARIANTS_ROLE: {
        "name": "Variant Collector 🎨",
        "description": "Unlock every variant at least once",
        "role": SALVAGE_ALL_VARIANTS_ROLE,
        "check": lambda ctx: ctx["salvage_all_variants"],
        "progress": lambda ctx: min(ctx["salvage_unique_variants_count"], len({v for v, _w in VARIANT_WEIGHTS})),
        "max": len({v for v, _w in VARIANT_WEIGHTS}),
    },
    SECRET_FINDER: {
        "name": "Secret Finder 🕵️",
        "description": "Unlock 5 hidden achievements",
        "role": SECRET_FINDER,
        "check": lambda ctx: ctx[HIDDEN_ACHIEVEMENTS_COUNT] >= 5,
        "progress": lambda ctx: min(ctx[HIDDEN_ACHIEVEMENTS_COUNT],51),
        "max": 5
    },
    MEME_1_ROLE: {
        "name": "Meme Dropper 📸",
        "description": "Post 1 meme in #memes",
        "role": MEME_1_ROLE,
        "check": lambda ctx: ctx.get(MEMES_POSTED, 0) >= 1,
        "progress": lambda ctx: min(ctx.get(MEMES_POSTED, 0), 1),
        "max": 1
    },
    MEME_5_ROLE: {
        "name": "Lowkey Funny 😼",
        "description": "Post 5 memes in #memes",
        "role": MEME_5_ROLE,
        "check": lambda ctx: ctx.get(MEMES_POSTED, 0) >= 5,
        "progress": lambda ctx: min(ctx.get(MEMES_POSTED, 0), 5),
        "max": 5
    },
    MEME_25_ROLE: {
        "name": "Certified Poster ✅",
        "description": "Post 25 memes in #memes",
        "role": MEME_25_ROLE,
        "check": lambda ctx: ctx.get(MEMES_POSTED, 0) >= 25,
        "progress": lambda ctx: min(ctx.get(MEMES_POSTED, 0), 25),
        "max": 25
    },
    MEME_100_ROLE: {
        "name": "Meme Supplier 📦",
        "description": "Post 20 memes in #memes",
        "role": MEME_100_ROLE,
        "check": lambda ctx: ctx.get(MEMES_POSTED, 0) >= 100,
        "progress": lambda ctx: min(ctx.get(MEMES_POSTED, 0), 100),
        "max": 100
    },
    BUG_HUNTER_1_ROLE: {
        "name": "Bug Spotter 🐛",
        "description": "Have 1 of your reported bugs fixed",
        "role": BUG_HUNTER_1_ROLE,
        "check": lambda ctx: ctx.get(BUGS_RESOLVED, 0) >= 1,
        "progress": lambda ctx: min(ctx.get(BUGS_RESOLVED, 0), 1),
        "max": 1
    },
    BUG_HUNTER_3_ROLE: {
        "name": "Bug Hunter 🪲",
        "description": "Have 3 of your reported bugs fixed",
        "role": BUG_HUNTER_3_ROLE,
        "check": lambda ctx: ctx.get(BUGS_RESOLVED, 0) >= 3,
        "progress": lambda ctx: min(ctx.get(BUGS_RESOLVED, 0), 3),
        "max": 3
    },
    BUG_HUNTER_10_ROLE: {
        "name": "Bug Dissolver 🧪",
        "description": "Have 10 of your reported bugs fixed",
        "role": BUG_HUNTER_10_ROLE,
        "check": lambda ctx: ctx.get(BUGS_RESOLVED, 0) >= 10,
        "progress": lambda ctx: min(ctx.get(BUGS_RESOLVED, 0), 10),
        "max": 10
    },
    CURIOUS_ROLE: {
        "name": "Curious George 🐵",
        "description": "Be extremely curious in the commands",
        "role": CURIOUS_ROLE,
        "check": lambda ctx: ctx[CURIOUS_WINDOW_OK] == True,
        "progress": lambda ctx: min(int(ctx[CURIOUS_WINDOW_OK]), 1),
        "max": 1,
        "hidden": True
    },
    YOU_FOUND_THIS_ROLE: {
        "name": "You Found This 👀",
        "description": "Find some help that the bot doesn't show",
        "role": YOU_FOUND_THIS_ROLE,
        "check": lambda ctx: ctx[YOU_FOUND_THIS] == True,
        "progress": lambda ctx: min(int(ctx[YOU_FOUND_THIS]), 1),
        "max": 1,
        "hidden": True
    },
    BUTTON_SMASHER_ROLE: {
        "name": "Button Smasher 🔘",
        "description": "Mash some buttons like your life depends on it",
        "role": BUTTON_SMASHER_ROLE,
        "check": lambda ctx: ctx[BUTTON_SMASHER] == True,
        "progress": lambda ctx: min(int(ctx[BUTTON_SMASHER]), 1),
        "max": 1,
        "hidden": True
    },
    USE_IT_WRONG_ROLE: {
        "name": "Use It Wrong 🤔",
        "description": "Some tools are meant to be misused",
        "role": USE_IT_WRONG_ROLE,
        "check": lambda ctx: ctx[USE_IT_WRONG] == True,
        "progress": lambda ctx: min(int(ctx[USE_IT_WRONG]), 1),
        "max": 1,
        "hidden": True
    },
    FOOTER_READER_ROLE: {
        "name": "Footer Reader 💚",
        "description": "Read the bots footer",
        "role": FOOTER_READER_ROLE,
        "check": lambda ctx: ctx[FOOTER_READER] == True,
        "progress": lambda ctx: min(int(ctx[FOOTER_READER]), 1),
        "max": 1,
        "hidden": True
    },
    ACCIDENTAL_PODCAST: {
        "name": "Accidental Podcast 🎙️",
        "description": "You weren't planning to be here that long...",
        "role": ACCIDENTAL_PODCAST,
        "check": lambda ctx: ctx[VOICE_SESSION_MAX] >= 4 * 60,
        "progress": lambda ctx: round(min(ctx[VOICE_SESSION_MAX], 240) / 60, 1),
        "max": 4,
        "hidden": True
    },
    WORDLE_BEST_TWO: {
        "name": "Sniped 🎯",
        "description": "Solve a Wordle in 2 guesses",
        "role": WORDLE_BEST_TWO,
        "check": lambda ctx: (ctx[WORDLE_BEST_TURN] is not None) and (ctx[WORDLE_BEST_TURN] <= 2),
        "progress": lambda ctx: 1 if ((ctx[WORDLE_BEST_TURN] is not None) and (ctx[WORDLE_BEST_TURN] <= 2)) else 0,
        "max": 1,
        "hidden": True
    },
    WORDLE_BEST_ONE: {
        "name": "Oracle 🔮",
        "description": "Solve a Wordle in 1 guess",
        "role": WORDLE_BEST_ONE,
        "check": lambda ctx: (ctx[WORDLE_BEST_TURN] is not None) and (ctx[WORDLE_BEST_TURN] <= 1),
        "progress": lambda ctx: 1 if ((ctx[WORDLE_BEST_TURN] is not None) and (ctx[WORDLE_BEST_TURN] <= 1)) else 0,
        "max": 1,
        "hidden": True
    },
    SERVER_EMOJI_ALL: {
        "name": "Emoji Connoisseur ♻️",
        "description": "Use 20 unique eReuse server emojis",
        "role": SERVER_EMOJI_ALL,
        "check": lambda ctx: ctx[EMOJI_ARCHIVIST] is True,
        "progress": lambda ctx: 1 if ctx[EMOJI_ARCHIVIST] else 0,
        "max": 1,
        "hidden": True
    },
    SALVAGE_ALL_3_DRAWS_ROLE: {
        "name": "Mutual Destruction 🤝",
        "description": "Draw all 3 rounds in a salvage battle",
        "role": SALVAGE_ALL_3_DRAWS_ROLE,
        "check": lambda ctx: ctx.get(SALVAGE_BATTLE_ALL_DRAWS, 0) >= 1,
        "progress": lambda ctx: min(ctx.get(SALVAGE_BATTLE_ALL_DRAWS, 0), 1),
        "max": 1,
        "hidden": True
    },
    "Fake_Achievement": {
        "name": "This isn't a real achievement lol",
        "description": "Ik you're looking at the code smh",
        "role": None,
        "check": lambda ctx: False,
        "progress": lambda ctx: 0,
        "max": 999999,
        "hidden": True
    }
}