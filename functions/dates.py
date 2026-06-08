import datetime

import polars as pl


def to_date(df: pl.DataFrame, column: str, format: str | None = None) -> pl.DataFrame:
    col = df[column]
    if col.dtype == pl.Date:
        return df
    if col.dtype == pl.Datetime:
        return df.with_columns(pl.col(column).cast(pl.Date))
    if format is not None:
        return df.with_columns(pl.col(column).str.to_date(format=format))
    return df.with_columns(pl.col(column).str.to_date())


def date_year(
    df: pl.DataFrame,
    date_column: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.year().alias(target))


def date_month(
    df: pl.DataFrame,
    date_column: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.month().alias(target))


def date_quarter(
    df: pl.DataFrame,
    date_column: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.quarter().alias(target))


def start_of_month(
    df: pl.DataFrame,
    date_column: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.truncate("1mo").alias(target))


def start_of_quarter(
    df: pl.DataFrame,
    date_column: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.truncate("1q").alias(target))


def start_of_year(
    df: pl.DataFrame,
    date_column: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.truncate("1y").alias(target))


def date_diff_days(
    df: pl.DataFrame,
    start_column: str,
    end_column: str,
    new_column: str = "days",
) -> pl.DataFrame:
    return df.with_columns(
        (pl.col(end_column) - pl.col(start_column)).dt.total_days().alias(new_column)
    )


def add_months(
    df: pl.DataFrame,
    date_column: str,
    months: int,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns(pl.col(date_column).dt.offset_by(f"{months}mo").alias(target))


def add_days(
    df: pl.DataFrame,
    date_column: str,
    days: int,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    return df.with_columns((pl.col(date_column) + pl.duration(days=days)).alias(target))


def today(
    df: pl.DataFrame,
    new_column: str = "today",
    value: datetime.date | None = None,
) -> pl.DataFrame:
    value = value if value is not None else datetime.date.today()
    return df.with_columns(pl.lit(value).alias(new_column))


def now(
    df: pl.DataFrame,
    new_column: str = "now",
    value: datetime.datetime | None = None,
) -> pl.DataFrame:
    value = value if value is not None else datetime.datetime.now()
    return df.with_columns(pl.lit(value).alias(new_column))


def fiscal_year(
    df: pl.DataFrame,
    date_column: str,
    fy_start_month: int = 1,
    new_column: str | None = None,
) -> pl.DataFrame:
    # FY = the calendar year in which the fiscal year ends.
    # e.g. fy_start_month=7: Jul 2025 - Jun 2026 is FY 2026.
    target = new_column if new_column is not None else date_column
    if fy_start_month == 1:
        return df.with_columns(pl.col(date_column).dt.year().alias(target))
    return df.with_columns(
        (
            pl.col(date_column).dt.year()
            + (pl.col(date_column).dt.month() >= fy_start_month).cast(pl.Int32)
        ).alias(target)
    )


def period_end(
    df: pl.DataFrame,
    date_column: str,
    granularity: str,
    new_column: str | None = None,
) -> pl.DataFrame:
    target = new_column if new_column is not None else date_column
    col = pl.col(date_column)
    if granularity == "month":
        expr = col.dt.month_end()
    elif granularity == "quarter":
        quarter_end_month = ((col.dt.month() - 1) // 3 + 1) * 3
        expr = pl.date(col.dt.year(), quarter_end_month, 1).dt.month_end()
    elif granularity == "year":
        expr = pl.date(col.dt.year(), 12, 31)
    else:
        raise ValueError(
            f"Unknown granularity: {granularity!r}. Use 'month', 'quarter', or 'year'."
        )
    return df.with_columns(expr.alias(target))


def epoch_to_datetime(
    df: pl.DataFrame, column: str, unit: str = "ms"
) -> pl.DataFrame:
    # Interpret an integer column as time since the Unix epoch (1970-01-01).
    # unit="ms" treats the integer as milliseconds, "us" microseconds, "ns"
    # nanoseconds. Common for timestamps exported from web/JSON systems.
    return df.with_columns(pl.col(column).cast(pl.Datetime(time_unit=unit)))
