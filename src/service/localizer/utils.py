from __future__ import annotations

import re
from pathlib import Path

from src.service.localizer.constants import _STOPWORDS


def extract_tokens(text: str) -> list[str]:
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", text)]
    return [t for t in tokens if t not in _STOPWORDS]


def extract_symbols(text: str) -> list[str]:
    symbols = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in symbols:
        key = item.lower()
        if key in seen or key in _STOPWORDS:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def safe_read_text(path: Path, max_file_size_bytes: int) -> str:
    try:
        if not path.exists() or path.stat().st_size > max_file_size_bytes:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def count_token_frequency(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for token in extract_tokens(text):
        counts[token] = counts.get(token, 0) + 1
    return counts
