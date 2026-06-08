import datetime
import operator
from decimal import Decimal

import polars as pl

from functions._rounding import (
    quantize,
    quantize_down,
    quantize_up,
    resolve_places,
)


def lowercase(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(pl.col(column).str.to_lowercase())


def to_int(df: pl.DataFrame, column: str) -> pl.DataFrame:
    return df.with_columns(pl.col(column).cast(pl.Int64))


def to_decimal(
    df: pl.DataFrame, column: str, places: int | None = None
) -> pl.DataFrame:
    # Convert a column to exact Decimal money. `places` defaults to the value in
    # settings.json (2). Rounding is always half-up. Rounds via Python Decimal
    # rather than Polars' native cast, which would round half-even at the wrong
    # scale — see functions/_rounding.py. Per-element, so it is exact; if this
    # ever becomes a hot-path bottleneck it can be vectorized behind the same API.
    places = resolve_places(places)
    return df.with_columns(
        pl.col(column)
        .cast(pl.String)
        .map_elements(
            lambda s: quantize(s, places),
            return_dtype=pl.Decimal(scale=places),
        )
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


def epoch_to_datetime(
    df: pl.DataFrame, column: str, unit: str = "ms"
) -> pl.DataFrame:
    # Interpret an integer column as time since the Unix epoch (1970-01-01).
    # unit="ms" treats the integer as milliseconds, "us" microseconds, "ns"
    # nanoseconds. Common for timestamps exported from web/JSON systems.
    return df.with_columns(pl.col(column).cast(pl.Datetime(time_unit=unit)))


# ---------------------------------------------------------------------------
# Computed columns — exact Decimal arithmetic between a column and another
# column or a constant. `operand` is a column name (str) or a number (constant).
# Each result is rounded once to `places` (settings.json default, 2) half-up, so
# money stays exact and predictably rounded. To carry full precision through a
# multi-step formula, pass a higher `places` to the intermediate steps.
# ---------------------------------------------------------------------------

def _arith(df, column, operand, op, new_column, places):
    places = resolve_places(places)
    target = new_column if new_column is not None else column
    operand_is_col = isinstance(operand, str)
    cols = [column] + ([operand] if operand_is_col else [])

    def compute(row):
        a = row[column]
        b = row[operand] if operand_is_col else operand
        if a is None or b is None:
            return None
        return quantize(op(Decimal(str(a)), Decimal(str(b))), places)

    return df.with_columns(
        pl.struct(cols)
        .map_elements(compute, return_dtype=pl.Decimal(scale=places))
        .alias(target)
    )


def add(df, column, operand, new_column=None, places=None):
    return _arith(df, column, operand, operator.add, new_column, places)


def subtract(df, column, operand, new_column=None, places=None):
    return _arith(df, column, operand, operator.sub, new_column, places)


def multiply(df, column, operand, new_column=None, places=None):
    return _arith(df, column, operand, operator.mul, new_column, places)


def divide(df, column, divisor, new_column=None, places=None, as_decimal=True):
    # Money division: exact Decimal, rounded once to `places` half-up — the
    # to_decimal step is folded in. For non-money ratios / unit conversions
    # (e.g. milliseconds -> hours) pass as_decimal=False to get a plain float.
    target = new_column if new_column is not None else column
    if not as_decimal:
        divisor_expr = pl.col(divisor) if isinstance(divisor, str) else divisor
        return df.with_columns((pl.col(column) / divisor_expr).alias(target))
    return _arith(df, column, divisor, operator.truediv, new_column, places)


def rename(df: pl.DataFrame, old_name: str, new_name: str) -> pl.DataFrame:
    return df.rename({old_name: new_name})


def sort(df: pl.DataFrame, column, descending: bool = False) -> pl.DataFrame:
    return df.sort(column, descending=descending)


# ---------------------------------------------------------------------------
# Explicit rounding — round a *result* on demand, to `places` decimals
# (settings.json default, 2). Always goes through the exact Python `Decimal`
# path in functions/_rounding.py, never Polars' native (half-even) Decimal cast,
# and produces an exact Decimal column. `round` breaks ties half-up; `round_up`
# rounds away from zero and `round_down` toward zero (Excel ROUNDUP/ROUNDDOWN).
# Pass `new_column` to write the result to a new column instead of in place.
# ---------------------------------------------------------------------------

def _round_with(df, column, places, new_column, quantizer):
    places = resolve_places(places)
    target = new_column if new_column is not None else column
    return df.with_columns(
        pl.col(column)
        .map_elements(
            lambda v: quantizer(v, places),
            return_dtype=pl.Decimal(scale=places),
        )
        .alias(target)
    )


def round(df, column, places=None, new_column=None):
    return _round_with(df, column, places, new_column, quantize)


def round_up(df, column, places=None, new_column=None):
    return _round_with(df, column, places, new_column, quantize_up)


def round_down(df, column, places=None, new_column=None):
    return _round_with(df, column, places, new_column, quantize_down)


def replace_null(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Replace nulls in `column` with `value` (coalesce) — e.g. treat a missing
    # amount as 0 so totals don't break. For a Decimal money column the fill is
    # converted exactly (Decimal(str(value))) to the column's scale, never a
    # binary float; other column types are filled with `value` as-is.
    dtype = df.schema[column]
    if dtype == pl.Decimal:
        scale = dtype.scale
        fill = quantize(value, scale)
        return df.with_columns(
            pl.col(column).fill_null(pl.lit(fill, dtype=pl.Decimal(scale=scale)))
        )
    return df.with_columns(pl.col(column).fill_null(value))


def absolute(df: pl.DataFrame, column: str, new_column: str | None = None) -> pl.DataFrame:
    # Absolute value (magnitude) of `column` — e.g. report variance size. Exact
    # for Decimal money (abs neither rounds nor changes scale). Pass `new_column`
    # to write to a new column instead of in place.
    target = new_column if new_column is not None else column
    return df.with_columns(pl.col(column).abs().alias(target))
