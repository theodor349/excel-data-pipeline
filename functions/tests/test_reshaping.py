from decimal import Decimal

import polars as pl
import pytest

from functions.reshaping import fill_down, fill_up, group, pivot, unpivot


def _monthly_money_df():
    return pl.DataFrame(
        {
            "account": ["A", "B"],
            "Jan": [Decimal("1.10"), Decimal("2.20")],
            "Feb": [Decimal("3.30"), Decimal("4.40")],
        }
    )


# ---------------------------------------------------------------------------
# unpivot
# ---------------------------------------------------------------------------

def test_unpivot_month_columns_to_rows():
    result = unpivot(
        _monthly_money_df(),
        columns=["Jan", "Feb"],
        index="account",
        variable_name="month",
        value_name="amount",
    )
    assert result.columns == ["account", "month", "amount"]
    assert result["account"].to_list() == ["A", "B", "A", "B"]
    assert result["month"].to_list() == ["Jan", "Jan", "Feb", "Feb"]
    assert result["amount"].to_list() == [
        Decimal("1.10"),
        Decimal("2.20"),
        Decimal("3.30"),
        Decimal("4.40"),
    ]
    assert result["amount"].dtype == pl.Decimal(scale=2)


def test_unpivot_does_not_mutate():
    df = _monthly_money_df()
    unpivot(df, columns=["Jan", "Feb"], index="account")
    assert df.columns == ["account", "Jan", "Feb"]


# ---------------------------------------------------------------------------
# pivot
# ---------------------------------------------------------------------------

def test_pivot_rows_to_columns_preserves_decimal():
    df = pl.DataFrame(
        {
            "account": ["A", "A", "B", "B"],
            "month": ["Jan", "Feb", "Jan", "Feb"],
            "amount": [
                Decimal("1.10"),
                Decimal("3.30"),
                Decimal("2.20"),
                Decimal("4.40"),
            ],
        }
    )
    result = pivot(
        df,
        index="account",
        columns="month",
        values="amount",
        aggregate_function="sum",
        sort_columns=True,
    )
    assert result.columns == ["account", "Feb", "Jan"]
    row_a = result.filter(pl.col("account") == "A")
    assert row_a["Jan"][0] == Decimal("1.10")
    assert row_a["Feb"][0] == Decimal("3.30")
    assert result["Jan"].dtype == pl.Decimal(scale=2)
    assert result["Feb"].dtype == pl.Decimal(scale=2)


def test_pivot_does_not_mutate():
    df = pl.DataFrame({"k": ["A"], "name": ["x"], "value": [1]})
    pivot(df, index="k", columns="name", values="value")
    assert df.columns == ["k", "name", "value"]


# ---------------------------------------------------------------------------
# fill_down / fill_up
# ---------------------------------------------------------------------------

def test_fill_down_propagates_values():
    df = pl.DataFrame({"section": ["A", None, None, "B", None]})
    result = fill_down(df, "section")
    assert result["section"].to_list() == ["A", "A", "A", "B", "B"]


def test_fill_up_propagates_values():
    df = pl.DataFrame({"section": [None, "A", None, "B"]})
    result = fill_up(df, "section")
    assert result["section"].to_list() == ["A", "A", "B", "B"]


def test_fill_multiple_columns_and_does_not_mutate():
    df = pl.DataFrame({"a": [1, None], "b": ["x", None]})
    result = fill_down(df, ["a", "b"])
    assert result["a"].to_list() == [1, 1]
    assert result["b"].to_list() == ["x", "x"]
    assert df["a"].to_list() == [1, None]
    assert df["b"].to_list() == ["x", None]


# ---------------------------------------------------------------------------
# group
# ---------------------------------------------------------------------------

def test_group_multiple_aggregations():
    df = pl.DataFrame(
        {
            "region": ["North", "North", "South"],
            "amount": [Decimal("1.00"), Decimal("3.00"), Decimal("5.00")],
        }
    )
    result = group(
        df,
        "region",
        [
            ("sum", "amount", "total"),
            ("avg", "amount", "average"),
            ("count", None, "rows"),
        ],
    )

    north = result.filter(pl.col("region") == "North")
    assert north["total"][0] == Decimal("4.00")
    assert north["average"][0] == Decimal("2.00")
    assert north["rows"][0] == 2


def test_group_accepts_dict_specs():
    df = pl.DataFrame({"region": ["North", "North"], "amount": [1, 3]})
    result = group(
        df,
        "region",
        [
            {"function": "min", "column": "amount", "alias": "low"},
            {"op": "max", "column": "amount", "as": "high"},
        ],
    )
    assert result["low"][0] == 1
    assert result["high"][0] == 3


def test_group_decimal_precision_regression():
    df = pl.DataFrame(
        {
            "region": ["North", "North"] + ["South"] * 1000,
            "amount": [Decimal("0.10"), Decimal("0.11")]
            + [Decimal("0.10")] * 1000,
        }
    )
    result = group(
        df,
        "region",
        [
            ("avg", "amount", "average"),
            ("sum", "amount", "total"),
        ],
    )
    north = result.filter(pl.col("region") == "North")
    south = result.filter(pl.col("region") == "South")
    assert north["average"][0] == Decimal("0.11")
    assert south["total"][0] == Decimal("100.00")
    assert north["average"].dtype == pl.Decimal(scale=2)
    assert south["total"].dtype == pl.Decimal(scale=2)


def test_group_does_not_mutate():
    df = pl.DataFrame({"region": ["North"], "amount": [Decimal("1.00")]})
    group(df, "region", [("sum", "amount", "total")])
    assert df.columns == ["region", "amount"]


def test_group_rejects_unknown_aggregation():
    df = pl.DataFrame({"region": ["North"], "amount": [1]})
    with pytest.raises(ValueError, match="unsupported aggregation function"):
        group(df, "region", [("median", "amount")])
