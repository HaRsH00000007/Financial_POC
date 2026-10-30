"""Shared, deterministic token parsing for periods and numbers."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_PERIOD_PATTERNS = [
    # Jan 2025 / January 2025 / Jan-2025 / Jan-25 / Jan'25
    re.compile(r"^(?P<mon>[A-Za-z]{3,9})[\s\-'/.]*(?P<yr>\d{2}|\d{4})$"),
    # 2025-01 / 2025/01
    re.compile(r"^(?P<yr>\d{4})[\-/](?P<mm>\d{1,2})$"),
    # 01/2025 / 1-2025
    re.compile(r"^(?P<mm>\d{1,2})[\-/](?P<yr>\d{4})$"),
]

MISSING_TOKENS = {"", "-", "—", "–", "n/a", "na", "nan", "none", "null", "?", "--"}


def period_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def period_label(key: str) -> str:
    y, m = key.split("-")
    return f"{MONTH_NAMES[int(m) - 1]} {y}"


def parse_period(token) -> Optional[str]:
    if isinstance(token, (datetime, date)):
        return period_key(token.year, token.month)
    if token is None:
        return None
    s = str(token).strip()
    for pat in _PERIOD_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        gd = m.groupdict()
        yr = int(gd["yr"])
        if yr < 100:
            yr += 2000
        if gd.get("mon"):
            mon = MONTHS.get(gd["mon"][:3].lower())
            if not mon:
                continue
        else:
            mon = int(gd["mm"])
            if not 1 <= mon <= 12:
                continue
        if 1990 <= yr <= 2100:
            return period_key(yr, mon)
    return None


def find_periods_in_line(line: str) -> list[str]:
    """Find period tokens in a free-text header line (e.g. from a PDF)."""
    pattern = re.compile(
        r"\b(?:[A-Za-z]{3,9}[\s\-']?\d{2,4}|\d{4}[\-/]\d{1,2}|\d{1,2}[\-/]\d{4})\b"
    )
    out = []
    for tok in pattern.findall(line):
        key = parse_period(tok)
        if key:
            out.append(key)
    return out


_NUM_RE = re.compile(r"^\(?-?\$?\(?[\d,]*\.?\d+\)?%?$")


def is_number_token(token: str) -> bool:
    t = token.strip().replace("$", "").replace("USD", "")
    return t.lower() in MISSING_TOKENS or bool(_NUM_RE.match(t))


def parse_number(token) -> tuple[Optional[float], bool]:
    """Return ``(value, ok)``. ``value`` is None for explicit missing tokens.

    ``ok`` is False when the token could not be interpreted at all.
    """
    if token is None:
        return None, True
    if isinstance(token, (int, float)):
        return float(token), True
    s = str(token).strip()
    if s.lower() in MISSING_TOKENS:
        return None, True
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()").lstrip("-").replace("$", "").replace(",", "").replace("USD", "").strip()
    try:
        v = float(s)
    except ValueError:
        return None, False
    return (-v if neg else v), True
