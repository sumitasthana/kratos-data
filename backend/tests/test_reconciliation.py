"""The most valuable test in the suite: replay the event stream from scratch
in a separate function and match the stored account_cycle table to the cent.
This catches projection bugs the invariants miss, and it is the proof that the
tables really are projections of the events, not a parallel fiction.
"""
from __future__ import annotations

from decimal import Decimal

from cardinal.engine import generate
from cardinal.spec import load_specs

CENT = Decimal("0.01")


def _replay(events_df) -> dict[tuple[int, int], Decimal]:
    """Reconstruct ending balance per (account, cycle) from events alone."""
    balances: dict[tuple[int, int], Decimal] = {}
    for aid, grp in events_df.groupby("account_id"):
        bal = Decimal("0")
        grp = grp.sort_values("cycle")
        for cycle, cyc_events in grp.groupby("cycle"):
            for _, e in cyc_events.iterrows():
                amt = Decimal("0") if e["amount"] is None else Decimal(str(e["amount"]))
                if e["type"] in ("account_opened", "purchase"):
                    bal += amt
                elif e["type"] == "payment":
                    bal -= amt
                # line_increase / change_in_terms_notice do not move the balance
            if cycle >= 1:
                balances[(int(aid), int(cycle))] = bal.quantize(CENT)
    return balances


def test_event_state_reconciliation(spec_path):
    bundle = load_specs(spec_path)
    bundle.portfolio.accounts = 200
    result = generate(bundle)

    replayed = _replay(result["events"])
    ac = result["account_cycle"]

    mismatches = 0
    for _, row in ac.iterrows():
        key = (int(row["account_id"]), int(row["cycle_seq"]))
        stored = Decimal(str(row["cycle_ending_balance"])).quantize(CENT)
        assert key in replayed, f"no events reconstruct {key}"
        if replayed[key] != stored:
            mismatches += 1
    assert mismatches == 0, f"{mismatches} rows where events do not match the stored balance"
