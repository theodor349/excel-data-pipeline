from decimal import Decimal

import pandas as pd
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
    df = pd.DataFrame({"name": ["Alice", "BOB", "carol"]})
    result = lowercase(df, "name")
    assert list(result["name"]) == ["alice", "bob", "carol"]


def test_lowercase_preserves_nan():
    df = pd.DataFrame({"name": ["Alice", None]})
    result = lowercase(df, "name")
    assert result["name"].iloc[0] == "alice"
    assert pd.isna(result["name"].iloc[1])


def test_lowercase_does_not_mutate():
    df = pd.DataFrame({"name": ["Alice"]})
    lowercase(df, "name")
    assert df["name"].iloc[0] == "Alice"


# ---------------------------------------------------------------------------
# to_int
# ---------------------------------------------------------------------------

def test_to_int_basic():
    df = pd.DataFrame({"n": [1.0, 2.0, 3.0]})
    result = to_int(df, "n")
    assert result["n"].dtype == "Int64"
    assert result["n"].iloc[0] == 1


def test_to_int_preserves_nan():
    df = pd.DataFrame({"n": [1.0, None]})
    result = to_int(df, "n")
    assert result["n"].dtype == "Int64"
    assert pd.isna(result["n"].iloc[1])


def test_to_int_does_not_mutate():
    df = pd.DataFrame({"n": [1.0, 2.0]})
    to_int(df, "n")
    assert df["n"].dtype == float


# ---------------------------------------------------------------------------
# to_decimal — CRITICAL precision tests
# ---------------------------------------------------------------------------

def test_to_decimal_float_exact():
    # Verifies str-based conversion: Decimal(str(0.1)) == Decimal("0.1"), not the
    # IEEE-754 binary expansion that Decimal(0.1) would produce.
    df = pd.DataFrame({"amount": [0.1, 0.2, 0.3]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].iloc[0] == Decimal("0.10")
    assert result["amount"].iloc[1] == Decimal("0.20")
    assert result["amount"].iloc[2] == Decimal("0.30")


def test_to_decimal_rounds_half_up():
    df = pd.DataFrame({"amount": [Decimal("1.234"), Decimal("5.678")]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].iloc[0] == Decimal("1.23")
    assert result["amount"].iloc[1] == Decimal("5.68")


def test_to_decimal_half_up_not_bankers():
    # 0.125 rounds to 0.13 with ROUND_HALF_UP; banker's rounding gives 0.12.
    df = pd.DataFrame({"amount": [0.125]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].iloc[0] == Decimal("0.13")


def test_to_decimal_preserves_none():
    # NaN/None values become None in the result column (object dtype).
    df = pd.DataFrame({"amount": [1.0, None]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].iloc[0] == Decimal("1.00")
    assert result["amount"].iloc[1] is None


def test_to_decimal_does_not_mutate():
    df = pd.DataFrame({"amount": [1.5, 2.5]})
    original_dtype = df["amount"].dtype
    to_decimal(df, "amount", places=2)
    assert df["amount"].dtype == original_dtype
    assert df["amount"].dtype != object


def test_to_decimal_result_dtype_is_object():
    df = pd.DataFrame({"amount": [1.0, 2.0]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].dtype == object


def test_to_decimal_custom_places():
    df = pd.DataFrame({"amount": [1.23456]})
    result = to_decimal(df, "amount", places=4)
    assert result["amount"].iloc[0] == Decimal("1.2346")


# ---------------------------------------------------------------------------
# to_float
# ---------------------------------------------------------------------------

def test_to_float_basic():
    df = pd.DataFrame({"ratio": ["1.5", "2.5"]})
    result = to_float(df, "ratio")
    assert result["ratio"].dtype == float
    assert result["ratio"].iloc[0] == 1.5


def test_to_float_does_not_mutate():
    df = pd.DataFrame({"ratio": ["1.5"]})
    to_float(df, "ratio")
    assert df["ratio"].dtype != float


# ---------------------------------------------------------------------------
# to_date
# ---------------------------------------------------------------------------

def test_to_date_permissive():
    df = pd.DataFrame({"date": ["2025-01-15", "2025-12-31"]})
    result = to_date(df, "date")
    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result["date"].iloc[0] == pd.Timestamp("2025-01-15")


def test_to_date_with_format():
    df = pd.DataFrame({"date": ["15/01/2025"]})
    result = to_date(df, "date", format="%d/%m/%Y")
    assert result["date"].iloc[0] == pd.Timestamp("2025-01-15")


def test_to_date_does_not_mutate():
    df = pd.DataFrame({"date": ["2025-01-15"]})
    to_date(df, "date")
    assert not pd.api.types.is_datetime64_any_dtype(df["date"])


# ---------------------------------------------------------------------------
# fiscal_year
# ---------------------------------------------------------------------------

def test_fiscal_year_calendar_year():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-03-15"])})
    result = fiscal_year(df, "date", fy_start_month=1)
    assert result["fiscal_year"].iloc[0] == 2025


def test_fiscal_year_july_start_in_new_fy():
    # July 1 2025 is the first day of FY 2026 (FY ends in Jun 2026).
    df = pd.DataFrame({"date": pd.to_datetime(["2025-07-01"])})
    result = fiscal_year(df, "date", fy_start_month=7)
    assert result["fiscal_year"].iloc[0] == 2026


def test_fiscal_year_july_start_before_start():
    # June 30 2025 is still in FY 2025.
    df = pd.DataFrame({"date": pd.to_datetime(["2025-06-30"])})
    result = fiscal_year(df, "date", fy_start_month=7)
    assert result["fiscal_year"].iloc[0] == 2025


def test_fiscal_year_custom_column_name():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-03-15"])})
    result = fiscal_year(df, "date", new_column="fy")
    assert "fy" in result.columns


def test_fiscal_year_does_not_mutate():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-07-01"])})
    fiscal_year(df, "date", fy_start_month=7)
    assert "fiscal_year" not in df.columns


# ---------------------------------------------------------------------------
# period_end
# ---------------------------------------------------------------------------

def test_period_end_month_feb():
    # Feb 2025 has 28 days — tests that month-end logic is not off-by-one.
    df = pd.DataFrame({"date": pd.to_datetime(["2025-02-15"])})
    result = period_end(df, "date", granularity="month")
    assert result["period_end"].iloc[0] == pd.Timestamp("2025-02-28")


def test_period_end_quarter():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-02-15"])})
    result = period_end(df, "date", granularity="quarter")
    assert result["period_end"].iloc[0] == pd.Timestamp("2025-03-31")


def test_period_end_year():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-06-15"])})
    result = period_end(df, "date", granularity="year")
    assert result["period_end"].iloc[0] == pd.Timestamp("2025-12-31")


def test_period_end_custom_column_name():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-01-01"])})
    result = period_end(df, "date", granularity="month", new_column="end_date")
    assert "end_date" in result.columns


def test_period_end_does_not_mutate():
    df = pd.DataFrame({"date": pd.to_datetime(["2025-01-01"])})
    period_end(df, "date", granularity="month")
    assert "period_end" not in df.columns


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

def test_rename_basic():
    df = pd.DataFrame({"old": [1, 2]})
    result = rename(df, "old", "new")
    assert "new" in result.columns
    assert "old" not in result.columns


def test_rename_does_not_mutate():
    # Rename adds a column under a new name — original must be unchanged.
    df = pd.DataFrame({"old": [1, 2]})
    rename(df, "old", "new")
    assert "old" in df.columns
    assert "new" not in df.columns


# ---------------------------------------------------------------------------
# keep_columns
# ---------------------------------------------------------------------------

def test_keep_columns_basic():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = keep_columns(df, ["a", "c"])
    assert list(result.columns) == ["a", "c"]


def test_keep_columns_order():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    result = keep_columns(df, ["c", "a"])
    assert list(result.columns) == ["c", "a"]


def test_keep_columns_raises_on_missing():
    df = pd.DataFrame({"a": [1], "b": [2]})
    with pytest.raises(KeyError):
        keep_columns(df, ["a", "z"])


def test_keep_columns_does_not_mutate():
    df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
    keep_columns(df, ["a"])
    assert list(df.columns) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# filter_rows
# ---------------------------------------------------------------------------

def test_filter_rows_basic():
    df = pd.DataFrame({"status": ["active", "inactive", "active"], "val": [1, 2, 3]})
    result = filter_rows(df, "status", "active")
    assert len(result) == 2
    assert list(result["val"]) == [1, 3]


def test_filter_rows_does_not_mutate():
    # filter_rows removes rows — original length must be unchanged.
    df = pd.DataFrame({"status": ["active", "inactive"], "val": [1, 2]})
    filter_rows(df, "status", "active")
    assert len(df) == 2


# ---------------------------------------------------------------------------
# drop_nulls
# ---------------------------------------------------------------------------

def test_drop_nulls_basic():
    df = pd.DataFrame({"name": ["alice", None, "bob"]})
    result = drop_nulls(df, "name")
    assert len(result) == 2
    assert list(result["name"]) == ["alice", "bob"]


def test_drop_nulls_does_not_mutate():
    # drop_nulls removes rows — original length must be unchanged.
    df = pd.DataFrame({"name": ["alice", None]})
    drop_nulls(df, "name")
    assert len(df) == 2
