"""Deterministic engine for annual statements.

Uses the same safe Decimal evaluator and ``run_formula`` as the T-12 engine; only
the formula registry differs. Sum formulas are declared as signed terms so that a
component a company does not report at all (e.g. no excise duty) is dropped and
listed as "not reported" instead of being zero-filled. A component that is
reported but missing for one year makes that year INCOMPLETE.
"""
from __future__ import annotations

from typing import Mapping, Optional

from app.calculations import expression as expr
from app.calculations.engine import run_formula
from app.calculations.formulas import RECONCILIATION
from app.models.domain import CalcStatus, Formula

ENGINE = "deterministic-decimal-v1 / annual-registry-v1"


def _sum(fid, metric, name, terms, description="", optional=()):
    expression = " ".join(f"{'-' if s == '-' else '+'} {t}" for s, t in terms).lstrip("+ ").strip()
    return Formula(formula_id=fid, metric=metric, name=name, expression=expression,
                   inputs=[t for _, t in terms], optional_inputs=list(optional), description=description)


def _ratio(fid, metric, name, expression, description=""):
    return Formula(formula_id=fid, metric=metric, name=name, expression=expression,
                   inputs=expr.dependencies(expression), output_format="percent", description=description)


def _plain(fid, metric, name, expression, description=""):
    return Formula(formula_id=fid, metric=metric, name=name, expression=expression,
                   inputs=expr.dependencies(expression), description=description)


TERMS: dict[str, list[tuple[str, str]]] = {
    "total_income": [("+", "revenue"), ("+", "other_income")],
    "total_expenses": [("+", "materials_cost"), ("+", "purchases_traded"), ("+", "inventory_change"),
                       ("+", "excise_duty"), ("+", "employee_costs"), ("+", "finance_costs"),
                       ("+", "depreciation"), ("+", "other_expenses")],
    "total_tax": [("+", "current_tax"), ("+", "deferred_tax")],
    "profit": [("+", "pbt"), ("+", "associates_share"), ("-", "total_tax"), ("+", "discontinued_profit")],
    "nca_total": [("+", "nca_investments"), ("+", "nca_other")],
    "ca_total": [("+", "inventories"), ("+", "current_investments"), ("+", "trade_receivables"),
                 ("+", "cash_equivalents"), ("+", "ca_other")],
    "total_assets": [("+", "nca_total"), ("+", "ca_total")],
    "total_equity": [("+", "share_capital"), ("+", "other_equity"), ("+", "nci")],
    "ncl_total": [("+", "borrowings_nc"), ("+", "lease_nc"), ("+", "ncl_other")],
    "cl_total": [("+", "borrowings_c"), ("+", "lease_c"), ("+", "trade_payables"), ("+", "cl_other")],
    "total_liabilities": [("+", "ncl_total"), ("+", "cl_total")],
    "total_debt": [("+", "borrowings_nc"), ("+", "borrowings_c")],
    "net_debt": [("+", "total_debt"), ("-", "cash_equivalents"), ("-", "current_investments")],
    "net_cash_change": [("+", "cfo"), ("+", "cfi"), ("+", "cff")],
    "closing_cash": [("+", "opening_cash"), ("+", "net_cash_change"), ("+", "cash_adjust_add"),
                     ("-", "cash_adjust_less")],
    "fcf": [("+", "cfo"), ("+", "capex")],
}
OPTIONAL = {"purchases_traded", "inventory_change", "excise_duty", "associates_share", "discontinued_profit",
            "nci", "nca_investments", "current_investments", "lease_nc", "lease_c", "cash_adjust_add",
            "cash_adjust_less", "nca_other", "ca_other", "ncl_other", "cl_other"}

FORMULAS: dict[str, Formula] = {f.metric: f for f in [
    _sum("TI_001", "total_income", "Total Income", TERMS["total_income"], "Revenue from operations plus other income."),
    _sum("TE_001", "total_expenses", "Total Expenses", TERMS["total_expenses"],
         "Sum of the expense lines of the Statement of Profit and Loss.", OPTIONAL),
    _plain("PBT_001", "pbt", "Profit Before Associates & Tax", "total_income - total_expenses"),
    _sum("TAX_001", "total_tax", "Total Tax Expense", TERMS["total_tax"]),
    _sum("PAT_001", "profit", "Profit for the Year", TERMS["profit"],
         "PBT plus share of associates/JVs, less tax, plus discontinued operations.", OPTIONAL),
    _plain("EBITDA_A01", "ebitda", "EBITDA", "pbt + finance_costs + depreciation",
           "Profit before associates & tax, adding back finance costs and depreciation/amortisation. Includes "
           "other income, as Indian companies typically present it."),
    _plain("EBITDA_A02", "ebitda_ex_oi", "EBITDA excl. Other Income", "ebitda - other_income"),
    _ratio("EBITDAM_A01", "ebitda_margin", "EBITDA Margin %", "ebitda / revenue"),
    _ratio("NM_A01", "net_margin", "Net Margin %", "profit / revenue"),
    _ratio("ETR_001", "effective_tax_rate", "Effective Tax Rate %", "total_tax / pbt"),
    _plain("ICR_001", "interest_cover", "Interest Cover (x)", "ebitda / finance_costs"),
    _sum("NCA_001", "nca_total", "Total Non-Current Assets", TERMS["nca_total"], optional=OPTIONAL),
    _sum("CA_001", "ca_total", "Total Current Assets", TERMS["ca_total"], optional=OPTIONAL),
    _sum("TA_001", "total_assets", "Total Assets", TERMS["total_assets"]),
    _sum("EQ_001", "total_equity", "Total Equity", TERMS["total_equity"], optional=OPTIONAL),
    _sum("NCL_001", "ncl_total", "Total Non-Current Liabilities", TERMS["ncl_total"], optional=OPTIONAL),
    _sum("CL_001", "cl_total", "Total Current Liabilities", TERMS["cl_total"], optional=OPTIONAL),
    _sum("TL_001", "total_liabilities", "Total Liabilities", TERMS["total_liabilities"]),
    _plain("BAL_001", "balance_difference", "Balance Check (Assets - Equity - Liabilities)",
           "total_assets - total_equity - total_liabilities", "Must be zero for a balanced balance sheet."),
    _sum("DEBT_001", "total_debt", "Total Borrowings", TERMS["total_debt"]),
    _sum("NDEBT_001", "net_debt", "Net Debt", TERMS["net_debt"],
         "Borrowings less cash and cash equivalents and current investments.", OPTIONAL),
    _plain("DE_001", "debt_to_equity", "Debt to Equity (x)", "total_debt / total_equity"),
    _plain("NDE_001", "net_debt_to_ebitda", "Net Debt to EBITDA (x)", "net_debt / ebitda"),
    _plain("CR_001", "current_ratio", "Current Ratio (x)", "ca_total / cl_total"),
    _ratio("ROE_001", "roe", "Return on Equity % (closing equity)", "profit / total_equity",
           "Profit for the year over closing total equity (including NCI)."),
    _sum("NCC_001", "net_cash_change", "Net Change in Cash", TERMS["net_cash_change"]),
    _sum("CC_001", "closing_cash", "Closing Cash (recomputed)", TERMS["closing_cash"], optional=OPTIONAL),
    _sum("FCF_001", "fcf", "Free Cash Flow", TERMS["fcf"],
         "Operating cash flow plus capital expenditure (capex is printed as a negative outflow)."),
    _ratio("CCONV_001", "cash_conversion", "Cash Conversion % (CFO / EBITDA)", "cfo / ebitda"),
    _plain("TIE_001", "cash_tieout", "Cash Tie-out (CF closing - BS cash)", "closing_cash_reported - cash_equivalents",
           "Cross-statement check: closing cash in the cash-flow statement must equal the balance sheet."),
]}

GROWTH_METRICS = ["revenue", "ebitda", "profit", "cfo", "total_assets", "net_debt"]
for _m in GROWTH_METRICS:
    FORMULAS[f"{_m}_growth"] = Formula(
        formula_id="GROWTH_A01", metric=f"{_m}_growth", name=f"YoY Growth - {_m.replace('_', ' ')}",
        expression=f"({_m} - {_m}_prev) / {_m}_prev", inputs=[_m, f"{_m}_prev"], output_format="percent",
        description="Growth versus the previous fiscal year.")

RATIO_KEYS = {k for k, f in FORMULAS.items() if f.output_format == "percent"}
MULTIPLE_KEYS = {"interest_cover", "debt_to_equity", "net_debt_to_ebitda", "current_ratio"}

# Printed subtotal -> engine metric it reconciles against (identity checks).
IDENTITIES: list[dict] = [
    {"id": "total_income", "reported": "total_income_reported", "metric": "total_income", "statement": "income_statement"},
    {"id": "total_expenses", "reported": "total_expenses_reported", "metric": "total_expenses", "statement": "income_statement"},
    {"id": "pbt", "reported": "pbt_reported", "metric": "pbt", "statement": "income_statement"},
    {"id": "profit", "reported": "profit_reported", "metric": "profit", "statement": "income_statement"},
    {"id": "nca_total", "reported": "total_nca_reported", "metric": "nca_total", "statement": "balance_sheet"},
    {"id": "ca_total", "reported": "total_ca_reported", "metric": "ca_total", "statement": "balance_sheet"},
    {"id": "total_assets", "reported": "total_assets_reported", "metric": "total_assets", "statement": "balance_sheet"},
    {"id": "total_equity", "reported": "total_equity_reported", "metric": "total_equity", "statement": "balance_sheet"},
    {"id": "ncl_total", "reported": "total_ncl_reported", "metric": "ncl_total", "statement": "balance_sheet"},
    {"id": "cl_total", "reported": "total_cl_reported", "metric": "cl_total", "statement": "balance_sheet"},
    {"id": "total_liabilities", "reported": "total_liabilities_reported", "metric": "total_liabilities", "statement": "balance_sheet"},
    {"id": "net_cash_change", "reported": "net_change_reported", "metric": "net_cash_change", "statement": "cash_flow"},
    {"id": "closing_cash", "reported": "closing_cash_reported", "metric": "closing_cash", "statement": "cash_flow"},
]
ZERO_CHECKS = [  # derived metrics that must evaluate to zero
    {"id": "balance", "metric": "balance_difference", "statement": "balance_sheet",
     "name": "Balance sheet balances (assets = equity + liabilities)"},
    {"id": "cash_tieout", "metric": "cash_tieout", "statement": "cross_statement",
     "name": "Cash-flow closing cash equals balance-sheet cash"},
]


def _toposort() -> list[str]:
    order: list[str] = []
    visiting: set[str] = set()

    def visit(m: str) -> None:
        if m in order or m not in FORMULAS:
            return
        if m in visiting:
            raise ValueError(f"Circular annual formula dependency at {m}")
        visiting.add(m)
        for d in expr.dependencies(FORMULAS[m].expression):
            visit(d.removesuffix("_prev") if d.endswith("_prev") else d)
        visiting.discard(m)
        order.append(m)

    for m in FORMULAS:
        visit(m)
    return order


ORDER = _toposort()


def tolerance(n_terms: int) -> float:
    """Printed lines are rounded to whole units; a sum of n rounded lines may drift."""
    return max(1.0, 0.5 * n_terms)


def build_model(periods: list[str], inputs: Mapping[str, Mapping[str, Optional[float]]],
                reported: Mapping[str, Mapping[str, Optional[float]]]) -> dict:
    periods = sorted(periods)
    present = set(inputs) | set(reported)
    not_reported = sorted({t for terms in TERMS.values() for _, t in terms
                           if t in OPTIONAL and t not in present and t not in FORMULAS})
    per_period: dict[str, dict[str, dict]] = {m: {} for m in ORDER}
    values: dict[str, dict[str, Optional[float]]] = {}
    for c, series in {**inputs, **reported}.items():
        values[c] = {p: series.get(p) for p in periods}

    sources = {**inputs, **reported}
    not_printed: dict[str, list[str]] = {}
    for i, p in enumerate(periods):
        prev = periods[i - 1] if i > 0 else None
        env: dict[str, Optional[float]] = {c: s.get(p) for c, s in values.items()}
        # Optional components not printed in the statement used for this year are dropped for
        # that year (a printed-but-unreadable value stays None and makes the year INCOMPLETE).
        absent = {t for t in OPTIONAL if t not in sources or p not in sources[t]}
        if absent - set(not_reported):
            not_printed[p] = sorted(absent - set(not_reported))
        for metric in ORDER:
            f = FORMULAS[metric]
            override = None
            if metric in TERMS:
                terms = [(s, t) for s, t in TERMS[metric] if t not in absent]
                override = " ".join(f"{'-' if s == '-' else '+'} {t}" for s, t in terms).lstrip("+ ").strip()
            if metric.endswith("_growth"):
                if prev is None:
                    continue
                base = metric.removesuffix("_growth")
                env[f"{base}_prev"] = values.get(base, {}).get(prev)
            res = run_formula(f, env, metric=metric, period=p, expression_override=override,
                              derived_names=[m for m in ORDER if m != metric])
            if f.output_format != "percent" and metric in MULTIPLE_KEYS and res.result is not None:
                res.result = round(res.result, 4)
            res.engine = ENGINE
            per_period[metric][p] = res.model_dump()
            env[metric] = res.result
            values.setdefault(metric, {})[p] = res.result

    identities: list[dict] = []
    for ident in IDENTITIES:
        if ident["reported"] not in reported:
            continue
        n_terms = len(TERMS.get(ident["metric"], [])) or 2
        for p in periods:
            rv = reported[ident["reported"]].get(p)
            cv = values.get(ident["metric"], {}).get(p)
            if rv is None or cv is None:
                continue
            res = run_formula(RECONCILIATION, {"reported": rv, "computed": cv},
                              metric=f"{ident['metric']}_variance", period=p)
            identities.append({"id": ident["id"], "metric": ident["metric"], "reported_category": ident["reported"],
                               "statement": ident["statement"], "period": p, "reported": rv, "computed": cv,
                               "variance": res.result, "tolerance": tolerance(n_terms),
                               "matches": res.result is not None and abs(res.result) <= tolerance(n_terms),
                               "calculation": res.model_dump()})
    for zc in ZERO_CHECKS:
        for p in periods:
            r = per_period[zc["metric"]].get(p)
            if not r or r["result"] is None:
                continue
            identities.append({"id": zc["id"], "metric": zc["metric"], "reported_category": None,
                               "statement": zc["statement"], "period": p, "reported": 0.0, "computed": r["result"],
                               "variance": r["result"], "tolerance": tolerance(4),
                               "matches": abs(r["result"]) <= tolerance(4), "name": zc["name"], "calculation": r})

    latest = periods[-1] if periods else None
    prior = periods[-2] if len(periods) >= 2 else None
    return {
        "kind": "annual", "engine": ENGINE, "periods": periods, "latest": latest, "prior": prior,
        "values": values, "per_period": per_period, "identities": identities, "not_reported": not_reported,
        "not_printed": not_printed, "order": ORDER,
    }


def incomplete(model: dict) -> list[dict]:
    out = []
    for metric, per in model["per_period"].items():
        for p, r in per.items():
            if r["status"] != CalcStatus.DETERMINISTIC.value:
                out.append({"metric": metric, "period": p, "status": r["status"], "missing": r["missing_inputs"]})
    return out


def graph() -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    depth: dict[str, int] = {}

    def node_depth(m: str) -> int:
        if m not in FORMULAS:
            return 0
        if m not in depth:
            deps = [d.removesuffix("_prev") for d in expr.dependencies(FORMULAS[m].expression)]
            depth[m] = 1 + max((node_depth(d) for d in deps if d != m), default=0)
        return depth[m]

    for m in ORDER:
        if m.endswith("_growth") or m in ("balance_difference", "cash_tieout"):
            continue
        f = FORMULAS[m]
        nodes[m] = {"id": m, "label": f.name, "kind": "derived", "formula_id": f.formula_id,
                    "expression": f.expression, "depth": node_depth(m), "format": f.output_format}
        for d in expr.dependencies(f.expression):
            if d not in nodes and d not in FORMULAS:
                nodes[d] = {"id": d, "label": d, "kind": "input", "depth": 0}
            edges.append({"from": d, "to": m})
    return {"nodes": list(nodes.values()), "edges": edges, "order": [m for m in ORDER if m in nodes]}
