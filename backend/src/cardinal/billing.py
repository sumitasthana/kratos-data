"""Billing module: the first real recipe on the shared cycle counter.

Implements correct billing for the account_cycle grain:
  - balance recurrence (ending = beginning + purchases + cash + fees + interest - payment - credits)
  - average-daily-balance interest, GATED BY GRACE (path-dependent on whether last
    cycle's statement was paid in full)
  - fees (late fee when the minimum was missed)
  - minimum payment (issuer-policy formula, capped at the statement balance)
  - payment behaviour by archetype (transactor / revolver / minimum-payer / erratic)

Every number lives in DEFAULTS below (a config, not literals in the logic). These
are DEMO defaults, chosen to look plausible, NOT calibrated targets. Calibration
against a published reference is Tier-1 work.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .money import money

# ---- DEMO defaults (not calibrated). Params live here, never in the logic. ----
DEFAULTS: dict[str, Any] = {
    "apr_values": [0.1499, 0.1999, 0.2499, 0.2999],
    "apr_weights": [0.25, 0.35, 0.25, 0.15],
    "limit_values": [1000, 2500, 5000, 10000, 20000],
    "limit_weights": [0.15, 0.30, 0.30, 0.18, 0.07],
    "archetype_mix": {
        "mostly_transactors": {"transactor": 0.60, "revolver": 0.20, "min_payer": 0.10, "erratic": 0.10},
        "mixed":              {"transactor": 0.35, "revolver": 0.40, "min_payer": 0.15, "erratic": 0.10},
        "mostly_revolvers":   {"transactor": 0.15, "revolver": 0.55, "min_payer": 0.20, "erratic": 0.10},
    },
    "pay_fraction_mean": {"transactor": 1.0, "revolver": 0.15, "min_payer": 0.0, "erratic": 0.5},
    "spend_mu": 6.2, "spend_sigma": 0.9, "spend_zero_prob": 0.10,
    "cash_adv_prob": 0.08, "cash_mu": 5.0, "cash_sigma": 0.8,
    "late_fee": 35.0,
    "min_pct": 0.02, "min_floor": 35.0,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


class BillingModule:
    name = "billing"
    domain_id = 20

    def __init__(self, behaviors: set[str] | None = None,
                 revolver_mix: str = "mixed", cfg: dict[str, Any] | None = None):
        self.behaviors = behaviors or {"grace_period", "fees", "minimum_payment"}
        self.revolver_mix = revolver_mix if revolver_mix in DEFAULTS["archetype_mix"] else "mixed"
        self.cfg = cfg or DEFAULTS

    def init_account(self, acct: dict[str, Any], rng: Any) -> None:
        c = self.cfg
        acct["apr"] = float(rng.choice(c["apr_values"], p=c["apr_weights"]))
        acct["credit_limit"] = money(rng.choice(c["limit_values"], p=c["limit_weights"]))
        mix = c["archetype_mix"][self.revolver_mix]
        acct["archetype"] = str(rng.choice(list(mix), p=list(mix.values())))
        acct["_balance"] = money(0)       # ending balance carried forward
        acct["_stmt_prev"] = money(0)     # last cycle's statement balance
        acct["_min_prev"] = money(0)      # last cycle's minimum due
        acct["_dpd"] = 0

    def step(self, acct: dict[str, Any], cycle: int, rng: Any) -> dict[str, Any]:
        c = self.cfg
        apr = acct["apr"]
        limit = acct["credit_limit"]
        arche = acct["archetype"]
        beginning = acct["_balance"]
        stmt_prev = acct["_stmt_prev"]
        min_prev = acct["_min_prev"]
        grace_on = "grace_period" in self.behaviors

        # --- payment pays LAST cycle's statement (the lag that makes grace real) ---
        if stmt_prev <= 0:
            payment = money(0)
        elif arche == "transactor":
            payment = stmt_prev
        elif arche == "min_payer":
            payment = min(min_prev, stmt_prev) if min_prev > 0 else money(stmt_prev * Decimal("0.02"))
        else:
            frac = _clamp01(rng.normal(c["pay_fraction_mean"][arche], 0.15))
            payment = money(stmt_prev * Decimal(str(frac)))
        payment = min(payment, stmt_prev) if stmt_prev > 0 else money(0)

        paid_in_full = (stmt_prev <= 0) or (payment >= stmt_prev)
        grace_eligible = paid_in_full if grace_on else False

        # --- balance after payment ---
        post_pay = money(beginning - payment)
        if post_pay < 0:
            post_pay = money(0)

        # --- spend this cycle, capped at available credit (over-limit is declined) ---
        available = money(limit - post_pay)
        if available < 0:
            available = money(0)
        if rng.random() < c["spend_zero_prob"]:
            purchases = money(0)
        else:
            purchases = money(min(float(available), rng.lognormal(c["spend_mu"], c["spend_sigma"])))
        cash = money(0)
        if "cash_advances" in self.behaviors and rng.random() < c["cash_adv_prob"]:
            cash = money(min(float(available - purchases), rng.lognormal(c["cash_mu"], c["cash_sigma"])))

        # --- fees: late fee when the prior minimum was missed ---
        fees = money(0)
        if "fees" in self.behaviors and stmt_prev > 0 and payment < min_prev:
            fees = money(c["late_fee"])
        # simplifying assumption: new charges spread evenly across the cycle
        adb = money(post_pay + (purchases + cash) / 2)
        interest = money(0) if grace_eligible else money(adb * Decimal(str(apr)) / Decimal(12))

        credits = money(0)  # refunds not modelled yet
        ending = money(post_pay + purchases + cash + fees + interest - credits)
        statement = ending

        # --- minimum due (always computed internally for payment realism) ---
        internal_min = money(max(c["min_floor"], c["min_pct"] * float(statement))) if statement > 0 else money(0)
        internal_min = min(internal_min, statement)
        minimum = internal_min if "minimum_payment" in self.behaviors else money(0)

        # --- simplified delinquency signal (a full model is the Collections domain) ---
        if stmt_prev > 0 and payment < min_prev:
            acct["_dpd"] = acct["_dpd"] + 30
        else:
            acct["_dpd"] = 0

        util = round(float(ending / limit), 4) if limit > 0 else 0.0

        acct["_balance"] = ending
        acct["_stmt_prev"] = statement
        acct["_min_prev"] = internal_min

        return {
            "credit_limit": float(limit), "apr": apr, "archetype": arche,
            "beginning_balance": float(beginning), "purchases": float(purchases),
            "cash_advance": float(cash), "payment": float(payment),
            "paid_in_full": bool(paid_in_full), "grace_eligible": bool(grace_eligible),
            "fees": float(fees), "interest": float(interest), "credits": float(credits),
            "average_daily_balance": float(adb), "ending_balance": float(ending),
            "statement_balance": float(statement), "minimum_due": float(minimum),
            "utilization": util, "dpd": int(acct["_dpd"]),
        }
