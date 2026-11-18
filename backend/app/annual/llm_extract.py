"""LLM assistance for annual reports, always behind deterministic verification.

* ``structure_statement`` - fallback only, used when the deterministic parser
  reads too few lines from a located statement page. The model may only copy
  value tokens; each returned token must occur verbatim on that page or the row
  is rejected. Only that single page is sent.
* ``suggest_mappings`` - labels only (no values), restricted to taxonomy keys.
"""
from __future__ import annotations

import json
import logging

from app.annual.statements import ParsedRow, parse_amount
from app.annual.taxonomy import CATEGORIES
from app.services import llm

log = logging.getLogger("fiw.annual.llm")

STRUCTURE_SYSTEM = """You convert one page of a financial statement into JSON. Copy text exactly; never
calculate, round, reformat or infer numbers. For each line item that has a value for every year column, return
{"label": str, "section": str, "values": [str, ...]} where values are the value tokens exactly as printed
(e.g. "10,75,675", "(10,267)", "-"), in the same order as the year columns. Respond with JSON only:
{"rows": [...]}"""


def structure_statement(ws, provider: llm.LLMProvider, rep, kind: str, page: int, text: str,
                        periods: list[str]) -> tuple[list[ParsedRow], str]:
    if not provider.live or not hasattr(provider, "_chat"):
        return [], "LLM structuring fallback unavailable offline - flagged for review"
    if len(periods) < 2:
        return [], "no fiscal-year header detected - LLM fallback skipped"
    from app.annual.pipeline import record_exposure

    record_exposure(ws, provider, f"statement structuring fallback ({kind})", chars=len(text),
                    pages=[{"document": rep.document.filename, "page": page}], content=text)
    try:
        msg = provider._chat(
            [{"role": "system", "content": STRUCTURE_SYSTEM},
             {"role": "user", "content": f"YEAR_COLUMNS: {periods}\n\nPAGE_TEXT:\n{text[:12000]}"}],
            max_tokens=4000, temperature=0, response_format={"type": "json_object"})
        data = json.loads(msg.content or "{}")
    except Exception as exc:
        log.warning("LLM structuring failed: %s", exc)
        return [], f"LLM structuring failed ({exc.__class__.__name__}) - flagged for review"
    tokens = set(text.split())
    rows: list[ParsedRow] = []
    rejected = 0
    for i, r in enumerate(data.get("rows", []), start=1):
        vals = r.get("values") or []
        if not isinstance(r.get("label"), str) or len(vals) != len(periods) or \
                not all(isinstance(v, str) and v in tokens for v in vals):
            rejected += 1
            continue
        parsed = {p: parse_amount(v)[0] for p, v in zip(periods, vals)}
        rows.append(ParsedRow(kind, str(r.get("section") or ""), r["label"].strip(), None, parsed,
                              dict(zip(periods, vals)), page, i, 0.8,
                              "LLM-structured; every value token verified verbatim on the page"))
    return rows, f"LLM structured {len(rows)} rows ({rejected} rejected by verbatim-token verification)"


def suggest_mappings(provider: llm.LLMProvider, labels: list[str]) -> list[dict]:
    if not labels or not hasattr(provider, "_chat"):
        return []
    taxonomy = [{"key": c.key, "name": c.name, "statement": c.statement, "examples": c.synonyms[:3]}
                for c in CATEGORIES if c.key != "excluded"]
    system = ("You classify annual-report line-item labels into a fixed Ind AS taxonomy. Use only the keys "
              "provided; use null when unsure. Respond with JSON only: "
              '{"mappings": [{"label": str, "category": str|null, "confidence": number, "rationale": str}]}')
    try:
        msg = provider._chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": f"TAXONOMY:\n{json.dumps(taxonomy)}\n\nLABELS:\n{json.dumps(labels)}"}],
            max_tokens=2000, temperature=0, response_format={"type": "json_object"})
        data = json.loads(msg.content or "{}")
    except Exception as exc:
        log.warning("AI mapping suggestions failed: %s", exc)
        return []
    valid = {c.key for c in CATEGORIES}
    out = []
    for m in data.get("mappings", []):
        if isinstance(m, dict) and m.get("label") in labels and (m.get("category") is None or m.get("category") in valid):
            try:
                m["confidence"] = max(0.0, min(1.0, float(m.get("confidence", 0))))
            except (TypeError, ValueError):
                m["confidence"] = 0.0
            out.append(m)
    return out
