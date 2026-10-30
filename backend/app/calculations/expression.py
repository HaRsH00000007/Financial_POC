"""A small, safe, deterministic formula evaluator.

Formulas are stored as data (strings such as ``"gross_profit - operating_expenses"``)
and parsed with Python's ``ast`` module. Only names, numeric literals, parentheses
and the four arithmetic operators are allowed - no function calls, attribute
access or anything else - so a formula can never execute arbitrary code.

All arithmetic uses ``decimal.Decimal`` so results are exact and reproducible
(no binary floating point drift). Missing inputs (``None``) propagate: if any
referenced input is missing, the result is ``None`` and the missing names are
reported. Division by zero yields an UNDEFINED result rather than an exception.
"""
from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from functools import lru_cache
from typing import Mapping, Optional

_ALLOWED_BINOPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


class FormulaError(ValueError):
    pass


class UndefinedResult(Exception):
    """Raised internally when an operation is mathematically undefined."""


@lru_cache(maxsize=256)
def parse(expression: str) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - defensive
        raise FormulaError(f"Invalid formula syntax: {expression!r}") from exc
    _validate(tree.body)
    return tree


def _validate(node: ast.AST) -> None:
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_BINOPS:
            raise FormulaError(f"Operator {type(node.op).__name__} is not allowed")
        _validate(node.left)
        _validate(node.right)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _validate(node.operand)
    elif isinstance(node, ast.Name):
        return
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return
    else:
        raise FormulaError(f"Unsupported formula element: {ast.dump(node)}")


def dependencies(expression: str) -> list[str]:
    """Names referenced by a formula, in first-appearance order."""
    seen: list[str] = []
    for node in ast.walk(parse(expression)):
        if isinstance(node, ast.Name) and node.id not in seen:
            seen.append(node.id)
    # ast.walk is breadth-first; re-order by source position for readability
    positions = {
        n.id: (n.lineno, n.col_offset)
        for n in ast.walk(parse(expression))
        if isinstance(n, ast.Name)
    }
    return sorted(seen, key=lambda name: positions[name])


def to_decimal(value: float | int | Decimal | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    # str() first so 0.1 becomes Decimal("0.1"), not its binary expansion
    return Decimal(str(value))


def evaluate(
    expression: str, values: Mapping[str, Optional[Decimal | float | int]]
) -> tuple[Optional[Decimal], list[str], bool]:
    """Evaluate ``expression`` against ``values``.

    Returns ``(result, missing_inputs, undefined)``.
    """
    tree = parse(expression)
    names = dependencies(expression)
    missing = [n for n in names if values.get(n) is None]
    if missing:
        return None, missing, False
    env = {n: to_decimal(values[n]) for n in names}  # type: ignore[arg-type]
    try:
        with localcontext() as ctx:
            ctx.prec = 34
            ctx.traps[DivisionByZero] = True
            ctx.traps[InvalidOperation] = True
            return _eval(tree.body, env), [], False
    except (UndefinedResult, DivisionByZero, InvalidOperation):
        return None, [], True


def _eval(node: ast.AST, env: Mapping[str, Decimal]) -> Decimal:
    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, env), _eval(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise UndefinedResult()
            return left / right
    if isinstance(node, ast.UnaryOp):
        return -_eval(node.operand, env)
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Constant):
        return to_decimal(node.value)
    raise FormulaError("unreachable")  # pragma: no cover


def substitute(expression: str, values: Mapping[str, Optional[float]]) -> str:
    """Render the formula with numbers in place of names, for audit display."""
    tree = parse(expression)

    def render(node: ast.AST, parent_prec: int = 0) -> str:
        if isinstance(node, ast.BinOp):
            prec = 1 if isinstance(node.op, (ast.Add, ast.Sub)) else 2
            text = f"{render(node.left, prec)} {_ALLOWED_BINOPS[type(node.op)]} {render(node.right, prec + 1)}"
            return f"({text})" if prec < parent_prec else text
        if isinstance(node, ast.UnaryOp):
            return f"-{render(node.operand, 3)}"
        if isinstance(node, ast.Name):
            v = values.get(node.id)
            return "MISSING" if v is None else f"{float(v):,.2f}"
        if isinstance(node, ast.Constant):
            return str(node.value)
        return "?"  # pragma: no cover

    return render(tree.body)
