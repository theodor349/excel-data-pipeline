"""Row-filtering vocabulary for queries.

Every function returns a new DataFrame and never mutates its input. Comparison
filters (`filter_greater_than`, `filter_between`, ...) leave the exact-Decimal
money path intact: when the column is Decimal, numeric bounds are converted via
`Decimal(str(value))` before comparing, so a money column is never silently cast
to float at the boundary. These functions only select rows — they never change a
value — so money precision is preserved by construction.
"""

import operator
from decimal import Decimal

import polars as pl


def _as_comparable(df: pl.DataFrame, column: str, value):
    # Keep money comparisons exact: compare a Decimal column against a Decimal
    # bound (built from the literal the user typed), never a binary float.
    if isinstance(value, bool) or value is None:
        return value
    if df.schema[column] == pl.Decimal and isinstance(value, (int, float)):
        return Decimal(str(value))
    return value


def _compare(df: pl.DataFrame, column: str, value, op) -> pl.DataFrame:
    return df.filter(op(pl.col(column), _as_comparable(df, column, value)))


# ---------------------------------------------------------------------------
# Equality
# ---------------------------------------------------------------------------

def filter_rows(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Keep rows where `column` equals `value`.
    return _compare(df, column, value, operator.eq)


def filter_not_equal(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Keep rows where `column` does not equal `value` (e.g. exclude an account).
    return _compare(df, column, value, operator.ne)


# ---------------------------------------------------------------------------
# Range / comparison — works for numbers, money (Decimal) and dates.
# ---------------------------------------------------------------------------

def filter_greater_than(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Keep rows where `column` > `value`.
    return _compare(df, column, value, operator.gt)


def filter_less_than(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Keep rows where `column` < `value`.
    return _compare(df, column, value, operator.lt)


def filter_at_least(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Keep rows where `column` >= `value`.
    return _compare(df, column, value, operator.ge)


def filter_at_most(df: pl.DataFrame, column: str, value) -> pl.DataFrame:
    # Keep rows where `column` <= `value`.
    return _compare(df, column, value, operator.le)


def filter_between(
    df: pl.DataFrame, column: str, low, high, inclusive: bool = True
) -> pl.DataFrame:
    # Keep rows where `column` is between `low` and `high`. Inclusive of both
    # bounds by default (e.g. a fiscal year start and end date); pass
    # inclusive=False to exclude the endpoints. Works for numbers, money and dates.
    low_op = operator.ge if inclusive else operator.gt
    high_op = operator.le if inclusive else operator.lt
    return df.filter(
        low_op(pl.col(column), _as_comparable(df, column, low))
        & high_op(pl.col(column), _as_comparable(df, column, high))
    )


# ---------------------------------------------------------------------------
# List membership
# ---------------------------------------------------------------------------

def filter_in_list(df: pl.DataFrame, column: str, values: list) -> pl.DataFrame:
    # Keep rows whose `column` value is one of `values` (e.g. a set of cost centres).
    return df.filter(pl.col(column).is_in(values))


def filter_not_in_list(df: pl.DataFrame, column: str, values: list) -> pl.DataFrame:
    # Keep rows whose `column` value is NOT one of `values`.
    return df.filter(~pl.col(column).is_in(values))


# ---------------------------------------------------------------------------
# Text matching
# ---------------------------------------------------------------------------

def filter_contains(df: pl.DataFrame, column: str, substring: str) -> pl.DataFrame:
    # Keep rows where the text in `column` contains `substring` (literal, not regex).
    return df.filter(pl.col(column).str.contains(substring, literal=True))


def filter_starts_with(df: pl.DataFrame, column: str, prefix: str) -> pl.DataFrame:
    # Keep rows where the text in `column` starts with `prefix`.
    return df.filter(pl.col(column).str.starts_with(prefix))


def filter_ends_with(df: pl.DataFrame, column: str, suffix: str) -> pl.DataFrame:
    # Keep rows where the text in `column` ends with `suffix`.
    return df.filter(pl.col(column).str.ends_with(suffix))


# ---------------------------------------------------------------------------
# Nulls
# ---------------------------------------------------------------------------

def drop_nulls(df: pl.DataFrame, column: str) -> pl.DataFrame:
    # Remove rows where `column` is null.
    return df.drop_nulls(subset=[column])


def keep_nulls(df: pl.DataFrame, column: str) -> pl.DataFrame:
    # Keep only rows where `column` is null — the inverse of drop_nulls.
    return df.filter(pl.col(column).is_null())


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------

def remove_duplicates(df: pl.DataFrame, columns: list | None = None) -> pl.DataFrame:
    # Keep one row per distinct value. With no `columns`, whole rows must match;
    # pass `columns` to dedupe on a subset (the first occurrence is kept). Row
    # order is preserved so output is deterministic for finance reconciliation.
    return df.unique(subset=columns, keep="first", maintain_order=True)


# ---------------------------------------------------------------------------
# Top / bottom N — strip header or footer junk rows.
# ---------------------------------------------------------------------------

def keep_top_rows(df: pl.DataFrame, n: int) -> pl.DataFrame:
    # Keep the first `n` rows.
    return df.head(n)


def keep_bottom_rows(df: pl.DataFrame, n: int) -> pl.DataFrame:
    # Keep the last `n` rows.
    return df.tail(n)


def remove_top_rows(df: pl.DataFrame, n: int) -> pl.DataFrame:
    # Drop the first `n` rows.
    return df.slice(n)


def remove_bottom_rows(df: pl.DataFrame, n: int) -> pl.DataFrame:
    # Drop the last `n` rows.
    if n <= 0:
        return df
    return df.head(-n)
