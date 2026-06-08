from decimal import Decimal

import polars as pl

from functions._rounding import quantize


def avg(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    dtype = df[column].dtype
    if isinstance(dtype, pl.Decimal):
        # Exact mean: sum (exact on Decimal) / count, divided in Python Decimal
        # and rounded once to the column's own scale, half-up. Polars' float mean
        # would drift; its Decimal cast would round half-even.
        scale = dtype.scale
        agg = df.group_by(group_by).agg(
            pl.col(column).sum().alias("_sum"),
            pl.len().alias("_n"),
        )

        def mean_value(row):
            total, n = row["_sum"], row["_n"]
            if total is None or n in (None, 0):
                return None
            return quantize(Decimal(str(total)) / Decimal(n), scale)

        agg = agg.with_columns(
            pl.struct(["_sum", "_n"])
            .map_elements(mean_value, return_dtype=pl.Decimal(scale=scale))
            .alias(column)
        )
        return agg.select(group_by + [column])

    return df.group_by(group_by).agg(pl.col(column).mean())


def sum(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.col(column).sum())


def count(df: pl.DataFrame, group_by: str | list) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.len().alias("count"))


def min(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.col(column).min())


def max(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.col(column).max())
