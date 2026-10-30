"""HTTP API. Routes are thin: they delegate to agents/services and never calculate."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.agents import pipeline
from app.audit.lineage import build_lineage
from app.calculations.formulas import ALL_FORMULAS, dependency_graph
from app.data.demo import SAMPLES
from app.normalization.taxonomy import CATEGORIES
from app.services import evaluation, llm
from app.services.formatting import verify_numeric_claims
from app.services.finance_tools import collect_numbers
from app.services.workspace import STORE, Workspace, incomplete_metrics, summarize_checks

router = APIRouter(prefix="/api")
MAX_UPLOAD = 20 * 1024 * 1024


def _ws(ws_id: str) -> Workspace:
    ws = STORE.get(ws_id)
    if not ws:
        raise HTTPException(404, "Workspace not found (the POC keeps state in memory; restart clears it).")
    return ws


def serialize(ws: Workspace) -> dict:
    ex = ws.extraction
    cat_vals = ws.category_values()
    return {
        "id": ws.id,
        "stage": ws.stage,
        "stale": ws.stale,
        "document": ws.document.model_dump(),
        "classification": ws.classification,
        "entity": ex.entity_name,
        "periods": ex.periods,
        "scale": ex.scale,
        "extraction_log": ex.log,
        "rows": [
            {**r.model_dump(), "effective_values": ws.effective_row_values(r)[0],
             "sign_flipped": r.id in ws.sign_flips}
            for r in ws.rows.values()
        ],
        "mappings": {k: m.model_dump() for k, m in ws.mappings.items()},
        "resolutions": [r.__dict__ for r in ws.resolutions],
        "checks": [c.model_dump() for c in ws.checks],
        "check_summary": summarize_checks(ws.checks),
        "categories_present": sorted(cat_vals.keys()),
        "agent_runs": ws.agent_runs,
        "has_model": ws.model is not None,
        "llm": llm.provider_info(),
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "llm": llm.provider_info()}


@router.get("/meta")
def meta() -> dict:
    return {
        "taxonomy": [c.model_dump() for c in CATEGORIES],
        "formulas": [f.model_dump() for f in ALL_FORMULAS],
        "graph": dependency_graph(),
        "llm": llm.provider_info(),
        "samples": list(SAMPLES.keys()),
    }


@router.get("/samples/{name}")
def sample(name: str) -> Response:
    if name not in SAMPLES:
        raise HTTPException(404, "Unknown sample")
    media = {"pdf": "application/pdf", "csv": "text/csv",
             "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}[name.rsplit(".", 1)[1]]
    return Response(SAMPLES[name](), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------- T-12 workflow ------------------------------ #
@router.post("/workspaces/demo")
def create_demo(fmt: str = "pdf") -> dict:
    name = next((n for n in SAMPLES if n.endswith("." + fmt)), None)
    if not name:
        raise HTTPException(400, "fmt must be pdf, xlsx or csv")
    ws = pipeline.ingest(SAMPLES[name](), name, is_demo=True)
    return serialize(ws)


@router.post("/workspaces/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File exceeds 20 MB POC limit")
    if not data:
        raise HTTPException(400, "Empty file")
    try:
        ws = pipeline.ingest(data, file.filename or "upload", is_demo=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(422, f"Could not read the document: {exc}")
    if not ws.rows:
        ws.audit.record("system", "ingestion.empty", "No monthly line items found", agent="Ingestion Agent")
    return serialize(ws)


@router.get("/workspaces/{ws_id}")
def get_workspace(ws_id: str) -> dict:
    return serialize(_ws(ws_id))


class MappingUpdate(BaseModel):
    row_id: str
    category: Optional[str]


@router.put("/workspaces/{ws_id}/mappings")
def update_mappings(ws_id: str, updates: list[MappingUpdate]) -> dict:
    ws = _ws(ws_id)
    for u in updates:
        if u.row_id not in ws.mappings:
            raise HTTPException(400, f"Unknown row {u.row_id}")
        try:
            pipeline.update_mapping(ws, u.row_id, u.category)
        except ValueError as exc:
            raise HTTPException(400, str(exc))
    return serialize(ws)


class ResolutionIn(BaseModel):
    type: str
    note: str
    row_id: Optional[str] = None
    period: Optional[str] = None
    value: Optional[float] = None
    category: Optional[str] = None


@router.post("/workspaces/{ws_id}/resolutions")
def add_resolution(ws_id: str, body: ResolutionIn) -> dict:
    ws = _ws(ws_id)
    try:
        pipeline.add_resolution(ws, body.model_dump())
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc))
    return serialize(ws)


@router.delete("/workspaces/{ws_id}/resolutions/{res_id}")
def delete_resolution(ws_id: str, res_id: str) -> dict:
    ws = _ws(ws_id)
    try:
        pipeline.remove_resolution(ws, res_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return serialize(ws)


@router.post("/workspaces/{ws_id}/calculate")
def calculate(ws_id: str) -> dict:
    ws = _ws(ws_id)
    if not ws.extraction.periods:
        raise HTTPException(400, "No periods extracted - nothing to calculate.")
    pipeline.calculate(ws)
    return get_model(ws_id)


@router.get("/workspaces/{ws_id}/model")
def get_model(ws_id: str) -> dict:
    ws = _ws(ws_id)
    if ws.model is None:
        raise HTTPException(409, "Model not calculated yet")
    return {"model": ws.model, "incomplete": incomplete_metrics(ws.model), "stale": ws.stale,
            "is_demo": ws.document.is_demo, "entity": ws.extraction.entity_name,
            "check_summary": summarize_checks(ws.checks)}


@router.get("/workspaces/{ws_id}/lineage")
def lineage(ws_id: str, metric: str, period: str = "T12") -> dict:
    ws = _ws(ws_id)
    if ws.model is None:
        raise HTTPException(409, "Model not calculated yet")
    try:
        return build_lineage(ws, metric, period)
    except KeyError as exc:
        raise HTTPException(404, f"No lineage for {metric} / {period}: {exc}")


@router.get("/workspaces/{ws_id}/audit")
def audit(ws_id: str) -> dict:
    ws = _ws(ws_id)
    return {"events": [e.model_dump() for e in ws.audit.events], "integrity": ws.audit.verify()}


@router.post("/workspaces/{ws_id}/commentary")
def commentary(ws_id: str) -> dict:
    ws = _ws(ws_id)
    if ws.model is None:
        raise HTTPException(409, "Run the deterministic calculation first")
    return pipeline.synthesize(ws)


class AssistantIn(BaseModel):
    question: str
    history: list[dict[str, Any]] = []


@router.post("/workspaces/{ws_id}/assistant")
def assistant(ws_id: str, body: AssistantIn) -> dict:
    ws = _ws(ws_id)
    if ws.model is None:
        raise HTTPException(409, "Run the deterministic calculation first")
    provider = llm.get_provider()
    note = None
    try:
        out = provider.assistant(ws, body.question, body.history)
    except Exception as exc:
        out = llm.MockProvider().assistant(ws, body.question, body.history)
        note = f"AI provider error ({exc.__class__.__name__}); answered by the offline assistant."
    # Numeric-claim guard: numbers in the answer must come from tool results.
    check = verify_numeric_claims(out["answer"], collect_numbers([c["result"] for c in out["tool_calls"]]))
    if not check["passed"] or not out["answer"].strip():
        reason = (f"{len(check['unverified'])} figure(s) not traceable to tool results "
                  f"({', '.join(check['unverified'][:3])})" if not check["passed"] else "an empty answer")
        out = llm.MockProvider().assistant(ws, body.question, body.history)
        check = verify_numeric_claims(out["answer"], collect_numbers([c["result"] for c in out["tool_calls"]]))
        note = f"The AI answer contained {reason}; replaced with the deterministic answer."
    ws.audit.record("ai", "assistant.answer", f"Q: {body.question[:120]}", agent="Finance Assistant",
                    details={"tools": [c["tool"] for c in out["tool_calls"]], "numeric_check": check,
                             "provider": provider.name})
    return {**out, "numeric_check": check, "provider": provider.name, "note": note,
            "disclaimer": llm.DISCLAIMER}


# ------------------------------- Evaluation --------------------------------- #
@router.get("/evaluation/framework")
def eval_framework() -> dict:
    return evaluation.framework()


@router.post("/evaluation/summary")
def eval_summary(body: dict) -> dict:
    return evaluation.summarize(body)


@router.post("/evaluation/report")
def eval_report(body: dict) -> dict:
    return {"markdown": evaluation.report_markdown(body), "summary": evaluation.summarize(body)}
