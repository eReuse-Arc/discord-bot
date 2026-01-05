from constants import FIRST_CHALLENGE_ROLE, THREE_STREAK_ROLE, FIVE_STREAK_ROLE, TEN_CHALLENGES_ROLE

ACHIEVEMENTS = {
    "first_challenge": {
        "name": "First Challenger ♻️",
        "description": "Complete your first challenge",
        "role": FIRST_CHALLENGE_ROLE,
        "check": lambda weeks, streak: len(weeks) >= 1
    },
    "three_streak": {
        "name": "On A Roll 🔥",
        "description": "Reach a 3-week streak",
        "role": THREE_STREAK_ROLE,
        "check": lambda weeks, streak: streak >= 3
    },
    "five_streak": {
        "name": "Consistency King 👑",
        "description": "Reach a 5-week streak",
        "role": FIVE_STREAK_ROLE,
        "check": lambda weeks, streak: streak >= 5
    },
    "ten_challenges": {
        "name": "eReuse Legend 🍀",
        "description": "Complete 10 Challenges",
        "role": TEN_CHALLENGES_ROLE,
        "check": lambda weeks, streak: len(weeks) >= 10
    }
}