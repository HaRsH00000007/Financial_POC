"""Presentation formatting and the numeric-claim guard for AI text."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from app.extraction.parsing import period_label


def fmt_currency(v: Optional[float], compact: bool = True) -> str:
    if v is None:
        return "n/a (incomplete)"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if compact and a >= 1_000_000:
        return f"{sign}${a / 1_000_000:,.2f}M"
    if compact and a >= 10_000:
        return f"{sign}${a / 1_000:,.1f}K"
    return f"{sign}${a:,.0f}"


def fmt_pct(v: Optional[float], signed: bool = False) -> str:
    if v is None:
        return "n/a"
    s = f"{v * 100:+.1f}%" if signed else f"{v * 100:.1f}%"
    return s


def fmt_period(p: str) -> str:
    try:
        return period_label(p)
    except Exception:
        return p


_NUM_IN_TEXT = re.compile(
    r"(?P<neg>[-−])?\$?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<unit>%|[KMB]\b|bps|pp|percentage points)?",
    re.IGNORECASE,
)


def extract_numeric_claims(text: str) -> list[dict]:
    claims = []
    for m in _NUM_IN_TEXT.finditer(text):
        raw = m.group(0).strip()
        num = float(m.group("num").replace(",", ""))
        unit = (m.group("unit") or "").upper()
        decimals = len(m.group("num").split(".")[1]) if "." in m.group("num") else 0
        claims.append({"raw": raw, "num": num, "unit": unit, "decimals": decimals,
                       "is_money": "$" in raw})
    return claims


def verify_numeric_claims(text: str, allowed_values: Iterable[float]) -> dict:
    """Check every number the AI wrote against values produced by the engine.

    A claim is accepted when some engine value, rendered at the claim's own
    precision and unit, equals the claim. Calendar numbers (years, day/month
    counts) are ignored.
    """
    allowed = [float(v) for v in allowed_values if v is not None]
    results = []
    for c in extract_numeric_claims(text):
        num, unit, dec = c["num"], c["unit"], c["decimals"]
        if not unit and not c["is_money"] and (1990 <= num <= 2100 or (num <= 31 and dec == 0)):
            continue  # years, "12 months", "T-12", "3 months"
        tol = 0.5 * 10 ** (-dec)
        candidates: list[float] = []
        for v in allowed:
            if unit == "%":
                candidates += [v * 100, abs(v * 100)]
            elif unit in ("PP", "PERCENTAGE POINTS", "BPS"):
                scale = 100 if unit != "BPS" else 10_000
                candidates += [v * scale, abs(v * scale)]
            elif unit == "M":
                candidates += [v / 1e6, abs(v / 1e6)]
            elif unit == "K":
                candidates += [v / 1e3, abs(v / 1e3)]
            elif unit == "B":
                candidates += [v / 1e9, abs(v / 1e9)]
            else:
                candidates += [v, abs(v)]
        ok = any(abs(x - num) <= tol + 1e-9 for x in candidates)
        results.append({"claim": c["raw"], "verified": ok})
    unverified = [r["claim"] for r in results if not r["verified"]]
    return {"checked": len(results), "verified": len(results) - len(unverified),
            "unverified": unverified, "passed": not unverified}
