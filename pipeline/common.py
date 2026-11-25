"""Shared helpers: paths, config loading, text utilities."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
CONTENT = ROOT / "content"
ARTICLES = CONTENT / "articles"
FLAGGED = CONTENT / "flagged"
STATE = ROOT / "state"


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8")) or {}


def settings() -> dict:
    return load_yaml("settings.yaml")


def sources() -> dict:
    return load_yaml("sources.yaml")


def now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "story"


_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "with", "its", "is", "at", "by", "as", "new"}


def title_words(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9.]+", title.lower()) if w not in _STOP}


def similar(a: str, b: str) -> float:
    """0..1 score for how alike two headlines are (word overlap blended with character match)."""
    wa, wb = title_words(a), title_words(b)
    jacc = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jacc, seq * 0.9)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def longest_copied_run(text: str, source: str) -> int:
    """Longest run of consecutive words in `text` that also appears word-for-word in `source`."""
    t = re.findall(r"\w+", text.lower())
    s = " " + " ".join(re.findall(r"\w+", source.lower())) + " "
    best, i = 0, 0
    while i < len(t):
        n = best + 1
        while i + n <= len(t) and (" " + " ".join(t[i:i + n]) + " ") in s:
            best = n
            n += 1
        i += 1
    return best
