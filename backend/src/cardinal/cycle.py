"""The shared counter: one generic per-account cycle loop that runs a list of
domain modules ("recipe cards") each month and assembles the account_cycle row.

Adding a domain later means writing one more module with init_account()/step()
and registering it here. The loop never changes. This is the additive path:
Payments, Delinquency, Fraud, etc. each become one more module on this counter.

Determinism: every module gets its own RNG stream per (domain, account, cycle),
so results never depend on module order execution timing or worker count.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd

from .rng import stream


@runtime_checkable
class CycleModule(Protocol):
    name: str
    domain_id: int   # distinct integer per domain, keys its RNG streams

    def init_account(self, acct: dict[str, Any], rng: Any) -> None:
        """Set up per-account state once (archetype, APR, limit, ...)."""

    def step(self, acct: dict[str, Any], cycle: int, rng: Any) -> dict[str, Any]:
        """Advance one cycle, mutate acct, return the columns it contributes."""


def simulate_account(aid: int, modules: list[CycleModule], seed: int, cycles: int) -> list[dict]:
    acct: dict[str, Any] = {"account_id": aid}
    for m in modules:
        m.init_account(acct, stream(seed, m.domain_id, aid, 0))
    rows: list[dict] = []
    for cycle in range(1, cycles + 1):
        row: dict[str, Any] = {"account_id": aid, "cycle_seq": cycle}
        for m in modules:
            row.update(m.step(acct, cycle, stream(seed, m.domain_id, aid, cycle)))
        rows.append(row)
    return rows


def generate_portfolio(modules: list[CycleModule], accounts: int, cycles: int,
                       seed: int = 42) -> pd.DataFrame:
    rows: list[dict] = []
    for aid in range(accounts):
        rows.extend(simulate_account(aid, modules, seed, cycles))
    return pd.DataFrame(rows)


def portfolio_kpis(df: pd.DataFrame) -> dict[str, float]:
    """KPIs billing can honestly support. Delinquency here is a simplified
    missed-payment signal, not a full collections model."""
    if df.empty:
        return {}
    adb_sum = float(df["average_daily_balance"].sum())
    return {
        "account_cycles": int(len(df)),
        "revolve_rate": round(float((df["ending_balance"] > 0).mean()), 4),
        "avg_utilization": round(float(df["utilization"].mean()), 4),
        "pay_in_full_rate": round(float(df["paid_in_full"].mean()), 4),
        "avg_interest_per_cycle": round(float(df["interest"].mean()), 2),
        "monthly_interest_yield": round(float(df["interest"].sum() / adb_sum), 4) if adb_sum else 0.0,
        "delinquency_rate": round(float((df["dpd"] > 0).mean()), 4),
    }
