"""A deliberately tiny predicate evaluator for eligibility gates.

Eligibility encodes law and policy, so it must be replayable and explainable:
the answer to "why no line increase?" is a named predicate that was false, not
"the sampler said no". Keeping this evaluator small and closed (comparisons of
one variable against one literal, combined with AND) keeps it auditable. It is
not a general expression language on purpose. A richer grammar is future work,
added only when a real gate needs it.
"""
from __future__ import annotations

import re
from typing import Any

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}
# Longest operators first so ">=" is not read as ">".
_PATTERN = re.compile(r"^\s*(\w+)\s*(>=|<=|==|!=|>|<)\s*(\S+)\s*$")


def _literal(token: str) -> Any:
    low = token.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    return float(token)


def evaluate(expr: str, variables: dict[str, Any]) -> bool:
    """Evaluate one `var OP literal` comparison against a variable dict."""
    m = _PATTERN.match(expr)
    if not m:
        raise ValueError(f"unsupported predicate: {expr!r}")
    name, op, rhs = m.groups()
    if name not in variables:
        raise KeyError(f"predicate references unknown variable: {name!r}")
    left = variables[name]
    right = _literal(rhs)
    if isinstance(right, bool):
        return _OPS[op](bool(left), right)
    return _OPS[op](float(left), right)


def all_true(exprs: list[str], variables: dict[str, Any]) -> bool:
    """True only if every predicate holds. Empty list is vacuously true."""
    return all(evaluate(e, variables) for e in exprs)
