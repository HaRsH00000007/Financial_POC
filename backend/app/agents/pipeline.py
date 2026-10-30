"""Coordinator-Specialist agent orchestration for the T-12 workflow.

    Coordinator
      -> Ingestion agent       (probabilistic assist: document classification; rule-based table parsing)
      -> Normalization agent   (rules first, AI suggestions only for what rules cannot map)
      -> Validation agent      (deterministic rules + engine reconciliation)
      -> Calculation agent     (deterministic engine only)
      -> Synthesis agent       (AI narrative over verified outputs, numeric-claim guarded)

Every step writes to the workspace's hash-chained audit log.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from contextlib import contextmanager

from app.calculations import engine
from app.extraction.extractors import extract
from app.models.domain import Document, Status, utcnow
from app.normalization.normalizer import map_row, user_override
from app.normalization.taxonomy import BY_KEY
from app.services import llm
from app.services.workspace import (
    STORE,
    Resolution,
    Workspace,
    detect_sign_flips,
    incomplete_metrics,
    run_validation,
    summarize_checks,
)

LAYER = {
    "Coordinator": "orchestration",
    "Ingestion Agent": "probabilistic",
    "Normalization Agent": "probabilistic",
    "Validation Agent": "deterministic",
    "Calculation Agent": "deterministic",
    "Synthesis Agent": "probabilistic",
}


@contextmanager
def agent_step(ws: Workspace, agent: str, action: str):
    run = {"id": uuid.uuid4().hex[:8], "agent": agent, "layer": LAYER.get(agent, "orchestration"),
           "action": action, "status": "running", "started_at": utcnow(), "outputs": {}}
    ws.agent_runs.append(run)
    t0 = time.perf_counter()
    try:
        yield run
        run["status"] = "completed"
    except Exception as exc:
        run["status"] = "error"
        run["error"] = str(exc)
        ws.audit.record("system", "agent.error", f"{agent} failed: {exc}", agent=agent)
        raise
    finally:
        run["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        run["finished_at"] = utcnow()


def ingest(data: bytes, filename: str, is_demo: bool = False) -> Workspace:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "xlsx", "csv"):
        raise ValueError("Unsupported file type. Upload a PDF, XLSX or CSV file.")
    doc_id = uuid.uuid4().hex[:10]
    extraction = extract(data, ext, doc_id, filename)
    doc = Document(id=doc_id, filename=filename, file_type=ext, size_bytes=len(data),
                   sha256=hashlib.sha256(data).hexdigest(), is_demo=is_demo,
                   pages=extraction.pages, sheets=extraction.sheets)
    ws = STORE.create(doc, extraction)
    provider = llm.get_provider()

    ws.audit.record("system", "workspace.created", f"Workspace created for {filename}",
                    agent="Coordinator", details={"document_sha256": doc.sha256, "demo": is_demo})
    with agent_step(ws, "Coordinator", "Plan T-12 spreading workflow") as run:
        run["outputs"] = {"plan": ["ingest", "normalize", "validate", "await human review", "calculate",
                                   "synthesize"], "llm_provider": provider.name}
        ws.audit.record("ai", "coordinator.plan", "Planned 6-step T-12 workflow", agent="Coordinator",
                        details=run["outputs"])

    with agent_step(ws, "Ingestion Agent", "Classify document and extract monthly tables") as run:
        sample = " ".join(r.label for r in extraction.rows)
        ws.classification = provider.classify_document(filename, sample)
        run["outputs"] = {
            "document_type": ws.classification.get("document_type"),
            "classification_method": ws.classification.get("method"),
            "pages": extraction.pages, "sheets": extraction.sheets, "rows": len(extraction.rows),
            "periods": len(extraction.periods), "scale": extraction.scale, "log": extraction.log,
            "entity": extraction.entity_name,
        }
        ws.audit.record("ai", "ingestion.classified", f"Classified as: {ws.classification.get('document_type')}",
                        agent="Ingestion Agent", details=ws.classification)
        ws.audit.record("system", "ingestion.extracted",
                        f"Extracted {len(extraction.rows)} rows across {len(extraction.periods)} periods",
                        agent="Ingestion Agent", details={"log": extraction.log, "issues": extraction.issues})

    normalize(ws, provider)
    validate(ws)
    return ws


def normalize(ws: Workspace, provider: llm.LLMProvider) -> None:
    with agent_step(ws, "Normalization Agent", "Map source labels to canonical taxonomy") as run:
        for row in ws.rows.values():
            ws.mappings[row.id] = map_row(row)
        unmapped = [m for m in ws.mappings.values() if m.category is None]
        ai_used = 0
        if unmapped and provider.live:
            suggestions = {s["label"]: s for s in provider.suggest_mappings([m.raw_label for m in unmapped])}
            for m in unmapped:
                s = suggestions.get(m.raw_label)
                if s and s.get("category") and s.get("confidence", 0) >= 0.6:
                    ws.mappings[m.row_id] = m.model_copy(update={
                        "category": s["category"], "method": "ai_suggested",
                        "confidence": round(float(s["confidence"]), 3), "status": Status.WARNING,
                        "rationale": f"AI suggestion ({provider.model}): {s.get('rationale', '')} Confirm before use."})
                    ai_used += 1
        methods: dict[str, int] = {}
        for m in ws.mappings.values():
            methods[m.method] = methods.get(m.method, 0) + 1
        ws.sign_flips = detect_sign_flips(ws)
        run["outputs"] = {"methods": methods, "ai_suggestions_applied": ai_used,
                          "unmapped": sum(1 for m in ws.mappings.values() if m.category is None),
                          "sign_convention_flips": len(ws.sign_flips)}
        ws.audit.record("ai" if ai_used else "system", "normalization.completed",
                        f"Mapped {len(ws.mappings)} rows ({methods})", agent="Normalization Agent",
                        details=run["outputs"])
    ws.stage = "normalized"


def validate(ws: Workspace) -> None:
    with agent_step(ws, "Validation Agent", "Run validation rules and reconcile source subtotals") as run:
        ws.checks = run_validation(ws)
        summary = summarize_checks(ws.checks)
        run["outputs"] = summary
        ws.audit.record("engine", "validation.completed",
                        (f"Validation: {summary['counts']['VALID']} valid, {summary['counts']['WARNING']} warnings, "
                         f"{summary['counts']['REVIEW_REQUIRED']} require review"), agent="Validation Agent", details=summary)
    ws.stage = "validated"
    if ws.model is not None:
        ws.stale = True


def update_mapping(ws: Workspace, row_id: str, category: str | None, user: str = "reviewer") -> None:
    old = ws.mappings[row_id]
    ws.mappings[row_id] = user_override(old, category)
    ws.sign_flips = detect_sign_flips(ws)
    ws.audit.record("user", "mapping.override",
                    f'"{old.raw_label}": {old.category or "unmapped"} -> {category or "unmapped"}',
                    agent=user, details={"row_id": row_id, "from": old.category, "to": category,
                                         "previous_method": old.method})
    validate(ws)


def add_resolution(ws: Workspace, payload: dict, user: str = "reviewer") -> Resolution:
    note = (payload.get("note") or "").strip()
    if not note:
        raise ValueError("A justification note is required for every manual resolution.")
    rtype = payload["type"]
    if rtype == "value":
        row_id, period = payload["row_id"], payload["period"]
        if row_id not in ws.rows or period not in ws.extraction.periods:
            raise ValueError("Unknown row or period")
        if payload.get("value") is None:
            raise ValueError("A value is required")
        ws.resolutions = [r for r in ws.resolutions if not (r.type == "value" and r.row_id == row_id and r.period == period)]
        res = Resolution(id=uuid.uuid4().hex[:8], type="value", note=note, row_id=row_id, period=period,
                         value=float(payload["value"]))
        summary = f'Manual value for "{ws.rows[row_id].label}" {period}: {res.value:,.2f}'
    elif rtype == "category_zero":
        cat = payload["category"]
        if cat not in BY_KEY or BY_KEY[cat].kind != "input":
            raise ValueError("Only input categories can be attested as zero")
        res = Resolution(id=uuid.uuid4().hex[:8], type="category_zero", note=note, category=cat)
        summary = f"{BY_KEY[cat].name} attested as zero for all periods"
    else:
        raise ValueError(f"Unknown resolution type {rtype}")
    ws.resolutions.append(res)
    ws.audit.record("user", f"resolution.{rtype}", summary, agent=user,
                    details={**payload, "resolution_id": res.id})
    validate(ws)
    return res


def remove_resolution(ws: Workspace, res_id: str, user: str = "reviewer") -> None:
    before = len(ws.resolutions)
    ws.resolutions = [r for r in ws.resolutions if r.id != res_id]
    if len(ws.resolutions) == before:
        raise ValueError("Unknown resolution")
    ws.audit.record("user", "resolution.removed", f"Resolution {res_id} withdrawn", agent=user)
    validate(ws)


def calculate(ws: Workspace) -> dict:
    with agent_step(ws, "Calculation Agent", "Execute deterministic formula engine") as run:
        inputs, reported = ws.engine_inputs()
        model = engine.build_model(ws.extraction.periods, inputs, reported)
        ws.model = model
        ws.stale = False
        ws.commentary = None
        n_results = sum(len(v) for v in model["per_period"].values()) + len(model["t12"]) + \
            len(model["prior_t12"]) + len(model["growth"])
        inc = incomplete_metrics(model)
        run["outputs"] = {
            "engine": model["engine"], "formulas_evaluated": n_results,
            "evaluation_order": list(model["per_period"].keys()),
            "window": [model["window"][0], model["window"][-1]] if model["window"] else [],
            "reconciliations": len(model["reconciliations"]),
            "reconciliation_breaks": sum(1 for r in model["reconciliations"] if not r["matches"]),
            "incomplete_values": len(inc), "llm_involved": False,
        }
        ws.audit.record("engine", "calculation.completed",
                        f"Deterministic engine evaluated {n_results} formula results", agent="Calculation Agent",
                        details={**run["outputs"], "open_review_items": summarize_checks(ws.checks)["counts"],
                                 "t12": {k: v["result"] for k, v in model["t12"].items()}})
    ws.stage = "calculated"
    return model


def synthesize(ws: Workspace) -> dict:
    provider = llm.get_provider()
    mock = llm.MockProvider()
    with agent_step(ws, "Synthesis Agent", "Generate commentary from verified outputs") as run:
        facts = llm.build_facts(ws)
        out = llm.guarded(lambda: provider.narrate(facts), facts, lambda: mock.narrate(facts))
        ws.commentary = {
            **out, "provider": provider.name, "model": provider.model, "generated_at": utcnow(),
            "label": "AI-generated commentary based on verified financial calculations.",
            "disclaimer": llm.DISCLAIMER, "facts": facts,
        }
        run["outputs"] = {"provider": provider.name, "numeric_check": out["numeric_check"], "note": out["note"]}
        ws.audit.record("ai", "synthesis.commentary", "Commentary generated from verified facts",
                        agent="Synthesis Agent", details=run["outputs"])
    return ws.commentary
