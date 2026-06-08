import datetime
from decimal import Decimal

import polars as pl
import pytest

from functions.transforms import (
    add,
    divide,
    drop_nulls,
    epoch_to_datetime,
    filter_rows,
    fiscal_year,
    keep_columns,
    lowercase,
    multiply,
    period_end,
    rename,
    sort,
    subtract,
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


def test_to_decimal_rounds():
    df = pl.DataFrame({"amount": ["1.234", "5.678"]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"][0] == Decimal("1.23")
    assert result["amount"][1] == Decimal("5.68")


def test_to_decimal_half_up():
    # Finance convention is ROUND_HALF_UP (away from zero on a tie), NOT Polars'
    # native half-even. 0.125 -> 0.13, 0.005 -> 0.01, -0.025 -> -0.03.
    df = pl.DataFrame({"amount": ["0.125", "0.005", "-0.025"]})
    result = to_decimal(df, "amount", places=2)
    assert result["amount"].to_list() == [
        Decimal("0.13"),
        Decimal("0.01"),
        Decimal("-0.03"),
    ]


def test_to_decimal_default_places_from_settings():
    # places omitted -> settings.json default (2).
    df = pl.DataFrame({"amount": ["1.239"]})
    result = to_decimal(df, "amount")
    assert isinstance(result["amount"].dtype, pl.Decimal)
    assert result["amount"].dtype.scale == 2
    assert result["amount"][0] == Decimal("1.24")


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


def test_to_decimal_result_dtype_is_decimal():
    df = pl.DataFrame({"amount": [1.0, 2.0]})
    result = to_decimal(df, "amount", places=2)
    assert isinstance(result["amount"].dtype, pl.Decimal)


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
# epoch_to_datetime
# ---------------------------------------------------------------------------

def test_epoch_to_datetime_ms():
    # 1704877200000 ms since epoch == 2024-01-10 09:00:00 UTC.
    df = pl.DataFrame({"ts": [1704877200000]})
    result = epoch_to_datetime(df, "ts")
    assert result["ts"].dtype == pl.Datetime(time_unit="ms")
    assert result["ts"][0] == datetime.datetime(2024, 1, 10, 9, 0, 0)


def test_epoch_to_datetime_does_not_mutate():
    df = pl.DataFrame({"ts": [1704877200000]})
    epoch_to_datetime(df, "ts")
    assert df["ts"].dtype == pl.Int64


# ---------------------------------------------------------------------------
# add / subtract / multiply — exact Decimal computed columns
# ---------------------------------------------------------------------------

def _money_df():
    return pl.DataFrame(
        {"a": ["1.10"], "b": ["2.05"], "qty": [3]},
        schema={"a": pl.String, "b": pl.String, "qty": pl.Int64},
    ).with_columns(
        pl.col("a").cast(pl.Decimal(scale=2)),
        pl.col("b").cast(pl.Decimal(scale=2)),
    )


def test_add_two_columns():
    result = add(_money_df(), "a", "b", new_column="total")
    assert result["total"][0] == Decimal("3.15")
    assert isinstance(result["total"].dtype, pl.Decimal)


def test_subtract_constant():
    result = subtract(_money_df(), "b", 0.05, new_column="net")
    assert result["net"][0] == Decimal("2.00")


def test_multiply_column_by_int_column():
    result = multiply(_money_df(), "a", "qty", new_column="line")
    assert result["line"][0] == Decimal("3.30")


def test_multiply_no_silent_precision_loss():
    # 1.10 * 1.05 = 1.1550. Polars' native Decimal multiply silently rounds this
    # to 1.16; going through Python Decimal keeps it exact when places allow.
    result = multiply(_money_df(), "a", 1.05, new_column="x", places=4)
    assert result["x"][0] == Decimal("1.1550")


def test_arith_null_propagates():
    df = pl.DataFrame({"a": ["1.10", None]}).with_columns(
        pl.col("a").cast(pl.Decimal(scale=2))
    )
    result = add(df, "a", 1, new_column="x")
    assert result["x"][0] == Decimal("2.10")
    assert result["x"][1] is None


def test_arith_does_not_mutate():
    df = _money_df()
    add(df, "a", "b", new_column="total")
    assert "total" not in df.columns


# ---------------------------------------------------------------------------
# divide
# ---------------------------------------------------------------------------

def test_divide_money_is_decimal_half_up():
    # 1.10 / 7 = 0.157... -> 0.16 half-up, exact Decimal, default 2 places.
    df = _money_df()
    result = divide(df, "a", 7, new_column="ratio")
    assert isinstance(result["ratio"].dtype, pl.Decimal)
    assert result["ratio"][0] == Decimal("0.16")


def test_divide_money_honors_places():
    df = _money_df()
    result = divide(df, "a", 7, new_column="ratio", places=4)
    assert result["ratio"][0] == Decimal("0.1571")


def test_divide_as_decimal_false_gives_float():
    # Unit conversion (ms -> hours): non-money, plain float.
    df = pl.DataFrame({"ms": [3600000, 1800000]})
    result = divide(df, "ms", 3_600_000, new_column="hours", as_decimal=False)
    assert result["hours"].dtype == pl.Float64
    assert result["hours"][0] == pytest.approx(1.0)
    assert result["hours"][1] == pytest.approx(0.5)


def test_divide_does_not_mutate():
    df = _money_df()
    divide(df, "a", 7, new_column="ratio")
    assert "ratio" not in df.columns


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


# ---------------------------------------------------------------------------
# sort
# ---------------------------------------------------------------------------

def test_sort_ascending():
    df = pl.DataFrame({"n": [3, 1, 2]})
    result = sort(df, "n")
    assert result["n"].to_list() == [1, 2, 3]


def test_sort_descending():
    df = pl.DataFrame({"n": [3, 1, 2]})
    result = sort(df, "n", descending=True)
    assert result["n"].to_list() == [3, 2, 1]


def test_sort_does_not_mutate():
    df = pl.DataFrame({"n": [3, 1, 2]})
    sort(df, "n")
    assert df["n"].to_list() == [3, 1, 2]
