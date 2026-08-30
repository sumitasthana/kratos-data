"""Make the `cardinal` package importable and expose the spec path."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

SPEC = BACKEND / "specs" / "portfolio.yaml"


@pytest.fixture
def spec_path() -> Path:
    return SPEC
