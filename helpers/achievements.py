from constants import *

ACHIEVEMENTS = {
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
        "progress": lambda ctx: min(ctx[REACTIONS_GIVEN], 3),
        "max": 3
    },
    THIRTY_ANNOUNCMENT_REACTS: {
        "name": "Town Crier 🗣️",
        "description": "React to thirty different announcements",
        "role": THIRTY_ANNOUNCMENT_REACTS,
        "check": lambda ctx: ctx[ANNOUNCEMENT_REACTS] >= 30,
        "progress": lambda ctx: min(ctx[REACTIONS_GIVEN], 30),
        "max": 30
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
        "name": "Braintrot 💩",
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
    }
}