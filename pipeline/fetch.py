"""Step 1: collect candidate items from RSS feeds and watched pages."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import feedparser
import requests

log = logging.getLogger(__name__)
UA = {"User-Agent": "FrontierDeskBot/1.0 (+news aggregator; contact in site footer)"}
TIMEOUT = 20


def _when(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    for key in ("published", "updated"):
        if entry.get(key):
            try:
                return parsedate_to_datetime(entry[key]).astimezone(timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def _clean(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def parse_feed(raw: bytes | str, src: dict) -> list[dict]:
    feed = feedparser.parse(raw)
    items = []
    for e in feed.entries:
        if not e.get("link") or not e.get("title"):
            continue
        items.append({
            "title": _clean(e.title),
            "url": e.link.strip(),
            "source": src["name"],
            "weight": src.get("weight", 1),
            "tags": list(src.get("tags", [])),
            "filter": bool(src.get("filter")),
            "published": (_when(e) or datetime.now(timezone.utc)).isoformat(),
            "summary": _clean(e.get("summary", ""))[:1500],
        })
    return items


def parse_page(html: str, src: dict) -> list[dict]:
    """Pick article links out of a news index page that has no RSS feed."""
    items, seen = [], set()
    for href, text in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', html, flags=re.S | re.I):
        if src["link_contains"] not in href:
            continue
        url = urljoin(src["url"], href)
        title = _clean(text)
        if url in seen or len(title) < 12 or url.rstrip("/") == src["url"].rstrip("/"):
            continue
        seen.add(url)
        items.append({
            "title": title[:200], "url": url, "source": src["name"],
            "weight": src.get("weight", 1), "tags": list(src.get("tags", [])),
            "filter": False, "published": datetime.now(timezone.utc).isoformat(),
            "summary": "", "undated": True,
        })
    return items[:20]


def get(url: str) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def collect(cfg: dict) -> list[dict]:
    items: list[dict] = []
    for src in cfg.get("feeds", []):
        try:
            items += parse_feed(get(src["url"]).content, src)
        except Exception as exc:  # one broken feed must not stop the run
            log.warning("Feed failed: %s (%s)", src["name"], exc)
    for src in cfg.get("pages", []):
        try:
            items += parse_page(get(src["url"]).text, src)
        except Exception as exc:
            log.warning("Page failed: %s (%s)", src["name"], exc)
    log.info("Collected %d items", len(items))
    return items


def article_text(url: str, fallback: str = "", limit: int = 8000) -> str:
    """Main text of an article page, used only as reference for the summary."""
    try:
        import trafilatura
        text = trafilatura.extract(get(url).text, include_comments=False, include_tables=False) or ""
    except Exception as exc:
        log.info("Could not read %s (%s); using feed summary", url, exc)
        text = ""
    return (text or fallback)[:limit]
