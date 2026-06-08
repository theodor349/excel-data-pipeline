"""Shared, exact-Decimal rounding used by every money function.

Rounding is hardcoded to half-up (finance convention) — not configurable, so the
same data always rounds the same way. Only the number of decimal `places` is
configurable (via settings.json), defaulting to 2.

Polars' native Decimal cast and Decimal arithmetic round half-even at scales we
don't control, and can silently drop precision (e.g. 1.10 * 1.05 -> 1.16). So
all money rounding goes through Python's `Decimal`, quantized once. We use
`Decimal(str(value))` (never `Decimal(value)`) so we round the literal the user
typed, not its IEEE-754 binary expansion.
"""

from decimal import ROUND_HALF_UP, Decimal

from engine.settings import get_default_places


def resolve_places(places: int | None) -> int:
    """A places argument of None falls back to the settings.json default."""
    return get_default_places() if places is None else places


def quantize(value, places: int) -> Decimal | None:
    """Round a single value to `places` decimals, half-up, exactly.

    None passes through unchanged.
    """
    if value is None:
        return None
    q = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)
