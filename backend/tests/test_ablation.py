"""Ablation proves the one domain actually does work, rather than sitting in
the schema disconnected. Turn the line-increase handler off and no limit should
ever change, and no CLI events should exist. Turn it on and both happen.
"""
from __future__ import annotations

from cardinal.engine import generate
from cardinal.spec import load_specs


def _run(spec_path, ablate):
    bundle = load_specs(spec_path)
    bundle.portfolio.accounts = 300
    return generate(bundle, ablate=ablate)


def test_handler_off_means_no_line_changes(spec_path):
    result = _run(spec_path, ablate=True)
    assert result["stats"]["cli_events"] == 0

    ac = result["account_cycle"]
    # With no CLIs, the in-force limit never departs from the initial limit.
    changed = (
        ac.groupby("account_id")["credit_limit_in_force"].nunique().gt(1).sum()
    )
    assert changed == 0


def test_handler_on_produces_line_changes(spec_path):
    result = _run(spec_path, ablate=False)
    assert result["stats"]["cli_events"] > 0

    ac = result["account_cycle"]
    changed = (
        ac.groupby("account_id")["credit_limit_in_force"].nunique().gt(1).sum()
    )
    assert changed > 0
