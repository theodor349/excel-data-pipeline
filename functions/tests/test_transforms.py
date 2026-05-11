import datetime
from decimal import Decimal

import polars as pl
import pytest

from functions.transforms import (
    drop_nulls,
    filter_rows,
    fiscal_year,
    keep_columns,
    lowercase,
    period_end,
    rename,
    to_date,
    to_decimal,
    to_float,
    to_int,
)


# ---------------------------------------------------------------------------
# lowercase
# ---------------------------------------------------------------------------

def test_lowercase_basic():
    df = pl.DataFrame({"name": ["Alice", "BOB", "carol"]})
    result = lowercase(df, "name")
    assert result["name"].to_list() == ["alice", "bob", "carol"]


def test_lowercase_preserves_nan():
    df = pl.DataFrame({"name": ["Alice", None]})
    result = lowercase(df, "name")
    assert result["name"][0] == "alice"
    assert result["name"][1] is None


def test_lowercase_does_not_mutate():
    df = pl.DataFrame({"name": ["Alice"]})
    lowercase(df, "name")
    assert df["name"][0] == "Alice"


# ---------------------------------------------------------------------------
# to_int
# ---------------------------------------------------------------------------

def test_to_int_basic():
    df = pl.DataFrame({"n": [1.0, 2.0, 3.0]})
    result = to_int(df, "n")
    assert result["n"].dtype == pl.Int64
    assert result["n"][0] == 1


def test_to_int_preserves_nan():
    df = pl.DataFrame({"n": [1.0, None]})
    result = to_int(df, "n")
    assert result["n"].dtype == pl.Int64
    assert result["n"][1] is None


def test_to_int_does_not_mutate():
    df = pl.DataFrame({"n": [1.0, 2.0]})
    to_int(df, "n")
    assert df["n"].dtype == pl.Float64


# ---------------------------------------------------------------------------
# to_decimal — CRITICAL precision tests
# ---------------------------------------------------------------------------

def test_to_decimal_float_exact():
    # Verifies str-based conversion: Decimal(str(0.1)) == Decimal("0.1"), not the
    # IEEE-754 binary expansion that Decimal(0.1) would produce.
    df = pl.DataFrame({"amount": [0.1, 0.2, 0.3]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"][0] == Decimal("0.10")
    assert result["amount"][1] == Decimal("0.20")
    assert result["amount"][2] == Decimal("0.30")


def test_to_decimal_rounds_half_up():
    df = pl.DataFrame({"amount": [Decimal("1.234"), Decimal("5.678")]}, schema={"amount": pl.Object})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"][0] == Decimal("1.23")
    assert result["amount"][1] == Decimal("5.68")


def test_to_decimal_half_up_not_bankers():
    # 0.125 rounds to 0.13 with ROUND_HALF_UP; banker's rounding gives 0.12.
    df = pl.DataFrame({"amount": [0.125]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"][0] == Decimal("0.13")


def test_to_decimal_preserves_none():
    df = pl.DataFrame({"amount": [1.0, None]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"][0] == Decimal("1.00")
    assert result["amount"][1] is None


def test_to_decimal_does_not_mutate():
    df = pl.DataFrame({"amount": [1.5, 2.5]})
    original_dtype = df["amount"].dtype
    to_decimal(df, "amount", places=2)
    assert df["amount"].dtype == original_dtype
    assert df["amount"].dtype != pl.Object


def test_to_decimal_result_dtype_is_object():
    df = pl.DataFrame({"amount": [1.0, 2.0]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].dtype == pl.Object


def test_to_decimal_custom_places():
    df = pl.DataFrame({"amount": [1.23456]})
    result = to_decimal(df, "amount", places=4)
    assert result["amount"][0] == Decimal("1.2346")


# ---------------------------------------------------------------------------
# to_float
# ---------------------------------------------------------------------------

def test_to_float_basic():
    df = pl.DataFrame({"ratio": ["1.5", "2.5"]})
    result = to_float(df, "ratio")
    assert result["ratio"].dtype == pl.Float64
    assert result["ratio"][0] == 1.5


def test_to_float_does_not_mutate():
    df = pl.DataFrame({"ratio": ["1.5"]})
    to_float(df, "ratio")
    assert df["ratio"].dtype != pl.Float64


# ---------------------------------------------------------------------------
# to_date
# ---------------------------------------------------------------------------

def test_to_date_permissive():
    df = pl.DataFrame({"date": ["2025-01-15", "2025-12-31"]})
    result = to_date(df, "date")
    assert result["date"].dtype == pl.Date
    assert result["date"][0] == datetime.date(2025, 1, 15)


def test_to_date_with_format():
    df = pl.DataFrame({"date": ["15/01/2025"]})
    result = to_date(df, "date", format="%d/%m/%Y")
    assert result["date"][0] == datetime.date(2025, 1, 15)


def test_to_date_does_not_mutate():
    df = pl.DataFrame({"date": ["2025-01-15"]})
    to_date(df, "date")
    assert df["date"].dtype != pl.Date


# ---------------------------------------------------------------------------
# fiscal_year
# ---------------------------------------------------------------------------

def test_fiscal_year_calendar_year():
    df = pl.DataFrame({"date": [datetime.date(2025, 3, 15)]})
    result = fiscal_year(df, "date", fy_start_month=1)
    assert result["fiscal_year"][0] == 2025


def test_fiscal_year_july_start_in_new_fy():
    # July 1 2025 is the first day of FY 2026 (FY ends in Jun 2026).
    df = pl.DataFrame({"date": [datetime.date(2025, 7, 1)]})
    result = fiscal_year(df, "date", fy_start_month=7)
    assert result["fiscal_year"][0] == 2026


def test_fiscal_year_july_start_before_start():
    # June 30 2025 is still in FY 2025.
    df = pl.DataFrame({"date": [datetime.date(2025, 6, 30)]})
    result = fiscal_year(df, "date", fy_start_month=7)
    assert result["fiscal_year"][0] == 2025


def test_fiscal_year_custom_column_name():
    df = pl.DataFrame({"date": [datetime.date(2025, 3, 15)]})
    result = fiscal_year(df, "date", new_column="fy")
    assert "fy" in result.columns


def test_fiscal_year_does_not_mutate():
    df = pl.DataFrame({"date": [datetime.date(2025, 7, 1)]})
    fiscal_year(df, "date", fy_start_month=7)
    assert "fiscal_year" not in df.columns


# ---------------------------------------------------------------------------
# period_end
# ---------------------------------------------------------------------------

def test_period_end_month_feb():
    # Feb 2025 has 28 days — tests that month-end logic is not off-by-one.
    df = pl.DataFrame({"date": [datetime.date(2025, 2, 15)]})
    result = period_end(df, "date", granularity="month")
    assert result["period_end"][0] == datetime.date(2025, 2, 28)


def test_period_end_quarter():
    df = pl.DataFrame({"date": [datetime.date(2025, 2, 15)]})
    result = period_end(df, "date", granularity="quarter")
    assert result["period_end"][0] == datetime.date(2025, 3, 31)


def test_period_end_year():
    df = pl.DataFrame({"date": [datetime.date(2025, 6, 15)]})
    result = period_end(df, "date", granularity="year")
    assert result["period_end"][0] == datetime.date(2025, 12, 31)


def test_period_end_custom_column_name():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 1)]})
    result = period_end(df, "date", granularity="month", new_column="end_date")
    assert "end_date" in result.columns


def test_period_end_does_not_mutate():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 1)]})
    period_end(df, "date", granularity="month")
    assert "period_end" not in df.columns


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

def test_rename_basic():
    df = pl.DataFrame({"old": [1, 2]})
    result = rename(df, "old", "new")
    assert "new" in result.columns
    assert "old" not in result.columns


def test_rename_does_not_mutate():
    df = pl.DataFrame({"old": [1, 2]})
    rename(df, "old", "new")
    assert "old" in df.columns
    assert "new" not in df.columns


# ---------------------------------------------------------------------------
# keep_columns
# ---------------------------------------------------------------------------

def test_keep_columns_basic():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = keep_columns(df, ["a", "c"])
    assert list(result.columns) == ["a", "c"]


def test_keep_columns_order():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = keep_columns(df, ["c", "a"])
    assert list(result.columns) == ["c", "a"]


def test_keep_columns_raises_on_missing():
    df = pl.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(KeyError):
        keep_columns(df, ["a", "z"])


def test_keep_columns_does_not_mutate():
    df = pl.DataFrame({"a": [1], "b": [2], "c": [3]})
    keep_columns(df, ["a"])
    assert list(df.columns) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# filter_rows
# ---------------------------------------------------------------------------

def test_filter_rows_basic():
    df = pl.DataFrame({"status": ["active", "inactive", "active"], "val": [1, 2, 3]})
    result = filter_rows(df, "status", "active")
    assert len(result) == 2
    assert result["val"].to_list() == [1, 3]


def test_filter_rows_does_not_mutate():
    df = pl.DataFrame({"status": ["active", "inactive"], "val": [1, 2]})
    filter_rows(df, "status", "active")
    assert len(df) == 2


# ---------------------------------------------------------------------------
# drop_nulls
# ---------------------------------------------------------------------------

def test_drop_nulls_basic():
    df = pl.DataFrame({"name": ["alice", None, "bob"]})
    result = drop_nulls(df, "name")
    assert len(result) == 2
    assert result["name"].to_list() == ["alice", "bob"]


def test_drop_nulls_does_not_mutate():
    df = pl.DataFrame({"name": ["alice", None]})
    drop_nulls(df, "name")
    assert len(df) == 2
