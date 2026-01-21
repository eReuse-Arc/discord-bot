from pathlib import Path
import tempfile
import re

VOLUNTEER_ROLE = "Volunteer"
SENIOR_VOLUNTEER_ROLE = "Senior Volunteer"
OFFICER_ROLE = "Officer"
COORDINATOR_ROLE = "Pio 🐐"
WEEKLY_CHALLENGE_ROLE = "Weekly Challenger"
FIRST_CHALLENGE_ROLE = "First Challenger"
THREE_STREAK_ROLE = "On A Roll"
FIVE_STREAK_ROLE = "Consistency King"
TEN_CHALLENGES_ROLE = "eReuse Legend"
BOT_REACTIONS_ROLE = "eReuse Ambassador"
HUNDRED_MESSAGES_ROLE = "Chatterbox"
FIVE_HUNDRED_MESSAGES_ROLE = "Yapper"
FIVE_THOUSAND_MESSAGES_ROLE = "Can't Stop Talking"
TEN_FILES = "Photographer"
VOLUNTEER_OF_WEEK = "Volunteer of the Week Winner"
FIRST_VOTER = "First Voter"
FIVE_VOTER = "Civic Duty"
TWELVE_VOTER = "Democracy Enjoyer"
TWENTY_FIVE_VOTER = "Community Pillar"
TEN_REACTS = "Reactor"
HUNDRED_REACTS = "React Goblin"
THREE_ANNOUNCEMENT_REACTS = "Actually Paying Attention"
THIRTY_ANNOUNCMENT_REACTS = "Town Crier"
ONE_BINGO = "Bingo Beginner"
THREE_BINGO = "Card Collector"
SIX_BINGO = "eReuse Bingo Goat"
SIX_SEVEN_ACH = "Brainrot"
BINGO_IDEA_ONE = "Bingo Brainstormer"
BINGO_IDEA_FIVE = "Grid Architect"
BINGO_IDEA_FIFTEEN = "Bingo's All Knowing"
CHALLENGE_IDEA_ONE = "Idea Haver"
CHALLENGE_IDEA_TEN = "Community Think Tank"
BOT_COMMAND_TEN = "Copper Age"
BOT_COMMAND_HUNDRED = "Power User"
BOT_COMMAND_FIVE_HUNDRED =  "Automation Overlord"
UNIQUE_COMMANDS_FIVE = "Explorer"
UNIQUE_COMMANDS_TEN = "Command Engineer"
UNIQUE_COMMANDS_TWENTY = "Command Master"
UNIQUE_REACTS_TEN = "Conversation Starter"
TOTAL_REACTS_FIFTEEN = "Crowd Favourite"
REACT_USERS_TWENTY = "Connector"
FIVE_VOTW_VOTES_RECIVED = "Recognised"
ADMIN_VICTIM_ROLE = "Admin Victim"
CURIOUS_ROLE = "Curious George"
YOU_FOUND_THIS_ROLE = "You Found This"
BUTTON_SMASHER_ROLE = "Button Smasher"
USE_IT_WRONG_ROLE = "Use It Wrong"
FOOTER_READER_ROLE = "Footer Reader"
SECRET_FINDER = "Secret Finder"
MINECRAFTER = "MineCrafter"
JOINED_CALL = "Joined Call"
MARATHON_CALLER = "Marathon Caller"
STILL_TALKING = "Still Talking"
GROUP_CHAT = "Group Chat"
THE_STACK = "The Stack"
ACCIDENTAL_PODCAST = "Accidental Podcast"
WORDLE_FIRST_SOLVE = "First Wordler"
WORDLE_TWENTY_FIVE_SOLVES = "Puzzle Addict"
WORDLE_HUNDRED_SOLVES = "Daily Ritual"
WORDLE_STREAK_SEVEN = "Week Without Shame"
WORDLE_STREAK_THIRTY = "Wordle Machine"
WORDLE_BEST_THREE = "Big Brain"
WORDLE_BEST_TWO = "Sniped"
WORDLE_BEST_ONE = "Oracle"
SERVER_EMOJI_TEN = "Emoji Enjoyer"
SERVER_EMOJI_HUNDRED = "Emoji Overlord"
SERVER_EMOJI_UNIQIE_FIVE = "Emoji Explorer"
SERVER_EMOJI_UNIQIE_TWENTY = "Emoji Connoisseur"
SERVER_EMOJI_ALL = "Archivist"




ADMIN_ROLES = [OFFICER_ROLE, SENIOR_VOLUNTEER_ROLE, COORDINATOR_ROLE]

IMAGE_OUTPUT_DIR = Path(tempfile.gettempdir()) / "discord-bot"

CHALLENGE_PATH = "data/challenges.json"
CHALLENGE_SUGGESTIONS_PATH = "data/challenge_suggestions.json"
CHALLENGE_POINTS_PATH = "data/challenge_points.json"
ACHEIVEMENTS_PATH = "data/challenge_achievements.json"
USER_STATS_PATH = "data/user_stats.json"
VOLUNTEER_OF_THE_WEEK_PATH = "data/volunteer_of_the_week.json"
VOLUNTEER_VOTES_PATH ="data/volunteer_votes.json"
BINGO_CARDS_PATH = "data/bingo_cards.json"
BINGO_PROGRESS_PATH = "data/bingo_progress.json"
BINGO_SUGGESTIONS_PATH = "data/bingo_suggestions.json"
MINECRAFT_LINKS_PATH = "data/minecraft_links.json"
WORDLE_STATS_PATH = "data/wordle.json"
COLLECTIBLES_PATH = "data/collectibles.json"
OWNERSHIP_PATH = "data/ownership.json"


MEMBER = "member"
USER_ID = "user_id"
WEEKS = "weeks"
TOTAL_CHALLENGES = "total_challenges"
CURRENT_STREAK = "current_streak"
LONGEST_STREAK = "longest_streak"
MESSAGES = "messages"
FILES = "files"
EREUSE_REACTS = "ereuse_reacts"
VOTW_WINS = "votw_wins"
VOTW_VOTES_CAST = "votw_votes_cast"
VOTW_VOTES_RECIEVED = "votes_received"
REACTIONS_GIVEN = "reactions_given"
ANNOUNCEMENT_REACTS = "announcement_reacts"
BINGOS_COMPLETE = "bingos_complete"
BINGO_CARDS = "bingo_cards"
SIX_SEVEN = "six_seven"
COMMANDS_USED = "commands_used"
UNIQUE_COMMANDS = "unique_commands"
COMMAND_USAGE = "command_usage"
BINGO_SUGGESTIONS = "bingo_suggestions"
CHALLENGE_SUGGESTIONS = "challenge_suggestions"
MAX_UNIQUE_REACTORS = "max_unique_reactors"
MAX_REACTIONS_ON_MESSAGE = "max_reactions_on_message"
REACTED_USERS = "reacted_users"
UNIQUE_USERS_REACTED_TO ="unique_users_reacted_to"
ADMIN_VICTIM = "admin_victim"
CURIOUS_WINDOW_OK = "curious_window_ok"
LAST_PROFILE_AT = "last_profile_at"
LAST_COMPARE_AT = "last_compare_at"
LAST_SERVERSTATS_AT = "last_serverstats_at"
YOU_FOUND_THIS = "you_found_this"
BUTTON_SMASHER = "button_smasher"
USE_IT_WRONG = "use_it_wrong"
FOOTER_READER = "footer_reader"
HIDDEN_ACHIEVEMENTS_COUNT = "hidden_achievement_count"
LINKED_MINECRAFT = "linked_minecraft"
VOICE_MINUTES = "voice_minutes"
VOICE_SESSION_MAX = "voice_session_max"
VOICE_3P_MINUTES = "voice_3p_minutes"
VOICE_5P_MINUTES = "voice_5p_minutes"
WORDLE_BEST_TURN = "wordle_best_turn"
WORDLE_BEST_STREAK = "wordle_best_streak"
WORDLE_TOTAL_SOLVED = "wordle_total_solved"
SERVER_EMOJIS_USED = "server_emojis_used"
UNIQUE_SERVER_EMOJIS = "unique_server_emojis"
EMOJI_ARCHIVIST = "emoji_archivist"


CHALLENGE_CHANNEL_ID = 1457312927395741797
BINGO_CHANNEL_ID = 1457313011776880814
MODERATOR_ONLY_CHANNEL_ID = 1446586140034470091
GENERAL_CHANNEL_ID = 1446585422305169610
ANNOUNCEMENT_CHANNEL_ID = 1446590797142298872
MINECRAFT_SERVER_CHANNEL_ID = 1460242818378236076
WORDLE_CHANNEL_ID = 1457392521901506774
ACHIEVEMENT_UNLOCKS_CHANNEL_ID = 1463421553285927138
SALVAGE_CHANNEL_ID = 1463507407463256098


WORDLE_BOT_ID = 1211781489931452447

MINECRAFT_SERVER_STATUS_MESSAGE_ID = 1460245150243754004

CURIOUS_WINDOW_SECONDS = 60 * 60 # 1 hour
RATE_LIMIT_SECONDS = 60


CUSTOM_EMOJI_REGEX = re.compile(r"<a?:\w+:(\d+)>")



SPAWN_CHANCE = 0.02
SPAWN_EXPIRE_SECONDS = 150
SPAWN_COOLDOWN_MIN = 180
SPAWN_COOLDOWN_MAX = 300

HINT_COOLDOWN_SECONDS = 30
MAX_HINTS_PER_SPAWN = 3

RARITY_ORDER = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]
RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟡",
}

RARITY_WEIGHTS = [
    ("Legendary", 1),
    ("Epic", 4),
    ("Rare", 12),
    ("Uncommon", 28),
    ("Common", 55),
]

VARIANT_WEIGHTS = [
    ("Normal", 970),
    ("Vintage", 20),
    ("Cursed", 8),
    ("Prototype", 1),
    ("Pristine", 1),
]
VARIANT_EMOJI = {
    "Normal": "",
    "Pristine": "✨",
    "Cursed": "🕷️",
    "Prototype": "🧪",
    "Vintage": "📼",
}