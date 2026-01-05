ACHIEVEMENTS = {
    "first_challenge": {
        "name": "First Challenger ♻️",
        "description": "Complete your first challenge",
        "check": lambda weeks, streak: len(weeks) >= 1
    },
    "three_streak": {
        "name": "On A Roll 🔥",
        "description": "Reach a 3-week streak",
        "check": lambda weeks, streak: streak >= 3
    },
    "five_streak": {
        "name": "Consistency King 👑",
        "description": "Reach a 5-week streak",
        "check": lambda weeks, streak: streak >= 5
    },
    "ten_challenges": {
        "name": "eReuse Legend 🍀",
        "description": "Complete 10 Challenges",
        "check": lambda weeks, streak: len(weeks) >= 10
    }
}