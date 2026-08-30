"""Seed derivation. Read this before touching anything else in the engine.

Determinism is absolute: same seed, same bytes, on any machine, at any level
of parallelism. That only holds if every entity draws from its own independent
stream, keyed by where it sits in the run, never from a shared global RNG
consumed in loop order. Thread scheduling must not be able to change a result.
"""
from __future__ import annotations

from numpy.random import Generator, PCG64, SeedSequence


def stream(
    master_seed: int,
    domain_id: int,
    entity_id: int,
    cycle: int = 0,
    attempt: int = 0,
) -> Generator:
    """One independent Generator per (domain, entity, cycle, attempt).

    `attempt` is part of the key so a rejected account regenerates with a
    different stream instead of replaying the same rejected draw. The spawn
    key makes streams reproducible regardless of processing order.
    """
    ss = SeedSequence(entropy=master_seed, spawn_key=(domain_id, entity_id, cycle, attempt))
    return Generator(PCG64(ss))
