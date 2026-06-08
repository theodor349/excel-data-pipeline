"""Shared, exact-Decimal rounding used by every money function.

The default rounding (`quantize`) is hardcoded to half-up (finance convention) —
not configurable, so the same data always rounds the same way. Only the number of
decimal `places` is configurable (via settings.json), defaulting to 2.

`quantize_up`/`quantize_down` are *separate, explicitly-named* directional
operations (not a swappable mode for `quantize`): they round away from zero and
toward zero respectively, matching Excel's ROUNDUP/ROUNDDOWN — the workflow this
pipeline replaces. Each has one fixed, deterministic behaviour.

Polars' native Decimal cast and Decimal arithmetic round half-even at scales we
don't control, and can silently drop precision (e.g. 1.10 * 1.05 -> 1.16). So
all money rounding goes through Python's `Decimal`, quantized once. We use
`Decimal(str(value))` (never `Decimal(value)`) so we round the literal the user
typed, not its IEEE-754 binary expansion.
"""

from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal

from engine.settings import get_default_places


def resolve_places(places: int | None) -> int:
    """A places argument of None falls back to the settings.json default."""
    return get_default_places() if places is None else places


def _quantize(value, places: int, rounding) -> Decimal | None:
    if value is None:
        return None
    q = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(q, rounding=rounding)


def quantize(value, places: int) -> Decimal | None:
    """Round a single value to `places` decimals, half-up, exactly.

    None passes through unchanged.
    """
    return _quantize(value, places, ROUND_HALF_UP)


def quantize_up(value, places: int) -> Decimal | None:
    """Round a single value to `places` decimals away from zero (Excel ROUNDUP).

    e.g. 1.41 -> 1.5 and -1.41 -> -1.5 at 1 place. None passes through unchanged.
    """
    return _quantize(value, places, ROUND_UP)


def quantize_down(value, places: int) -> Decimal | None:
    """Round a single value to `places` decimals toward zero (Excel ROUNDDOWN).

    e.g. 1.49 -> 1.4 and -1.49 -> -1.4 at 1 place. None passes through unchanged.
    """
    return _quantize(value, places, ROUND_DOWN)
