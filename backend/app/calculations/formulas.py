"""Formula registry - the single source of truth for every financial calculation.

Formulas are declarative metadata. The engine evaluates the ``expression`` with the
deterministic evaluator in ``expression.py``; no calculation logic lives anywhere
else (not in API routes, not in agents, never in the LLM).
"""
from __future__ import annotations

from app.calculations.expression import dependencies
from app.models.domain import Formula

OPEX_COMPONENTS = ["payroll", "rent", "sales_marketing", "technology", "general_admin", "other_opex"]

FORMULAS: dict[str, Formula] = {
    f.metric: f
    for f in [
        Formula(
            formula_id="OPEX_001",
            metric="operating_expenses",
            name="Operating Expenses",
            expression=" + ".join(OPEX_COMPONENTS),
            inputs=OPEX_COMPONENTS,
            optional_inputs=OPEX_COMPONENTS,
            description="Sum of operating expense components. Components not reported anywhere "
            "in the source are excluded (and listed as 'not reported'); a component that is "
            "reported but missing for a month makes that month INCOMPLETE.",
        ),
        Formula(
            formula_id="GP_001",
            metric="gross_profit",
            name="Gross Profit",
            expression="revenue - cogs",
            inputs=["revenue", "cogs"],
            description="Revenue less cost of goods sold.",
        ),
        Formula(
            formula_id="EBITDA_001",
            metric="ebitda",
            name="EBITDA",
            expression="gross_profit - operating_expenses",
            inputs=["gross_profit", "operating_expenses"],
            description="Earnings before interest, taxes, depreciation and amortization.",
        ),
        Formula(
            formula_id="NI_001",
            metric="net_income",
            name="Net Income",
            expression="ebitda - depreciation - interest - taxes",
            inputs=["ebitda", "depreciation", "interest", "taxes"],
            description="EBITDA less depreciation & amortization, interest and income taxes.",
        ),
        Formula(
            formula_id="GM_001",
            metric="gross_margin",
            name="Gross Margin %",
            expression="gross_profit / revenue",
            inputs=["gross_profit", "revenue"],
            output_format="percent",
        ),
        Formula(
            formula_id="EBITDAM_001",
            metric="ebitda_margin",
            name="EBITDA Margin %",
            expression="ebitda / revenue",
            inputs=["ebitda", "revenue"],
            output_format="percent",
        ),
        Formula(
            formula_id="NM_001",
            metric="net_margin",
            name="Net Margin %",
            expression="net_income / revenue",
            inputs=["net_income", "revenue"],
            output_format="percent",
        ),
    ]
}

# Formulas that operate on series rather than on a single period.
T12_SUM = Formula(
    formula_id="T12_001",
    metric="t12_total",
    name="Trailing-12-Month Total",
    expression=" + ".join(f"m{i:02d}" for i in range(1, 13)),
    inputs=[f"m{i:02d}" for i in range(1, 13)],
    description="Sum of the 12 monthly values in the trailing window. Any missing month makes the "
    "total INCOMPLETE - totals are never extrapolated.",
)
GROWTH = Formula(
    formula_id="GROWTH_001",
    metric="growth",
    name="Period-over-Period Growth %",
    expression="(current - prior) / prior",
    inputs=["current", "prior"],
    output_format="percent",
)
RECONCILIATION = Formula(
    formula_id="REC_001",
    metric="reconciliation_variance",
    name="Reported vs. Recomputed Variance",
    expression="reported - computed",
    inputs=["reported", "computed"],
    description="Difference between a subtotal printed in the source document and the value "
    "recomputed by the engine from its components.",
)
DIFFERENCE = Formula(
    formula_id="DIFF_001",
    metric="difference",
    name="Change (current - prior)",
    expression="current - prior",
    inputs=["current", "prior"],
    output_format="percent",
    description="Absolute change; used for margin movements in percentage points.",
)
AGGREGATE = Formula(
    formula_id="AGG_001",
    metric="category_total",
    name="Category Aggregation",
    expression="row_1",
    inputs=["row_1"],
    description="Sum of all source rows mapped to one canonical category. The expression is "
    "specialized per category (row_1 + row_2 + ...). A missing row value makes the period INCOMPLETE.",
)
AVERAGE_3 = Formula(
    formula_id="AVG3_001",
    metric="three_month_average",
    name="Three-Month Average",
    expression="(a + b + c) / 3",
    inputs=["a", "b", "c"],
)

ALL_FORMULAS: list[Formula] = [*FORMULAS.values(), AGGREGATE, T12_SUM, GROWTH, DIFFERENCE, RECONCILIATION, AVERAGE_3]

# Per-period derived metrics in evaluation (topological) order.
DERIVED_ORDER: list[str] = []


def _toposort() -> list[str]:
    order: list[str] = []
    visiting: set[str] = set()

    def visit(metric: str) -> None:
        if metric in order or metric not in FORMULAS:
            return
        if metric in visiting:
            raise ValueError(f"Circular formula dependency at {metric}")
        visiting.add(metric)
        for dep in dependencies(FORMULAS[metric].expression):
            visit(dep)
        visiting.discard(metric)
        order.append(metric)

    for m in FORMULAS:
        visit(m)
    return order


DERIVED_ORDER = _toposort()


def dependency_graph() -> dict:
    """Nodes/edges for the UI dependency visualization."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    depth: dict[str, int] = {}

    def node_depth(metric: str) -> int:
        if metric not in FORMULAS:
            return 0
        if metric not in depth:
            depth[metric] = 1 + max(node_depth(d) for d in dependencies(FORMULAS[metric].expression))
        return depth[metric]

    for metric in DERIVED_ORDER:
        f = FORMULAS[metric]
        nodes[metric] = {
            "id": metric,
            "label": f.name,
            "kind": "derived",
            "formula_id": f.formula_id,
            "expression": f.expression,
            "depth": node_depth(metric),
            "format": f.output_format,
        }
        for dep in dependencies(f.expression):
            if dep not in nodes and dep not in FORMULAS:
                nodes[dep] = {"id": dep, "label": dep, "kind": "input", "depth": 0}
            edges.append({"from": dep, "to": metric})
    return {"nodes": list(nodes.values()), "edges": edges, "order": DERIVED_ORDER}
