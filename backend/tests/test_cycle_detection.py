"""ADR-003: a cycle among lag-0 edges must fail at build time.

The real specs describe the limit -> utilisation -> score -> limit loop and
must pass, because every back-edge in that loop crosses a time step. A spec
where someone forgot a lag must fail with a clear message.
"""
from __future__ import annotations

import pytest

from cardinal.dag import BuildError, build_order
from cardinal.spec import FieldSpec, InvariantSpec, PortfolioSpec, SpecBundle, load_specs


def _bundle(fields: dict[str, FieldSpec]) -> SpecBundle:
    return SpecBundle(
        portfolio=PortfolioSpec(name="t", accounts=1, cycles=1, seed=1),
        fields=fields,
        events={},
        invariants=[],
    )


def test_real_specs_are_acyclic(spec_path):
    bundle = load_specs(spec_path)
    order = build_order(bundle)  # must not raise
    assert set(bundle.fields).issubset(set(order))


def test_lag0_cycle_is_rejected():
    fields = {
        "a": FieldSpec(name="a", grain="account_cycle", dtype="f",
                       depends_on=[{"field": "b", "lag": 0}]),
        "b": FieldSpec(name="b", grain="account_cycle", dtype="f",
                       depends_on=[{"field": "a", "lag": 0}]),
    }
    with pytest.raises(BuildError):
        build_order(_bundle(fields))


def test_same_cycle_lagged_is_accepted():
    # Same two fields, but one edge now crosses a time step. Legal.
    fields = {
        "a": FieldSpec(name="a", grain="account_cycle", dtype="f",
                       depends_on=[{"field": "b", "lag": 0}]),
        "b": FieldSpec(name="b", grain="account_cycle", dtype="f",
                       depends_on=[{"field": "a", "lag": 1}]),
    }
    order = build_order(_bundle(fields))
    assert order.index("b") < order.index("a")
