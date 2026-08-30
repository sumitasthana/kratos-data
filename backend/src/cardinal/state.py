"""Account state and the event record.

An account is a state machine advanced by events. The tabular rows are
projections of the event stream, never sampled directly. This is what lets a
reviewer ask "why did this limit change?" and get an answer from the log.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class Event:
    """One thing that happened to an account, in order."""

    event_id: str
    account_id: int
    cycle: int
    type: str
    amount: Decimal | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountState:
    """Mutable state carried through the per-account cycle loop."""

    account_id: int

    # Set at origination, fixed for the life of the account.
    fico_at_origination: float = 0.0
    utilization_propensity: float = 0.0
    credit_limit_initial: Decimal = Decimal("0")

    # Advanced every cycle.
    limit_in_force: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    refreshed_fico: float = 0.0
    utilization: float = 0.0

    # Trailing context used by eligibility gates and hazards.
    util_history: list[float] = field(default_factory=list)
    max_dpd_last_12m: int = 0
    ability_to_pay_assessed: bool = True

    def utilization_last_3m_avg(self) -> float:
        window = self.util_history[-3:]
        return sum(window) / len(window) if window else 0.0
