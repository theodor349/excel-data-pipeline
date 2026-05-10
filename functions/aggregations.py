import builtins
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from pandas import DataFrame


def _is_decimal_column(series: pd.Series) -> bool:
    first_non_null = series.dropna().iloc[0] if not series.dropna().empty else None
    return isinstance(first_non_null, Decimal)


def _detect_places(series: pd.Series, sample: int = 20) -> int:
    detected = []
    for val in series.dropna().head(sample):
        if isinstance(val, Decimal):
            sign, digits, exponent = val.as_tuple()
            if exponent < 0:
                detected.append(builtins.abs(int(exponent)))
    return builtins.max(detected) if detected else 2


def avg(df: DataFrame, group_by: str | list, column: str) -> DataFrame:
    df = df.copy()
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df[column]):
        places = _detect_places(df[column])
        quantizer = Decimal(10) ** -places

        def _decimal_avg(s):
            vals = [v for v in s if v is not None and not (isinstance(v, float) and pd.isna(v))]
            if not vals:
                return None
            total = builtins.sum(vals, Decimal(0))
            n = Decimal(len(vals))
            return (total / n).quantize(quantizer, rounding=ROUND_HALF_UP)

        result = df.groupby(group_by, as_index=False)[column].agg(_decimal_avg)
    else:
        result = df.groupby(group_by, as_index=False)[column].mean()

    return result


def sum(df: DataFrame, group_by: str | list, column: str) -> DataFrame:
    df = df.copy()
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df[column]):
        # pandas groupby on object dtype can silently widen to float when types are mixed;
        # use an explicit Python-level accumulator seeded with Decimal(0) to guarantee
        # Decimal results regardless of pandas version behaviour.
        def _decimal_sum(s):
            return builtins.sum(
                (v for v in s if v is not None and not (isinstance(v, float) and pd.isna(v))),
                Decimal(0),
            )

        result = df.groupby(group_by, as_index=False)[column].agg(_decimal_sum)
    else:
        result = df.groupby(group_by, as_index=False)[column].sum()

    return result


def count(df: DataFrame, group_by: str | list) -> DataFrame:
    df = df.copy()
    if isinstance(group_by, str):
        group_by = [group_by]

    result = df.groupby(group_by, as_index=False).size()
    result = result.rename(columns={"size": "count"})
    return result


def min(df: DataFrame, group_by: str | list, column: str) -> DataFrame:
    df = df.copy()
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df[column]):
        # pandas min on object dtype may widen to float; use Python builtin explicitly.
        def _decimal_min(s):
            vals = [v for v in s if v is not None and not (isinstance(v, float) and pd.isna(v))]
            return builtins.min(vals) if vals else None

        result = df.groupby(group_by, as_index=False)[column].agg(_decimal_min)
    else:
        result = df.groupby(group_by, as_index=False)[column].min()

    return result


def max(df: DataFrame, group_by: str | list, column: str) -> DataFrame:
    df = df.copy()
    if isinstance(group_by, str):
        group_by = [group_by]

    if _is_decimal_column(df[column]):
        # pandas max on object dtype may widen to float; use Python builtin explicitly.
        def _decimal_max(s):
            vals = [v for v in s if v is not None and not (isinstance(v, float) and pd.isna(v))]
            return builtins.max(vals) if vals else None

        result = df.groupby(group_by, as_index=False)[column].agg(_decimal_max)
    else:
        result = df.groupby(group_by, as_index=False)[column].max()

    return result
