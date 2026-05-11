import builtins
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import polars as pl


def _is_decimal_column(df: pl.DataFrame, column: str) -> bool:
    col = df[column]
    if col.dtype != pl.Object:
        return False
    for val in col:
        if val is not None:
            return isinstance(val, Decimal)
    return False


def _detect_places(df: pl.DataFrame, column: str, sample: int = 20) -> int:
    detected = []
    for val in df[column].head(sample):
        if isinstance(val, Decimal):
            sign, digits, exponent = val.as_tuple()
            if exponent < 0:
                detected.append(builtins.abs(int(exponent)))
    return builtins.max(detected) if detected else 2


def _group_key_schema(df: pl.DataFrame, group_by: list[str]) -> dict:
    return {col: df.schema[col] for col in group_by}


def _decimal_group_agg(df: pl.DataFrame, group_by: list[str], column: str, agg_func) -> pl.DataFrame:
    """Python-level group aggregation for Decimal Object columns."""
    groups: dict = defaultdict(list)
    for row in df.iter_rows(named=True):
        key = tuple(row[g] for g in group_by)
        v = row[column]
        if v is not None:
            groups[key].append(v)

    result_rows = []
    for key, vals in groups.items():
        row = dict(zip(group_by, key))
        row[column] = agg_func(vals)
        result_rows.append(row)

    if not result_rows:
        schema = _group_key_schema(df, group_by)
        schema[column] = pl.Object
        return pl.DataFrame(schema=schema)

    schema = _group_key_schema(df, group_by)
    schema[column] = pl.Object
    return pl.DataFrame(result_rows, schema=schema)


def avg(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df, column):
        places = _detect_places(df, column)
        quantizer = Decimal(10) ** -places

        def _decimal_avg(vals):
            if not vals:
                return None
            total = builtins.sum(vals, Decimal(0))
            n = Decimal(len(vals))
            return (total / n).quantize(quantizer, rounding=ROUND_HALF_UP)

        return _decimal_group_agg(df, group_by, column, _decimal_avg)

    return df.group_by(group_by).agg(pl.col(column).mean())


def sum(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df, column):
        return _decimal_group_agg(
            df, group_by, column,
            lambda vals: builtins.sum(vals, Decimal(0))
        )

    return df.group_by(group_by).agg(pl.col(column).sum())


def count(df: pl.DataFrame, group_by: str | list) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    return df.group_by(group_by).agg(pl.len().alias("count"))


def min(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df, column):
        return _decimal_group_agg(
            df, group_by, column,
            lambda vals: builtins.min(vals) if vals else None
        )

    return df.group_by(group_by).agg(pl.col(column).min())


def max(df: pl.DataFrame, group_by: str | list, column: str) -> pl.DataFrame:
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df, column):
        return _decimal_group_agg(
            df, group_by, column,
            lambda vals: builtins.max(vals) if vals else None
        )

    return df.group_by(group_by).agg(pl.col(column).max())
