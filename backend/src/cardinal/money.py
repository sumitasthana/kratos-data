"""Money is Decimal in domain logic, never float. Balances that drift by a
cent are a bug the whole system is built to catch, so the arithmetic must be
exact."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def money(x: object) -> Decimal:
    """Coerce to a Decimal rounded to cents."""
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def round_to(x: Decimal, step: int) -> Decimal:
    """Round a Decimal to the nearest `step` dollars (e.g. limits to 500)."""
    s = Decimal(step)
    return (x / s).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * s
