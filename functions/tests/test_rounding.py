from decimal import Decimal

from functions._rounding import quantize, quantize_down, quantize_up


# ---------------------------------------------------------------------------
# quantize — half-up
# ---------------------------------------------------------------------------


def test_quantize_half_up():
    assert quantize("0.125", 2) == Decimal("0.13")
    assert quantize("0.124", 2) == Decimal("0.12")


def test_quantize_half_up_from_float_uses_literal():
    # Decimal(str(2.675)) -> "2.675", half-up -> 2.68 (binary Decimal(2.675)
    # would be 2.67499... and round down).
    assert quantize(2.675, 2) == Decimal("2.68")


def test_quantize_none_passthrough():
    assert quantize(None, 2) is None


# ---------------------------------------------------------------------------
# quantize_up — away from zero (Excel ROUNDUP)
# ---------------------------------------------------------------------------


def test_quantize_up_positive_away_from_zero():
    assert quantize_up("1.41", 1) == Decimal("1.5")
    assert quantize_up("1.40", 1) == Decimal("1.4")  # exact, no rounding


def test_quantize_up_negative_away_from_zero():
    assert quantize_up("-1.41", 1) == Decimal("-1.5")


def test_quantize_up_none_passthrough():
    assert quantize_up(None, 2) is None


# ---------------------------------------------------------------------------
# quantize_down — toward zero (Excel ROUNDDOWN)
# ---------------------------------------------------------------------------


def test_quantize_down_positive_toward_zero():
    assert quantize_down("1.49", 1) == Decimal("1.4")


def test_quantize_down_negative_toward_zero():
    assert quantize_down("-1.49", 1) == Decimal("-1.4")


def test_quantize_down_none_passthrough():
    assert quantize_down(None, 2) is None
