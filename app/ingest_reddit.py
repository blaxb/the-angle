import httpx
from typing import List, Dict

USER_AGENT = "theangle/0.1"

QUESTION_WORDS = ("how", "why", "what", "where", "when", "should", "best", "recommend")

def looks_like_question(title: str) -> bool:
    t = (title or "").strip().lower()
    return ("?" in t) or any(t.startswith(w + " ") for w in QUESTION_WORDS)

async def fetch_reddit(
    subreddit: str,
    sort: str = "hot",
    limit: int = 50,
    conversations_only: bool = True,
) -> List[Dict]:
    """
    conversations_only=True filters to self posts + question-like titles (more discussion, fewer link posts).
    """
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        r = await client.get(url)
        # If subreddit doesn't exist, Reddit returns 404 or a JSON with error; handle both
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json()

    out = []
    for c in data.get("data", {}).get("children", []):
        d = c.get("data", {})
        if d.get("stickied"):
            continue

        title = d.get("title") or ""
        is_self = bool(d.get("is_self"))

        if conversations_only:
            # keep text posts + question-like posts
            if not is_self and not looks_like_question(title):
                continue

        out.append({
            "source": "reddit",
            "source_id": d.get("id"),
            "title": title,
            "url": "https://www.reddit.com" + (d.get("permalink") or ""),
            "author": d.get("author"),
            "created_utc": int(d.get("created_utc") or 0),
            "score": int(d.get("score") or 0),
            "num_comments": int(d.get("num_comments") or 0),
        })

    return out


async def fetch_reddit_search(
    query: str,
    sort: str = "hot",
    limit: int = 50,
    conversations_only: bool = True,
) -> List[Dict]:
    """
    Search Reddit posts globally by topic query.
    """
    url = "https://www.reddit.com/search.json"
    headers = {"User-Agent": USER_AGENT}
    params = {
        "q": query,
        "sort": sort,
        "limit": limit,
        "type": "link",
    }

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        r = await client.get(url, params=params)
        if r.status_code != 200:
            return []
        data = r.json()

    out = []
    for c in data.get("data", {}).get("children", []):
        d = c.get("data", {})
        if d.get("stickied"):
            continue

        title = d.get("title") or ""
        is_self = bool(d.get("is_self"))

        if conversations_only:
            if not is_self and not looks_like_question(title):
                continue

        out.append({
            "source": "reddit",
            "source_id": d.get("id"),
            "title": title,
            "url": "https://www.reddit.com" + (d.get("permalink") or ""),
            "author": d.get("author"),
            "created_utc": int(d.get("created_utc") or 0),
            "score": int(d.get("score") or 0),
            "num_comments": int(d.get("num_comments") or 0),
        })

    return out
