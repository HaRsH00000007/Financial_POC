"""Lineage for annual metrics: result -> formula -> inputs -> statement line -> page.

Returns the same shape as the T-12 lineage so the UI's Audit Trail drawer renders
both. Inputs named ``<metric>_prev`` resolve to the previous fiscal year.
"""
from __future__ import annotations

from app.annual.engine import FORMULAS, MULTIPLE_KEYS, RATIO_KEYS
from app.annual.taxonomy import BY_KEY


def metric_name(key: str) -> str:
    if key in FORMULAS:
        return FORMULAS[key].name
    if key in BY_KEY:
        return BY_KEY[key].name
    return key.replace("_", " ").title()


def fmt_of(key: str) -> str:
    if key in RATIO_KEYS:
        return "percent"
    if key in MULTIPLE_KEYS:
        return "multiple"
    if key in ("eps_basic", "eps_diluted"):
        return "number"
    return "currency"


def _prev(ws, period: str) -> str | None:
    ps = ws.model["periods"]
    i = ps.index(period) if period in ps else -1
    return ps[i - 1] if i > 0 else None


def _source_node(ws, category: str, period: str, cv: dict) -> dict:
    fv = cv.get(category, {}).get(period)
    rows, confs = [], []
    for rid in (fv.component_rows if fv else []):
        row = ws.rows[rid]
        vals, srcs = ws.effective_row_values(row)
        src = srcs.get(period)
        if src and vals.get(period) is not None:
            confs.append(src.confidence)
        meta = ws.row_meta[rid]
        rows.append({"row_id": rid, "raw_label": f"{row.label}" + (f" ({meta.section})" if meta.section else ""),
                     "value": vals.get(period), "raw_value": row.values.get(period), "scale": 1,
                     "sign_flipped": False, "source": src.model_dump() if src else None,
                     "mapping": ws.mappings[rid].model_dump() if rid in ws.mappings else None})
    if fv and not fv.component_rows and fv.source:
        confs.append(fv.source.confidence)
        rows.append({"row_id": None, "raw_label": fv.source.row_label, "value": fv.value, "raw_value": None,
                     "scale": 1, "sign_flipped": False, "source": fv.source.model_dump(), "mapping": None})
    status = fv.status.value if fv else "INCOMPLETE"
    if fv is None and category in ws.model.get("not_printed", {}).get(period, []):
        status = "NOT_PRINTED"
    return {"metric": category, "name": metric_name(category), "period": period, "kind": "source",
            "value": fv.value if fv else None, "status": status, "format": fmt_of(category),
            "formula": {"formula_id": "AGG_001", "name": "Category Aggregation",
                        "expression": " + ".join(f"row_{i}" for i in range(1, len(rows) + 1))} if len(rows) > 1 else None,
            "normalized_category": {"key": category, "name": metric_name(category)},
            "sources": rows, "children": [], "confidence": min(confs) if confs else None}


def node(ws, metric: str, period: str, cv: dict, depth: int = 6) -> dict:
    per = ws.model["per_period"].get(metric)
    if per is None or period not in per:
        return _source_node(ws, metric, period, cv)
    res = per[period]
    f = FORMULAS[metric]
    children = []
    if depth > 0:
        for inp in res["inputs"]:
            name = inp["name"]
            if name.endswith("_prev"):
                p = _prev(ws, period)
                if p:
                    children.append(node(ws, name.removesuffix("_prev"), p, cv, depth - 1))
            else:
                children.append(node(ws, name, period, cv, depth - 1))
    confs = [c["confidence"] for c in children if c.get("confidence") is not None]
    return {"metric": metric, "name": metric_name(metric), "period": period, "kind": "derived",
            "value": res["result"], "status": res["status"], "format": fmt_of(metric),
            "formula": {"formula_id": res["formula_id"], "name": f.name, "expression": res["expression"],
                        "substituted": res["substituted"], "registered_expression": f.expression},
            "inputs": res["inputs"], "missing_inputs": res["missing_inputs"], "children": children, "sources": [],
            "confidence": min(confs) if confs else None, "engine": res["engine"]}


def build_lineage(ws, metric: str, period: str) -> dict:
    if period not in ws.model["periods"]:
        raise KeyError(period)
    cv = ws.category_values()
    tree = node(ws, metric, period, cv)
    leaves: list[dict] = []

    def walk(n: dict) -> None:
        for s in n.get("sources", []):
            leaves.append({"category": n["metric"], "period": n["period"], **s})
        for c in n.get("children", []):
            walk(c)

    walk(tree)
    docs = sorted({l["source"]["document_name"] for l in leaves if l.get("source")})
    pages = sorted({l["source"]["page"] for l in leaves if l.get("source") and l["source"].get("page")})
    return {"tree": tree, "leaf_sources": leaves, "documents": docs, "pages": pages,
            "calculation_status": tree["status"]}
