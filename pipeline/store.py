"""Save drafts as Markdown files and keep track of what has been seen."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from .common import ARTICLES, FLAGGED, STATE, read_json, slugify, write_json

def load_seen() -> set[str]:
    return set(read_json(STATE / "seen.json", []))


def save_seen(urls: set[str]) -> None:
    write_json(STATE / "seen.json", sorted(urls)[-5000:])  # cap size


def read_article(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm), body.strip()


def published_titles(dirs=None) -> list[str]:
    titles = []
    for d in dirs or (ARTICLES, FLAGGED):
        for p in sorted(d.glob("*.md"))[-400:]:
            try:
                meta, _ = read_article(p)
                titles.append(meta.get("title", ""))
                titles += [s.get("title", "") for s in meta.get("sources", [])]
            except Exception:
                continue
    return [t for t in titles if t]


def save_article(article: dict, when: datetime) -> Path:
    folder = FLAGGED if article["problems"] else ARTICLES
    folder.mkdir(parents=True, exist_ok=True)
    slug = slugify(article["headline"])
    path = folder / f"{when:%Y-%m-%d}-{slug}.md"
    n = 2
    while path.exists():
        path = folder / f"{when:%Y-%m-%d}-{slug}-{n}.md"
        n += 1
    meta = {
        "title": article["headline"],
        "slug": path.stem,
        "date": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": article["summary"],
        "tags": article["tags"],
        "why_it_matters": article["why_it_matters"],
        "sources": article["sources"],
        "ai_drafted": True,
    }
    if article["problems"]:
        meta["problems"] = article["problems"]
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True) + "---\n\n"
                    + article["body"] + "\n", encoding="utf-8")
    return path


def report(saved: list[Path], skipped: list[str]) -> str:
    """Text for the approval pull request."""
    lines = ["## New AI news drafts", "",
             "Read each draft below (Files changed tab). Edit anything that is wrong.",
             "**Merge this pull request to publish the drafts in `content/articles/`.**",
             "To reject a draft, delete its file in this pull request before merging.", ""]
    ready = [p for p in saved if p.parent == ARTICLES]
    flagged = [p for p in saved if p.parent == FLAGGED]
    lines.append(f"### Ready to publish ({len(ready)})")
    for p in ready:
        meta, _ = read_article(p)
        lines.append(f"- **{meta['title']}** ({', '.join(meta['tags'])}) — sources: "
                     + ", ".join(f"[{s['name']}]({s['url']})" for s in meta["sources"]))
    if flagged:
        lines += ["", f"### Needs a human fix ({len(flagged)})",
                  "These are in `content/flagged/` and will NOT be published. Fix the problem, delete the "
                  "`problems:` lines, and move the file to `content/articles/` to publish it."]
        for p in flagged:
            meta, _ = read_article(p)
            lines.append(f"- **{meta['title']}**")
            lines += [f"  - {pr}" for pr in meta.get("problems", [])]
    if skipped:
        lines += ["", f"### Skipped as not newsworthy ({len(skipped)})"] + [f"- {t}" for t in skipped]
    return "\n".join(lines) + "\n"
