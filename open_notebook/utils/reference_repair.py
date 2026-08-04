"""Repair truncated document reference IDs in model-generated answers.

LLMs frequently truncate SurrealDB record IDs (20-char random strings) when
writing citations, e.g. ``source:lh9mbuyd1m9g4bh56u36`` becomes
``source:lh9mbu``. The frontend renders whatever ID the model wrote, so the
citation link breaks. Given the set of IDs that were actually in scope for the
answer, this module replaces truncated references with the unique full ID when
a one-to-one match exists; ambiguous or unmatched references are left as-is.
"""

import re
from typing import Collection, Optional

REFERENCE_PATTERN = re.compile(r"(source_insight|insight|note|source):([a-zA-Z0-9_]+)")

#: Prefix aliases that normalize to the same canonical type
_TYPE_ALIASES = {
    "insight": "source_insight",
}


def _canonical_type(label: str) -> str:
    return _TYPE_ALIASES.get(label, label)


def _find_unique_full_id(short_id: str, known_ids: Collection[str]) -> Optional[str]:
    """Return the unique full reference matching ``short_id``, or None."""
    candidates: list[str] = []
    for known in known_ids:
        if not isinstance(known, str) or ":" not in known:
            continue
        real_id = known.split(":", 1)[1]
        if real_id == short_id:
            # Already a full ID - the reference is fine as-is
            return known
        if (
            real_id.startswith(short_id)
            or real_id.endswith(short_id)
            or short_id in real_id
        ):
            candidates.append(known)
    if len(candidates) == 1:
        return candidates[0]
    return None


def repair_reference_ids(text: str, known_ids: Collection[str]) -> str:
    """Replace truncated ``type:shortid`` references with full IDs.

    ``known_ids`` is the collection of complete references (e.g.
    ``source:abc123``) that were in scope for the answer. Only unambiguous
    matches are rewritten; everything else stays untouched.
    """
    if not text or not known_ids:
        return text
    known_by_type: dict[str, list[str]] = {}
    for known in known_ids:
        if not isinstance(known, str) or ":" not in known:
            continue
        known_by_type.setdefault(_canonical_type(known.split(":", 1)[0]), []).append(known)

    def _replace(match: re.Match[str]) -> str:
        label, short_id = match.group(1), match.group(2)
        candidates = known_by_type.get(_canonical_type(label))
        if not candidates:
            return match.group(0)
        full = _find_unique_full_id(short_id, candidates)
        if full is None:
            return match.group(0)
        return full

    return REFERENCE_PATTERN.sub(_replace, text)
