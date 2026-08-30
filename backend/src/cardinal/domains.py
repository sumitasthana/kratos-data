"""Domain handlers. The skeleton ships exactly one: the credit line increase.

This is the "one real event" that exercises the whole event machinery:
eligibility as an auditable gate, a behavioural hazard with randomness, and a
fire step that emits events and mutates account state through declared effects.
Adding a domain later means writing one more class like this and registering
it. Nothing in the engine changes.

Every number this handler uses (thresholds, hazard coefficients, multipliers)
comes from the event spec YAML, never from a literal here. That is hard rule:
no tuned constants in domain code.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .money import money, round_to
from .predicate import all_true
from .spec import EventSpec
from .state import AccountState, Event


class LineIncreaseHandler:
    """Proactive credit line increase (Reg Z 1026.51 gates the eligibility)."""

    event_type = "credit_line_increase"
    domain = "line_management"
    # Distinct integer per domain, used to key its RNG streams.
    domain_id = 8

    def __init__(self, spec: EventSpec) -> None:
        self.spec = spec

    # -- variables the eligibility gate and hazard read -------------------
    def _variables(self, acct: AccountState, cycle: int) -> dict[str, Any]:
        return {
            "months_on_book": cycle,
            "max_dpd_last_12m": acct.max_dpd_last_12m,
            "refreshed_fico": acct.refreshed_fico,
            "utilization_last_3m_avg": acct.utilization_last_3m_avg(),
            "ability_to_pay_assessed": acct.ability_to_pay_assessed,
        }

    # -- protocol ---------------------------------------------------------
    def eligible(self, acct: AccountState, cycle: int) -> bool:
        """Deterministic policy gate. No RNG in here."""
        return all_true(self.spec.eligibility, self._variables(acct, cycle))

    def hazard(self, acct: AccountState, cycle: int) -> float:
        """Logistic P(event | eligible). Coefficients come from the spec."""
        h = self.spec.hazard or {}
        z = float(h.get("intercept", 0.0))
        variables = self._variables(acct, cycle)
        # A fico scaled roughly onto a unit range for a stable coefficient.
        variables["refreshed_fico_scaled"] = (acct.refreshed_fico - 660.0) / 100.0
        variables["tenure_years"] = cycle / 12.0
        for name, coef in (h.get("coefficients") or {}).items():
            z += float(coef) * float(variables.get(name, 0.0))
        return 1.0 / (1.0 + math.exp(-z))

    def fire(self, acct: AccountState, cycle: int, rng: np.random.Generator) -> list[Event]:
        """Draw a multiplier, raise the limit, emit the required events."""
        amt = self.spec.amount or {}
        multipliers = np.asarray(amt.get("multipliers", [1.0]), dtype=float)
        weights = np.asarray(amt.get("weights", [1.0]), dtype=float)
        weights = weights / weights.sum()
        step = int(amt.get("round_to", 1))

        multiplier = float(rng.choice(multipliers, p=weights))
        prior = acct.limit_in_force
        acct.limit_in_force = round_to(money(prior * money(multiplier)), step)

        base = f"{acct.account_id}-{cycle}-cli"
        return [
            Event(
                event_id=f"{base}",
                account_id=acct.account_id,
                cycle=cycle,
                type="line_increase",
                amount=acct.limit_in_force - prior,
                payload={"prior_limit": str(prior), "new_limit": str(acct.limit_in_force),
                         "multiplier": multiplier},
            ),
            # Reg Z 1026.9(c) advance notice; the timing invariant lives in the
            # spec. Emitted here so the event exists to check against.
            Event(
                event_id=f"{base}-cit",
                account_id=acct.account_id,
                cycle=cycle,
                type="change_in_terms_notice",
                payload={"reason": "credit_line_increase"},
            ),
        ]


def build_registry(events: dict[str, EventSpec]) -> list[Any]:
    """Instantiate every handler whose event spec is present.

    The skeleton wires one handler. Disable it (return []) and the CLI
    ablation flag proves the domain is actually doing work: utilisation will
    no longer drop and refill.
    """
    registry: list[Any] = []
    if "credit_line_increase" in events:
        registry.append(LineIncreaseHandler(events["credit_line_increase"]))
    return registry
