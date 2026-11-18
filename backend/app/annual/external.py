"""External context connectors (market / private-company intelligence).

External facts enrich the Insight Brief; they never feed the calculation engine.
Every fact carries its source and as-of date so AI insights can cite it, and its
numbers pass the same numeric guard as engine figures.

Connectors
* ``manual`` - facts pasted or uploaded by an analyst (e.g. an export from Tracxn,
  a broker note, a peer table). Always available.
* ``tracxn`` - slot for a live Tracxn connector. It needs API access and an agreed
  field mapping (and confirmation that the licence permits sending Tracxn data to an
  LLM and including it in reports). Until then it reports itself as not connected
  rather than inventing endpoints.
"""
from __future__ import annotations

import os
import uuid

from app.models.domain import utcnow

MAX_FACTS = 50
MAX_TEXT = 600


def providers() -> list[dict]:
    return [
        {"key": "manual", "name": "Manual import (analyst-provided facts)", "connected": True,
         "detail": "Paste facts from Tracxn exports, broker notes or peer tables, each with its source and date."},
        {"key": "tracxn", "name": "Tracxn", "connected": False,
         "configured": bool(os.getenv("TRACXN_API_KEY")),
         "detail": "Connector slot. Needs Tracxn API access, the field mapping for the entities you track, and "
                   "licence confirmation for LLM use and redistribution. Use manual import meanwhile."},
    ]


def validate_facts(items: list[dict]) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise ValueError("Provide a non-empty list of facts.")
    if len(items) > MAX_FACTS:
        raise ValueError(f"At most {MAX_FACTS} external facts per workspace.")
    out = []
    for it in items:
        text = str(it.get("text") or "").strip()
        source = str(it.get("source") or "").strip()
        if not text or not source:
            raise ValueError("Every external fact needs 'text' and 'source'.")
        out.append({"id": f"X{uuid.uuid4().hex[:5]}", "text": text[:MAX_TEXT], "source": source[:120],
                    "as_of": str(it.get("as_of") or "")[:40], "title": str(it.get("title") or "")[:120],
                    "provider": str(it.get("provider") or "manual")[:40], "added_at": utcnow()})
    return out
