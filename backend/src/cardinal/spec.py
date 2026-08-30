"""Spec language: pydantic models plus the three core protocols.

The specs are the product. The engine is an interpreter for these files. The
three protocols (Distribution, EventHandler, Invariant) are the only sockets a
new capability plugs into. Adding a domain means implementing EventHandler and
registering it. Nothing else in the engine changes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel

Grain = Literal["applicant", "account", "account_cycle", "event", "reference"]
Mechanism = Literal["weight_tilt", "scale", "shift", "gate", "logit", "formula"]


# --------------------------------------------------------------------------
# Spec models (mirror the YAML)
# --------------------------------------------------------------------------
class DependsOn(BaseModel):
    field: str
    lag: int = 0
    mechanism: Mechanism = "scale"
    strength: float = 1.0


class FieldSpec(BaseModel):
    name: str
    grain: Grain
    dtype: str
    unit: str | None = None
    dist: dict[str, Any] | None = None
    depends_on: list[DependsOn] = []
    bounds: dict[str, Any] | None = None
    calibration: str | None = None


class EventSpec(BaseModel):
    name: str
    grain: str = "account"
    trigger: dict[str, Any] | None = None
    eligibility: list[str] = []
    hazard: dict[str, Any] | None = None
    amount: dict[str, Any] | None = None
    effects: list[str] = []
    emits: list[str] = []
    downstream: list[DependsOn] = []


class InvariantSpec(BaseModel):
    id: str
    grain: str = "account_cycle"
    expr: str
    severity: Literal["hard", "soft"] = "hard"
    source: str | None = None
    note: str | None = None


class PortfolioSpec(BaseModel):
    name: str
    accounts: int
    cycles: int
    seed: int
    out: str = "data"


class SpecBundle(BaseModel):
    portfolio: PortfolioSpec
    fields: dict[str, FieldSpec]
    events: dict[str, EventSpec]
    invariants: list[InvariantSpec]


# --------------------------------------------------------------------------
# Core protocols: the three plug points
# --------------------------------------------------------------------------
@runtime_checkable
class Distribution(Protocol):
    family: str

    def sample(self, n: int, rng: np.random.Generator, params: dict[str, Any]) -> np.ndarray:
        ...


@runtime_checkable
class EventHandler(Protocol):
    event_type: str
    domain: str

    def eligible(self, acct: Any, cycle: int) -> bool:
        """Deterministic policy or regulatory gate. No RNG in here."""

    def hazard(self, acct: Any, cycle: int) -> float:
        """P(event | eligible), in [0, 1]."""

    def fire(self, acct: Any, cycle: int, rng: np.random.Generator) -> list[Any]:
        """Produce events and mutate acct via declared effects."""


@runtime_checkable
class Invariant(Protocol):
    id: str
    severity: str
    grain: str

    def check(self, frame: pd.DataFrame) -> pd.Series:
        """Boolean Series indexed like frame. True means satisfied."""


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------
def _yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_specs(portfolio_path: str | Path) -> SpecBundle:
    """Load a portfolio.yaml and every sibling spec directory beside it."""
    p = Path(portfolio_path)
    root = p.parent

    portfolio = PortfolioSpec(**_yaml(p))

    fields: dict[str, FieldSpec] = {}
    for f in sorted((root / "fields").glob("*.yaml")):
        for name, body in (_yaml(f).get("fields") or {}).items():
            fields[name] = FieldSpec(name=name, **body)

    events: dict[str, EventSpec] = {}
    for f in sorted((root / "domains").glob("*.yaml")):
        for name, body in (_yaml(f).get("events") or {}).items():
            events[name] = EventSpec(name=name, **body)

    invariants: list[InvariantSpec] = []
    for f in sorted((root / "invariants").glob("*.yaml")):
        for inv in _yaml(f).get("invariants") or []:
            invariants.append(InvariantSpec(**inv))

    return SpecBundle(portfolio=portfolio, fields=fields, events=events, invariants=invariants)
