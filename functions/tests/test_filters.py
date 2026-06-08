from decimal import Decimal

import polars as pl

from functions.filters import (
    drop_nulls,
    filter_at_least,
    filter_at_most,
    filter_between,
    filter_contains,
    filter_ends_with,
    filter_greater_than,
    filter_in_list,
    filter_less_than,
    filter_not_equal,
    filter_not_in_list,
    filter_rows,
    filter_starts_with,
    keep_bottom_rows,
    keep_nulls,
    keep_top_rows,
    remove_bottom_rows,
    remove_duplicates,
    remove_top_rows,
)


def _money_df():
    # Scale-2 Decimal money column with bounds that are not exactly
    # representable as binary floats.
    return pl.DataFrame(
        {
            "amount": [Decimal("0.10"), Decimal("0.29"), Decimal("0.30"), Decimal("1.05")],
            "id": [1, 2, 3, 4],
        }
    )


# ---------------------------------------------------------------------------
# filter_rows (equality)
# ---------------------------------------------------------------------------

def test_filter_rows_basic():
    df = pl.DataFrame({"status": ["active", "inactive", "active"], "val": [1, 2, 3]})
    result = filter_rows(df, "status", "active")
    assert result["val"].to_list() == [1, 3]


def test_filter_rows_does_not_mutate():
    df = pl.DataFrame({"status": ["active", "inactive"], "val": [1, 2]})
    filter_rows(df, "status", "active")
    assert len(df) == 2


def test_filter_rows_money_exact():
    df = _money_df()
    result = filter_rows(df, "amount", 0.30)
    assert result["amount"].to_list() == [Decimal("0.30")]


# ---------------------------------------------------------------------------
# filter_not_equal
# ---------------------------------------------------------------------------

def test_filter_not_equal_basic():
    df = pl.DataFrame({"acct": ["A", "B", "A", "C"]})
    result = filter_not_equal(df, "acct", "A")
    assert result["acct"].to_list() == ["B", "C"]


def test_filter_not_equal_does_not_mutate():
    df = pl.DataFrame({"acct": ["A", "B"]})
    filter_not_equal(df, "acct", "A")
    assert df["acct"].to_list() == ["A", "B"]


# ---------------------------------------------------------------------------
# Range / comparison
# ---------------------------------------------------------------------------

def test_filter_greater_than():
    df = pl.DataFrame({"n": [1, 5, 10]})
    assert filter_greater_than(df, "n", 5)["n"].to_list() == [10]


def test_filter_less_than():
    df = pl.DataFrame({"n": [1, 5, 10]})
    assert filter_less_than(df, "n", 5)["n"].to_list() == [1]


def test_filter_at_least():
    df = pl.DataFrame({"n": [1, 5, 10]})
    assert filter_at_least(df, "n", 5)["n"].to_list() == [5, 10]


def test_filter_at_most():
    df = pl.DataFrame({"n": [1, 5, 10]})
    assert filter_at_most(df, "n", 5)["n"].to_list() == [1, 5]


def test_filter_comparison_does_not_mutate():
    df = pl.DataFrame({"n": [1, 5, 10]})
    filter_greater_than(df, "n", 5)
    assert df["n"].to_list() == [1, 5, 10]


def test_filter_comparison_on_dates():
    import datetime

    df = pl.DataFrame(
        {"d": [datetime.date(2024, 12, 31), datetime.date(2025, 7, 1), datetime.date(2026, 6, 30)]}
    )
    result = filter_at_least(df, "d", datetime.date(2025, 7, 1))
    assert result["d"].to_list() == [datetime.date(2025, 7, 1), datetime.date(2026, 6, 30)]


def test_filter_at_least_money_exact_boundary():
    # 0.29 is not exactly representable as a binary float; the boundary must be
    # compared as exact Decimal so the 0.29 row is kept and 0.10 is excluded.
    df = _money_df()
    result = filter_at_least(df, "amount", 0.29)
    assert result["amount"].to_list() == [Decimal("0.29"), Decimal("0.30"), Decimal("1.05")]


def test_filter_greater_than_money_excludes_boundary():
    df = _money_df()
    result = filter_greater_than(df, "amount", 0.29)
    assert result["amount"].to_list() == [Decimal("0.30"), Decimal("1.05")]


# ---------------------------------------------------------------------------
# filter_between
# ---------------------------------------------------------------------------

def test_filter_between_inclusive():
    df = pl.DataFrame({"n": [1, 2, 3, 4, 5]})
    assert filter_between(df, "n", 2, 4)["n"].to_list() == [2, 3, 4]


def test_filter_between_exclusive():
    df = pl.DataFrame({"n": [1, 2, 3, 4, 5]})
    assert filter_between(df, "n", 2, 4, inclusive=False)["n"].to_list() == [3]


def test_filter_between_dates():
    import datetime

    df = pl.DataFrame(
        {
            "d": [
                datetime.date(2024, 6, 30),
                datetime.date(2025, 7, 1),
                datetime.date(2026, 6, 30),
                datetime.date(2026, 7, 1),
            ]
        }
    )
    result = filter_between(df, "d", datetime.date(2025, 7, 1), datetime.date(2026, 6, 30))
    assert result["d"].to_list() == [datetime.date(2025, 7, 1), datetime.date(2026, 6, 30)]


def test_filter_between_money_exact_boundaries():
    df = _money_df()
    result = filter_between(df, "amount", 0.29, 0.30)
    assert result["amount"].to_list() == [Decimal("0.29"), Decimal("0.30")]


def test_filter_between_does_not_mutate():
    df = pl.DataFrame({"n": [1, 2, 3]})
    filter_between(df, "n", 1, 2)
    assert df["n"].to_list() == [1, 2, 3]


# ---------------------------------------------------------------------------
# List membership
# ---------------------------------------------------------------------------

def test_filter_in_list():
    df = pl.DataFrame({"cc": ["100", "200", "300", "100"]})
    assert filter_in_list(df, "cc", ["100", "300"])["cc"].to_list() == ["100", "300", "100"]


def test_filter_not_in_list():
    df = pl.DataFrame({"cc": ["100", "200", "300", "100"]})
    assert filter_not_in_list(df, "cc", ["100", "300"])["cc"].to_list() == ["200"]


def test_filter_in_list_does_not_mutate():
    df = pl.DataFrame({"cc": ["100", "200"]})
    filter_in_list(df, "cc", ["100"])
    assert df["cc"].to_list() == ["100", "200"]


def test_filter_in_list_money_exact():
    df = _money_df()
    result = filter_in_list(df, "amount", [Decimal("0.10"), Decimal("1.05")])
    assert result["amount"].to_list() == [Decimal("0.10"), Decimal("1.05")]


# ---------------------------------------------------------------------------
# Text matching
# ---------------------------------------------------------------------------

def test_filter_contains():
    df = pl.DataFrame({"name": ["alpha", "beta", "gamma"]})
    assert filter_contains(df, "name", "a")["name"].to_list() == ["alpha", "beta", "gamma"]


def test_filter_contains_literal_not_regex():
    df = pl.DataFrame({"code": ["A.1", "A1", "B.2"]})
    assert filter_contains(df, "code", ".")["code"].to_list() == ["A.1", "B.2"]


def test_filter_starts_with():
    df = pl.DataFrame({"acct": ["4000", "4100", "5000"]})
    assert filter_starts_with(df, "acct", "4")["acct"].to_list() == ["4000", "4100"]


def test_filter_ends_with():
    df = pl.DataFrame({"acct": ["4000", "4105", "5000"]})
    assert filter_ends_with(df, "acct", "00")["acct"].to_list() == ["4000", "5000"]


def test_filter_text_does_not_mutate():
    df = pl.DataFrame({"name": ["alpha", "beta"]})
    filter_contains(df, "name", "a")
    assert df["name"].to_list() == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# Nulls
# ---------------------------------------------------------------------------

def test_drop_nulls_basic():
    df = pl.DataFrame({"name": ["alice", None, "bob"]})
    result = drop_nulls(df, "name")
    assert result["name"].to_list() == ["alice", "bob"]


def test_drop_nulls_does_not_mutate():
    df = pl.DataFrame({"name": ["alice", None]})
    drop_nulls(df, "name")
    assert len(df) == 2


def test_keep_nulls_basic():
    df = pl.DataFrame({"name": ["alice", None, "bob"], "id": [1, 2, 3]})
    result = keep_nulls(df, "name")
    assert result["id"].to_list() == [2]


def test_keep_nulls_does_not_mutate():
    df = pl.DataFrame({"name": ["alice", None]})
    keep_nulls(df, "name")
    assert len(df) == 2


# ---------------------------------------------------------------------------
# remove_duplicates
# ---------------------------------------------------------------------------

def test_remove_duplicates_whole_row():
    df = pl.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    result = remove_duplicates(df)
    assert result["a"].to_list() == [1, 2]
    assert result["b"].to_list() == ["x", "y"]


def test_remove_duplicates_subset_keeps_first():
    df = pl.DataFrame({"k": [1, 1, 2], "v": ["a", "b", "c"]})
    result = remove_duplicates(df, ["k"])
    assert result["k"].to_list() == [1, 2]
    assert result["v"].to_list() == ["a", "c"]


def test_remove_duplicates_preserves_order():
    df = pl.DataFrame({"k": [3, 1, 3, 2, 1]})
    assert remove_duplicates(df)["k"].to_list() == [3, 1, 2]


def test_remove_duplicates_does_not_mutate():
    df = pl.DataFrame({"a": [1, 1, 2]})
    remove_duplicates(df)
    assert df["a"].to_list() == [1, 1, 2]


def test_remove_duplicates_money_preserved():
    df = pl.DataFrame({"amount": [Decimal("0.10"), Decimal("0.10"), Decimal("0.30")]})
    result = remove_duplicates(df)
    assert result["amount"].to_list() == [Decimal("0.10"), Decimal("0.30")]
    assert result.schema["amount"] == pl.Decimal


# ---------------------------------------------------------------------------
# Top / bottom N
# ---------------------------------------------------------------------------

def test_keep_top_rows():
    df = pl.DataFrame({"n": [1, 2, 3, 4]})
    assert keep_top_rows(df, 2)["n"].to_list() == [1, 2]


def test_keep_bottom_rows():
    df = pl.DataFrame({"n": [1, 2, 3, 4]})
    assert keep_bottom_rows(df, 2)["n"].to_list() == [3, 4]


def test_remove_top_rows():
    df = pl.DataFrame({"n": [1, 2, 3, 4]})
    assert remove_top_rows(df, 1)["n"].to_list() == [2, 3, 4]


def test_remove_bottom_rows():
    df = pl.DataFrame({"n": [1, 2, 3, 4]})
    assert remove_bottom_rows(df, 1)["n"].to_list() == [1, 2, 3]


def test_remove_bottom_rows_zero_keeps_all():
    df = pl.DataFrame({"n": [1, 2, 3]})
    assert remove_bottom_rows(df, 0)["n"].to_list() == [1, 2, 3]


def test_top_bottom_does_not_mutate():
    df = pl.DataFrame({"n": [1, 2, 3, 4]})
    keep_top_rows(df, 1)
    keep_bottom_rows(df, 1)
    remove_top_rows(df, 1)
    remove_bottom_rows(df, 1)
    assert df["n"].to_list() == [1, 2, 3, 4]
