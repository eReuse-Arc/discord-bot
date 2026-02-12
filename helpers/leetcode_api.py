import json
import random
from dataclasses import dataclass
from typing import Any

import aiohttp

LEETCODE_ALL_PROBLEMS_URL = "https://leetcode.com/api/problems/all/"
LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql/"

DIFF_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}

BASE_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://leetcode.com/",
    "Origin": "https://leetcode.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

TIMEOUT = aiohttp.ClientTimeout(total=25)


@dataclass(frozen=True)
class LeetCodeProblem:
    question_id: str
    title: str
    title_slug: str
    difficulty: str
    url: str


class LeetCodeAPIError(RuntimeError):
    pass


def _snippet(text: str, n: int = 300) -> str:
    s = (text or "")[:n]
    return " ".join(s.split())


async def _read_json_lenient(resp: aiohttp.ClientResponse) -> Any:
    text = await resp.text()
    try:
        return json.loads(text)
    except Exception:
        raise LeetCodeAPIError(
            f"LeetCode did not return JSON. "
            f"status={resp.status} content_type={resp.headers.get('Content-Type')} "
            f"snippet={_snippet(text)!r}"
        )


async def fetch_all_problems(session: aiohttp.ClientSession) -> dict:
    async with session.get(
        LEETCODE_ALL_PROBLEMS_URL,
        headers=BASE_HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    ) as r:
        if r.status >= 400:
            text = await r.text()
            raise LeetCodeAPIError(
                f"LeetCode /api/problems/all/ HTTP {r.status}. snippet={_snippet(text)!r}"
            )
        data = await _read_json_lenient(r)

    if not isinstance(data, dict) or "stat_status_pairs" not in data:
        raise LeetCodeAPIError(
            "LeetCode /api/problems/all/ returned JSON but missing expected fields "
            f"(keys={list(data.keys())[:20] if isinstance(data, dict) else type(data)})."
        )

    return data


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
        if avoid_slugs:
            return pick_random_free_problem(all_json, set(), weights)
        raise LeetCodeAPIError("No free problems found in LeetCode problem list response.")

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
        "query": (
            "query recentAcSubmissions($username: String!, $limit: Int!) "
            "{ recentAcSubmissionList(username: $username, limit: $limit) { titleSlug timestamp } }"
        ),
        "variables": {"username": username, "limit": limit},
    }

    headers = {
        **BASE_HEADERS,
        "Content-Type": "application/json",
    }

    async with session.post(
        LEETCODE_GRAPHQL_URL,
        json=payload,
        headers=headers,
        timeout=TIMEOUT,
        allow_redirects=True,
    ) as r:
        if r.status >= 400:
            text = await r.text()
            raise LeetCodeAPIError(
                f"LeetCode GraphQL HTTP {r.status}. snippet={_snippet(text)!r}"
            )
        data = await _read_json_lenient(r)

    if not isinstance(data, dict):
        raise LeetCodeAPIError("LeetCode GraphQL returned non-dict JSON.")

    if data.get("errors"):
        raise LeetCodeAPIError(f"LeetCode GraphQL returned errors: {data.get('errors')}")

    items = (data.get("data") or {}).get("recentAcSubmissionList") or []
    if not isinstance(items, list):
        return []
    return items
