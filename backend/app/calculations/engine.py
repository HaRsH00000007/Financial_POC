"""Deterministic financial calculation engine.

The engine consumes normalized, source-referenced ``FinancialValue`` inputs and
produces ``CalculationResult`` records. It is pure: the same inputs always give
the same outputs, it has no I/O, and it never consults an LLM.

Public single-purpose functions (``calculate_gross_profit`` etc.) exist so each
calculation can be unit-tested in isolation; they all route through the same
registered formulas that the full model build uses.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Mapping, Optional, Sequence

from app.calculations import expression as expr
from app.calculations.formulas import (
    AGGREGATE,
    AVERAGE_3,
    DERIVED_ORDER,
    DIFFERENCE,
    FORMULAS,
    GROWTH,
    OPEX_COMPONENTS,
    RECONCILIATION,
    T12_SUM,
)
from app.models.domain import CalcStatus, CalculationInput, CalculationResult, Formula

Number = Optional[float | int | Decimal]

CENT = Decimal("0.01")
RATIO_Q = Decimal("0.000001")

SOURCE_INPUTS = ["revenue", "cogs", *OPEX_COMPONENTS, "depreciation", "interest", "taxes"]
CURRENCY_METRICS = [
    "revenue", "cogs", "gross_profit", *OPEX_COMPONENTS, "operating_expenses",
    "ebitda", "depreciation", "interest", "taxes", "net_income",
]
RATIO_METRICS = ["gross_margin", "ebitda_margin", "net_margin"]
REPORTED_SUBTOTALS = {
    "gross_profit_reported": "gross_profit",
    "operating_expenses_reported": "operating_expenses",
    "ebitda_reported": "ebitda",
    "net_income_reported": "net_income",
}


def _quantize(value: Decimal, fmt: str) -> float:
    q = RATIO_Q if fmt == "percent" else CENT
    return float(value.quantize(q, rounding=ROUND_HALF_UP))


def run_formula(
    formula: Formula,
    values: Mapping[str, Number],
    *,
    metric: str | None = None,
    period: str = "",
    expression_override: str | None = None,
    derived_names: Iterable[str] = (),
) -> CalculationResult:
    """Evaluate one registered formula and return a fully-described result."""
    expression = expression_override or formula.expression
    names = expr.dependencies(expression)
    result, missing, undefined = expr.evaluate(expression, values)
    derived = set(derived_names)
    if missing:
        status = CalcStatus.INCOMPLETE
    elif undefined:
        status = CalcStatus.UNDEFINED
    else:
        status = CalcStatus.DETERMINISTIC
    return CalculationResult(
        metric=metric or formula.metric,
        period=period,
        formula_id=formula.formula_id,
        expression=expression,
        substituted=expr.substitute(expression, {n: _f(values.get(n)) for n in names}),
        inputs=[
            CalculationInput(name=n, value=_f(values.get(n)), kind="derived" if n in derived else "source")
            for n in names
        ],
        result=None if result is None else _quantize(result, formula.output_format),
        status=status,
        missing_inputs=missing,
    )


def _f(v: Number) -> Optional[float]:
    return None if v is None else float(v)


# --------------------------------------------------------------------------- #
# Single-purpose, independently testable calculation functions
# --------------------------------------------------------------------------- #
def calculate_gross_profit(revenue: Number, cogs: Number) -> Optional[float]:
    return run_formula(FORMULAS["gross_profit"], {"revenue": revenue, "cogs": cogs}).result


def calculate_operating_expenses(**components: Number) -> Optional[float]:
    present = [c for c in OPEX_COMPONENTS if c in components]
    if not present:
        return None
    return run_formula(
        FORMULAS["operating_expenses"], components, expression_override=" + ".join(present)
    ).result


def calculate_ebitda(gross_profit: Number, operating_expenses: Number) -> Optional[float]:
    return run_formula(
        FORMULAS["ebitda"], {"gross_profit": gross_profit, "operating_expenses": operating_expenses}
    ).result


def calculate_net_income(
    ebitda: Number, depreciation: Number, interest: Number, taxes: Number
) -> Optional[float]:
    return run_formula(
        FORMULAS["net_income"],
        {"ebitda": ebitda, "depreciation": depreciation, "interest": interest, "taxes": taxes},
    ).result


def calculate_margin(numerator: Number, revenue: Number) -> Optional[float]:
    return run_formula(FORMULAS["ebitda_margin"], {"ebitda": numerator, "revenue": revenue}).result


def calculate_growth(current: Number, prior: Number) -> Optional[float]:
    return run_formula(GROWTH, {"current": current, "prior": prior}).result


def calculate_t12(monthly_values: Sequence[Number]) -> Optional[float]:
    return t12_result(monthly_values).result


def t12_result(monthly_values: Sequence[Number], metric: str = "t12_total", period: str = "T12") -> CalculationResult:
    if len(monthly_values) != 12:
        raise ValueError(f"T-12 requires exactly 12 monthly values, got {len(monthly_values)}")
    return run_formula(
        T12_SUM,
        {f"m{i:02d}": v for i, v in enumerate(monthly_values, start=1)},
        metric=metric,
        period=period,
    )


def aggregate_rows(row_values: Sequence[Number], metric: str = "category_total", period: str = "") -> CalculationResult:
    """Deterministically sum the source rows mapped to one category."""
    if not row_values:
        raise ValueError("aggregate_rows needs at least one row")
    names = [f"row_{i}" for i in range(1, len(row_values) + 1)]
    return run_formula(AGGREGATE, dict(zip(names, row_values)), metric=metric, period=period,
                       expression_override=" + ".join(names))


def calculate_difference(current: Number, prior: Number) -> Optional[float]:
    return run_formula(DIFFERENCE, {"current": current, "prior": prior}).result


def calculate_reconciliation(reported: Number, computed: Number) -> Optional[float]:
    return run_formula(RECONCILIATION, {"reported": reported, "computed": computed}).result


# --------------------------------------------------------------------------- #
# Full model build
# --------------------------------------------------------------------------- #
class FinancialModel(dict):
    """Plain-dict model so it serializes straight to JSON."""


def build_model(
    periods: list[str],
    inputs: Mapping[str, Mapping[str, Optional[float]]],
    reported: Mapping[str, Mapping[str, Optional[float]]] | None = None,
) -> FinancialModel:
    """Build the complete deterministic model.

    ``inputs``    canonical category -> period -> value (None = missing)
    ``reported``  reported-subtotal category -> period -> value
    """
    reported = reported or {}
    periods = sorted(periods)
    present_opex = [c for c in OPEX_COMPONENTS if c in inputs]
    not_reported = [c for c in SOURCE_INPUTS if c not in inputs]

    per_period: dict[str, dict[str, CalculationResult]] = {m: {} for m in DERIVED_ORDER}
    values: dict[str, dict[str, Optional[float]]] = {
        c: {p: inputs.get(c, {}).get(p) for p in periods} for c in SOURCE_INPUTS if c in inputs
    }

    for p in periods:
        env: dict[str, Optional[float]] = {c: values[c][p] for c in SOURCE_INPUTS if c in inputs}
        for metric in DERIVED_ORDER:
            f = FORMULAS[metric]
            override = None
            if metric == "operating_expenses":
                if present_opex:
                    override = " + ".join(present_opex)
                elif "operating_expenses_reported" in reported:
                    # Source only reports a total: carry it as a source input, flagged.
                    env["operating_expenses"] = reported["operating_expenses_reported"].get(p)
                    per_period[metric][p] = CalculationResult(
                        metric=metric, period=p, formula_id="SOURCE_TOTAL",
                        expression="operating_expenses_reported", substituted="as reported",
                        inputs=[CalculationInput(name="operating_expenses_reported",
                                                 value=env["operating_expenses"], kind="source")],
                        result=env["operating_expenses"],
                        status=CalcStatus.DETERMINISTIC if env["operating_expenses"] is not None else CalcStatus.INCOMPLETE,
                        missing_inputs=[] if env["operating_expenses"] is not None else ["operating_expenses_reported"],
                    )
                    continue
            res = run_formula(
                f, env, metric=metric, period=p, expression_override=override,
                derived_names=DERIVED_ORDER,
            )
            per_period[metric][p] = res
            env[metric] = res.result
        for metric in DERIVED_ORDER:
            values.setdefault(metric, {})[p] = per_period[metric][p].result

    window = periods[-12:] if len(periods) >= 12 else list(periods)
    prior_window = periods[-24:-12] if len(periods) >= 24 else None

    def window_totals(win: list[str], label: str) -> dict[str, CalculationResult]:
        out: dict[str, CalculationResult] = {}
        if len(win) != 12:
            return out
        for metric in CURRENCY_METRICS:
            if metric in values:
                out[metric] = t12_result([values[metric][p] for p in win], metric=metric, period=label)
        env = {m: r.result for m, r in out.items()}
        for metric in RATIO_METRICS:
            f = FORMULAS[metric]
            out[metric] = run_formula(f, env, metric=metric, period=label, derived_names=CURRENCY_METRICS)
        return out

    t12 = window_totals(window, "T12")
    prior_t12 = window_totals(prior_window, "T12_PRIOR") if prior_window else {}

    growth: dict[str, CalculationResult] = {}
    for metric in ["revenue", "gross_profit", "ebitda", "net_income", "operating_expenses", "cogs", *present_opex]:
        if metric in t12 and metric in prior_t12:
            growth[metric] = run_formula(
                GROWTH,
                {"current": t12[metric].result, "prior": prior_t12[metric].result},
                metric=f"{metric}_growth_yoy",
                period="T12 vs prior T12",
            )

    # Cross-foot: applying each formula to the T-12 totals of its inputs must equal the
    # sum of the monthly results (true for the linear P&L formulas).
    crossfoot: list[dict] = []
    for metric in ["gross_profit", "operating_expenses", "ebitda", "net_income"]:
        if metric not in t12 or t12[metric].result is None:
            continue
        f = FORMULAS[metric]
        override = " + ".join(present_opex) if metric == "operating_expenses" and present_opex else None
        if metric == "operating_expenses" and not present_opex:
            continue
        env = {n: (t12[n].result if n in t12 else None) for n in expr.dependencies(override or f.expression)}
        via_totals = run_formula(f, env, metric=metric, period="T12", expression_override=override,
                                 derived_names=CURRENCY_METRICS)
        check = run_formula(RECONCILIATION, {"reported": t12[metric].result, "computed": via_totals.result})
        crossfoot.append({"metric": metric, "sum_of_months": t12[metric].result,
                          "formula_on_totals": via_totals.result, "difference": check.result,
                          "passed": check.result is not None and abs(check.result) < 0.005,
                          "calculation": via_totals.model_dump()})

    reconciliations: list[dict] = []
    for rep_key, metric in REPORTED_SUBTOTALS.items():
        if rep_key not in reported or metric not in values:
            continue
        if metric == "operating_expenses" and not present_opex:
            continue  # nothing independent to reconcile against
        for p in periods:
            rv = reported[rep_key].get(p)
            cv = values[metric].get(p)
            if rv is None or cv is None:
                continue
            res = run_formula(RECONCILIATION, {"reported": rv, "computed": cv},
                              metric=f"{metric}_variance", period=p)
            reconciliations.append({
                "metric": metric, "reported_category": rep_key, "period": p,
                "reported": rv, "computed": cv, "variance": res.result,
                "matches": res.result is not None and abs(res.result) < 0.5,
                "calculation": res.model_dump(),
            })

    return FinancialModel(
        engine="deterministic-decimal-v1",
        periods=periods,
        window=window,
        window_complete=len(window) == 12,
        prior_window=prior_window,
        opex_components=present_opex,
        not_reported=not_reported,
        values=values,
        per_period={m: {p: r.model_dump() for p, r in d.items()} for m, d in per_period.items()},
        t12={m: r.model_dump() for m, r in t12.items()},
        prior_t12={m: r.model_dump() for m, r in prior_t12.items()},
        growth={m: r.model_dump() for m, r in growth.items()},
        reconciliations=reconciliations,
        crossfoot=crossfoot,
    )


# --------------------------------------------------------------------------- #
# Deterministic analytics used by the AI layer as tools
# --------------------------------------------------------------------------- #
def rank_periods(model: Mapping, metric: str, descending: bool = True) -> list[dict]:
    series = model["values"].get(metric, {})
    rows = [{"period": p, "value": series.get(p)} for p in model["window"]]
    known = [r for r in rows if r["value"] is not None]
    known.sort(key=lambda r: r["value"], reverse=descending)
    return known + [r for r in rows if r["value"] is None]


def quarter_shift(model: Mapping, metric: str) -> dict:
    """First-3 vs last-3 months of the T-12 window (averages + growth), deterministic."""
    win = model["window"]
    series = model["values"].get(metric, {})
    if len(win) < 6:
        return {"metric": metric, "status": "INCOMPLETE", "reason": "fewer than 6 months"}
    first = run_formula(AVERAGE_3, dict(zip("abc", [series.get(p) for p in win[:3]])),
                        metric=f"{metric}_avg_first3", period=f"{win[0]}..{win[2]}")
    last = run_formula(AVERAGE_3, dict(zip("abc", [series.get(p) for p in win[-3:]])),
                       metric=f"{metric}_avg_last3", period=f"{win[-3]}..{win[-1]}")
    change = run_formula(GROWTH, {"current": last.result, "prior": first.result},
                         metric=f"{metric}_first3_to_last3", period="last 3 vs first 3")
    return {"metric": metric, "first3": first.model_dump(), "last3": last.model_dump(),
            "change": change.model_dump()}


def ratio_shift(model: Mapping, ratio: str) -> dict:
    """Ratio over the first 3 vs last 3 months (computed from summed components)."""
    f = FORMULAS[ratio]
    num, den = expr.dependencies(f.expression)
    win = model["window"]
    out = {}
    for label, months in (("first3", win[:3]), ("last3", win[-3:])):
        n = [model["values"].get(num, {}).get(p) for p in months]
        d = [model["values"].get(den, {}).get(p) for p in months]
        n_sum = run_formula(AVERAGE_3, dict(zip("abc", n)))
        d_sum = run_formula(AVERAGE_3, dict(zip("abc", d)))
        out[label] = run_formula(f, {num: n_sum.result, den: d_sum.result}, metric=f"{ratio}_{label}",
                                 period=f"{months[0]}..{months[-1]}").model_dump()
    out["change_pp"] = run_formula(DIFFERENCE, {"current": out["last3"]["result"], "prior": out["first3"]["result"]},
                                   metric=f"{ratio}_change", period="last 3 vs first 3").model_dump()
    return out
