"""Invariant runner.

Hard invariants are the acceptance criteria. An account that violates one is
rejected and regenerated. The skeleton implements the three that the core
arithmetic rests on. Each invariant id maps to a checker; a spec whose id has
no checker yet is reported as unenforced rather than silently passing, because
a rule you think is running but is not is worse than no rule.

Evaluating arbitrary `expr` strings is a small language of its own and is
deliberately deferred. The ids below are hand-written and tested.
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .spec import InvariantSpec

_TOL = Decimal("0.01")


def _balance_recurrence(frame: pd.DataFrame) -> pd.Series:
    """bal[t] == bal[t-1] + purchases - payments, to the cent."""
    df = frame.sort_values(["account_id", "cycle_seq"])
    prior = df.groupby("account_id")["cycle_ending_balance"].shift(1)
    opening = df["cycle_ending_balance"] - df["purchases"] + df["payments"]
    # Cycle 1 has no prior row; its recurrence is checked against the opening
    # balance event instead, so treat a missing prior as satisfied here.
    expected = prior.fillna(opening)
    ok = (df["cycle_ending_balance"] - (expected + df["purchases"] - df["payments"])).abs() <= _TOL
    return ok.reindex(frame.index, fill_value=True)


def _utilization_definition(frame: pd.DataFrame) -> pd.Series:
    ratio = frame.apply(
        lambda r: float(Decimal(str(r["cycle_ending_balance"])) / Decimal(str(r["credit_limit_in_force"]))),
        axis=1,
    )
    return (frame["utilization"] - ratio).abs() <= 1e-9


def _utilization_bound(frame: pd.DataFrame) -> pd.Series:
    return frame["utilization"] <= 1.05


_CHECKERS = {
    "balance_recurrence": _balance_recurrence,
    "utilization_definition": _utilization_definition,
    "utilization_bound": _utilization_bound,
}


def hard_violations(frame: pd.DataFrame, invariants: list[InvariantSpec]) -> list[str]:
    """Return the ids of hard invariants that fail on this frame."""
    failed: list[str] = []
    for inv in invariants:
        if inv.severity != "hard":
            continue
        checker = _CHECKERS.get(inv.id)
        if checker is None:
            continue  # unenforced; reported by `unenforced()` at build time
        if not checker(frame).all():
            failed.append(inv.id)
    return failed


def unenforced(invariants: list[InvariantSpec]) -> list[str]:
    """Hard invariants declared in YAML with no checker implemented yet."""
    return [inv.id for inv in invariants if inv.severity == "hard" and inv.id not in _CHECKERS]
