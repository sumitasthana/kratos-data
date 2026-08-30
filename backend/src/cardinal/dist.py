"""Distribution family registry.

Each family is a small pure function of (n, rng, params). Parameters always
come from the field spec YAML, never from a literal in this file. Add a family
by writing one function and registering it. Nothing else changes.

Mean and variance are never inputs. Almost nothing on a card account is
Gaussian, so fields declare a family and its own parameters.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
from scipy import stats

Sampler = Callable[[int, np.random.Generator, dict[str, Any]], np.ndarray]


def _constant(n: int, rng: np.random.Generator, p: dict[str, Any]) -> np.ndarray:
    return np.full(n, p["value"])


def _categorical(n: int, rng: np.random.Generator, p: dict[str, Any]) -> np.ndarray:
    values = np.asarray(p["values"])
    weights = np.asarray(p["weights"], dtype=float)
    weights = weights / weights.sum()
    idx = rng.choice(len(values), size=n, p=weights)
    return values[idx]


def _truncated_normal(n: int, rng: np.random.Generator, p: dict[str, Any]) -> np.ndarray:
    mu, sigma = float(p["mu"]), float(p["sigma"])
    lo, hi = float(p["lo"]), float(p["hi"])
    a, b = (lo - mu) / sigma, (hi - mu) / sigma
    return stats.truncnorm.rvs(a, b, loc=mu, scale=sigma, size=n, random_state=rng)


def _beta(n: int, rng: np.random.Generator, p: dict[str, Any]) -> np.ndarray:
    return rng.beta(float(p["a"]), float(p["b"]), size=n)


_REGISTRY: dict[str, Sampler] = {
    "constant": _constant,
    "categorical": _categorical,
    "truncated_normal": _truncated_normal,
    "beta": _beta,
}


def sample(spec: dict[str, Any], n: int, rng: np.random.Generator) -> np.ndarray:
    """Sample n values from a field's `dist` block."""
    family = spec.get("family")
    if family not in _REGISTRY:
        raise ValueError(f"unknown distribution family: {family!r}")
    params = {k: v for k, v in spec.items() if k != "family"}
    return _REGISTRY[family](n, rng, params)


def categorical_row_weighted(
    values: np.ndarray, log_weights: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Sample one categorical value per row given per-row log-weights (n, k).

    Used by the weight_tilt mechanism, where each account gets its own tilted
    weight vector derived from a parent value.
    """
    w = np.exp(log_weights - log_weights.max(axis=1, keepdims=True))
    w = w / w.sum(axis=1, keepdims=True)
    cum = np.cumsum(w, axis=1)
    u = rng.random(size=(w.shape[0], 1))
    idx = (cum < u).sum(axis=1)
    idx = np.clip(idx, 0, len(values) - 1)
    return values[idx]
