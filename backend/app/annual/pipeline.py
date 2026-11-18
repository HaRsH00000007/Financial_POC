"""Coordinator-Specialist orchestration for annual reports (RAG pipeline).

    Coordinator
      -> Retrieval agent      (deterministic: page text, chunking, BM25 index, statement location)
      -> Extraction agent     (deterministic parser; LLM structuring only as a verified fallback)
      -> Normalization agent  (rules first; AI suggestions only for what rules cannot map)
      -> Validation agent     (deterministic: identities, restatements, coverage)
      -> Calculation agent    (deterministic engine only)
      -> Insight agent        (AI over the Insight Brief only, numeric-claim guarded)

Every time report content is sent to a language model, the pages/chunks and the
character count are written to the workspace's AI exposure ledger and the audit log.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

from app.agents.pipeline import agent_step
from app.annual import engine as aengine
from app.annual import llm_extract
from app.annual.pdftext import page_texts
from app.annual.rag import BM25Index, chunk_pages
from app.annual.statements import STATEMENTS, locate, parse_statement
from app.annual.taxonomy import BY_KEY, map_annual_row
from app.annual.workspace import AnnualWorkspace, ExtractionInfo, ReportFile, RowMeta, new_id, run_validation
from app.models.domain import Document, RawLineItem, SourceReference, Status, utcnow
from app.normalization.normalizer import user_override
from app.services import llm
from app.services.workspace import STORE, summarize_checks

LAYER = {"Coordinator": "orchestration", "Retrieval Agent": "deterministic", "Extraction Agent": "deterministic",
         "Normalization Agent": "probabilistic", "Validation Agent": "deterministic",
         "Calculation Agent": "deterministic", "Insight Agent": "probabilistic"}
MAX_REPORTS = 5
_ENTITY = re.compile(r"\b([A-Z][A-Za-z&]+(?:\s+[A-Z][A-Za-z&]+){0,4}\s+Limited)\b")
_ABBR = {"income_statement": "IS", "balance_sheet": "BS", "cash_flow": "CF"}


def record_exposure(ws: AnnualWorkspace, provider: llm.LLMProvider, purpose: str, *, chars: int,
                    pages: list[dict] | None = None, chunks: list[str] | None = None, content: str) -> None:
    """Log exactly what leaves the platform for a hosted LLM."""
    if not provider.live:
        return
    entry = {"at": utcnow(), "purpose": purpose, "provider": provider.name, "model": provider.model,
             "chars": chars, "pages": pages or [], "chunks": chunks or [], "content": content}
    ws.exposure.append(entry)
    ws.audit.record("ai", "ai.context_shared", f"Shared with {provider.name} for {purpose}: {chars:,} characters",
                    agent="AI Exposure Ledger", details={k: v for k, v in entry.items() if k != "content"})


def _entity(pages: list[str]) -> str | None:
    hits = Counter(m.group(1).strip() for p in pages[:10] for m in _ENTITY.finditer(p))
    return hits.most_common(1)[0][0] if hits else None


def ingest_reports(files: list[tuple[bytes, str]]) -> AnnualWorkspace:
    if not files:
        raise ValueError("Upload at least one annual report (PDF).")
    if len(files) > MAX_REPORTS:
        raise ValueError(f"At most {MAX_REPORTS} reports per workspace.")
    for _, name in files:
        if not name.lower().endswith(".pdf"):
            raise ValueError(f'"{name}" is not a PDF. Annual reports must be uploaded as PDF.')
    provider = llm.get_provider()
    index = BM25Index()
    reports: list[ReportFile] = []
    rows: dict[str, RawLineItem] = {}
    meta: dict[str, RowMeta] = {}
    issues: list[dict] = []
    log: list[str] = []
    entity = None

    ws = AnnualWorkspace(id=new_id(), reports=reports, rows=rows, row_meta=meta, index=index,
                         extraction=ExtractionInfo(periods=[], log=log, issues=issues))
    ws.audit.record("system", "workspace.created", f"Annual-report workspace created for {len(files)} report(s)",
                    agent="Coordinator", details={"files": [n for _, n in files]})
    with agent_step(ws, "Coordinator", "Plan annual-report RAG workflow") as run:
        run["outputs"] = {"plan": ["index pages", "locate statements", "parse & verify", "normalize", "validate",
                                   "await human review", "calculate", "insight brief", "AI insights"],
                          "llm_provider": provider.name,
                          "llm_scope": "statement pages only on parser failure; retrieved passages for Q&A; "
                                       "Insight Brief for insights - never the full report"}
        ws.audit.record("ai", "coordinator.plan", "Planned annual-report workflow", agent="Coordinator",
                        details=run["outputs"])

    with agent_step(ws, "Retrieval Agent", "Read pages, build BM25 index, locate statements") as run:
        out = []
        for data, name in files:
            doc_id = f"r{len(reports) + 1}"
            pages, text_engine = page_texts(data)
            doc = Document(id=doc_id, filename=name, file_type="pdf", size_bytes=len(data),
                           sha256=hashlib.sha256(data).hexdigest(), pages=len(pages))
            entity = entity or _entity(pages)
            prelim = BM25Index()
            prelim.add(chunk_pages(doc_id, name, pages, {}))
            locs = locate(pages, prelim, doc_id)
            kinds = {loc.page: "statement" for loc in locs.values()}
            index.add(chunk_pages(doc_id, name, pages, kinds))
            reports.append(ReportFile(document=doc, pages=pages, fiscal_years=[], unit="unknown",
                                      statements=locs, text_engine=text_engine))
            out.append({"document": name, "pages": len(pages), "text_engine": text_engine,
                        "statements": {k: {"page": v.page, "scope": v.scope, "method": v.method,
                                           "bm25_rank": v.bm25_rank} for k, v in locs.items()}})
            log.append(f"{name}: {len(pages)} pages read ({text_engine}); statements at " +
                       ", ".join(f"{_ABBR[k]} p.{v.page}" for k, v in locs.items()))
        run["outputs"] = {"reports": out, "index": index.stats()}
        ws.audit.record("system", "retrieval.indexed",
                        f"Indexed {index.stats()['chunks']} chunks from {len(files)} report(s); statements located",
                        agent="Retrieval Agent", details=run["outputs"])

    with agent_step(ws, "Extraction Agent", "Parse statements into source-referenced line items") as run:
        counts = {}
        for rep in reports:
            fys: list[str] = []
            units = set()
            for kind, loc in rep.statements.items():
                text = rep.pages[loc.page - 1]
                parsed = parse_statement(text, kind, loc.page)
                method = "pdf-statement-parser"
                if len(parsed.rows) < 8:
                    llm_rows, note = llm_extract.structure_statement(ws, provider, rep, kind, loc.page, text,
                                                                    parsed.periods)
                    log.append(f"{rep.document.filename} {_ABBR[kind]}: parser read {len(parsed.rows)} rows; {note}")
                    if llm_rows:
                        parsed.rows, method = llm_rows, "llm-structured (values verified against page text)"
                for i in parsed.issues:
                    issues.append({**i, "document": rep.document.filename})
                units.add(parsed.unit)
                for p in parsed.periods:
                    if p not in fys:
                        fys.append(p)
                for n, prow in enumerate(parsed.rows, start=1):
                    rid = f"{rep.document.id}-{_ABBR[kind]}{n:02d}"
                    sources = {p: SourceReference(
                        document_id=rep.document.id, document_name=rep.document.filename, page=prow.page,
                        cell=f"{_ABBR[kind]} line {prow.line_no}", row_label=prow.label, raw_text=prow.raw.get(p),
                        extraction_method=method, confidence=prow.confidence) for p in prow.values}
                    rows[rid] = RawLineItem(id=rid, label=prow.label, values=prow.values, sources=sources,
                                            confidence=prow.confidence, notes=[prow.note] if prow.note else [])
                    meta[rid] = RowMeta(rep.document.id, kind, prow.section, prow.note_ref)
                counts[f"{rep.document.filename} {_ABBR[kind]}"] = len(parsed.rows)
            rep.fiscal_years = sorted(fys)
            rep.unit = units.pop() if len(units) == 1 else ("mixed" if units else "unknown")
        reports.sort(key=lambda r: max(r.fiscal_years) if r.fiscal_years else "")  # oldest -> latest
        ws.extraction.periods = sorted({p for r in reports for p in r.fiscal_years})
        ws.extraction.entity_name = entity
        ws.unit = reports[-1].unit if reports else "crore"
        run["outputs"] = {"rows": len(rows), "per_statement": counts, "periods": ws.extraction.periods,
                          "issues": len(issues), "entity": entity}
        ws.audit.record("system", "extraction.completed",
                        f"Extracted {len(rows)} line items for {', '.join(ws.extraction.periods)}",
                        agent="Extraction Agent", details=run["outputs"])

    years = ws.extraction.periods
    ws.classification = {
        "document_type": f"Annual report - consolidated financial statements ({years[0]}-{years[-1]})" if years
        else "Annual report (no statements found)",
        "method": "statement locator (structural markers + BM25)", "confidence": None}
    if provider.live and rows:
        headings = " | ".join(dict.fromkeys(r.label for r in rows.values()))[:3000]
        record_exposure(ws, provider, "document classification (row labels only, no values)",
                        chars=len(headings), content=headings)
        llm_cls = provider.classify_document(reports[-1].document.filename, headings)
        ws.classification["llm_document_type"] = llm_cls.get("document_type")

    normalize(ws, provider)
    validate(ws)
    STORE._items[ws.id] = ws  # shared in-memory store (POC)
    return ws


def normalize(ws: AnnualWorkspace, provider: llm.LLMProvider) -> None:
    with agent_step(ws, "Normalization Agent", "Map statement lines to the Ind AS taxonomy") as run:
        for rid, row in ws.rows.items():
            m = ws.row_meta[rid]
            ws.mappings[rid] = map_annual_row(rid, m.statement, m.section, row.label)
        unmapped = [m for m in ws.mappings.values() if m.category is None]
        ai_used = 0
        if unmapped and provider.live:
            labels = sorted({m.raw_label for m in unmapped})
            record_exposure(ws, provider, "mapping suggestions (labels only, no values)",
                            chars=sum(len(x) for x in labels), content="\n".join(labels))
            suggestions = {s["label"]: s for s in llm_extract.suggest_mappings(provider, labels)}
            for m in unmapped:
                s = suggestions.get(m.raw_label)
                stmt = ws.row_meta[m.row_id].statement
                if s and s.get("category") in BY_KEY and BY_KEY[s["category"]].statement == stmt \
                        and s.get("confidence", 0) >= 0.6:
                    ws.mappings[m.row_id] = m.model_copy(update={
                        "category": s["category"], "method": "ai_suggested",
                        "confidence": round(float(s["confidence"]), 3), "status": Status.WARNING,
                        "rationale": f"AI suggestion ({provider.model}): {s.get('rationale', '')} Confirm before use."})
                    ai_used += 1
        methods = Counter(m.method for m in ws.mappings.values())
        run["outputs"] = {"methods": dict(methods), "ai_suggestions_applied": ai_used,
                          "unmapped": sum(1 for m in ws.mappings.values() if m.category is None)}
        ws.audit.record("ai" if ai_used else "system", "normalization.completed",
                        f"Mapped {len(ws.mappings)} rows ({dict(methods)})", agent="Normalization Agent",
                        details=run["outputs"])
    ws.stage = "normalized"


def validate(ws: AnnualWorkspace) -> None:
    with agent_step(ws, "Validation Agent", "Identity checks, restatements, coverage") as run:
        ws.checks = run_validation(ws)
        summary = summarize_checks(ws.checks)
        run["outputs"] = summary
        ws.audit.record("engine", "validation.completed",
                        (f"Validation: {summary['counts']['VALID']} valid, {summary['counts']['WARNING']} warnings, "
                         f"{summary['counts']['REVIEW_REQUIRED']} require review"), agent="Validation Agent",
                        details=summary)
    ws.stage = "validated"
    if ws.model is not None:
        ws.stale = True


def update_mapping(ws: AnnualWorkspace, row_id: str, category: str | None, user: str = "reviewer") -> None:
    if category is not None:
        cat = BY_KEY.get(category)
        if cat is None:
            raise ValueError(f"Unknown category {category!r}")
        stmt = ws.row_meta[row_id].statement
        if cat.statement not in (stmt, "none"):
            raise ValueError(f"{cat.name} belongs to the {cat.statement.replace('_', ' ')}; this row is on the "
                             f"{stmt.replace('_', ' ')}.")
    old = ws.mappings[row_id]
    ws.mappings[row_id] = user_override(old, None).model_copy(update={
        "category": category, "confidence": 1.0 if category else 0.0,
        "status": Status.VALID if category else Status.REVIEW_REQUIRED,
        "rationale": "Set by reviewer." if category else "Cleared by reviewer."})
    ws.audit.record("user", "mapping.override",
                    f'"{old.raw_label}": {old.category or "unmapped"} -> {category or "unmapped"}', agent=user,
                    details={"row_id": row_id, "from": old.category, "to": category, "previous_method": old.method})
    validate(ws)


def calculate(ws: AnnualWorkspace) -> dict:
    with agent_step(ws, "Calculation Agent", "Execute deterministic annual formula registry") as run:
        inputs, reported = ws.engine_inputs()
        model = aengine.build_model(ws.extraction.periods, inputs, reported)
        model["restatements"] = ws.restatements()
        ws.model = model
        ws.stale = False
        ws.commentary = None
        n_results = sum(len(v) for v in model["per_period"].values())
        breaks = [i for i in model["identities"] if not i["matches"]]
        run["outputs"] = {"engine": model["engine"], "formulas_evaluated": n_results,
                          "evaluation_order": [m for m in model["order"] if not m.endswith("_growth")],
                          "periods": model["periods"], "identity_checks": len(model["identities"]),
                          "identity_breaks": len(breaks), "restatements": len(model["restatements"]),
                          "incomplete_values": len(aengine.incomplete(model)), "llm_involved": False}
        ws.audit.record("engine", "calculation.completed",
                        f"Deterministic engine evaluated {n_results} formula results", agent="Calculation Agent",
                        details={**run["outputs"], "open_review_items": summarize_checks(ws.checks)["counts"]})
    ws.stage = "calculated"
    return model


def statement_rows(ws: AnnualWorkspace) -> dict:
    """Statements as printed, for the UI: latest report's line order, values per year."""
    out: dict[str, list[dict]] = {k: [] for k in STATEMENTS}
    seen: set[tuple] = set()
    for rep in sorted(ws.reports, key=lambda r: ws.report_rank(r.document.id), reverse=True):
        for rid, row in ws.rows.items():
            meta = ws.row_meta[rid]
            if meta.document_id != rep.document.id:
                continue
            key = (meta.statement, meta.section, row.label.lower())
            if key in seen:
                continue
            seen.add(key)
            m = ws.mappings.get(rid)
            vals = {}
            for r2, row2 in ws.rows.items():  # same printed line across reports (latest wins)
                m2 = ws.row_meta[r2]
                if (m2.statement, m2.section, row2.label.lower()) == key:
                    for p, v in ws.effective_row_values(row2)[0].items():
                        if p not in vals or ws.report_rank(m2.document_id) > vals[p][1]:
                            vals[p] = (v, ws.report_rank(m2.document_id), row2.sources.get(p))
            out[meta.statement].append({
                "row_id": rid, "label": row.label, "section": meta.section, "note_ref": meta.note_ref,
                "category": m.category if m else None,
                "kind": BY_KEY[m.category].kind if m and m.category else None,
                "values": {p: v[0] for p, v in vals.items()},
                "pages": {p: (v[2].page if v[2] else None) for p, v in vals.items()},
            })
    return out


def add_resolution(ws: AnnualWorkspace, payload: dict, user: str = "reviewer"):
    from app.services.workspace import Resolution

    note = (payload.get("note") or "").strip()
    if not note:
        raise ValueError("A justification note is required for every manual resolution.")
    rtype = payload["type"]
    if rtype == "value":
        row_id, period = payload["row_id"], payload["period"]
        if row_id not in ws.rows or period not in ws.documents[ws.row_meta[row_id].document_id].fiscal_years:
            raise ValueError("Unknown row or fiscal year")
        if payload.get("value") is None:
            raise ValueError("A value is required")
        ws.resolutions = [r for r in ws.resolutions
                          if not (r.type == "value" and r.row_id == row_id and r.period == period)]
        res = Resolution(id=new_id()[:8], type="value", note=note, row_id=row_id, period=period,
                         value=float(payload["value"]))
        summary = f'Manual value for "{ws.rows[row_id].label}" {period}: {res.value:,.2f}'
    elif rtype == "category_zero":
        cat = payload["category"]
        if cat not in BY_KEY or BY_KEY[cat].kind != "input":
            raise ValueError("Only input categories can be attested as zero")
        res = Resolution(id=new_id()[:8], type="category_zero", note=note, category=cat)
        summary = f"{BY_KEY[cat].name} attested as zero for all years"
    else:
        raise ValueError(f"Unknown resolution type {rtype}")
    ws.resolutions.append(res)
    ws.audit.record("user", f"resolution.{rtype}", summary, agent=user, details={**payload, "resolution_id": res.id})
    validate(ws)
    return res


def remove_resolution(ws: AnnualWorkspace, res_id: str, user: str = "reviewer") -> None:
    before = len(ws.resolutions)
    ws.resolutions = [r for r in ws.resolutions if r.id != res_id]
    if len(ws.resolutions) == before:
        raise ValueError("Unknown resolution")
    ws.audit.record("user", "resolution.removed", f"Resolution {res_id} withdrawn", agent=user)
    validate(ws)


def serialize(ws: AnnualWorkspace) -> dict:
    from app.annual import external
    from app.annual.taxonomy import CATEGORIES

    cat_vals = ws.category_values()
    rows = []
    for r in ws.rows.values():
        meta = ws.row_meta[r.id]
        rows.append({**r.model_dump(), "effective_values": ws.effective_row_values(r)[0], "sign_flipped": False,
                     "statement": meta.statement, "section": meta.section, "document_id": meta.document_id,
                     "note_ref": meta.note_ref,
                     "context": f"{ws.documents[meta.document_id].document.filename} · {_ABBR[meta.statement]}"
                                f"{' · ' + meta.section if meta.section else ''}"})
    return {
        "id": ws.id, "kind": "annual", "stage": ws.stage, "stale": ws.stale,
        "document": ws.document.model_dump(),
        "documents": [{**rep.document.model_dump(), "fiscal_years": rep.fiscal_years, "unit": rep.unit,
                       "text_engine": rep.text_engine,
                       "statements": {k: {"page": v.page, "scope": v.scope, "method": v.method, "score": v.score,
                                          "bm25_rank": v.bm25_rank, "candidates": v.candidates}
                                      for k, v in rep.statements.items()}}
                      for rep in ws.reports],
        "classification": ws.classification, "entity": ws.extraction.entity_name,
        "periods": ws.extraction.periods, "scale": 1, "currency": ws.currency, "unit": ws.unit,
        "extraction_log": ws.extraction.log, "rows": rows,
        "mappings": {k: m.model_dump() for k, m in ws.mappings.items()},
        "resolutions": [r.__dict__ for r in ws.resolutions],
        "checks": [c.model_dump() for c in ws.checks], "check_summary": summarize_checks(ws.checks),
        "categories_present": sorted(cat_vals.keys()), "agent_runs": ws.agent_runs,
        "has_model": ws.model is not None, "llm": llm.provider_info(),
        "taxonomy": [c.model_dump() for c in CATEGORIES],
        "index": ws.index.stats(),
        "exposure": exposure_summary(ws),
        "external": ws.external, "external_providers": external.providers(),
    }


def exposure_summary(ws: AnnualWorkspace) -> dict:
    pages_total = sum(len(r.pages) for r in ws.reports)
    shared = {(p["document"], p["page"]) for e in ws.exposure for p in e["pages"]}
    return {"provider_live": llm.get_provider().live, "events": len(ws.exposure),
            "chars_shared": sum(e["chars"] for e in ws.exposure),
            "report_chars_total": sum(len(p) for r in ws.reports for p in r.pages),
            "pages_total": pages_total, "pages_shared": len(shared),
            "ledger": [{k: v for k, v in e.items() if k != "content"} | {"preview": e["content"][:400]}
                       for e in ws.exposure[-30:]]}
