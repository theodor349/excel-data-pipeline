"""Column add/manage vocabulary for queries.

Every function returns a new DataFrame and never mutates its input.

`conditional_column` reads a condition as plain comparison parameters (the same
vocabulary as `functions/filters.py`) so a non-developer can author an if/then/else
column without touching Polars. `add_literal_column` keeps money exact: a constant
Decimal column goes through the half-up `Decimal` path, never a binary float.
"""

import operator
from decimal import Decimal

import polars as pl

from functions._rounding import quantize, resolve_places

# Comparison names mirror the filters vocabulary (filter_greater_than, ...) so a
# query author meets the same words in both places.
_COMPARISONS = {
    "equals": operator.eq,
    "not_equal": operator.ne,
    "greater_than": operator.gt,
    "less_than": operator.lt,
    "at_least": operator.ge,
    "at_most": operator.le,
}


def _as_comparable(df: pl.DataFrame, column: str, value):
    # Keep money comparisons exact: compare a Decimal column against a Decimal
    # bound built from the literal the user typed, never a binary float. Mirrors
    # the same guard in functions/filters.py.
    if isinstance(value, bool) or value is None:
        return value
    if df.schema[column] == pl.Decimal and isinstance(value, (int, float)):
        return Decimal(str(value))
    return value


def conditional_column(
    df: pl.DataFrame,
    when_column: str,
    comparison: str,
    value,
    then_value,
    else_value,
    name: str,
) -> pl.DataFrame:
    # Add a new column whose value depends on a condition: where
    # `when_column` `comparison` `value` is true use `then_value`, otherwise
    # `else_value`. `comparison` is one of: equals, not_equal, greater_than,
    # less_than, at_least, at_most. e.g. flag amounts over a budget:
    #   conditional_column(df, "amount", "greater_than", 1000,
    #                       "Over budget", "Within budget", "status")
    # A null in `when_column` makes the comparison false (so `else_value` is used).
    if comparison not in _COMPARISONS:
        raise ValueError(
            f"Unknown comparison: {comparison!r}. "
            f"Use one of: {', '.join(_COMPARISONS)}."
        )
    op = _COMPARISONS[comparison]
    condition = op(pl.col(when_column), _as_comparable(df, when_column, value))
    return df.with_columns(
        pl.when(condition)
        .then(pl.lit(then_value))
        .otherwise(pl.lit(else_value))
        .alias(name)
    )


def add_literal_column(
    df: pl.DataFrame,
    name: str,
    value,
    as_decimal: bool = False,
    places: int | None = None,
) -> pl.DataFrame:
    # Add a constant column with the same `value` in every row — stamp a report
    # period, source label, or currency code. The type is inferred from `value`
    # (string, integer, float, date). For a money constant pass as_decimal=True
    # (or a Decimal `value`): the value goes through the exact half-up Decimal
    # path at `places` decimals (settings.json default), never a binary float.
    if as_decimal or isinstance(value, Decimal):
        places = resolve_places(places)
        quantized = quantize(value, places)
        return df.with_columns(
            pl.lit(quantized, dtype=pl.Decimal(scale=places)).alias(name)
        )
    return df.with_columns(pl.lit(value).alias(name))


def keep_columns(df: pl.DataFrame, columns: list) -> pl.DataFrame:
    # Keep only the named columns, in the given order. Raises if any is missing.
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")
    return df.select(columns)


def remove_columns(df: pl.DataFrame, columns: list) -> pl.DataFrame:
    # Drop the named columns. Inverse of keep_columns. Raises if any is missing.
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")
    return df.drop(columns)


def duplicate_column(df: pl.DataFrame, source: str, target: str) -> pl.DataFrame:
    # Copy a column under a new name, preserving its type (Decimal money stays
    # Decimal). Useful for keeping an original alongside a transformed version.
    if source not in df.columns:
        raise KeyError(f"Source column '{source}' not found in DataFrame")
    return df.with_columns(pl.col(source).alias(target))


def reorder_columns(df: pl.DataFrame, column_order: list) -> pl.DataFrame:
    # Reorder columns to match the given list. Raises if any column is missing.
    # Listing a subset also drops the unlisted columns (like keep_columns).
    missing = [c for c in column_order if c not in df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")
    return df.select(column_order)
