from decimal import Decimal

import pytest

from app.calculations import expression as expr


def test_basic_arithmetic_is_exact_decimal():
    result, missing, undefined = expr.evaluate("a + b", {"a": 0.1, "b": 0.2})
    assert result == Decimal("0.3")  # float arithmetic would give 0.30000000000000004
    assert missing == [] and not undefined


def test_precedence_and_parentheses():
    assert expr.evaluate("a - b * c", {"a": 10, "b": 2, "c": 3})[0] == Decimal(4)
    assert expr.evaluate("(a - b) * c", {"a": 10, "b": 2, "c": 3})[0] == Decimal(24)


def test_missing_inputs_propagate_and_are_reported():
    result, missing, undefined = expr.evaluate("revenue - cogs", {"revenue": 100, "cogs": None})
    assert result is None
    assert missing == ["cogs"]
    assert not undefined


def test_division_by_zero_is_undefined_not_an_exception():
    result, missing, undefined = expr.evaluate("a / b", {"a": 1, "b": 0})
    assert result is None and undefined and missing == []


def test_dependencies_in_source_order():
    assert expr.dependencies("ebitda - depreciation - interest - taxes") == [
        "ebitda", "depreciation", "interest", "taxes"]


@pytest.mark.parametrize("bad", ["__import__('os')", "a.b", "a ** 2", "f(a)", "a if b else c", "[a]"])
def test_unsafe_expressions_rejected(bad):
    with pytest.raises(expr.FormulaError):
        expr.parse(bad)


def test_substitute_renders_values_and_missing():
    assert expr.substitute("a - b", {"a": 1000, "b": None}) == "1,000.00 - MISSING"
