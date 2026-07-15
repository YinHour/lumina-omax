from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bounded_text(value: Any, max_chars: int = 12000) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text[:max_chars]


def strip_markup(value: Any, max_chars: int = 12000) -> str | None:
    if value is None:
        return None
    without_tags = re.sub(r"<[^>]+>", " ", str(value))
    return bounded_text(html.unescape(without_tags), max_chars=max_chars)


def normalize_doi(value: Any) -> str | None:
    text = bounded_text(value, max_chars=512)
    if not text:
        return None
    lowered = text.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip() or None


def reconstruct_inverted_abstract(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    positioned: list[tuple[int, str]] = []
    for word, positions in value.items():
        if not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned.append((position, str(word)))
    positioned.sort(key=lambda item: item[0])
    return bounded_text(" ".join(word for _, word in positioned))
