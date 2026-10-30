"""Build explainable lineage trees: result -> formula -> inputs -> source cells."""
from __future__ import annotations

from typing import Optional

from app.calculations.formulas import ALL_FORMULAS, FORMULAS
from app.normalization.taxonomy import BY_KEY

_FORMULA_BY_ID = {f.formula_id: f for f in ALL_FORMULAS}

NAMES = {
    "gross_profit": "Gross Profit", "operating_expenses": "Operating Expenses", "ebitda": "EBITDA",
    "net_income": "Net Income", "gross_margin": "Gross Margin %", "ebitda_margin": "EBITDA Margin %",
    "net_margin": "Net Margin %",
}


def metric_name(key: str) -> str:
    if key in NAMES:
        return NAMES[key]
    if key in BY_KEY:
        return BY_KEY[key].name
    return key.replace("_", " ").title()


def _fmt(metric: str) -> str:
    f = FORMULAS.get(metric)
    return f.output_format if f else "currency"


def _category_values(ws) -> dict:
    cache = getattr(ws, "_lineage_cv", None)
    return cache if cache is not None else ws.category_values()


def _source_node(ws, category: str, period: str) -> dict:
    cv = _category_values(ws).get(category, {})
    fv = cv.get(period)
    rows = []
    confs = []
    for rid in (fv.component_rows if fv else []):
        row = ws.rows[rid]
        vals, srcs = ws.effective_row_values(row)
        src = srcs.get(period)
        m = ws.mappings.get(rid)
        if src and vals.get(period) is not None:  # missing cells carry no confidence
            confs.append(src.confidence)
        rows.append({
            "row_id": rid,
            "raw_label": row.label,
            "value": vals.get(period),
            "raw_value": row.values.get(period),
            "scale": ws.extraction.scale,
            "sign_flipped": rid in ws.sign_flips,
            "source": src.model_dump() if src else None,
            "mapping": m.model_dump() if m else None,
        })
    if fv and not fv.component_rows and fv.source:  # reviewer-attested category
        confs.append(fv.source.confidence)
        rows.append({"row_id": None, "raw_label": fv.source.row_label, "value": fv.value, "raw_value": None,
                     "scale": 1, "sign_flipped": False, "source": fv.source.model_dump(), "mapping": None})
    expression = " + ".join(f"row_{i}" for i in range(1, len(rows) + 1)) or "-"
    return {
        "metric": category, "name": metric_name(category), "period": period, "kind": "source",
        "value": fv.value if fv else None, "status": fv.status.value if fv else "INCOMPLETE",
        "format": "currency",
        "formula": {"formula_id": "AGG_001", "name": "Category Aggregation", "expression": expression}
        if len(rows) > 1 else None,
        "normalized_category": {"key": category, "name": metric_name(category)},
        "sources": rows, "children": [],
        "confidence": min(confs) if confs else None,
    }


def _derived_node(ws, metric: str, period: str, depth: int) -> dict:
    res = ws.model["per_period"][metric][period]
    f = _FORMULA_BY_ID.get(res["formula_id"])
    children = []
    if depth > 0:
        for inp in res["inputs"]:
            children.append(node(ws, inp["name"], period, depth - 1))
    confs = [c["confidence"] for c in children if c.get("confidence") is not None]
    return {
        "metric": metric, "name": metric_name(metric), "period": period, "kind": "derived",
        "value": res["result"], "status": res["status"], "format": _fmt(metric),
        "formula": {"formula_id": res["formula_id"], "name": f.name if f else res["formula_id"],
                    "expression": res["expression"], "substituted": res["substituted"],
                    "registered_expression": f.expression if f else None},
        "inputs": res["inputs"], "missing_inputs": res["missing_inputs"],
        "children": children, "sources": [],
        "confidence": min(confs) if confs else None,
        "engine": res["engine"],
    }


def node(ws, metric: str, period: str, depth: int = 6) -> dict:
    model = ws.model
    if period == "YOY":
        res = model["growth"][metric]
        f = _FORMULA_BY_ID.get(res["formula_id"])
        children = [node(ws, metric, "T12", 1), node(ws, metric, "T12_PRIOR", 1)] if depth > 0 else []
        confs = [c["confidence"] for c in children if c.get("confidence") is not None]
        return {
            "metric": metric, "name": f"{metric_name(metric)} growth (YoY)", "period": "YOY", "kind": "derived",
            "value": res["result"], "status": res["status"], "format": "percent",
            "formula": {"formula_id": res["formula_id"], "name": f.name if f else res["formula_id"],
                        "expression": res["expression"], "substituted": res["substituted"]},
            "inputs": res["inputs"], "missing_inputs": res["missing_inputs"],
            "children": children, "sources": [], "confidence": min(confs) if confs else None,
            "engine": res["engine"],
        }
    if period in ("T12", "T12_PRIOR"):
        table = model["t12"] if period == "T12" else model["prior_t12"]
        res = table.get(metric)
        if res is None:
            return {"metric": metric, "name": metric_name(metric), "period": period, "kind": "t12",
                    "value": None, "status": "INCOMPLETE", "children": [], "sources": [], "format": _fmt(metric)}
        win = model["window"] if period == "T12" else model["prior_window"]
        f = _FORMULA_BY_ID.get(res["formula_id"])
        if res["formula_id"] == "T12_001":
            children = [node(ws, metric, p, 0) for p in win] if depth > 0 else []
            month_map = {f"m{i:02d}": p for i, p in enumerate(win, start=1)}
        else:  # ratio on T12 totals
            children = [node(ws, i["name"], period, 1) for i in res["inputs"]] if depth > 0 else []
            month_map = {}
        confs = [c["confidence"] for c in children if c.get("confidence") is not None]
        return {
            "metric": metric, "name": metric_name(metric), "period": period, "kind": "t12",
            "value": res["result"], "status": res["status"], "format": _fmt(metric),
            "formula": {"formula_id": res["formula_id"], "name": f.name if f else res["formula_id"],
                        "expression": res["expression"], "substituted": res["substituted"]},
            "inputs": res["inputs"], "missing_inputs": res["missing_inputs"], "month_map": month_map,
            "children": children, "sources": [], "confidence": min(confs) if confs else None,
            "engine": res["engine"],
        }
    if metric in model["per_period"]:
        return _derived_node(ws, metric, period, depth)
    return _source_node(ws, metric, period)


def build_lineage(ws, metric: str, period: str) -> dict:
    ws._lineage_cv = ws.category_values()  # computed once per request
    try:
        tree = node(ws, metric, period)
        leaves: list[dict] = []

        def walk(n: dict) -> None:
            for s in n.get("sources", []):
                leaves.append({"category": n["metric"], "period": n["period"], **s})
            for c in n.get("children", []):
                walk(c)

        if period in ("T12", "T12_PRIOR", "YOY"):
            # Aggregates: collect source cells from the full monthly lineage of every
            # period in the window(s), so the drawer shows every underlying cell.
            m = ws.model
            windows = {"T12": [m["window"]], "T12_PRIOR": [m["prior_window"] or []],
                       "YOY": [m["window"], m["prior_window"] or []]}[period]
            base_metrics = [metric]
            f = FORMULAS.get(metric)
            if f and f.output_format == "percent":
                base_metrics = [i["name"] for i in tree.get("inputs", [])] or [metric]
            for win in windows:
                for p in win:
                    for bm in base_metrics:
                        walk(node(ws, bm, p))
        else:
            walk(tree)
    finally:
        ws._lineage_cv = None
    confs = [l["source"]["confidence"] for l in leaves if l.get("source") and l.get("value") is not None]
    if confs and period in ("T12", "T12_PRIOR", "YOY"):
        tree["confidence"] = min(confs)
    docs = sorted({l["source"]["document_name"] for l in leaves if l.get("source")})
    pages = sorted({l["source"]["page"] for l in leaves if l.get("source") and l["source"].get("page")})
    return {"tree": tree, "leaf_sources": leaves, "documents": docs, "pages": pages,
            "calculation_status": "DETERMINISTIC" if tree["status"] == "DETERMINISTIC" else tree["status"]}


def value_of(model: dict, metric: str, period: str) -> Optional[float]:
    if period == "T12":
        r = model["t12"].get(metric)
        return r["result"] if r else None
    return model["values"].get(metric, {}).get(period)
