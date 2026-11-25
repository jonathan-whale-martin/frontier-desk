"""Step 3 and 4: Claude drafts each story from its sources, then a second pass fact-checks it."""
from __future__ import annotations

import json
import logging
import re

from .common import longest_copied_run

log = logging.getLogger(__name__)

MAX_COPIED_WORDS = 15  # longest run of words allowed to match a source word-for-word

DRAFT_SYSTEM = """You are a news writer for {site}, a UK site that covers AI news only.
You write short, accurate news summaries for busy professionals and business owners.

Rules you must follow:
- Use ONLY facts stated in the SOURCES. Never add facts, figures, dates, names or quotes from memory.
- If sources disagree, say so plainly and name which source says what.
- Attribute claims: "OpenAI said", "according to Search Engine Roundtable". Say "reportedly" for anything not confirmed by the company involved.
- Write in your own words. Never reuse more than 6 words in a row from a source, apart from names and titles. Quote at most one short phrase (under 15 words), in quotation marks, only if the exact wording matters.
- No hype, no opinions presented as fact, no clickbait. British English.
- Headline: factual, under 90 characters, says what happened.
- Body: 150 to 300 words, short paragraphs, most important facts first.
- why_it_matters: one modest sentence on what this means for people or businesses using AI. Do not guess who is "mainly" affected, predict outcomes, or add facts. If nothing sensible follows from the sources, return an empty string.
- tags: choose from {sections}. Use "AI for business" only when there is a practical takeaway for businesses.
- Set newsworthy to false if the item is not really AI news (for example an unrelated product, an event listing, a job post, or a page with no news in it).

Submit your answer with the submit tool."""

CHECK_SYSTEM = """You are a fact-checker. Compare the DRAFT with the SOURCES.
List every factual claim in the HEADLINE, SUMMARY and BODY (names, numbers, dates, what happened, who said what).
For each, decide if the sources clearly support it.
A claim is unsupported if it is missing from the sources, goes further than they do, or states as fact something the sources only report as a rumour.
The WHY IT MATTERS line is labelled analysis. Do not flag it for being an interpretation. Only flag it if it states a new fact (a name, number, date or event) that is not in the sources, or contradicts them.

Submit your answer with the submit tool. Set passed to false if any claim is unsupported."""


REWRITE_SYSTEM = """You rewrite news copy so it does not copy its sources.
Keep every fact exactly the same and add nothing. Change the wording and sentence structure so that no more
than 6 words in a row match the sources, apart from names and titles. British English.
Submit your answer with the submit tool."""


def _sources_block(story: dict, texts: dict[str, str]) -> str:
    parts = []
    for n, it in enumerate(story["items"], 1):
        parts.append(
            f"[Source {n}] {it['source']} | {it['published'][:10]} | {it['url']}\n"
            f"Headline: {it['title']}\n"
            f"Text:\n{texts.get(it['url']) or it.get('summary') or '(no text available)'}"
        )
    return "\n\n".join(parts)


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        raise ValueError("model did not return JSON")
    return json.loads(m.group(0))


def _ask(client, model: str, system: str, user: str, schema: dict, max_tokens: int = 3000) -> dict:
    """Ask Claude and force a structured answer through a tool, so the reply is always valid JSON."""
    msg = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{"name": "submit", "description": "Submit your answer.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "submit"},
    )
    for b in msg.content:
        if getattr(b, "type", "") == "tool_use":
            return b.input
    text = "".join(getattr(b, "text", "") for b in msg.content)
    try:
        return _json(text)
    except Exception:
        raise ValueError(f"no structured answer (stop reason: {getattr(msg, 'stop_reason', '?')}): {text[:200]!r}")


_S = {"type": "string"}
DRAFT_SCHEMA = {"type": "object", "properties": {
    "newsworthy": {"type": "boolean"}, "headline": _S, "summary": _S, "body": _S, "why_it_matters": _S,
    "tags": {"type": "array", "items": _S}}, "required": ["newsworthy", "headline", "summary", "body", "why_it_matters", "tags"]}
CHECK_SCHEMA = {"type": "object", "properties": {
    "claims": {"type": "array", "items": {"type": "object", "properties": {
        "claim": _S, "supported": {"type": "boolean"}, "note": _S}, "required": ["claim", "supported"]}},
    "passed": {"type": "boolean"}}, "required": ["claims", "passed"]}
REWRITE_SCHEMA = {"type": "object", "properties": {
    "headline": _S, "summary": _S, "body": _S, "why_it_matters": _S}, "required": ["headline", "summary", "body", "why_it_matters"]}


def draft_story(client, story: dict, texts: dict[str, str], settings: dict) -> dict | None:
    """Returns an article dict, or None if the story is not worth publishing."""
    p = settings["pipeline"]
    sections = settings["sections"]
    src = _sources_block(story, texts)

    d = _ask(client, p["model"],
             DRAFT_SYSTEM.format(site=settings["site"]["name"], sections=json.dumps(sections)),
             f"SOURCES:\n\n{src}", DRAFT_SCHEMA)
    if not d.get("newsworthy", True) or not d.get("headline") or not d.get("body"):
        log.info("Skipped (not newsworthy): %s", story["title"])
        return None

    tags = [t for t in d.get("tags", []) if t in sections] or [t for t in story["tags"] if t in sections]
    article = {
        "headline": d["headline"].strip(),
        "summary": d.get("summary", "").strip(),
        "body": d["body"].strip(),
        "why_it_matters": d.get("why_it_matters", "").strip(),
        "tags": tags or ["New models"],
        "sources": [{"name": i["source"], "url": i["url"], "title": i["title"]} for i in story["items"]],
        "problems": [],
    }

    # Deterministic copy check: catches sentences lifted from a source. One automatic rewrite, then flag.
    all_src = " ".join(texts.get(i["url"], "") + " " + i.get("summary", "") for i in story["items"])
    fields = ("headline", "summary", "body", "why_it_matters")
    joined = lambda a: " ".join(a[f] for f in fields)
    if longest_copied_run(joined(article), all_src) > MAX_COPIED_WORDS:
        try:
            r = _ask(client, p["model"], REWRITE_SYSTEM,
                     f"SOURCES:\n\n{src}\n\nCOPY TO REWRITE:\n" + json.dumps({f: article[f] for f in fields}),
                     REWRITE_SCHEMA)
            for f in fields:
                if r.get(f) or f == "why_it_matters":
                    article[f] = (r.get(f) or "").strip()
        except Exception as exc:
            log.info("Rewrite failed: %s", exc)
    copied = longest_copied_run(joined(article), all_src)
    if copied > MAX_COPIED_WORDS:
        article["problems"].append(f"{copied} words in a row match a source word-for-word. Rewrite before publishing.")
    full = (f"HEADLINE: {article['headline']}\nSUMMARY: {article['summary']}\nBODY: {article['body']}\n"
            f"WHY IT MATTERS (analysis): {article['why_it_matters']}")

    # Second model pass: every claim must be in the sources.
    try:
        chk = _ask(client, p["check_model"], CHECK_SYSTEM,
                   f"SOURCES:\n\n{src}\n\nDRAFT:\n{full}", CHECK_SCHEMA)
        bad = [c for c in chk.get("claims", []) if not c.get("supported", False)]
        for c in bad:
            article["problems"].append(f"Unsupported claim: {c.get('claim')} ({c.get('note', '')})".strip())
        if not chk.get("passed", not bad) and not bad:
            article["problems"].append("Fact-check did not pass.")
    except Exception as exc:
        article["problems"].append(f"Fact-check could not run: {exc}")

    return article
