"""Step 2: keep AI stories, drop ones already covered, group duplicates, rank."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from .common import similar


def is_ai(item: dict, keywords: list[str]) -> bool:
    text = f"{item['title']} {item.get('summary', '')}"
    for kw in keywords:
        flags = 0 if kw.isupper() else re.I  # "AI" and "GPT" must be capitals, avoiding "said", "aid"
        if re.search(rf"(?<![A-Za-z]){re.escape(kw)}(?![A-Za-z])", text, flags):
            return True
    return False


def recent(item: dict, now: datetime, hours: int) -> bool:
    return datetime.fromisoformat(item["published"]) >= now - timedelta(hours=hours)


def cluster(items: list[dict], threshold: float) -> list[list[dict]]:
    """Group items that report the same story (similar headlines)."""
    groups: list[list[dict]] = []
    for it in items:
        for g in groups:
            if any(similar(it["title"], o["title"]) >= threshold for o in g):
                g.append(it)
                break
        else:
            groups.append([it])
    return groups


def score(group: list[dict]) -> float:
    outlets = {i["source"] for i in group}
    return max(i["weight"] for i in group) + (len(outlets) - 1)


def choose(items: list[dict], *, seen_urls: set[str], published_titles: list[str],
           settings: dict, now: datetime) -> list[dict]:
    p = settings["pipeline"]
    th = p["similar_title_threshold"]
    keep = []
    for it in items:
        if it["url"] in seen_urls:
            continue
        if it.get("filter") and not is_ai(it, settings["ai_keywords"]):
            continue
        if not recent(it, now, p["lookback_hours"]):
            continue
        if any(similar(it["title"], t) >= th for t in published_titles):
            continue  # we already ran this story
        keep.append(it)

    stories = []
    for g in cluster(keep, th):
        g.sort(key=lambda i: (-i["weight"], i["published"]))
        tags = sorted({t for i in g for t in i["tags"]})
        stories.append({
            "title": g[0]["title"],
            "score": score(g),
            "tags": tags,
            "items": g,
            "published": max(i["published"] for i in g),
        })
    stories = [s for s in stories if s["score"] >= p["min_score"]]
    stories.sort(key=lambda s: (s["score"], s["published"]), reverse=True)
    return stories[: p["max_drafts_per_run"]]
