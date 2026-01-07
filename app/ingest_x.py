import httpx
from typing import List, Dict, Optional

# NOTE: Requires X API access + bearer token.
# We keep this minimal; we can expand to search queries, lists, etc.

async def fetch_x_recent(query: str, bearer_token: str, max_results: int = 25) -> List[Dict]:
    if not bearer_token:
        return []

    url = "https://api.x.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "query": query,
        "max_results": max(10, min(max_results, 100)),
        "tweet.fields": "created_at,public_metrics,author_id",
    }

    async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    tweets = data.get("data", []) or []
    out: List[Dict] = []
    for t in tweets:
        metrics = t.get("public_metrics") or {}
        out.append({
            "source": "x",
            "source_id": t.get("id"),
            "title": (t.get("text") or "")[:280],
            "url": f"https://x.com/i/web/status/{t.get('id')}",
            "author": t.get("author_id"),
            "created_utc": 0,  # we’ll compute later if needed
            "score": int(metrics.get("like_count") or 0),
            "num_comments": int(metrics.get("reply_count") or 0),
        })
    return out

