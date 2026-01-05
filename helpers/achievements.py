from constants import FIRST_CHALLENGE_ROLE, THREE_STREAK_ROLE, FIVE_STREAK_ROLE, TEN_CHALLENGES_ROLE

ACHIEVEMENTS = {
    "first_challenge": {
        "name": "First Challenger ♻️",
        "description": "Complete your first challenge",
        "role": FIRST_CHALLENGE_ROLE,
        "check": lambda weeks, streak: len(weeks) >= 1,
        "progress": lambda weeks, streak: min(len(weeks), 1),
        "max": 1
    },
    "three_streak": {
        "name": "On A Roll 🔥",
        "description": "Reach a 3-week streak",
        "role": THREE_STREAK_ROLE,
        "check": lambda weeks, streak: streak >= 3,
        "progress": lambda weeks, streak: min(streak, 3),
        "max": 3
    },
    "five_streak": {
        "name": "Consistency King 👑",
        "description": "Reach a 5-week streak",
        "role": FIVE_STREAK_ROLE,
        "check": lambda weeks, streak: streak >= 5,
        "progress": lambda weeks, streak: min(streak, 5),
        "max": 5
    },
    "ten_challenges": {
        "name": "eReuse Legend 🍀",
        "description": "Complete 10 Challenges",
        "role": TEN_CHALLENGES_ROLE,
        "check": lambda weeks, streak: len(weeks) >= 10,
        "progress": lambda weeks, streak: min(len(weeks), 10),
        "max": 10
    }
}