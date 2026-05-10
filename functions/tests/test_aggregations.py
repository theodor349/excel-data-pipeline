from decimal import Decimal

import pandas as pd
import pytest

from functions.aggregations import avg, count, max, min, sum


def make_decimal_df(groups, amounts):
    return pd.DataFrame(
        {"group": groups, "amount": pd.array(amounts, dtype=object)}
    )


# ---------------------------------------------------------------------------
# sum — Decimal precision
# ---------------------------------------------------------------------------

def test_sum_decimal_1000_rows_exact():
    """1000 rows of Decimal('0.10') in one group must sum to exactly Decimal('100.00')."""
    values = [Decimal("0.10")] * 1000
    df = make_decimal_df(["A"] * 1000, values)
    result = sum(df, "group", "amount")
    assert result.loc[0, "amount"] == Decimal("100.00")


def test_sum_decimal_two_groups():
    amounts = [Decimal("0.10")] * 3 + [Decimal("0.20")] * 5
    df = make_decimal_df(["A"] * 3 + ["B"] * 5, amounts)
    result = sum(df, "group", "amount")
    a_total = result.loc[result["group"] == "A", "amount"].iloc[0]
    b_total = result.loc[result["group"] == "B", "amount"].iloc[0]
    assert isinstance(a_total, Decimal)
    assert isinstance(b_total, Decimal)
    assert a_total == Decimal("0.30")
    assert b_total == Decimal("1.00")


def test_sum_result_column_named_after_input():
    df = make_decimal_df(["A"], [Decimal("1.00")])
    result = sum(df, "group", "amount")
    assert "amount" in result.columns
    assert "amount_sum" not in result.columns


def test_sum_float_column_returns_float():
    df = pd.DataFrame({"group": ["A", "A", "B"], "value": [1.5, 2.5, 3.0]})
    result = sum(df, "group", "value")
    a_val = result.loc[result["group"] == "A", "value"].iloc[0]
    assert isinstance(a_val, float)
    assert a_val == 4.0


# ---------------------------------------------------------------------------
# avg — Decimal precision and rounding
# ---------------------------------------------------------------------------

def test_avg_decimal_uniform():
    """avg of [0.10, 0.10, 0.10] must be exactly Decimal('0.10')."""
    df = make_decimal_df(["A", "A", "A"], [Decimal("0.10")] * 3)
    result = avg(df, "group", "amount")
    assert result.loc[0, "amount"] == Decimal("0.10")


def test_avg_decimal_round_half_up():
    """avg of [1.00, 2.00, 4.00] = 7/3 = 2.333... -> Decimal('2.33') with ROUND_HALF_UP."""
    df = make_decimal_df(
        ["A", "A", "A"],
        [Decimal("1.00"), Decimal("2.00"), Decimal("4.00")],
    )
    result = avg(df, "group", "amount")
    assert result.loc[0, "amount"] == Decimal("2.33")


def test_avg_decimal_half_up_vs_banker():
    """avg([0.10, 0.11]) = 0.105 -> ROUND_HALF_UP at 2 places = 0.11; banker's = 0.10.
    The function must use ROUND_HALF_UP (finance convention).
    """
    df = make_decimal_df(["A", "A"], [Decimal("0.10"), Decimal("0.11")])
    result = avg(df, "group", "amount")
    assert result.loc[0, "amount"] == Decimal("0.11")


def test_avg_decimal_honors_column_precision_above_two():
    """A 4-place column (e.g. FX rates) must produce a 4-place avg result."""
    df = make_decimal_df(
        ["A", "A"], [Decimal("1.2345"), Decimal("1.2347")]
    )
    result = avg(df, "group", "amount")
    assert result.loc[0, "amount"] == Decimal("1.2346")


def test_avg_result_column_named_after_input():
    df = make_decimal_df(["A", "A"], [Decimal("1.00"), Decimal("3.00")])
    result = avg(df, "group", "amount")
    assert "amount" in result.columns
    assert "amount_mean" not in result.columns


# ---------------------------------------------------------------------------
# min / max — Decimal preservation
# ---------------------------------------------------------------------------

def test_min_decimal_returns_decimal():
    df = make_decimal_df(
        ["A", "A", "A"],
        [Decimal("3.00"), Decimal("1.00"), Decimal("2.00")],
    )
    result = min(df, "group", "amount")
    val = result.iloc[0]["amount"]
    assert isinstance(val, Decimal)
    assert val == Decimal("1.00")


def test_max_decimal_returns_decimal():
    df = make_decimal_df(
        ["A", "A", "A"],
        [Decimal("3.00"), Decimal("1.00"), Decimal("2.00")],
    )
    result = max(df, "group", "amount")
    val = result.iloc[0]["amount"]
    assert isinstance(val, Decimal)
    assert val == Decimal("3.00")


def test_min_result_column_named_after_input():
    df = make_decimal_df(["A"], [Decimal("1.00")])
    result = min(df, "group", "amount")
    assert "amount" in result.columns


def test_max_result_column_named_after_input():
    df = make_decimal_df(["A"], [Decimal("1.00")])
    result = max(df, "group", "amount")
    assert "amount" in result.columns


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------

def test_count_basic():
    df = pd.DataFrame({"group": ["A", "A", "B", "B", "B"]})
    result = count(df, "group")
    assert "count" in result.columns
    a_count = result.loc[result["group"] == "A", "count"].iloc[0]
    b_count = result.loc[result["group"] == "B", "count"].iloc[0]
    assert a_count == 2
    assert b_count == 3


def test_count_returns_int():
    df = pd.DataFrame({"group": ["A", "A"]})
    result = count(df, "group")
    val = result.loc[0, "count"]
    assert isinstance(val, (int, )) or pd.api.types.is_integer_dtype(type(val))


# ---------------------------------------------------------------------------
# group_by as list (multi-key groupby)
# ---------------------------------------------------------------------------

def test_sum_multi_key_groupby():
    df = pd.DataFrame(
        {
            "region": ["North", "North", "South", "South"],
            "product": ["X", "X", "Y", "Y"],
            "amount": pd.array(
                [Decimal("1.00"), Decimal("2.00"), Decimal("3.00"), Decimal("4.00")],
                dtype=object,
            ),
        }
    )
    result = sum(df, ["region", "product"], "amount")
    assert "region" in result.columns
    assert "product" in result.columns
    north_x = result.loc[
        (result["region"] == "North") & (result["product"] == "X"), "amount"
    ].iloc[0]
    south_y = result.loc[
        (result["region"] == "South") & (result["product"] == "Y"), "amount"
    ].iloc[0]
    assert north_x == Decimal("3.00")
    assert south_y == Decimal("7.00")


def test_count_multi_key_groupby():
    df = pd.DataFrame(
        {
            "region": ["North", "North", "South"],
            "product": ["X", "X", "Y"],
        }
    )
    result = count(df, ["region", "product"])
    north_x = result.loc[
        (result["region"] == "North") & (result["product"] == "X"), "count"
    ].iloc[0]
    assert north_x == 2


def test_avg_single_key_string():
    df = make_decimal_df(["A", "A"], [Decimal("2.00"), Decimal("4.00")])
    result = avg(df, "group", "amount")
    assert result.loc[0, "amount"] == Decimal("3.00")
