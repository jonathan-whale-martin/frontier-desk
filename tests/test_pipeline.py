"""Offline tests: sample feeds and a stand-in for Claude, so no internet or API key is needed."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import choose, fetch, run, store
from pipeline.common import longest_copied_run, settings, similar

NOW = datetime.now(timezone.utc)
FIX = Path(__file__).parent / "fixtures"


def rss(items):
    body = "".join(
        f"<item><title>{t}</title><link>{u}</link><pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>"
        f"<description>{s}</description></item>" for t, u, d, s in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{body}</channel></rss>'


LAB = {"name": "Example Lab", "weight": 3, "tags": ["New models"]}
PRESS = {"name": "Example Tech News", "weight": 1}
SEARCH = {"name": "Example Search News", "weight": 2, "tags": ["AI search"], "filter": True}


def sample_items():
    h = timedelta(hours=1)
    return (
        fetch.parse_feed(rss([
            ("Example Lab releases Nova 2 model for coding", "https://lab.example/nova-2", NOW - 2 * h,
             "Example Lab today released Nova 2, a model for software engineering tasks, priced at $3 per million input tokens."),
            ("Example Lab old post", "https://lab.example/old", NOW - 100 * h, "Old news about a model."),
        ]), LAB)
        + fetch.parse_feed(rss([
            ("Example Lab launches Nova 2 coding model", "https://press.example/nova2", NOW - h,
             "Example Lab has launched Nova 2, its new coding model."),
        ]), PRESS)
        + fetch.parse_feed(rss([
            ("Search engine adds AI Mode ads in follow-up questions", "https://search.example/ads", NOW - 3 * h,
             "Ads now appear in AI Mode follow-up questions."),
            ("Local listings get a new button", "https://search.example/button", NOW - 3 * h,
             "A new button for business listings, said the company."),
        ]), SEARCH)
    )


class FakeClient:
    """Stands in for the Anthropic client. Returns a draft, then a fact-check result."""

    def __init__(self, draft, check):
        self.replies = []
        self.draft, self.check = draft, check
        self.messages = self

    def create(self, model, max_tokens, system, messages, **kw):
        out = self.check if "fact-checker" in system else self.draft
        if callable(out):
            out = out(messages[0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=out)], stop_reason="tool_use")


GOOD_DRAFT = {
    "newsworthy": True,
    "headline": "Example Lab releases Nova 2, a model built for coding",
    "summary": "The model is aimed at software engineering work.",
    "body": "Example Lab has released Nova 2, a new AI model designed for software engineering.\n\n"
            "The company said it costs $3 per million input tokens. Tech press also covered the launch.",
    "why_it_matters": "Teams writing code with AI have another option to compare on price.",
    "tags": ["New models", "Not a section"],
}
PASS = {"claims": [{"claim": "Nova 2 released", "supported": True}], "passed": True}
FAIL = {"claims": [{"claim": "Nova 2 beats every rival", "supported": False, "note": "not in sources"}], "passed": False}


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    for name in ("articles", "flagged"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(store, "ARTICLES", tmp_path / "articles")
    monkeypatch.setattr(store, "FLAGGED", tmp_path / "flagged")
    monkeypatch.setattr(store, "STATE", tmp_path / "state")
    (tmp_path / "state").mkdir()
    return tmp_path


def test_parse_and_filter():
    items = sample_items()
    assert len(items) == 5
    assert choose.is_ai(items[3], settings()["ai_keywords"])
    assert not choose.is_ai(items[4], settings()["ai_keywords"])  # "said" must not match "AI"


def test_choose_groups_same_story_and_ranks():
    stories = choose.choose(sample_items(), seen_urls=set(), published_titles=[], settings=settings(), now=NOW)
    assert [len(s["items"]) for s in stories] == [2, 1]  # lab + press grouped, old post dropped
    assert stories[0]["items"][0]["source"] == "Example Lab"  # primary source first
    assert stories[0]["score"] == 4


def test_choose_skips_seen_and_already_published():
    s = choose.choose(sample_items(), seen_urls={"https://search.example/ads"},
                      published_titles=["Example Lab releases Nova 2 model for coding"], settings=settings(), now=NOW)
    assert s == []


def test_page_parser():
    html = '<a href="/news/claude-update">Introducing a new model update today</a><a href="/careers">Jobs</a><a href="/news/x">Short</a>'
    items = fetch.parse_page(html, {"name": "Lab", "url": "https://lab.example/news", "link_contains": "/news/"})
    assert [i["url"] for i in items] == ["https://lab.example/news/claude-update"]


def test_copy_check():
    assert longest_copied_run("one two three four five", "x two three four y") == 3


def test_similar():
    assert similar("Example Lab releases Nova 2 model", "Example Lab launches Nova 2 model") > 0.55
    assert similar("Example Lab releases Nova 2 model", "Search ads come to AI Mode") < 0.45  # well under the 0.55 threshold


def test_full_run_good_draft(tmp_repo):
    res = run.run(items=sample_items(), client=FakeClient(GOOD_DRAFT, PASS), read_text=lambda u, f: f)
    assert len(res["saved"]) == 2
    meta, body = store.read_article(res["saved"][0])
    assert res["saved"][0].parent == tmp_repo / "articles"
    assert meta["tags"] == ["New models"]
    assert len(meta["sources"]) == 2 and "Nova 2" in body
    report = (tmp_repo / "state" / "last_report.md").read_text()
    assert "Ready to publish (2)" in report
    # second run finds nothing new
    res2 = run.run(items=sample_items(), client=FakeClient(GOOD_DRAFT, PASS), read_text=lambda u, f: f)
    assert res2["saved"] == []


def test_unsupported_claim_is_flagged(tmp_repo):
    res = run.run(items=sample_items()[:1], client=FakeClient(GOOD_DRAFT, FAIL), read_text=lambda u, f: f)
    path = res["saved"][0]
    assert path.parent == tmp_repo / "flagged"
    meta, _ = store.read_article(path)
    assert "Unsupported claim" in meta["problems"][0]


def test_copied_text_is_flagged(tmp_repo):
    src = "Example Lab today released Nova 2, a model for software engineering tasks, priced at $3 per million input tokens."
    copied = dict(GOOD_DRAFT, body=src + " It is available now.")
    res = run.run(items=sample_items()[:1], client=FakeClient(copied, PASS), read_text=lambda u, f: f)
    meta, _ = store.read_article(res["saved"][0])
    assert any("word-for-word" in p for p in meta["problems"])


def test_not_newsworthy_is_skipped(tmp_repo):
    res = run.run(items=sample_items()[:1], client=FakeClient({"newsworthy": False}, PASS), read_text=lambda u, f: f)
    assert res["saved"] == [] and len(res["skipped"]) == 1


def test_build_site(tmp_repo, monkeypatch, tmp_path):
    from web import build
    run.run(items=sample_items(), client=FakeClient(GOOD_DRAFT, PASS), read_text=lambda u, f: f)
    run.run(items=sample_items()[:1], client=FakeClient(GOOD_DRAFT, FAIL), read_text=lambda u, f: f)
    monkeypatch.setattr(build, "ARTICLES", tmp_repo / "articles")
    monkeypatch.setattr(build, "OUT", tmp_path / "public")
    n = build.build()
    assert n == 2  # flagged draft is not published
    out = tmp_path / "public"
    home = (out / "index.html").read_text()
    assert "Example Lab releases Nova 2" in home and "Advertisement" in home
    art = next((out / "news").glob("*/index.html")).read_text()
    assert "NewsArticle" in art and "Sources" in art and "How we use AI" in art
    assert (out / "section" / "new-models" / "index.html").exists()
    assert "<loc>" in (out / "sitemap.xml").read_text()
    privacy = (out / "privacy" / "index.html").read_text()
    assert "Buttondown" in privacy and "ico.org.uk" in privacy and "privacy/" in home


def test_copied_text_is_rewritten_automatically(tmp_repo):
    src = "Example Lab today released Nova 2, a model for software engineering tasks, priced at $3 per million input tokens."
    copied = dict(GOOD_DRAFT, body=src)
    calls = []

    def draft(user):
        calls.append(user)
        return GOOD_DRAFT if "COPY TO REWRITE" in user else copied

    res = run.run(items=sample_items()[:1], client=FakeClient(draft, PASS), read_text=lambda u, f: f)
    assert res["saved"][0].parent == tmp_repo / "articles"
    assert any("COPY TO REWRITE" in c for c in calls)


def test_undated_page_is_baselined_first_time(tmp_repo):
    page = fetch.parse_page('<a href="/news/old-post-from-last-year">An old announcement from last year</a>',
                            {"name": "Lab", "url": "https://lab.example/news", "link_contains": "/news/", "weight": 3})
    res = run.run(items=page, client=FakeClient(GOOD_DRAFT, PASS), read_text=lambda u, f: f)
    assert res["saved"] == []  # old post not drafted
    page2 = page + fetch.parse_page('<a href="/news/brand-new-model">Introducing a brand new model today</a>',
                                    {"name": "Lab", "url": "https://lab.example/news", "link_contains": "/news/", "weight": 3})
    res2 = run.run(items=page2, client=FakeClient(GOOD_DRAFT, PASS), read_text=lambda u, f: f)
    assert len(res2["saved"]) == 1  # only the new link


def test_text_reply_without_json_is_a_clear_error():
    from pipeline import writer
    bad = SimpleNamespace(messages=SimpleNamespace(create=lambda **k: SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Sorry")], stop_reason="end_turn")))
    with pytest.raises(ValueError, match="no structured answer"):
        writer._ask(bad, "m", "s", "u", {})
