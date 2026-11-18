"""Locate and parse primary financial statements inside an annual report.

Locator: structural markers (the line items every Ind AS / IFRS statement must
print) decide which pages are statements; the BM25 rank of the page is recorded
as corroborating evidence. Consolidated statements are preferred by default.

Parser: deterministic. Each line is split into label, optional note reference and
one value per fiscal-year column. Indian digit grouping ("10,75,675"), bracketed
negatives and "-" (nil) are handled; anything that cannot be aligned to the year
columns with certainty is reported as an issue instead of being guessed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.annual.rag import BM25Index

STATEMENTS = {
    "income_statement": "Statement of Profit and Loss",
    "balance_sheet": "Balance Sheet",
    "cash_flow": "Statement of Cash Flows",
}

_MARKERS = {
    "balance_sheet": [["total assets"], ["total equity and liabilities"]],
    "income_statement": [["total income"], ["total expenses"], ["profit"]],
    "cash_flow": [["operating activities"], ["investing activities"], ["net cash"]],
}
_QUERIES = {
    "balance_sheet": "balance sheet total assets total equity and liabilities current liabilities borrowings",
    "income_statement": "statement of profit and loss revenue from operations total income total expenses profit",
    "cash_flow": "cash flow operating activities investing activities financing activities net cash",
}

_FY_RANGE = re.compile(r"\b(20\d{2})\s?[-–]\s?(\d{2})\b")
_MARCH = re.compile(r"31(?:st)?\s+march,?\s+(20\d{2})", re.IGNORECASE)
_VALUE = re.compile(r"^\(?-?[\d,]*\d(?:\.\d+)?\)?$")
_DASH = {"-", "–", "—"}
_NOTE = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2})?|[A-C]-[A-C])$")
_UNIT = re.compile(r"in\s+(crore|lakhs?|millions?|thousands?|billions?)", re.IGNORECASE)

_SECTIONS = {
    "balance_sheet": {
        "non-current assets": "Non-Current Assets", "current assets": "Current Assets",
        "equity": "Equity", "non-current liabilities": "Non-Current Liabilities",
        "current liabilities": "Current Liabilities",
    },
    "income_statement": {
        "income": "Income", "expenses": "Expenses", "tax expenses": "Tax Expenses",
        "other comprehensive income": "Other Comprehensive Income",
        "other comprehensive income:": "Other Comprehensive Income",
        "net profit attributable to:": "Profit Attribution",
        "other comprehensive income attributable to:": "OCI Attribution",
        "total comprehensive income attributable to:": "TCI Attribution",
    },
    "cash_flow": {
        "a. cash flow from operating activities": "Operating Activities",
        "b. cash flow from investing activities": "Investing Activities",
        "c. cash flow from financing activities": "Financing Activities",
    },
}
_CONNECTORS = (" as per", " of", " and", " to", " the", " in", " for", " from")
_STOP = ("material accounting policies", "as per our report", "see accompanying notes",
         "change in liability arising from financing", "cash flow from supplier financing")
_SKIP = re.compile(r"(integrated annual report|^\d{2,3}(\s+\d{2,3})?$|^notes$|^\(.{0,3}in crore\)$|^particulars$)",
                   re.IGNORECASE)


@dataclass
class StatementLocation:
    statement: str
    page: int
    scope: str                 # consolidated | standalone | unknown
    score: float
    method: str
    bm25_rank: Optional[int]
    candidates: list[int] = field(default_factory=list)


@dataclass
class ParsedRow:
    statement: str
    section: str
    label: str
    note_ref: Optional[str]
    values: dict[str, Optional[float]]
    raw: dict[str, str]
    page: int
    line_no: int
    confidence: float
    note: Optional[str] = None


@dataclass
class ParsedStatement:
    statement: str
    page: int
    periods: list[str]
    unit: str
    rows: list[ParsedRow]
    issues: list[dict]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def page_scope(text: str) -> str:
    head = _squash(text[:700])
    if "consolidated" in head:
        return "consolidated"
    if "standalone" in head:
        return "standalone"
    return "unknown"


def classify_page(text: str) -> Optional[str]:
    low = re.sub(r"\s+", " ", text.lower())
    for kind, groups in _MARKERS.items():
        if all(any(m in low for m in g) for g in groups):
            # notes pages reprint some markers; a primary statement has many value rows
            if sum(1 for line in text.split("\n") if _trailing_values(line)[1] >= 2) >= 12:
                return kind
    return None


def locate(pages: list[str], index: BM25Index, document_id: str, prefer: str = "consolidated") -> dict[str, StatementLocation]:
    found: dict[str, list[tuple[int, str]]] = {}
    for i, text in enumerate(pages, start=1):
        kind = classify_page(text)
        if kind:
            found.setdefault(kind, []).append((i, page_scope(text)))
    out: dict[str, StatementLocation] = {}
    for kind in STATEMENTS:
        cands = found.get(kind, [])
        ranked = index.search(_QUERIES[kind], k=40, document_id=document_id)
        rank_of = {}
        for r, (c, _) in enumerate(ranked, start=1):
            rank_of.setdefault(c.page, r)
        if cands:
            scoped = [c for c in cands if c[1] == prefer]
            if scoped:
                page, scope = scoped[0]
                method = f"structural markers + '{prefer}' heading"
            elif len(cands) >= 2 and all(s == "unknown" for _, s in cands) and prefer == "consolidated":
                # Annual reports print standalone statements before consolidated ones.
                page, scope = cands[1][0], "consolidated (inferred from order)"
                method = "structural markers + report order (standalone precedes consolidated)"
            else:
                page, scope = cands[0]
                method = "structural markers"
            score = 1.0 if scope == prefer else 0.8
            out[kind] = StatementLocation(kind, page, scope, score, method, rank_of.get(page),
                                          [p for p, _ in cands])
        elif ranked:
            page = ranked[0][0].page
            out[kind] = StatementLocation(kind, page, page_scope(pages[page - 1]), 0.4,
                                          "BM25 retrieval only (no structural match) - review", 1, [])
    return out


# --------------------------------------------------------------------------- #
# Line parsing
# --------------------------------------------------------------------------- #
def parse_amount(token: str) -> tuple[Optional[float], bool]:
    t = token.strip()
    if t in _DASH:
        return 0.0, True
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    t = t.strip("()").lstrip("-").replace(",", "")
    try:
        v = float(t)
    except ValueError:
        return None, False
    return (-v if neg else v), True


def _is_value(tok: str) -> bool:
    return tok in _DASH or bool(_VALUE.match(tok))


def _trailing_values(line: str) -> tuple[list[str], int]:
    toks = line.split()
    vals: list[str] = []
    while toks and _is_value(toks[-1]):
        vals.insert(0, toks.pop())
    return toks, len(vals)


def detect_periods(text: str) -> list[str]:
    head = "\n".join(text.split("\n")[:25])
    periods: list[str] = []
    for m in _FY_RANGE.finditer(head):
        start, end2 = int(m.group(1)), int(m.group(2))
        if (start + 1) % 100 == end2:
            key = f"FY{start + 1}"
            if key not in periods:
                periods.append(key)
    if len(periods) < 2:
        for m in _MARCH.finditer(head):
            key = f"FY{m.group(1)}"
            if key not in periods:
                periods.append(key)
    return periods[:2]


def detect_unit(text: str) -> str:
    m = _UNIT.search(text[:600])
    if not m:
        return "unknown"
    u = m.group(1).lower().rstrip("s")
    return {"lakh": "lakh", "million": "million", "thousand": "thousand", "billion": "billion"}.get(u, "crore")


def parse_statement(text: str, statement: str, page: int) -> ParsedStatement:
    periods = detect_periods(text)
    n = len(periods)
    rows: list[ParsedRow] = []
    issues: list[dict] = []
    section = ""
    pending: list[str] = []
    sections = _SECTIONS[statement]
    seen_values = False

    for line_no, raw_line in enumerate(text.split("\n"), start=1):
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if seen_values and any(low.startswith(s) for s in _STOP):
            break
        if pending and pending[-1].lower().endswith(_CONNECTORS) and not _trailing_values(line)[1]:
            pending.append(line)  # wrapped label, e.g. "... as per" / "Statement of Profit and Loss"
            continue
        if _SKIP.search(line) or _MARCH.search(line) or low.startswith((
                "notes ", "consolidated ", "standalone ", "for the year ended", "as at", "statement of",
                "balance sheet", "31st march")):
            if n and _FY_RANGE.search(line) or "31st march" in low or "as at" == low:
                pending = []
            continue
        if low in sections or low.rstrip(":") in sections:
            section = sections.get(low, sections.get(low.rstrip(":"), section))
            pending = []
            continue
        label_toks, nvals = _trailing_values(line)
        if nvals == 0 or n == 0:
            pending.append(line)
            pending = pending[-3:]
            continue
        tokens = line.split()
        value_toks = tokens[len(tokens) - nvals:]
        note_ref = None
        if nvals > n:
            extra = value_toks[: nvals - n]
            value_toks = value_toks[nvals - n:]
            if len(extra) == 1 and _NOTE.match(extra[0]) and label_toks:
                note_ref = extra[0]
            else:
                label_toks += extra
        label = " ".join(label_toks).strip(" .:*@#")
        joined = False
        if not label and pending:
            tail = pending[-1]
            k = len(pending) - 1
            while k > 0 and pending[k - 1].lower().endswith(_CONNECTORS):
                k -= 1
            label = " ".join(pending[k:]) if k < len(pending) - 1 else (
                " ".join(pending[-2:]) if len(pending) >= 2 and _continues(pending[-2]) else tail)
            joined = True
        elif label and pending and (label[0].islower() or label.startswith("(")) and _continues_any(pending[-1]):
            label = f"{pending[-1]} {label}"
            joined = True
        pending = []
        if not label or not re.search(r"[A-Za-z]", label):
            continue
        if len(value_toks) != n:
            issues.append({"type": "column_mismatch", "page": page, "label": label,
                           "detail": f"Found {len(value_toks)} value(s) for {n} year column(s); not assigned."})
            continue
        values: dict[str, Optional[float]] = {}
        raw: dict[str, str] = {}
        ok_all = True
        for p, tok in zip(periods, value_toks):
            v, ok = parse_amount(tok)
            values[p], raw[p] = v, tok
            ok_all &= ok
        seen_values = True
        conf = 0.97 if ok_all else 0.5
        if joined:
            conf = min(conf, 0.85)
        rows.append(ParsedRow(statement, section, label, note_ref, values, raw, page, line_no, conf,
                              "Label joined from wrapped lines" if joined else None))
    if n < 2:
        issues.append({"type": "periods", "page": page, "label": STATEMENTS[statement],
                       "detail": f"Detected {n} fiscal-year column(s) in the header; expected 2."})
    return ParsedStatement(statement, page, periods, detect_unit(text), rows, issues)


def _continues(line: str) -> bool:
    return not line.endswith((".", ":")) and len(line) > 25


def _continues_any(line: str) -> bool:
    return len(line) > 3 and not line.lower() in {s for d in _SECTIONS.values() for s in d}
