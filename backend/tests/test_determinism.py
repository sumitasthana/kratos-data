"""Determinism is absolute: same seed, same content hash. Different seed,
different content hash. This is the cheapest, highest-value guard in the suite.
"""
from __future__ import annotations

from cardinal.emit import content_hash
from cardinal.engine import generate
from cardinal.spec import load_specs

FRAMES = ("account_cycle", "events", "accounts")


def _hash(spec_path, seed):
    bundle = load_specs(spec_path)
    bundle.portfolio.accounts = 200
    bundle.portfolio.seed = seed
    result = generate(bundle)
    return content_hash({k: result[k] for k in FRAMES})


def test_same_seed_same_output(spec_path):
    assert _hash(spec_path, 42) == _hash(spec_path, 42)


def test_different_seed_different_output(spec_path):
    assert _hash(spec_path, 42) != _hash(spec_path, 43)
