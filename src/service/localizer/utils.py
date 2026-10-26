from __future__ import annotations

import re
from pathlib import Path

from src.service.localizer.constants import _PROGRAMMING_KEYWORDS, _STOPWORDS

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`|```[a-zA-Z0-9+#-]*\n(.*?)```", re.S)

#: Weight awarded to identifiers whose shape marks them as code (CamelCase,
#: snake_case, diagnostic codes such as ``AKKASG003``).
_COMPOUND_WEIGHT = 3.0
#: Weight awarded to identifiers the issue author placed inside a code span.
_CODE_SPAN_WEIGHT = 2.0
#: Weight retained by ordinary prose words so that issues written without any
#: code formatting still produce candidate symbols.
_PROSE_WEIGHT = 0.5


def extract_tokens(text: str) -> list[str]:
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{3,}", text)]
    return [t for t in tokens if t not in _STOPWORDS]


def extract_code_span_identifiers(text: str) -> set[str]:
    """Return identifiers appearing inside inline or fenced code spans."""

    identifiers: set[str] = set()
    for match in _CODE_SPAN_RE.finditer(text):
        span = match.group(1) or match.group(2) or ""
        identifiers.update(_IDENTIFIER_RE.findall(span))
    return identifiers


def _is_compound_identifier(symbol: str) -> bool:
    if re.search(r"[a-z][A-Z]", symbol):
        return True
    if "_" in symbol:
        return True
    if re.search(r"[A-Za-z]\d", symbol):
        return True
    return symbol.isupper() and len(symbol) > 3


def extract_weighted_symbols(text: str) -> list[tuple[str, float]]:
    """Extract issue symbols ranked by how discriminative their shape is.

    Prose words are kept with a low weight so that callers which rely on a
    non-empty result still work on issues written without code formatting.
    """

    code_span_identifiers = extract_code_span_identifiers(text)
    weights: dict[str, tuple[str, float]] = {}

    for symbol in _IDENTIFIER_RE.findall(text):
        key = symbol.lower()
        if key in _STOPWORDS or key in _PROGRAMMING_KEYWORDS:
            continue

        weight = 0.0
        if _is_compound_identifier(symbol):
            weight += _COMPOUND_WEIGHT
        if symbol in code_span_identifiers:
            weight += _CODE_SPAN_WEIGHT
        if weight == 0.0:
            weight = _PROSE_WEIGHT

        current = weights.get(key)
        if current is None or weight > current[1]:
            weights[key] = (symbol, weight)

    ranked = sorted(weights.values(), key=lambda item: (-item[1], item[0]))
    return [(symbol, weight) for symbol, weight in ranked]


def extract_symbols(text: str) -> list[str]:
    """Extract issue symbols, most discriminative first.

    Callers that truncate the result (for example to build a bounded regular
    expression) therefore keep the highest-signal identifiers.
    """

    return [symbol for symbol, _ in extract_weighted_symbols(text)]


def extract_focus_symbols(text: str, limit: int = 40) -> list[str]:
    """Return only the identifiers that look like code, when any exist.

    Strategies that intersect issue symbols with whole-file symbol sets are
    otherwise dominated by prose words, which match almost every file in a
    large repository. When the issue contains no code-shaped identifier at all
    the ranked prose symbols are returned instead, so callers never receive an
    empty result for a non-empty issue.
    """

    weighted = extract_weighted_symbols(text)
    focused = [symbol for symbol, weight in weighted if weight > _PROSE_WEIGHT]
    if focused:
        return focused[:limit]
    return [symbol for symbol, _ in weighted][:limit]


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
