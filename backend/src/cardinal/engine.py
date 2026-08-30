"""Generation engine: population synthesis and the per-account cycle loop.

The loop is the heart of the event-sourcing architecture. Each cycle advances
lagged attributes, fires eligible events, runs placeholder economics, closes
the cycle, and projects one account_cycle row. Accounts are independent given
the shared context, so this parallelises cleanly; the skeleton runs it serially
for clarity, but the per-entity RNG streams mean the result would be identical
in parallel.

The economics here (spend and payment) are placeholders, drawn from field
specs, not calibrated billing. Real billing arithmetic is Tier 1 work. The
skeleton's job is to prove the machine, so it keeps the economics honest and
simple and says so.
"""
from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from . import dist
from .domains import build_registry
from .invariants import hard_violations
from .money import money
from .rng import stream
from .spec import SpecBundle
from .state import AccountState, Event

MAX_ATTEMPTS = 3


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _refresh_strength(bundle: SpecBundle) -> float:
    """Points of FICO lost per unit of prior-cycle utilisation.

    Read from the refreshed_fico field's lag-1 dependency on utilization, so
    the number lives in YAML, not here.
    """
    fs = bundle.fields.get("refreshed_fico")
    if fs is not None:
        for dep in fs.depends_on:
            if dep.field == "utilization" and dep.lag >= 1:
                return dep.strength
    return 0.0


def synth_population(bundle: SpecBundle) -> pd.DataFrame:
    """Sample the account-grain fields for every account, deterministically."""
    n = bundle.portfolio.accounts
    rng = stream(bundle.portfolio.seed, domain_id=0, entity_id=0)

    fico = dist.sample(bundle.fields["fico_at_origination"].dist, n, rng)
    propensity = dist.sample(bundle.fields["utilization_propensity"].dist, n, rng)

    # credit_limit_initial depends on fico via weight_tilt: higher score tilts
    # mass toward higher limit bands. The tilt strength comes from the spec.
    limit_spec = bundle.fields["credit_limit_initial"]
    values = np.asarray(limit_spec.dist["values"])
    base_w = np.asarray(limit_spec.dist["weights"], dtype=float)
    strength = next(
        (d.strength for d in limit_spec.depends_on if d.field == "fico_at_origination"), 0.0
    )
    z = (fico - fico.mean()) / (fico.std() + 1e-9)
    rank = np.linspace(-0.5, 0.5, len(values))
    log_w = np.log(base_w)[None, :] + strength * z[:, None] * rank[None, :]
    limit = dist.categorical_row_weighted(values, log_w, rng)

    return pd.DataFrame(
        {
            "account_id": np.arange(n),
            "fico_at_origination": fico,
            "utilization_propensity": propensity,
            "credit_limit_initial": limit.astype(float),
        }
    )


def simulate_account(
    row: pd.Series, bundle: SpecBundle, handlers: list, attempt: int
) -> tuple[list[dict], list[Event]]:
    """Run one account through the horizon. Returns (cycle_rows, events)."""
    seed = bundle.portfolio.seed
    aid = int(row["account_id"])
    strength = _refresh_strength(bundle)

    acct = AccountState(
        account_id=aid,
        fico_at_origination=float(row["fico_at_origination"]),
        utilization_propensity=float(row["utilization_propensity"]),
        credit_limit_initial=money(row["credit_limit_initial"]),
    )
    acct.limit_in_force = acct.credit_limit_initial
    acct.balance = money(acct.credit_limit_initial * Decimal(str(acct.utilization_propensity)))

    opening_util = float(acct.balance / acct.limit_in_force)
    acct.util_history = [opening_util]
    util_prev = opening_util

    events: list[Event] = [
        Event(
            event_id=f"{aid}-0-open",
            account_id=aid,
            cycle=0,
            type="account_opened",
            amount=acct.balance,
            payload={"initial_limit": str(acct.limit_in_force)},
        )
    ]
    rows: list[dict] = []

    spend_spec = bundle.fields["spend_factor"].dist
    pay_spec = bundle.fields["payment_fraction"].dist

    for cycle in range(1, bundle.portfolio.cycles + 1):
        # a. lagged attribute refresh: prior-cycle utilisation moves the score.
        acct.refreshed_fico = _clamp(acct.fico_at_origination - strength * util_prev, 300.0, 850.0)

        # b. fire eligible events (the one real handler: line increase).
        for h in handlers:
            hrng = stream(seed, h.domain_id, aid, cycle, attempt)
            if h.eligible(acct, cycle) and hrng.random() < h.hazard(acct, cycle):
                events.extend(h.fire(acct, cycle, hrng))

        # c/d/e. placeholder economics: spend scales with the limit, payment is
        # a fraction of the post-spend balance. Both draws come from field specs.
        econ = stream(seed, 1, aid, cycle, attempt)
        spend_factor = float(dist.sample(spend_spec, 1, econ)[0])
        purchases = money(acct.limit_in_force * Decimal(str(spend_factor)))
        events.append(Event(f"{aid}-{cycle}-buy", aid, cycle, "purchase", purchases))

        pay_fraction = float(dist.sample(pay_spec, 1, econ)[0])
        pre_payment = money(acct.balance + purchases)
        payments = money(pre_payment * Decimal(str(pay_fraction)))
        if payments > pre_payment:
            payments = pre_payment
        events.append(Event(f"{aid}-{cycle}-pay", aid, cycle, "payment", payments))

        acct.balance = money(pre_payment - payments)

        # f. derived utilisation.
        acct.utilization = float(acct.balance / acct.limit_in_force)
        acct.util_history.append(acct.utilization)
        util_prev = acct.utilization

        # g. project the account_cycle row.
        rows.append(
            {
                "account_id": aid,
                "cycle_seq": cycle,
                "credit_limit_in_force": float(acct.limit_in_force),
                "cycle_ending_balance": float(acct.balance),
                "purchases": float(purchases),
                "payments": float(payments),
                "utilization": acct.utilization,
                "refreshed_fico": acct.refreshed_fico,
                "dpd": 0,
            }
        )

    return rows, events


def generate(bundle: SpecBundle, ablate: bool = False) -> dict:
    """Generate the whole portfolio. Returns frames plus run stats."""
    handlers = [] if ablate else build_registry(bundle.events)
    population = synth_population(bundle)

    all_rows: list[dict] = []
    all_events: list[Event] = []
    rejected = 0

    for _, row in population.iterrows():
        rows: list[dict] = []
        events: list[Event] = []
        for attempt in range(MAX_ATTEMPTS):
            rows, events = simulate_account(row, bundle, handlers, attempt)
            frame = pd.DataFrame(rows)
            if not hard_violations(frame, bundle.invariants):
                break
            rejected += 1
        all_rows.extend(rows)
        all_events.extend(events)

    account_cycle = pd.DataFrame(all_rows)
    events_df = pd.DataFrame(
        [
            {
                "event_id": e.event_id,
                "account_id": e.account_id,
                "cycle": e.cycle,
                "type": e.type,
                "amount": float(e.amount) if e.amount is not None else None,
            }
            for e in all_events
        ]
    )
    accounts = population.copy()

    attempts_total = len(population) + rejected
    stats = {
        "accounts": len(population),
        "cycles": bundle.portfolio.cycles,
        "seed": bundle.portfolio.seed,
        "rejected": rejected,
        "rejection_rate": rejected / attempts_total if attempts_total else 0.0,
        "cli_events": int((events_df["type"] == "line_increase").sum()) if len(events_df) else 0,
        "ablated": ablate,
    }
    return {
        "account_cycle": account_cycle,
        "events": events_df,
        "accounts": accounts,
        "stats": stats,
    }
