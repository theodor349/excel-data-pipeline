import datetime
from decimal import Decimal, ROUND_HALF_UP

import polars as pl


def lowercase(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(pl.col(column).str.to_lowercase())


def to_int(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(pl.col(column).cast(pl.Int64))


def to_decimal(df: pl.DataFrame, column: str, places: int = 2) -> pl.DataFrame:
    quantizer = Decimal(10) ** -places

    def _convert(value):
        if value is None:
            return None
        return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)

    return df.with_columns(
        pl.col(column).map_elements(_convert, return_dtype=pl.Object)
    )


def to_float(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(pl.col(column).cast(pl.Float64))


def to_date(df: pl.DataFrame, column: str, format: str | None = None) -> pl.DataFrame:
    col = df[column]
    if col.dtype == pl.Date:
        return df
    if col.dtype == pl.Datetime:
        return df.with_columns(pl.col(column).cast(pl.Date))
    if format is not None:
        return df.with_columns(pl.col(column).str.to_date(format=format))
    return df.with_columns(pl.col(column).str.to_date())


def fiscal_year(
    df: pl.DataFrame,
    date_column: str,
    fy_start_month: int = 1,
    new_column: str = "fiscal_year",
) -> pl.DataFrame:
    # FY = the calendar year in which the fiscal year ends.
    # e.g. fy_start_month=7: Jul 2025 – Jun 2026 is FY 2026.
    if fy_start_month == 1:
        return df.with_columns(
            pl.col(date_column).dt.year().alias(new_column)
        )
    return df.with_columns(
        (
            pl.col(date_column).dt.year()
            + (pl.col(date_column).dt.month() >= fy_start_month).cast(pl.Int32)
        ).alias(new_column)
    )


def period_end(
    df: pl.DataFrame,
    date_column: str,
    granularity: str,
    new_column: str = "period_end",
) -> pl.DataFrame:
    col = pl.col(date_column)
    if granularity == "month":
        expr = col.dt.month_end()
    elif granularity == "quarter":
        # Quarter end months: 3, 6, 9, 12
        quarter_end_month = ((col.dt.month() - 1) // 3 + 1) * 3
        expr = pl.date(col.dt.year(), quarter_end_month, 1).dt.month_end()
    elif granularity == "year":
        expr = pl.date(col.dt.year(), 12, 31)
    else:
        raise ValueError(f"Unknown granularity: {granularity!r}. Use 'month', 'quarter', or 'year'.")
    return df.with_columns(expr.alias(new_column))


def rename(df: pl.DataFrame, old_name: str, new_name: str) -> pl.DataFrame:
    return df.rename({old_name: new_name})


def keep_columns(df: pl.DataFrame, columns: list) -> pl.DataFrame:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")
    return df.select(columns)


def filter_rows(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    return df.filter(pl.col(column) == value)


def drop_nulls(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.drop_nulls(subset=[column])
