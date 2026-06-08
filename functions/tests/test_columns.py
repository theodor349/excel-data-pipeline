from decimal import Decimal

import polars as pl
import pytest

from functions.columns import (
    add_literal_column,
    conditional_column,
    duplicate_column,
    keep_columns,
    remove_columns,
    reorder_columns,
)


# ---------------------------------------------------------------------------
# conditional_column
# ---------------------------------------------------------------------------


def test_conditional_column_greater_than():
    df = pl.DataFrame({"amount": [500, 1000, 1500]})
    result = conditional_column(
        df, "amount", "greater_than", 1000, "Over budget", "Within budget", "status"
    )
    assert result["status"].to_list() == [
        "Within budget",
        "Within budget",
        "Over budget",
    ]


def test_conditional_column_equals():
    df = pl.DataFrame({"region": ["EU", "US", "EU"]})
    result = conditional_column(
        df, "region", "equals", "EU", "domestic", "foreign", "kind"
    )
    assert result["kind"].to_list() == ["domestic", "foreign", "domestic"]


def test_conditional_column_at_least_and_at_most():
    df = pl.DataFrame({"n": [1, 2, 3]})
    at_least = conditional_column(df, "n", "at_least", 2, "hi", "lo", "f")
    assert at_least["f"].to_list() == ["lo", "hi", "hi"]
    at_most = conditional_column(df, "n", "at_most", 2, "hi", "lo", "f")
    assert at_most["f"].to_list() == ["hi", "hi", "lo"]


def test_conditional_column_numeric_then_else():
    df = pl.DataFrame({"flag": [10, 0, 5]})
    result = conditional_column(df, "flag", "greater_than", 0, 1, 0, "active")
    assert result["active"].to_list() == [1, 0, 1]


def test_conditional_column_null_uses_else():
    df = pl.DataFrame({"n": [5, None, 1]})
    result = conditional_column(df, "n", "greater_than", 3, "yes", "no", "result")
    # A null comparison is not true, so the else branch is taken.
    assert result["result"].to_list() == ["yes", "no", "no"]


def test_conditional_column_decimal_compare_exact():
    # Money column compared against a bound that is not exactly a binary float.
    df = pl.DataFrame(
        {"amount": [Decimal("0.10"), Decimal("0.30"), Decimal("0.31")]}
    )
    result = conditional_column(
        df, "amount", "greater_than", 0.30, "over", "ok", "flag"
    )
    assert result["flag"].to_list() == ["ok", "ok", "over"]


def test_conditional_column_unknown_comparison_raises():
    df = pl.DataFrame({"n": [1]})
    with pytest.raises(ValueError, match="Unknown comparison"):
        conditional_column(df, "n", "roughly", 1, "a", "b", "f")


def test_conditional_column_does_not_mutate():
    df = pl.DataFrame({"n": [1, 2]})
    conditional_column(df, "n", "greater_than", 1, "a", "b", "result")
    assert "result" not in df.columns


# ---------------------------------------------------------------------------
# add_literal_column
# ---------------------------------------------------------------------------


def test_add_literal_column_string():
    df = pl.DataFrame({"x": [1, 2, 3]})
    result = add_literal_column(df, "report_period", "FY2026")
    assert result["report_period"].to_list() == ["FY2026", "FY2026", "FY2026"]


def test_add_literal_column_int():
    df = pl.DataFrame({"x": [1, 2]})
    result = add_literal_column(df, "year", 2026)
    assert result["year"].to_list() == [2026, 2026]


def test_add_literal_column_float_without_decimal():
    df = pl.DataFrame({"x": [1, 2]})
    result = add_literal_column(df, "ratio", 1.5)
    assert result["ratio"].to_list() == [1.5, 1.5]


def test_add_literal_column_does_not_mutate():
    df = pl.DataFrame({"x": [1]})
    add_literal_column(df, "const", "value")
    assert "const" not in df.columns


def test_add_literal_column_decimal_from_decimal_value():
    df = pl.DataFrame({"x": [1, 2]})
    result = add_literal_column(df, "rate", Decimal("1.05"))
    assert result["rate"].dtype == pl.Decimal(scale=2)
    assert result["rate"].to_list() == [Decimal("1.05"), Decimal("1.05")]


def test_add_literal_column_decimal_via_flag():
    df = pl.DataFrame({"x": [1]})
    result = add_literal_column(df, "money", "99.99", as_decimal=True)
    assert result["money"].dtype == pl.Decimal(scale=2)
    assert result["money"].to_list() == [Decimal("99.99")]


def test_add_literal_column_decimal_half_up_rounding():
    # 0.125 -> 0.13 under half-up (not 0.12 from native half-even).
    df = pl.DataFrame({"x": [1]})
    result = add_literal_column(df, "rounded", 0.125, as_decimal=True)
    assert result["rounded"].to_list() == [Decimal("0.13")]


def test_add_literal_column_decimal_exact_precision():
    # The exact-Decimal path is load-bearing: no binary float drift.
    df = pl.DataFrame({"x": list(range(1000))})
    result = add_literal_column(df, "rate", Decimal("0.10"))
    assert result["rate"].to_list() == [Decimal("0.10")] * 1000


def test_add_literal_column_decimal_custom_places():
    df = pl.DataFrame({"x": [1]})
    result = add_literal_column(df, "fx", Decimal("1.2345"), places=4)
    assert result["fx"].dtype == pl.Decimal(scale=4)
    assert result["fx"].to_list() == [Decimal("1.2345")]


# ---------------------------------------------------------------------------
# keep_columns
# ---------------------------------------------------------------------------


def test_keep_columns_basic():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = keep_columns(df, ["a", "c"])
    assert result.columns == ["a", "c"]


def test_keep_columns_order():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = keep_columns(df, ["c", "a"])
    assert result.columns == ["c", "a"]


def test_keep_columns_missing_raises():
    df = pl.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(KeyError, match="Columns not found"):
        keep_columns(df, ["a", "z"])


def test_keep_columns_does_not_mutate():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    keep_columns(df, ["a"])
    assert df.columns == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# remove_columns
# ---------------------------------------------------------------------------


def test_remove_columns_single():
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    result = remove_columns(df, ["b"])
    assert result.columns == ["a", "c"]


def test_remove_columns_multiple():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]})
    result = remove_columns(df, ["b", "d"])
    assert result.columns == ["a", "c"]


def test_remove_columns_does_not_mutate():
    df = pl.DataFrame({"a": [1], "b": [2]})
    remove_columns(df, ["b"])
    assert "b" in df.columns


def test_remove_columns_missing_raises():
    df = pl.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(KeyError, match="Columns not found"):
        remove_columns(df, ["x"])


def test_remove_columns_preserves_data():
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    result = remove_columns(df, ["b"])
    assert result["a"].to_list() == [1, 2]
    assert result["c"].to_list() == [5, 6]


# ---------------------------------------------------------------------------
# duplicate_column
# ---------------------------------------------------------------------------


def test_duplicate_column_basic():
    df = pl.DataFrame({"original": [1, 2, 3]})
    result = duplicate_column(df, "original", "copy")
    assert result["copy"].to_list() == [1, 2, 3]
    assert result.columns == ["original", "copy"]


def test_duplicate_column_does_not_mutate():
    df = pl.DataFrame({"a": [1, 2]})
    duplicate_column(df, "a", "b")
    assert "b" not in df.columns


def test_duplicate_column_preserves_decimal_dtype():
    df = pl.DataFrame({"amount": [Decimal("1.50"), Decimal("2.30")]})
    result = duplicate_column(df, "amount", "amount_copy")
    assert result["amount_copy"].dtype == pl.Decimal(scale=2)
    assert result["amount_copy"].to_list() == [Decimal("1.50"), Decimal("2.30")]


def test_duplicate_column_missing_source_raises():
    df = pl.DataFrame({"a": [1]})
    with pytest.raises(KeyError, match="Source column"):
        duplicate_column(df, "missing", "target")


def test_duplicate_column_with_nulls():
    df = pl.DataFrame({"source": [1, None, 3]})
    result = duplicate_column(df, "source", "target")
    assert result["target"].to_list() == [1, None, 3]


# ---------------------------------------------------------------------------
# reorder_columns
# ---------------------------------------------------------------------------


def test_reorder_columns_basic():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = reorder_columns(df, ["c", "a", "b"])
    assert result.columns == ["c", "a", "b"]


def test_reorder_columns_does_not_mutate():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    reorder_columns(df, ["b", "a", "c"])
    assert df.columns == ["a", "b", "c"]


def test_reorder_columns_subset():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3], "d": [4]})
    result = reorder_columns(df, ["d", "a"])
    assert result.columns == ["d", "a"]


def test_reorder_columns_missing_raises():
    df = pl.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(KeyError, match="Columns not found"):
        reorder_columns(df, ["a", "x", "b"])


def test_reorder_columns_preserves_data():
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4], "c": [5, 6]})
    result = reorder_columns(df, ["c", "a", "b"])
    assert result["a"].to_list() == [1, 2]
    assert result["b"].to_list() == [3, 4]
    assert result["c"].to_list() == [5, 6]
