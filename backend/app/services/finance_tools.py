"""Deterministic data/calculation functions exposed to the AI layer as tools.

The LLM can only *request* these functions. Every number it receives comes from
the verified model built by the deterministic engine, together with the formula
ID that produced it, so explanations remain traceable.
"""
from __future__ import annotations

from typing import Any

from app.audit.lineage import build_lineage, metric_name
from app.calculations import engine
from app.services.formatting import fmt_currency, fmt_pct, fmt_period
from app.services.workspace import Workspace, incomplete_metrics, summarize_checks

METRIC_KEYS = ["revenue", "cogs", "gross_profit", "operating_expenses", "ebitda", "depreciation", "interest",
               "taxes", "net_income", "gross_margin", "ebitda_margin", "net_margin", "payroll", "rent",
               "sales_marketing", "technology", "general_admin", "other_opex"]
RATIOS = {"gross_margin", "ebitda_margin", "net_margin"}


def _fmt(metric: str, v):
    return fmt_pct(v) if metric in RATIOS else fmt_currency(v)


def _t12(ws: Workspace, metric: str) -> dict | None:
    return ws.model["t12"].get(metric)


def get_kpis(ws: Workspace) -> dict:
    m = ws.model
    out = {"window": f"{fmt_period(m['window'][0])} - {fmt_period(m['window'][-1])}", "metrics": {}}
    for k in ["revenue", "gross_profit", "operating_expenses", "ebitda", "net_income", "gross_margin",
              "ebitda_margin", "net_margin"]:
        r = _t12(ws, k)
        if r:
            out["metrics"][k] = {"name": metric_name(k), "value": r["result"], "display": _fmt(k, r["result"]),
                                 "status": r["status"], "formula_id": r["formula_id"]}
    g = m["growth"].get("revenue")
    out["metrics"]["revenue_growth_yoy"] = (
        {"name": "Revenue Growth (T-12 YoY)", "value": g["result"], "display": fmt_pct(g["result"], True),
         "status": g["status"], "formula_id": g["formula_id"]} if g else
        {"name": "Revenue Growth (T-12 YoY)", "value": None, "display": "not computable",
         "status": "INCOMPLETE", "reason": "No complete prior 12-month window in the source."})
    return out


def get_metric(ws: Workspace, metric: str, period: str = "T12") -> dict:
    lin = build_lineage(ws, metric, period)
    t = lin["tree"]
    return {"metric": metric, "name": t["name"], "period": period, "value": t["value"],
            "display": _fmt(metric, t["value"]), "status": t["status"], "formula": t.get("formula"),
            "missing_inputs": t.get("missing_inputs", []), "confidence": t.get("confidence")}


def get_monthly_series(ws: Workspace, metric: str) -> dict:
    series = ws.model["values"].get(metric)
    if series is None:
        return {"error": f"Unknown or unavailable metric '{metric}'"}
    return {"metric": metric, "name": metric_name(metric),
            "series": [{"period": p, "label": fmt_period(p), "value": series.get(p),
                        "display": _fmt(metric, series.get(p))} for p in ws.model["window"]]}


def rank_months(ws: Workspace, metric: str = "revenue", order: str = "desc", top: int = 3) -> dict:
    ranked = engine.rank_periods(ws.model, metric, descending=order != "asc")
    known = [r for r in ranked if r["value"] is not None]
    missing = [r["period"] for r in ranked if r["value"] is None]
    return {"metric": metric, "name": metric_name(metric), "order": order,
            "top": [{"period": r["period"], "label": fmt_period(r["period"]), "value": r["value"],
                     "display": _fmt(metric, r["value"])} for r in known[:top]],
            "excluded_incomplete_months": missing,
            "method": "Sorted monthly engine values within the T-12 window (deterministic)."}


def explain_calculation(ws: Workspace, metric: str, period: str = "T12") -> dict:
    lin = build_lineage(ws, metric, period)
    t = lin["tree"]

    def brief(n: dict) -> dict:
        return {"name": n["name"], "period": n["period"], "value": n["value"],
                "display": _fmt(n["metric"], n["value"]), "status": n["status"],
                "formula": (n.get("formula") or {}).get("expression")}

    definition = None
    cf = next((c for c in ws.model.get("crossfoot", []) if c["metric"] == metric), None)
    if period == "T12" and cf:
        calc = cf["calculation"]
        definition = {"formula_id": calc["formula_id"], "expression": calc["expression"],
                      "on_t12_totals": [{"name": metric_name(i["name"]), "value": i["value"],
                                         "display": _fmt(i["name"], i["value"])} for i in calc["inputs"]],
                      "crossfoot_passed": cf["passed"]}
    return {"metric": metric, "name": t["name"], "period": period, "value": t["value"],
            "display": _fmt(metric, t["value"]), "status": t["status"], "definition": definition,
            "formula_id": (t.get("formula") or {}).get("formula_id"),
            "formula": (t.get("formula") or {}).get("expression"),
            "substituted": (t.get("formula") or {}).get("substituted"),
            "inputs": [brief(c) for c in t["children"]][:12],
            "source_documents": lin["documents"], "source_pages": lin["pages"],
            "min_extraction_confidence": t.get("confidence")}


def expense_changes(ws: Workspace) -> dict:
    m = ws.model
    cats = ["cogs", *m["opex_components"], "depreciation", "interest", "taxes"]
    rows = []
    for c in cats:
        if c not in m["values"]:
            continue
        q = engine.quarter_shift(m, c)
        yoy = m["growth"].get(c)
        rows.append({
            "category": c, "name": metric_name(c),
            "t12": (_t12(ws, c) or {}).get("result"),
            "first3_avg": q.get("first3", {}).get("result"), "last3_avg": q.get("last3", {}).get("result"),
            "first3_to_last3_change": q.get("change", {}).get("result"),
            "yoy_t12_change": yoy["result"] if yoy else None,
        })
    ranked = sorted([r for r in rows if r["first3_to_last3_change"] is not None],
                    key=lambda r: r["first3_to_last3_change"], reverse=True)
    return {"categories": rows, "largest_increase": ranked[0] if ranked else None,
            "method": "AVG3_001 over first/last three months of the T-12 window, GROWTH_001 for % change; "
                      "YoY uses T-12 vs prior T-12 totals."}


def margin_trend(ws: Workspace) -> dict:
    m = ws.model
    out = {}
    for ratio in ["gross_margin", "ebitda_margin", "net_margin"]:
        s = engine.ratio_shift(m, ratio)
        out[ratio] = {"first3": s["first3"]["result"], "last3": s["last3"]["result"],
                      "change_pp": s["change_pp"]["result"],
                      "t12": (m["t12"].get(ratio) or {}).get("result"),
                      "prior_t12": (m["prior_t12"].get(ratio) or {}).get("result")}
    for metric in ["revenue", "ebitda", "operating_expenses", "gross_profit"]:
        out[f"{metric}_shift"] = engine.quarter_shift(m, metric).get("change", {}).get("result")
    out["window"] = [m["window"][0], m["window"][-1]]
    return out


def review_items(ws: Workspace) -> dict:
    open_checks = [c for c in ws.checks if c.status.value != "VALID" and not c.resolved]
    return {"summary": summarize_checks(ws.checks),
            "open_items": [{"status": c.status.value, "title": c.title, "detail": c.detail} for c in open_checks],
            "incomplete_metrics": incomplete_metrics(ws.model) if ws.model else []}


TOOLS: dict[str, dict[str, Any]] = {
    "get_kpis": {"fn": get_kpis, "description": "Headline T-12 KPIs from the verified model.",
                 "params": {}},
    "get_metric": {"fn": get_metric, "description": "Value, formula and status of one metric for a period "
                   "('T12', 'T12_PRIOR' or 'YYYY-MM').",
                   "params": {"metric": {"type": "string", "enum": METRIC_KEYS},
                              "period": {"type": "string"}}},
    "get_monthly_series": {"fn": get_monthly_series, "description": "Monthly values of a metric in the T-12 window.",
                           "params": {"metric": {"type": "string", "enum": METRIC_KEYS}}},
    "rank_months": {"fn": rank_months, "description": "Rank months in the T-12 window by a metric.",
                    "params": {"metric": {"type": "string", "enum": METRIC_KEYS},
                               "order": {"type": "string", "enum": ["desc", "asc"]},
                               "top": {"type": "integer"}}},
    "explain_calculation": {"fn": explain_calculation, "description": "Formula, substituted inputs and source "
                            "lineage for a metric.",
                            "params": {"metric": {"type": "string", "enum": METRIC_KEYS},
                                       "period": {"type": "string"}}},
    "expense_changes": {"fn": expense_changes, "description": "Change in each expense category across the "
                        "window and year over year.", "params": {}},
    "margin_trend": {"fn": margin_trend, "description": "Margin movement (first 3 vs last 3 months, T-12 vs "
                     "prior T-12) and revenue/EBITDA/opex shifts.", "params": {}},
    "review_items": {"fn": review_items, "description": "Open validation items and incomplete metrics that "
                     "require human review.", "params": {}},
}


def call_tool(ws: Workspace, name: str, args: dict) -> dict:
    if name not in TOOLS:
        return {"error": f"Unknown tool {name}"}
    try:
        return TOOLS[name]["fn"](ws, **(args or {}))
    except Exception as exc:  # surfaced to the model as a tool error
        return {"error": str(exc)}


def collect_numbers(obj: Any) -> list[float]:
    """Every numeric value in a tool/fact payload (for the numeric-claim guard)."""
    out: list[float] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out += collect_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += collect_numbers(v)
    return out
