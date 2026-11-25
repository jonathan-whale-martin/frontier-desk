"""Build the static website from approved articles in content/articles/.

    python -m web.build      ->  writes the finished site to public/
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

from pipeline.common import ARTICLES, ROOT, settings, slugify
from pipeline.store import read_article

HERE = Path(__file__).resolve().parent
OUT = ROOT / "public"
HUES = {"New models": "#ffd84a", "OpenAI": "#7fd1b9", "Anthropic": "#ffa38a", "Google": "#9ab8ff",
        "AI search": "#c9b6ff", "AI for business": "#8fd3ff"}


def art(key: str, cols: int, rows: int, colour: str, ratio: float) -> str:
    """Abstract 'model weights' illustration, unique to each article."""
    s = int(hashlib.md5(key.encode()).hexdigest()[:8], 16) or 1
    w, h, cells = 100 / cols, 100 / rows, []
    for r in range(rows):
        for c in range(cols):
            s = s * 16807 % 2147483647
            v = s / 2147483647
            on = v > 0.72
            cells.append(f'<rect x="{c*w+w*.18:.2f}" y="{r*h+h*.18:.2f}" width="{w*.64:.2f}" height="{h*.64:.2f}" '
                         f'rx="1" fill="{colour if on else "#2a3440"}" opacity="{1 if on else round(.35+v*.5, 2)}"/>')
    return (f'<svg viewBox="0 0 100 {100*ratio:.0f}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
            f'<rect width="100" height="100" fill="#101418"/><g transform="scale(1 {ratio})">{"".join(cells)}</g></svg>')


def load_articles(cfg: dict) -> list[dict]:
    out = []
    for p in ARTICLES.glob("*.md"):
        meta, body = read_article(p)
        if meta.get("problems"):
            continue  # never publish a draft that still has open problems
        date = datetime.fromisoformat(str(meta["date"]).replace("Z", "+00:00"))
        paras = markdown.markdown(body).split("</p>")
        paras = [x + "</p>" for x in paras if x.strip()]
        tags = [t for t in meta.get("tags", []) if t in cfg["sections"]] or ["New models"]
        a = {
            **meta,
            "slug": meta.get("slug") or p.stem,
            "tags": tags,
            "tag_links": [{"name": t, "slug": slugify(t)} for t in tags],
            "dt": date,
            "date_label": date.strftime("%-d %B %Y"),
            "date_short": date.strftime("%-d %b"),
            "body_first": "".join(paras[:2]),
            "body_rest": "".join(paras[2:]),
            "read_mins": max(1, round(len(body.split()) / 220)),
            "source_names": ", ".join(dict.fromkeys(s["name"] for s in meta.get("sources", []))),
        }
        colour = HUES.get(tags[0], "#ffd84a")
        a["art_small"] = art(a["slug"], 14, 5, colour, .4)
        a["art_large"] = art(a["slug"], 28, 12, colour, .5)
        a["jsonld"] = json.dumps({
            "@context": "https://schema.org", "@type": "NewsArticle", "headline": a["title"],
            "description": a.get("summary", ""), "datePublished": date.isoformat(),
            "publisher": {"@type": "Organization", "name": cfg["site"]["name"]},
            "mainEntityOfPage": f'{cfg["site"]["url"]}/news/{a["slug"]}/',
            "isBasedOn": [s["url"] for s in meta.get("sources", [])],
        }).replace("</", "<\\/")
        out.append(a)
    return sorted(out, key=lambda a: a["dt"], reverse=True)


def write(rel: str, html: str) -> None:
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def build() -> int:
    cfg = settings()
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    arts = load_articles(cfg)
    sections = [{"name": s, "slug": slugify(s)} for s in cfg["sections"]]
    base = {"site": cfg["site"], "m": cfg["monetisation"], "sections": sections}

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(HERE / "static", OUT / "static")

    def listing(items, current, path, root):
        return env.get_template("list.html").render(
            **base, root=root, current=current, path=path,
            lead=items[0] if items else None, brief=items[1:8], rest=items[1:])

    write("index.html", listing(arts, None, "/", "./"))
    for s in sections:
        items = [a for a in arts if s["name"] in a["tags"]]
        write(f'section/{s["slug"]}/index.html', listing(items, s["name"], f'/section/{s["slug"]}/', "../../"))
    for a in arts:
        write(f'news/{a["slug"]}/index.html',
              env.get_template("article.html").render(**base, root="../../", current=None, a=a))
    write("how-we-use-ai/index.html", env.get_template("policy.html").render(**base, root="../", current=None))

    url = cfg["site"]["url"]
    pages = ["/", "/how-we-use-ai/"] + [f'/section/{s["slug"]}/' for s in sections] + [f'/news/{a["slug"]}/' for a in arts]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"<url><loc>{escape(url + p)}</loc></url>\n" for p in pages) + "</urlset>\n")
    items = "".join(
        f"<item><title>{escape(a['title'])}</title><link>{escape(url)}/news/{a['slug']}/</link>"
        f"<guid>{escape(url)}/news/{a['slug']}/</guid><pubDate>{format_datetime(a['dt'])}</pubDate>"
        f"<description>{escape(a.get('summary', ''))}</description></item>\n" for a in arts[:50])
    write("rss.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{escape(cfg["site"]["name"])}</title>'
          f'<link>{escape(url)}/</link><description>{escape(cfg["site"]["tagline"])}</description>\n{items}</channel></rss>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {url}/sitemap.xml\n")
    if cfg["monetisation"].get("adsense_client"):
        pub = cfg["monetisation"]["adsense_client"].replace("ca-", "")
        write("ads.txt", f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    print(f"Built {len(arts)} articles into {OUT}")
    return len(arts)


if __name__ == "__main__":
    build()
