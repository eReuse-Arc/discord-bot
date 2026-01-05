from constants import FIRST_CHALLENGE_ROLE, THREE_STREAK_ROLE, FIVE_STREAK_ROLE, TEN_CHALLENGES_ROLE, BOT_REACTIONS_ROLE, TEN_FILES, HUNDRED_MESSAGES_ROLE, FIVE_HUNDRED_MESSAGES_ROLE, VOLUNTEER_OF_WEEK

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
    }
}