import datetime

import polars as pl

from functions.dates import (
    add_days,
    add_months,
    date_diff_days,
    date_month,
    date_quarter,
    date_year,
    epoch_to_datetime,
    fiscal_year,
    now,
    period_end,
    start_of_month,
    start_of_quarter,
    start_of_year,
    to_date,
    today,
)


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


def test_date_parts():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    assert date_year(df, "date")["date"][0] == 2025
    assert date_month(df, "date")["date"][0] == 5
    assert date_quarter(df, "date")["date"][0] == 2


def test_date_parts_custom_column_names():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    result = date_quarter(
        date_month(date_year(df, "date", new_column="report_year"), "date", "report_month"),
        "date",
        "report_quarter",
    )
    assert result["report_year"][0] == 2025
    assert result["report_month"][0] == 5
    assert result["report_quarter"][0] == 2


def test_date_parts_do_not_mutate():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    date_year(df, "date")
    date_month(df, "date")
    date_quarter(df, "date")
    assert df.columns == ["date"]
    assert df["date"][0] == datetime.date(2025, 5, 17)


def test_date_part_replaces_source_column_by_default_without_mutating_input():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    result = date_year(df, "date")
    assert result.columns == ["date"]
    assert result["date"][0] == 2025
    assert df["date"][0] == datetime.date(2025, 5, 17)


def test_start_of_periods():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    assert start_of_month(df, "date")["date"][0] == datetime.date(2025, 5, 1)
    assert start_of_quarter(df, "date")["date"][0] == datetime.date(2025, 4, 1)
    assert start_of_year(df, "date")["date"][0] == datetime.date(2025, 1, 1)


def test_start_of_periods_custom_column_names():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    result = start_of_year(
        start_of_quarter(
            start_of_month(df, "date", new_column="bucket_month"),
            "date",
            new_column="bucket_quarter",
        ),
        "date",
        new_column="bucket_year",
    )
    assert result["bucket_month"][0] == datetime.date(2025, 5, 1)
    assert result["bucket_quarter"][0] == datetime.date(2025, 4, 1)
    assert result["bucket_year"][0] == datetime.date(2025, 1, 1)


def test_start_of_periods_do_not_mutate():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    start_of_month(df, "date")
    start_of_quarter(df, "date")
    start_of_year(df, "date")
    assert df.columns == ["date"]
    assert df["date"][0] == datetime.date(2025, 5, 17)


def test_start_of_period_replaces_source_column_by_default_without_mutating_input():
    df = pl.DataFrame({"date": [datetime.date(2025, 5, 17)]})
    result = start_of_month(df, "date")
    assert result.columns == ["date"]
    assert result["date"][0] == datetime.date(2025, 5, 1)
    assert df["date"][0] == datetime.date(2025, 5, 17)


def test_date_diff_days():
    df = pl.DataFrame(
        {
            "invoice_date": [datetime.date(2025, 1, 1), datetime.date(2025, 1, 10)],
            "paid_date": [datetime.date(2025, 1, 10), datetime.date(2025, 1, 1)],
        }
    )
    result = date_diff_days(df, "invoice_date", "paid_date", new_column="age_days")
    assert result["age_days"].to_list() == [9, -9]


def test_date_diff_days_does_not_mutate():
    df = pl.DataFrame(
        {
            "invoice_date": [datetime.date(2025, 1, 1)],
            "paid_date": [datetime.date(2025, 1, 10)],
        }
    )
    date_diff_days(df, "invoice_date", "paid_date")
    assert "days" not in df.columns


def test_add_months_clamps_to_month_end():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 31)]})
    result = add_months(df, "date", 1, new_column="due_date")
    assert result["due_date"][0] == datetime.date(2025, 2, 28)


def test_add_months_can_update_in_place_without_mutating_input():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 31)]})
    result = add_months(df, "date", -1)
    assert result["date"][0] == datetime.date(2024, 12, 31)
    assert df["date"][0] == datetime.date(2025, 1, 31)


def test_add_days():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 31)]})
    result = add_days(df, "date", 5, new_column="follow_up")
    assert result["follow_up"][0] == datetime.date(2025, 2, 5)


def test_add_days_can_update_in_place_without_mutating_input():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 31)]})
    result = add_days(df, "date", -5)
    assert result["date"][0] == datetime.date(2025, 1, 26)
    assert df["date"][0] == datetime.date(2025, 1, 31)


def test_today_adds_date_column():
    df = pl.DataFrame({"id": [1, 2]})
    result = today(df, value=datetime.date(2026, 6, 8))
    assert result["today"].to_list() == [
        datetime.date(2026, 6, 8),
        datetime.date(2026, 6, 8),
    ]
    assert result["today"].dtype == pl.Date


def test_today_does_not_mutate():
    df = pl.DataFrame({"id": [1]})
    today(df, value=datetime.date(2026, 6, 8))
    assert "today" not in df.columns


def test_now_adds_datetime_column():
    df = pl.DataFrame({"id": [1, 2]})
    value = datetime.datetime(2026, 6, 8, 11, 30, 45)
    result = now(df, value=value)
    assert result["now"].to_list() == [value, value]
    assert result["now"].dtype == pl.Datetime(time_unit="us")


def test_now_does_not_mutate():
    df = pl.DataFrame({"id": [1]})
    now(df, value=datetime.datetime(2026, 6, 8, 11, 30, 45))
    assert "now" not in df.columns


def test_fiscal_year_calendar_year():
    df = pl.DataFrame({"date": [datetime.date(2025, 3, 15)]})
    result = fiscal_year(df, "date", fy_start_month=1)
    assert result["date"][0] == 2025


def test_fiscal_year_july_start_in_new_fy():
    df = pl.DataFrame({"date": [datetime.date(2025, 7, 1)]})
    result = fiscal_year(df, "date", fy_start_month=7)
    assert result["date"][0] == 2026


def test_fiscal_year_does_not_mutate():
    df = pl.DataFrame({"date": [datetime.date(2025, 7, 1)]})
    fiscal_year(df, "date", fy_start_month=7)
    assert df["date"][0] == datetime.date(2025, 7, 1)


def test_fiscal_year_replaces_source_column_by_default_without_mutating_input():
    df = pl.DataFrame({"date": [datetime.date(2025, 7, 1)]})
    result = fiscal_year(df, "date", fy_start_month=7)
    assert result.columns == ["date"]
    assert result["date"][0] == 2026
    assert df["date"][0] == datetime.date(2025, 7, 1)


def test_period_end_quarter():
    df = pl.DataFrame({"date": [datetime.date(2025, 2, 15)]})
    result = period_end(df, "date", granularity="quarter")
    assert result["date"][0] == datetime.date(2025, 3, 31)


def test_period_end_does_not_mutate():
    df = pl.DataFrame({"date": [datetime.date(2025, 1, 1)]})
    period_end(df, "date", granularity="month")
    assert df["date"][0] == datetime.date(2025, 1, 1)


def test_period_end_replaces_source_column_by_default_without_mutating_input():
    df = pl.DataFrame({"date": [datetime.date(2025, 2, 15)]})
    result = period_end(df, "date", granularity="month")
    assert result.columns == ["date"]
    assert result["date"][0] == datetime.date(2025, 2, 28)
    assert df["date"][0] == datetime.date(2025, 2, 15)


def test_epoch_to_datetime_ms():
    df = pl.DataFrame({"ts": [1704877200000]})
    result = epoch_to_datetime(df, "ts")
    assert result["ts"].dtype == pl.Datetime(time_unit="ms")
    assert result["ts"][0] == datetime.datetime(2024, 1, 10, 9, 0, 0)


def test_epoch_to_datetime_does_not_mutate():
    df = pl.DataFrame({"ts": [1704877200000]})
    epoch_to_datetime(df, "ts")
    assert df["ts"].dtype == pl.Int64
