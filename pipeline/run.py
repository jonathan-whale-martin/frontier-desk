"""Run the whole pipeline once.

    python -m pipeline.run              # live: fetch feeds, draft with Claude, save drafts
    python -m pipeline.run --dry-run    # show which stories would be drafted, no Claude calls
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from . import choose, fetch, store, writer
from .common import now, read_json, settings, sources, write_json

log = logging.getLogger("pipeline")


def run(items=None, client=None, dry_run=False, read_text=fetch.article_text) -> dict:
    cfg = settings()
    t = now()
    if items is None:
        items = fetch.collect(sources())
    seen = store.load_seen()
    # Pages without dates (such as Anthropic's newsroom): the first time we read one, record what is
    # already there as seen, so old posts are not drafted as news. After that, only new links count.
    done = set(read_json(store.STATE / "baselined_pages.json", []))
    fresh = {i["source"] for i in items if i.get("undated")} - done
    if fresh:
        seen.update(i["url"] for i in items if i.get("undated") and i["source"] in fresh)
        write_json(store.STATE / "baselined_pages.json", sorted(done | fresh))
        if not dry_run:
            store.save_seen(seen)
    stories = choose.choose(items, seen_urls=seen, published_titles=store.published_titles(),
                            settings=cfg, now=t)
    log.info("%d stories chosen", len(stories))
    if dry_run:
        for s in stories:
            print(f"[{s['score']}] {s['title']}  ({', '.join(i['source'] for i in s['items'])})")
        return {"stories": stories, "saved": [], "skipped": []}

    if client is None:
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("ANTHROPIC_API_KEY is not set.")
        client = anthropic.Anthropic()

    saved, skipped = [], []
    for s in stories:
        texts = {i["url"]: read_text(i["url"], i.get("summary", "")) for i in s["items"]}
        try:
            art = writer.draft_story(client, s, texts, cfg)
        except Exception as exc:
            log.warning("Drafting failed for %s: %s", s["title"], exc)
            continue  # not marked seen, so it is retried next run
        seen.update(i["url"] for i in s["items"])
        if art is None:
            skipped.append(s["title"])
            continue
        saved.append(store.save_article(art, t))

    store.save_seen(seen)
    (store.STATE / "last_report.md").write_text(store.report(saved, skipped), encoding="utf-8")
    log.info("Saved %d drafts, skipped %d", len(saved), len(skipped))
    return {"stories": stories, "saved": saved, "skipped": skipped}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(dry_run=a.dry_run)


if __name__ == "__main__":
    main()
