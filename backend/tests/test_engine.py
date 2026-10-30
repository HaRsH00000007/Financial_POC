import pytest

from app.calculations import engine
from app.calculations.formulas import DERIVED_ORDER, FORMULAS, dependency_graph


def test_gross_profit():
    assert engine.calculate_gross_profit(10_000_000, 4_000_000) == 6_000_000


def test_ebitda():
    assert engine.calculate_ebitda(6_000_000, 2_000_000) == 4_000_000


def test_net_income():
    assert engine.calculate_net_income(4_000_000, 500_000, 250_000, 800_000) == 2_450_000


def test_operating_expenses_sums_only_reported_components():
    assert engine.calculate_operating_expenses(payroll=100, rent=50) == 150
    assert engine.calculate_operating_expenses(payroll=100, rent=None) is None


def test_margin_and_growth():
    assert engine.calculate_margin(4_000_000, 20_000_000) == 0.2
    assert engine.calculate_growth(108.4, 100) == 0.084
    assert engine.calculate_growth(100, 0) is None  # undefined, never infinity
    assert engine.calculate_difference(0.126, 0.137) == -0.011


def test_t12_requires_twelve_complete_months():
    assert engine.calculate_t12([100.0] * 12) == 1200
    assert engine.calculate_t12([100.0] * 11 + [None]) is None
    with pytest.raises(ValueError):
        engine.calculate_t12([1.0] * 11)


def test_t12_is_exact_for_cents():
    assert engine.calculate_t12([0.1] * 12) == 1.2


def test_aggregate_rows_and_reconciliation():
    r = engine.aggregate_rows([158_000, 33_200])
    assert r.result == 191_200 and r.expression == "row_1 + row_2"
    assert engine.calculate_reconciliation(121_140, 121_410) == -270


def test_results_carry_formula_and_inputs():
    r = engine.run_formula(FORMULAS["ebitda"], {"gross_profit": 6e6, "operating_expenses": 2e6}, period="2026-01")
    assert r.formula_id == "EBITDA_001"
    assert r.expression == "gross_profit - operating_expenses"
    assert [i.name for i in r.inputs] == ["gross_profit", "operating_expenses"]
    assert r.status.value == "DETERMINISTIC"
    assert r.substituted == "6,000,000.00 - 2,000,000.00"


def test_topological_order():
    order = DERIVED_ORDER
    assert order.index("gross_profit") < order.index("ebitda") < order.index("net_income")
    assert order.index("operating_expenses") < order.index("ebitda")
    g = dependency_graph()
    assert {"from": "revenue", "to": "gross_profit"} in g["edges"]


def _inputs(n=24, missing=None):
    periods = [f"{2024 + (8 + i) // 12:04d}-{(8 + i) % 12 + 1:02d}" for i in range(n)]
    base = {"revenue": 1000.0, "cogs": 400.0, "payroll": 200.0, "rent": 50.0, "depreciation": 20.0,
            "interest": 10.0, "taxes": 30.0}
    inputs = {k: {p: v for p in periods} for k, v in base.items()}
    if missing:
        cat, idx = missing
        inputs[cat][periods[idx]] = None
    return periods, inputs


def test_build_model_end_to_end():
    periods, inputs = _inputs()
    m = engine.build_model(periods, inputs, {"net_income_reported": {p: 290.0 for p in periods}})
    assert m["window"] == periods[-12:] and m["prior_window"] == periods[:12]
    assert m["t12"]["revenue"]["result"] == 12_000
    assert m["t12"]["gross_profit"]["result"] == 7_200
    assert m["t12"]["operating_expenses"]["result"] == 3_000
    assert m["t12"]["ebitda"]["result"] == 4_200
    assert m["t12"]["net_income"]["result"] == 3_480
    assert m["t12"]["ebitda_margin"]["result"] == 0.35
    assert m["growth"]["revenue"]["result"] == 0
    assert all(r["matches"] for r in m["reconciliations"])
    assert all(c["passed"] for c in m["crossfoot"])
    assert "sales_marketing" in m["not_reported"]


def test_missing_value_is_never_imputed():
    periods, inputs = _inputs(missing=("rent", 20))
    m = engine.build_model(periods, inputs)
    p = periods[20]
    assert m["per_period"]["operating_expenses"][p]["status"] == "INCOMPLETE"
    assert m["per_period"]["operating_expenses"][p]["missing_inputs"] == ["rent"]
    assert m["per_period"]["net_income"][p]["result"] is None
    assert m["t12"]["net_income"]["result"] is None
    assert m["t12"]["net_income"]["status"] == "INCOMPLETE"
    assert m["t12"]["revenue"]["result"] == 12_000  # unaffected metrics still compute


def test_short_history_has_no_t12_or_growth():
    periods, inputs = _inputs(n=9)
    m = engine.build_model(periods, inputs)
    assert not m["window_complete"]
    assert m["t12"] == {} and m["growth"] == {}


def test_reconciliation_detects_source_error():
    periods, inputs = _inputs()
    reported = {"net_income_reported": {p: 290.0 for p in periods}}
    reported["net_income_reported"][periods[-1]] = 209.0
    m = engine.build_model(periods, inputs, reported)
    bad = [r for r in m["reconciliations"] if not r["matches"]]
    assert len(bad) == 1 and bad[0]["variance"] == -81


def test_determinism():
    periods, inputs = _inputs()
    assert engine.build_model(periods, inputs) == engine.build_model(periods, inputs)
