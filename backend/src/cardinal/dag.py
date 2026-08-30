"""Dependency graph: build it, and prove the unrolled version is acyclic.

The core card economics loop is a real cycle:

    credit_limit[t] -> utilization[t] -> refreshed_fico[t+1] -> cli[t+1] -> ...

Written in one time slice that is a cycle and the topological sort fails.
Broken with an explicit lag (fico[t] <- utilization[t-1]) the graph unrolled
over time is acyclic and the feedback still plays out across cycles.

So the check is simple and exact: a cycle in the dependency graph is legal
only if it crosses a time step, i.e. it contains at least one edge with
lag >= 1. Equivalently, the subgraph of lag-0 edges must itself be acyclic.
A cycle among lag-0 edges means someone forgot a lag. That is the whole point
of ADR-003, and it fails at build time, not runtime.
"""
from __future__ import annotations

from .spec import SpecBundle


class BuildError(Exception):
    """Raised when the spec cannot be turned into a valid build plan."""


def _edges(bundle: SpecBundle) -> list[tuple[str, str, int]]:
    """(parent_field, child_field, lag) for every declared field dependency."""
    out: list[tuple[str, str, int]] = []
    for child, fs in bundle.fields.items():
        for dep in fs.depends_on:
            out.append((dep.field, child, dep.lag))
    return out


def build_order(bundle: SpecBundle) -> list[str]:
    """Return a topological order of the lag-0 subgraph, or raise BuildError.

    The returned order is the order fields can be sampled within a single
    cycle. Nodes referenced only as parents (produced elsewhere) are included.
    """
    edges = _edges(bundle)

    nodes: set[str] = set(bundle.fields.keys())
    for parent, child, _ in edges:
        nodes.add(parent)
        nodes.add(child)

    # Kahn's algorithm over lag-0 edges only.
    lag0 = [(a, b) for a, b, lag in edges if lag == 0]
    indeg: dict[str, int] = {n: 0 for n in nodes}
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in lag0:
        adj[a].append(b)
        indeg[b] += 1

    queue = sorted(n for n in nodes if indeg[n] == 0)
    order: list[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in sorted(adj[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
        queue.sort()

    if len(order) != len(nodes):
        stuck = sorted(n for n in nodes if indeg[n] > 0)
        raise BuildError(
            "cycle among lag-0 edges (a dependency is missing a lag): "
            + ", ".join(stuck)
            + ". Break it by giving one edge in the cycle lag >= 1."
        )
    return order
