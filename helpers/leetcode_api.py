import random
from dataclasses import dataclass

import aiohttp

LEETCODE_ALL_PROBLEMS_URL = "https://leetcode.com/api/problems/all/"
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql/"

DIFF_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}

@dataclass(frozen=True)
class LeetCodeProblem:
    question_id: str
    title: str
    title_slug: str
    difficulty: str
    url: str

async def fetch_all_problems(session: aiohttp.ClientSession) -> dict:
    async with session.get(LEETCODE_ALL_PROBLEMS_URL, timeout=aiohttp.ClientTimeout(total=25)) as r:
        r.raise_for_status()
        return await r.json()

def pick_random_free_problem(
    all_json: dict,
    avoid_slugs: set[str] | None = None,
    weights: tuple[float, float, float] = (0.55, 0.40, 0.05),
) -> LeetCodeProblem:
    avoid_slugs = avoid_slugs or set()

    pairs = all_json.get("stat_status_pairs", [])

    easy: list[LeetCodeProblem] = []
    medium: list[LeetCodeProblem] = []
    hard: list[LeetCodeProblem] = []

    for p in pairs:
        if p.get("paid_only"):
            continue

        stat = p.get("stat") or {}
        slug = stat.get("question__title_slug")
        title = stat.get("question__title")
        qid = stat.get("question_id")

        if not slug or not title or not qid:
            continue
        if slug in avoid_slugs:
            continue

        diff_level = (p.get("difficulty") or {}).get("level")
        difficulty = DIFF_MAP.get(diff_level, "Unknown")

        prob = LeetCodeProblem(
            question_id=str(qid),
            title=title,
            title_slug=slug,
            difficulty=difficulty,
            url=f"https://leetcode.com/problems/{slug}/",
        )

        if diff_level == 1:
            easy.append(prob)
        elif diff_level == 2:
            medium.append(prob)
        elif diff_level == 3:
            hard.append(prob)
        else:
            continue

    if not (easy or medium or hard):
        return pick_random_free_problem(all_json, set(), weights)

    buckets = [easy, medium, hard]
    w = list(weights)

    non_empty = [i for i, b in enumerate(buckets) if len(b) > 0]
    if len(non_empty) < 3:
        total = sum(w[i] for i in non_empty) or 1.0
        w2 = [0.0, 0.0, 0.0]
        for i in non_empty:
            w2[i] = w[i] / total
        w = w2

    r = random.random()
    acc = 0.0
    chosen_idx = non_empty[0]
    for i in range(3):
        acc += w[i]
        if r <= acc:
            chosen_idx = i
            break

    chosen_bucket = buckets[chosen_idx]
    return random.choice(chosen_bucket)

RECENT_AC_QUERY = """
query recentAcSubmissions($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) {
    titleSlug
    timestamp
  }
}
"""

async def recent_accepted_submissions(
    session: aiohttp.ClientSession,
    username: str,
    limit: int = 25,
) -> list[dict]:
    payload = {
        "operationName": "recentAcSubmissions",
        "query": "query recentAcSubmissions($username: String!, $limit: Int!) { recentAcSubmissionList(username: $username, limit: $limit) { titleSlug timestamp } }",
        "variables": {"username": username, "limit": limit},
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": "https://leetcode.com/",
        "User-Agent": "eReuseBot/1.0 (+discord.py)",
    }

    async with session.post(
        LEETCODE_GRAPHQL_URL,
        json=payload,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=25),
    ) as r:
        r.raise_for_status()
        data = await r.json()

    items = (data.get("data") or {}).get("recentAcSubmissionList") or []
    return items
