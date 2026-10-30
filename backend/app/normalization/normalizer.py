"""Map raw source labels onto the canonical taxonomy.

Order of precedence:
1. user override (human-in-the-loop, always wins)
2. exact synonym match (rule-based)
3. fuzzy match against synonyms (rule-based, flagged WARNING)
4. AI suggestion for anything still unmapped (probabilistic, flagged WARNING)
5. unmapped (REVIEW REQUIRED) - nothing is guessed silently
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.models.domain import Mapping, RawLineItem, Status
from app.normalization.taxonomy import BY_KEY, CATEGORIES

FUZZY_ACCEPT = 0.86
FUZZY_SUGGEST = 0.6


def clean_label(label: str) -> str:
    s = label.lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9/ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


_SYNONYMS: list[tuple[str, str]] = [
    (clean_label(syn), c.key) for c in CATEGORIES for syn in c.synonyms
]
_EXACT = {syn: key for syn, key in _SYNONYMS}


def candidates(label: str, limit: int = 3) -> list[dict]:
    cl = clean_label(label)
    best: dict[str, float] = {}
    for syn, key in _SYNONYMS:
        score = SequenceMatcher(None, cl, syn).ratio()
        if score > best.get(key, 0):
            best[key] = score
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"category": k, "name": BY_KEY[k].name, "score": round(s, 3)} for k, s in ranked]


def map_row(row: RawLineItem) -> Mapping:
    cl = clean_label(row.label)
    if cl in _EXACT:
        key = _EXACT[cl]
        return Mapping(row_id=row.id, raw_label=row.label, category=key, method="exact_synonym",
                       confidence=0.98, status=Status.VALID,
                       rationale=f'"{row.label}" is a registered synonym of {BY_KEY[key].name}.')
    alts = candidates(row.label)
    top = alts[0] if alts else None
    if top and top["score"] >= FUZZY_ACCEPT:
        return Mapping(row_id=row.id, raw_label=row.label, category=top["category"], method="fuzzy_match",
                       confidence=round(top["score"] * 0.95, 3), status=Status.WARNING,
                       rationale=f'Closest synonym match to {top["name"]} (similarity {top["score"]:.0%}). '
                                 "Confirm the mapping.",
                       alternatives=alts)
    return Mapping(row_id=row.id, raw_label=row.label, category=None, method="unmapped", confidence=0.0,
                   status=Status.REVIEW_REQUIRED,
                   rationale="No reliable match in the taxonomy. A reviewer must map or exclude this row.",
                   alternatives=[a for a in alts if a["score"] >= FUZZY_SUGGEST])


def user_override(existing: Mapping, category: str | None) -> Mapping:
    if category is not None and category not in BY_KEY:
        raise ValueError(f"Unknown category {category!r}")
    return Mapping(
        row_id=existing.row_id, raw_label=existing.raw_label, category=category, method="user_override",
        confidence=1.0 if category else 0.0,
        status=Status.VALID if category else Status.REVIEW_REQUIRED,
        rationale="Set by reviewer." if category else "Cleared by reviewer.",
        alternatives=existing.alternatives,
    )
